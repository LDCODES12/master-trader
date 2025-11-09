from temporalio import activity
import psycopg, hashlib, re, json
from .c2pa_utils import c2pa_inspect
from apps.executor.utils.market_data import get_latest_close_http
from apps.executor.utils.exchange_rules import get_exchange_info, _symbol_info, validate_order_filters
from apps.risk.metrics import compute_fractional_kelly, update_ath_metrics, deflated_sharpe_ratio
from apps.attention.aslf import aslf_score
import os
from apps.rag.collector import collect as rag_collect
from apps.executor.impact import choose_strategy
from apps.science.experiments import BanditDecision
from apps.models.worldmodel import probability_drawdown_exceeds
import time


@activity.defn
async def verify_evidence(evidence):
    import httpx
    async with httpx.AsyncClient(timeout=15) as c:
        with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
            for ev in evidence:
                url = ev["url"]
                r = await c.get(url)
                if r.status_code != 200:
                    return False
                text = r.text
                norm = re.sub(r"\s+", " ", text).strip()
                b = norm.encode()
                sha = hashlib.sha256(b).hexdigest()
                c2 = c2pa_inspect(r.headers.get("content-type", ""), r.content)
                if len(b) < 1024 or c2 == "invalid":
                    return False
                conn.execute(
                    "insert into evidence_artifacts(url, sha256, c2pa_status, bytes_len) values (%s,%s,%s,%s)",
                    (url, sha, c2, len(b)),
                )
                conn.commit()
    return True


@activity.defn
async def reverify_evidence(evidence):
    # re-fetch and ensure hash matches stored value
    import httpx
    async with httpx.AsyncClient(timeout=15) as c:
        with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
            for ev in evidence:
                url = ev["url"]
                prev = conn.execute("select sha256 from evidence_artifacts where url=%s order by created_at desc limit 1", (url,)).fetchone()
                if not prev:
                    return False
                r = await c.get(url)
                if r.status_code != 200:
                    return False
                norm = re.sub(r"\s+", " ", r.text).strip().encode()
                sha = hashlib.sha256(norm).hexdigest()
                if sha != prev[0]:
                    return False
    return True


@activity.defn
async def compute_counterfactual(symbol: str, entry_price: float) -> dict:
    # Public price fetch and simple delta pnl
    import httpx
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=1")
        r.raise_for_status()
        close = float(r.json()[0][4])
    pnl_trade = close - entry_price
    pnl_no_trade = 0.0
    return {"mark_price": close, "pnl_trade": pnl_trade, "pnl_no_trade": pnl_no_trade, "counterfactual_delta": pnl_trade - pnl_no_trade}


@activity.defn
async def record_execution(order_id: str, proposal: dict, exec_res: dict):
    body = exec_res.get("body")
    venue = exec_res.get("venue", "binance") or "binance"
    
    with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
        conn.execute(
            "insert into executions(proposal_id, venue, order_id, status, fills, error) values (NULL, %s, %s, %s, %s, %s)",
            (venue, order_id, str(exec_res.get("code")), json.dumps(body) if body is not None else None, None),
        )
        conn.commit()
    
    # Track position if trade was filled
    if body and exec_res.get("code") in (200, 201):
        try:
            from apps.analytics.positions import open_position
            
            symbol = proposal.get("symbol", body.get("symbol", "BTCUSDT"))
            side = proposal.get("side", "buy")
            
            # Extract fill details
            fills = body.get("fills", [])
            if fills:
                total_qty = sum(float(f.get("qty", 0)) for f in fills)
                total_quote = sum(float(f.get("quoteQty", f.get("quote_qty", 0))) for f in fills)
                avg_price = float(body.get("avg_price", 0)) or (total_quote / total_qty if total_qty > 0 else 0)
                fees = sum(float(f.get("commission", 0)) for f in fills)
                
                if total_qty > 0 and avg_price > 0:
                    open_position(
                        symbol=symbol,
                        side=side,
                        base_qty=total_qty,
                        quote_qty=total_quote,
                        entry_price=avg_price,
                        execution_id=order_id,
                        venue=venue,
                        fees_paid=fees,
                    )
        except Exception as e:
            # Log error but don't fail the execution record
            import logging
            logging.warning(f"Failed to track position: {e}")
    
    return True


@activity.defn
async def update_postmortem(order_id: str, postmortem: dict):
    with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
        conn.execute(
            "update executions set postmortem = %s where order_id = %s",
            (json.dumps(postmortem), order_id),
        )
        conn.commit()
    return True


@activity.defn
async def validate_venue_rules(proposal: dict) -> bool:
    symbol = proposal["symbol"]
    price = await get_latest_close_http(symbol, "1m")
    info = await get_exchange_info()
    s = _symbol_info(info, symbol)
    if not s:
        return False
    ok, _ = validate_order_filters(s, price, quote_qty=20.0)
    if not ok:
        return False
    # Env allowlist (optional)
    allowlist = [t.strip() for t in os.getenv("ALLOWED_SYMBOLS", "").split(",") if t.strip()]
    if allowlist and symbol not in allowlist:
        return False
    return True


@activity.defn
async def compute_trade_size(proposal: dict, equity_start: float = 10000.0, k_cap: float = 0.2, force_probe_bps: float | None = None) -> float:
    # Map confidence to naive edge; variance stubbed
    conf = float(proposal.get("confidence", 0.5))
    aslf = float(proposal.get("_aslf", 0.0))
    edge = max(0.0, conf - 0.5) + max(0.0, aslf) * 0.05
    variance = 0.04  # placeholder variance
    cap_env = float(os.getenv("FRACTIONAL_KELLY_MAX", str(k_cap)))
    k_cap = min(k_cap, cap_env)
    # Probe override: convert bps of equity to notional
    if force_probe_bps is not None and force_probe_bps > 0:
        size = equity_start * (force_probe_bps / 1e4)
    else:
        size = compute_fractional_kelly(edge, variance, k_cap, equity_start)
    # cap to reasonable quote size
    return max(5.0, min(size, equity_start * k_cap))

@activity.defn
async def collect_docs(proposal: dict):
    query = str(proposal.get("thesis") or proposal.get("symbol") or "")
    horizon = int(proposal.get("horizon_minutes", 60))
    return rag_collect(query, horizon)

@activity.defn
async def bandit_decide(proposal: dict) -> dict:
    key = f"aslf:{proposal.get('symbol','')}"
    # Thompson sampling over Beta(alpha,beta): success=recent HWM hit proxy (not tracked yet) → use prior
    with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
        row = conn.execute("select alpha,beta,promoted from hypotheses where key=%s", (key,)).fetchone()
        if not row:
            conn.execute("insert into hypotheses(key,alpha,beta,promoted) values(%s,1,1,false)", (key,))
            conn.commit()
            alpha, beta, promoted = 1.0, 1.0, False
        else:
            alpha, beta, promoted = float(row[0]), float(row[1]), bool(row[2])
    import random
    sample = random.betavariate(alpha, beta)
    # Promotion threshold + probe bps from env
    promote_threshold = float(os.getenv("PROMOTE_PROB_THRESHOLD", "0.8"))
    probe_bps = float(os.getenv("PROBE_SIZE_BPS", "3"))
    # Map sample to size multiplier in [0.05, 1.0]; cap for probes until promoted
    max_mult = 0.25 if (not promoted and sample < promote_threshold) else 1.0
    mult = max(0.05, min(max_mult, sample))
    is_probe = (not promoted and sample < promote_threshold)
    return {"status": "promoted" if not is_probe else "probe", "size_multiplier": mult, "key": key, "is_probe": is_probe, "probe_bps": probe_bps}

@activity.defn
async def risk_simulate(proposal: dict) -> dict:
    symbol = proposal.get("symbol","BTCUSDT")
    horizon = int(proposal.get("horizon_minutes", 60))
    dd_limit_bps = float(os.getenv("SIM_DD_LIMIT_BPS","300"))
    # Pull last 120 closes to estimate returns
    import httpx
    bases = []
    fb = os.getenv("BINANCE_FRICTION_BASE")
    if fb:
        bases.append(fb)
    bases.append(os.getenv("BINANCE_BASE", "https://api.binance.com"))
    data = None
    async with httpx.AsyncClient(timeout=10) as c:
        for base in bases:
            try:
                r = await c.get(f"{base}/api/v3/klines?symbol={symbol}&interval=1m&limit=120")
                if r.status_code in (451,403,429):
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                data = r.json()
                break
            except Exception:
                continue
    if data is None:
        return {"ok": True, "prob_dd_exceed": 0.0}  # fail-open for sim if markets unreachable
    closes = [float(k[4]) for k in data]
    rets = []
    for i in range(1,len(closes)):
        rets.append((closes[i]/closes[i-1])-1.0)
    prob = probability_drawdown_exceeds(rets, min(horizon,30), dd_limit_bps)
    return {"ok": prob < 0.5, "prob_dd_exceed": prob}

@activity.defn
async def choose_execution(proposal: dict, notional: float) -> dict:
    # Reuse market data used by ASLF friction to fetch spread/depth
    base = os.getenv("BINANCE_BASE", "https://api.binance.com")
    import httpx
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{base}/api/v3/depth?symbol={proposal['symbol']}&limit=5")
        r.raise_for_status()
        ob = r.json()
    best_bid = float(ob["bids"][0][0]); best_ask = float(ob["asks"][0][0])
    spread_bps = (best_ask - best_bid) / ((best_ask + best_bid) / 2) * 1e4
    depth_ratio = sum(float(q) for _,q in ob["bids"][:5]) / max((notional / ((best_ask+best_bid)/2)), 1e-9)
    choice = choose_strategy(spread_bps, depth_ratio, notional)
    max_slip = float(os.getenv("IMPACT_MAX_SLIPPAGE_BPS", "15"))
    if choice.get("impact_bps", 0) > max_slip:
        # Force POV/VWAP if impact too high
        choice["style"] = "POV"
        choice["slices"] = max(5, choice.get("slices", 5))
    return choice

@activity.defn
async def attribute_trade(order: dict, context: dict) -> bool:
    body = order.get("body",{}) if isinstance(order,dict) else {}
    order_id = body.get("orderId") or body.get("order_id")
    symbol = body.get("symbol", context.get("symbol"))
    # Determine status
    code = int(order.get("code", 0)) if isinstance(order, dict) else 0
    raw_status = (body.get("status") or "").lower() if isinstance(body, dict) else ""
    status = "exchange_error"
    if "mock_filled" in raw_status:
        status = "mock_filled"
    elif 200 <= code < 300:
        status = "filled"
    with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
        conn.execute(
            "insert into trade_attribution(order_id,symbol,mechanism,aslf,execution_style,impact_bps,notes,status) values (%s,%s,%s,%s,%s,%s,%s,%s)",
            (order_id, symbol, "aslf", context.get("aslf"), context.get("style"), context.get("impact_bps"), context.get("notes",""), status),
        )
        conn.commit()
    return True

@activity.defn
async def record_hypothesis_outcome(exec_ctx: dict) -> bool:
    # exec_ctx should include symbol and inferred status
    symbol = exec_ctx.get("symbol") or exec_ctx.get("body", {}).get("symbol") or "BTCUSDT"
    status = (exec_ctx.get("status") or "").lower()
    key = f"aslf:{symbol}"
    promote_threshold = float(os.getenv("PROMOTE_PROB_THRESHOLD", "0.8"))
    with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
        row = conn.execute("select alpha,beta,promoted from hypotheses where key=%s", (key,)).fetchone()
        if not row:
            alpha, beta, promoted = 1.0, 1.0, False
            conn.execute("insert into hypotheses(key,alpha,beta,promoted) values (%s,%s,%s,%s)", (key, alpha, beta, promoted))
        else:
            alpha, beta, promoted = float(row[0]), float(row[1]), bool(row[2])
        if status in ("filled","mock_filled"):
            alpha += 1.0
        else:
            beta += 1.0
        pmean = alpha / max(1.0, (alpha + beta))
        promoted = promoted or (pmean >= promote_threshold)
        conn.execute("update hypotheses set alpha=%s,beta=%s,promoted=%s,updated_at=now() where key=%s", (alpha, beta, promoted, key))
        conn.commit()
    return True

@activity.defn
async def compute_aslf_activity(proposal: dict) -> dict:
    symbol = proposal["symbol"]
    notional =  float(os.getenv("ASLF_NOTIONAL_TEST", "25"))
    res = await aslf_score(symbol, notional)
    theta_buy = float(os.getenv("ASLF_THETA_BUY", "1.2"))
    theta_fade = float(os.getenv("ASLF_THETA_FADE", "-1.2"))
    decision = "allow" if res["aslf"] >= theta_buy else ("fade" if res["aslf"] <= theta_fade else "deny")
    with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
        conn.execute(
            "insert into attention_aslf(symbol, aas, lmf, aslf, decision, notes) values (%s,%s,%s,%s,%s,%s)",
            (symbol, res["aas"], res["lmf"], res["aslf"], decision, f"spread_bps={res['spread_bps']:.2f};depth={res['depth_ratio']:.2f}"),
        )
        conn.commit()
    return {**res, "decision": decision}


@activity.defn
async def update_equity_stats(symbol: str, entry_price: float | None = None):
    latest = await get_latest_close_http(symbol, "1m")
    with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
        row = conn.execute("select equity, high_water_mark, max_drawdown from equity_stats order by ts desc limit 1").fetchone()
        prev_equity = float(row[0]) if row else 10000.0
        prev_hwm = float(row[1]) if row else prev_equity
        prev_mdd = float(row[2]) if row else 0.0
        # unrealized PnL stub: none (flat); realized if entry provided
        realized = 0.0
        if entry_price is not None:
            realized = latest - entry_price
        equity_t = prev_equity + realized
        hwm, mdd, romad, _ = update_ath_metrics(prev_equity, prev_hwm, prev_mdd, equity_t)
        conn.execute(
            "insert into equity_stats(equity, high_water_mark, max_drawdown, romad, notes) values (%s,%s,%s,%s,%s)",
            (equity_t, hwm, mdd, romad, f"mark {latest}"),
        )
        conn.commit()
    return {"equity": equity_t, "high_water_mark": hwm, "max_drawdown": mdd, "romad": romad}


@activity.defn
async def gate_policy(proposal: dict):
    with psycopg.connect("dbname=mastertrader user=trader password=traderpw host=db") as conn:
        enabled = conn.execute("select trading_enabled from policy_flags where id=1").fetchone()[0]
    if not enabled:
        return False
    return True


@activity.defn
async def call_executor(params: dict):
    # Heartbeat once at start for visibility on long calls
    try:
        activity.heartbeat("starting")
    except Exception:
        pass
    proposal = params["proposal"]
    # Mock mode for proof runs
    mode = os.getenv("EXECUTOR_MODE", "live").lower()
    if mode == "mock":
        price = await get_latest_close_http(proposal["symbol"], "1m")
        q = float(params.get("quote_qty", 20))
        qty = max(1e-9, q / max(price, 1e-9))
        oid = f"mock-{proposal['symbol']}-{int(time.time())}"
        return {
            "code": 200,
            "body": {
                "status": "mock_filled",
                "symbol": proposal["symbol"],
                "order_id": oid,
                "avg_price": price,
                "fills": [{"price": price, "qty": qty, "quote_qty": q}],
            },
        }
    body = {
        "symbol": proposal["symbol"],
        "side": proposal["side"],
        "quote_qty": params.get("quote_qty", 20),
        "venue": "binance",
        "idempotency_key": params.get("idempotency_key", "wf-" + proposal["symbol"]),
    }
    import httpx
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("http://executor:8001/orders", json=body)
        return {"code": r.status_code, "body": r.json()}

@activity.defn
async def postmortem_enqueue(exec_result: dict):
    # Best-effort extraction for symbol and entry price
    body = exec_result.get("body", {}) if isinstance(exec_result, dict) else {}
    symbol = body.get("symbol") or "BTCUSDT"
    price = None
    try:
        price = float(body.get("avg_price") or (body.get("fills", [{}])[0].get("price")))
    except Exception:
        price = None
    if price is None:
        return {"queued": False, "reason": "no_entry_price"}
    # Compute counterfactual immediately and update executions if possible
    cf = await compute_counterfactual(symbol, price)
    # If order_id available, persist
    order_id = body.get("orderId") or body.get("order_id")
    if order_id:
        await update_postmortem(order_id, cf)
    return {"queued": True, "postmortem": cf}


