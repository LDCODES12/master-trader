import os, math, time
import httpx
from urllib.parse import urlparse
from apps.rag.collector import collect as rag_collect


# --- Hawkes-style burst proxy (online) ---
# We maintain lightweight per-symbol state so intensity responds to recent arrivals.
_STATE = {}  # symbol -> dict(lambda_ema, baseline_ema, last_ts)

# Tuning (seconds)
HAWKES_TAU_S = float(os.getenv("AAS_HAWKES_TAU", "120"))           # fast intensity horizon
BASELINE_TAU_S = float(os.getenv("AAS_BASELINE_TAU", "900"))       # slow baseline horizon
MIN_UNIQUE_SOURCES = int(os.getenv("AAS_MIN_UNIQUE_SOURCES", "2"))


def _exp_decay_weight(dt_s: float, tau_s: float) -> float:
    if tau_s <= 0:
        return 0.0
    return math.exp(-max(0.0, dt_s) / tau_s)


def _now_s() -> float:
    return time.time()


def _source_domain(url: str) -> str:
    try:
        return urlparse(url).netloc or ""
    except Exception:
        return ""


def _update_hawkes(symbol: str, events_count: int, unique_sources: int) -> float:
    now = _now_s()
    st = _STATE.get(symbol, {"lambda": 0.0, "baseline": 0.0, "ts": now})
    dt = now - st["ts"]
    w_fast = _exp_decay_weight(dt, HAWKES_TAU_S)
    w_slow = _exp_decay_weight(dt, BASELINE_TAU_S)
    # Convert events/min proxy -> per tick arrival weight
    arrivals = float(events_count)
    lam = st["lambda"] * w_fast + arrivals * (1 - w_fast)
    base = st["baseline"] * w_slow + arrivals * (1 - w_slow)
    _STATE[symbol] = {"lambda": lam, "baseline": base, "ts": now}
    # Burst score relative to baseline
    denom = max(1e-6, base)
    burst = lam / denom
    # Require minimum diversity of sources
    if unique_sources < MIN_UNIQUE_SOURCES:
        burst *= 0.5
    return burst


def compute_attention(symbol: str) -> tuple[float, int]:
    # Pull recent docs for symbol/thesis; count arrivals + source diversity
    docs = rag_collect(symbol, 60)
    events = len(docs)
    unique_src = len({ _source_domain(d.get("url", "")) for d in docs if d.get("url") })
    burst = _update_hawkes(symbol, events, unique_src)
    return burst, unique_src


def auth_weight(unique_sources: int) -> float:
    # Increase weight with unique source diversity (simple saturation curve)
    k = MAX_UNIQUE = max(MIN_UNIQUE_SOURCES, 5)
    return max(0.0, min(1.0, unique_sources / k))


async def liquidity_friction(symbol: str, notional: float) -> tuple[float, dict]:
    # Prefer friction base; fall back to trade base
    bases = []
    fb = os.getenv("BINANCE_FRICTION_BASE")
    if fb:
        bases.append(fb)
    bases.append(os.getenv("BINANCE_BASE", "https://api.binance.com"))
    headers = {"User-Agent": "MasterTrader/1.0", "Accept": "application/json"}
    last_exc = None
    ob = None
    async with httpx.AsyncClient(timeout=10, headers=headers) as c:
        for base in bases:
            try:
                url = f"{base}/api/v3/depth?symbol={symbol}&limit=5"
                r = await c.get(url)
                # Treat 451/403/429 as hard failures to trigger fallback
                if r.status_code in (451, 403, 429):
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                ob = r.json()
                break
            except Exception as e:
                last_exc = e
                continue
    if ob is None:
        # surface the original exception
        raise last_exc or RuntimeError("failed to fetch order book")
    best_bid = float(ob["bids"][0][0])
    best_ask = float(ob["asks"][0][0])
    spread_bps = (best_ask - best_bid) / ((best_ask + best_bid) / 2) * 1e4
    # depth ratio on bid side relative to notional
    bid_qty = sum(float(qty) for _, qty in ob["bids"][:5])
    price = (best_ask + best_bid) / 2
    base_needed = notional / max(price, 1e-9)
    depth_ratio = bid_qty / max(base_needed, 1e-9)
    # simple vol burst placeholder
    vol_burst = 0.0
    alpha = float(os.getenv("LMF_ALPHA", "1.0"))
    beta = float(os.getenv("LMF_BETA", "0.7"))
    gamma = float(os.getenv("LMF_GAMMA", "0.5"))
    lmf = alpha * spread_bps - beta * math.log(1 + depth_ratio) + gamma * vol_burst
    return lmf, {"spread_bps": spread_bps, "depth_ratio": depth_ratio, "price": price}


async def aslf_score(symbol: str, notional: float) -> dict:
    burst, uniq = compute_attention(symbol)
    w = auth_weight(uniq)
    aas = burst * w
    # Try friction; if fails, deny by default
    try:
        lmf, md = await liquidity_friction(symbol, notional)
    except Exception:
        return {"aas": aas, "lmf": float("inf"), "aslf": -1e9, "spread_bps": None, "depth_ratio": None, "price": None}
    lam = float(os.getenv("ASLF_LAMBDA", "0.5"))
    aslf = aas - lam * lmf
    return {"aas": aas, "lmf": lmf, "aslf": aslf, **md}


