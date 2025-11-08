import os
import asyncio
import json
import httpx


GATEWAY_BASE = os.getenv("GATEWAY_BASE", "http://gateway:8000")
SYMBOLS = [s.strip() for s in os.getenv("DISPATCHER_SYMBOLS", "BTCUSDT").split(",") if s.strip()]
ASLF_POLL_S = float(os.getenv("DISPATCHER_ASLF_POLL_S", "10"))
NOTIONAL = float(os.getenv("DISPATCHER_NOTIONAL", "25"))


async def fetch_aslf(client: httpx.AsyncClient, symbol: str) -> dict:
    r = await client.get(f"{GATEWAY_BASE}/aslf", params={"symbol": symbol, "notional": NOTIONAL})
    r.raise_for_status()
    return r.json()


async def submit_proposal(client: httpx.AsyncClient, symbol: str):
    body = {
        "proposal": {
            "action": "open",
            "symbol": symbol,
            "side": "buy",
            "size_bps_equity": 4.0,
            "horizon_minutes": 120,
            "thesis": "dispatcher-aslf",
            "risk": {"stop_loss_bps": 60, "take_profit_bps": 120, "max_slippage_bps": 3},
            "evidence": [{"url": "https://www.binance.com/en/support/announcement", "type": "exchange_status"}],
            "confidence": 0.7,
        }
    }
    r = await client.post(f"{GATEWAY_BASE}/submit-proposal", json=body, timeout=15)
    r.raise_for_status()
    return r.json()


async def wait_for_gateway(client: httpx.AsyncClient, timeout_s: int = 30) -> None:
    start = asyncio.get_event_loop().time()
    last_err: Exception | None = None
    while asyncio.get_event_loop().time() - start < timeout_s:
        try:
            r = await client.get(f"{GATEWAY_BASE}/status", timeout=5)
            r.raise_for_status()
            print(f"[dispatcher] gateway ready at {GATEWAY_BASE}")
            return
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.0)
    raise RuntimeError(f"gateway not ready after {timeout_s}s: {last_err}")

async def main():
    print(f"[dispatcher] starting; symbols={SYMBOLS} poll_s={ASLF_POLL_S}")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await wait_for_gateway(client, 30)
        except Exception as e:
            print(f"[dispatcher] gateway readiness failed: {e}")
        backoff = ASLF_POLL_S
        while True:
            any_success = False
            for sym in SYMBOLS:
                try:
                    aslf = await fetch_aslf(client, sym)
                    decision = aslf.get("decision")
                    if decision == "allow":
                        res = await submit_proposal(client, sym)
                        wid = res.get("workflow_id")
                        print(f"[dispatcher] submitted workflow_id={wid} symbol={sym} aslf={aslf.get('aslf')}")
                    any_success = True
                except Exception as e:
                    print(f"[dispatcher] error symbol={sym} base={GATEWAY_BASE}: {e}")
            # jittered backoff on errors
            if any_success:
                backoff = ASLF_POLL_S
            else:
                backoff = min(backoff * 1.5, 60)
            import random
            await asyncio.sleep(backoff + random.uniform(0, 1.0))


if __name__ == "__main__":
    asyncio.run(main())


