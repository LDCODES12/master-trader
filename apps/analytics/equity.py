import os, math
import psycopg
import httpx

PG_DSN = os.getenv("PG_DSN", "postgresql://trader:traderpw@db:5432/mastertrader")
EXECUTOR_BASE = os.getenv("EXECUTOR_BASE", "http://executor:8001")


def _price(symbol: str) -> float:
    with httpx.Client(timeout=4.0) as c:
        r = c.get(f"{EXECUTOR_BASE}/price", params={"symbol": symbol})
        r.raise_for_status()
        body = r.json()
        return float(body["price"])


def _fetch_open_positions(conn):
    try:
        cur = conn.execute("select symbol, side, 0.0::numeric as qty, 0.0::numeric as avg_price from executions where status='OPEN'")
        return cur.fetchall()
    except Exception:
        return []


def update_equity(mark_only: bool = False):
    with psycopg.connect(PG_DSN) as conn:
        cur = conn.execute("select equity, high_water_mark, max_drawdown from equity_stats order by ts desc limit 1")
        row = cur.fetchone()
        equity = float(row[0]) if row else 10000.0
        hwm = float(row[1]) if row else equity
        mdd = float(row[2]) if row else 0.0

        realized = 0.0
        unreal = 0.0
        for symbol, side, qty, avg_px in _fetch_open_positions(conn):
            px = _price(symbol)
            pnl = (px - float(avg_px)) * float(qty) if str(side).lower() == "buy" else (float(avg_px) - px) * float(qty)
            unreal += pnl

        new_equity = equity + realized + unreal
        new_hwm = max(hwm, new_equity)
        new_mdd = max(mdd, new_hwm - new_equity)
        romad = (new_equity - 0.0) / new_mdd if new_mdd > 1e-9 else float("inf")

        conn.execute(
            "insert into equity_stats (equity, high_water_mark, max_drawdown, romad) values (%s,%s,%s,%s)",
            (new_equity, new_hwm, new_mdd, (romad if math.isfinite(romad) else None)),
        )
        conn.commit()
        return {
            "equity": float(new_equity),
            "hwm": float(new_hwm),
            "mdd": float(new_mdd),
            "romad": (float(romad) if math.isfinite(romad) else None),
        }

