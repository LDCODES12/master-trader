from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, time, hmac, hashlib, httpx
from .utils.market_data import get_latest_close_http, get_latest_close_replay, compute_simulated_fill


app = FastAPI()


class OrderReq(BaseModel):
    symbol: str
    side: str           # buy|sell
    quote_qty: float    # demo: quoteOrderQty $ amount
    venue: str          # binance|kraken|coinbase
    idempotency_key: str


@app.get("/status")
def status():
    return {"ok": True}


@app.get("/price")
async def price(symbol: str, interval: str = "1m"):
    # Public market data endpoint (no auth)
    p = await get_latest_close_http(symbol, interval)
    return {"symbol": symbol, "interval": interval, "price": p}


@app.post("/orders")
async def orders(req: OrderReq):
    exec_mode = os.getenv("EXEC_MODE", "dry_run").lower()
    v = req.venue.lower()
    if v == "binance":
        if exec_mode == "live":
            return await place_binance(req)
        # dry_run / replay: simulate fills using market data
        if exec_mode == "replay":
            cache_path = os.getenv("REPLAY_KLINES_PATH", "apps/executor/data/klines_BTCUSDT_1m.json")
            p = get_latest_close_replay(cache_path)
        else:
            p = await get_latest_close_http(req.symbol, "1m")
        sim = compute_simulated_fill(req.side, req.quote_qty, p)
        return {"status": 200, "body": sim}
    if v == "kraken":
        # Placeholder: implement create order via Kraken private API if desired
        raise HTTPException(501, "kraken order not implemented in scaffold")
    if v == "coinbase":
        # Placeholder
        raise HTTPException(501, "coinbase order not implemented in scaffold")
    raise HTTPException(400, "unknown venue")


async def place_binance(req: OrderReq):
    base = os.getenv("BINANCE_BASE", "https://testnet.binance.vision")
    api_key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_API_SECRET", "").encode()
    if not api_key or not secret:
        raise HTTPException(500, "Missing BINANCE_API_KEY/SECRET")
    ts = int(time.time() * 1000)
    params = (
        f"symbol={req.symbol}&side={'BUY' if req.side=='buy' else 'SELL'}"
        f"&type=MARKET&quoteOrderQty={req.quote_qty}&timestamp={ts}"
    )
    sig = hmac.new(secret, params.encode(), hashlib.sha256).hexdigest()
    url = f"{base}/api/v3/order?{params}&signature={sig}"
    headers = {"X-MBX-APIKEY": api_key}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, headers=headers)
    return {"status": r.status_code, "body": r.json()}


