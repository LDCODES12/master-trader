import os, httpx

_CACHE = {"exchangeInfo": None}


async def get_exchange_info():
    if _CACHE["exchangeInfo"] is not None:
        return _CACHE["exchangeInfo"]
    base = os.getenv("BINANCE_BASE", "https://api.binance.com")
    url = f"{base}/api/v3/exchangeInfo"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url)
        r.raise_for_status()
        data = r.json()
    _CACHE["exchangeInfo"] = data
    return data


def _symbol_info(data, symbol):
    for s in data.get("symbols", []):
        if s.get("symbol") == symbol:
            return s
    return None


def validate_order_filters(symbol_info: dict, price: float, quote_qty: float) -> tuple[bool, str | None]:
    notional = price * (quote_qty / price)  # equals quote_qty
    min_notional = None
    step_size = None
    for f in symbol_info.get("filters", []):
        if f.get("filterType") == "MIN_NOTIONAL":
            min_notional = float(f.get("minNotional", 0))
        if f.get("filterType") == "LOT_SIZE":
            step_size = float(f.get("stepSize", 0))
    if min_notional is not None and quote_qty < min_notional:
        return False, f"minNotional {min_notional} > quote_qty {quote_qty}"
    # LOT_SIZE check requires baseQty; approximate baseQty = quote_qty/price
    if step_size:
        base_qty = quote_qty / max(price, 1e-9)
        # allow small float tolerance
        if (base_qty / step_size) % 1 > 1e-6:
            return False, "LOT_SIZE step mismatch"
    return True, None


