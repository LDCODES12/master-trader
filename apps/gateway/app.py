from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
from temporalio.client import Client
from libs.schemas.proposal import Proposal
from apps.temporal_worker.workflows_pure import TraderWorkflow
import uuid, asyncio
import os, httpx, time
import psycopg
from apps.attention.aslf import aslf_score
from apps.analytics.equity import update_equity


app = FastAPI()


class SubmitReq(BaseModel):
    proposal: Proposal


@app.get("/status")
def status():
    return {"ok": True}


@app.post("/submit-proposal")
async def submit_proposal(body: SubmitReq, background_tasks: BackgroundTasks, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    run_id = idempotency_key or f"wf-{uuid.uuid4().hex[:8]}"

    async def _kickoff():
        client = await Client.connect("temporal:7233")
        await client.start_workflow(
            TraderWorkflow.run,
            body.proposal.model_dump(mode="json"),
            id=run_id,
            task_queue="trader-tq",
        )

    background_tasks.add_task(asyncio.run, _kickoff())
    return {"accepted": True, "workflow_id": run_id}


@app.get("/preflight")
async def preflight():
    # Prefer friction base for unauthenticated checks
    bases = []
    fb = os.getenv("BINANCE_FRICTION_BASE")
    if fb:
        bases.append(fb)
    bases.append(os.getenv("BINANCE_BASE", "https://api.binance.com"))
    out = {"binance": {}, "temporal": {}}
    headers = {"User-Agent": "MasterTrader/1.0", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as c:
        # server time and ping
        for base in bases:
            try:
                t = await c.get(f"{base}/api/v3/time")
                if t.status_code in (451, 403, 429):
                    raise httpx.HTTPStatusError(f"HTTP {t.status_code}", request=t.request, response=t)
                srv_ms = t.json().get("serverTime")
                drift_ms = abs(int(time.time() * 1000) - int(srv_ms)) if srv_ms else None
                out["binance"]["server_time_ms"] = srv_ms
                out["binance"]["clock_drift_ms"] = drift_ms
                p = await c.get(f"{base}/api/v3/ping")
                out["binance"]["ping_status"] = p.status_code
                break
            except Exception as e:
                out["binance"]["ping_error"] = str(e)
                continue
    # Temporal connectivity
    try:
        client = await Client.connect("temporal:7233")
        out["temporal"]["connected"] = True
    except Exception as e:
        out["temporal"]["error"] = str(e)
    return out


@app.get("/metrics")
async def metrics():
    green = True
    notes = []
    stats = {"equity": 10000.0, "high_water_mark": 10000.0, "max_drawdown": 0.0, "romad": None}
    # Update equity snapshot (mark-only path)
    try:
        snap = update_equity(mark_only=True)
        if isinstance(snap, dict):
            stats = {
                "equity": snap.get("equity", stats["equity"]),
                "high_water_mark": snap.get("hwm", snap.get("high_water_mark", stats["high_water_mark"])),
                "max_drawdown": snap.get("mdd", snap.get("max_drawdown", stats["max_drawdown"])),
                "romad": snap.get("romad", stats["romad"]),
            }
    except Exception as e:
        green = False
        notes.append(f"equity_error:{e}")

    # preflight checks
    try:
        pf = await preflight()
        if not pf.get("temporal", {}).get("connected"):
            green = False
            notes.append("temporal_down")
        if pf.get("binance", {}).get("ping_status") != 200:
            green = False
            notes.append("ping_fail")
    except Exception as e:
        green = False
        notes.append(f"preflight_error:{e}")
    return {"stats": stats, "green_to_trade": green, "notes": notes}


@app.get("/aslf")
async def aslf(symbol: str, notional: float = 25.0):
    res = await aslf_score(symbol, notional)
    theta_buy = float(os.getenv("ASLF_THETA_BUY", "1.2"))
    theta_fade = float(os.getenv("ASLF_THETA_FADE", "-1.2"))
    decision = "allow" if res["aslf"] >= theta_buy else ("fade" if res["aslf"] <= theta_fade else "deny")
    return {**res, "decision": decision}

@app.get("/health")
async def health(symbol: str = "BTCUSDT", notional: float = 25.0):
    pf = await preflight()
    try:
        s = await aslf(symbol, notional)  # reuse endpoint logic
    except Exception as e:
        s = {"error": str(e)}
    return {"preflight": pf, "aslf": s}


