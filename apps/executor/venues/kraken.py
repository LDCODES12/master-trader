import base64, hashlib, hmac, time, httpx, os


async def kraken_private(path: str, data: dict):
    api_key = os.getenv("KRAKEN_API_KEY")
    secret_b64 = os.getenv("KRAKEN_API_SECRET", "")
    if not api_key or not secret_b64:
        raise RuntimeError("Missing KRAKEN_API_KEY/SECRET")
    secret = base64.b64decode(secret_b64)
    nonce = str(int(time.time() * 1000))
    data["nonce"] = nonce
    post = "&".join([f"{k}={v}" for k, v in data.items()])
    message = path.encode() + hashlib.sha256((nonce + post).encode()).digest()
    sig = hmac.new(secret, message, hashlib.sha512).digest()
    headers = {"API-Key": api_key, "API-Sign": base64.b64encode(sig).decode()}
    url = f"https://api.kraken.com{path}"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, data=data, headers=headers)
    return r.json()


