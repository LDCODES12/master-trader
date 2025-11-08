import os, json, httpx


DATA_BASE = os.getenv("BINANCE_DATA_BASE", "https://api.binance.com")


async def get_latest_close_http(symbol: str, interval: str = "1m") -> float:
    url = f"{DATA_BASE}/api/v3/klines?symbol={symbol}&interval={interval}&limit=1"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url)
        r.raise_for_status()
        data = r.json()
    # kline schema: [open time, open, high, low, close, volume, ...]
    close = float(data[0][4])
    return close


def get_latest_close_replay(path: str) -> float:
    with open(path, "r") as f:
        data = json.load(f)
    return float(data[0][4])


def compute_simulated_fill(side: str, quote_qty: float, price: float) -> dict:
    base_qty = round(quote_qty / price, 8)
    fill_price = price
    return {
        "status": "simulated",
        "fills": [{"price": fill_price, "qty": base_qty, "quote_qty": quote_qty}],
        "avg_price": fill_price,
        "executed_qty": base_qty,
    }


