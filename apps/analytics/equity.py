import os, math
import psycopg
import httpx
from apps.analytics.positions import update_position_prices, get_open_positions, get_portfolio_exposure

PG_DSN = os.getenv("PG_DSN", "postgresql://trader:traderpw@db:5432/mastertrader")
EXECUTOR_BASE = os.getenv("EXECUTOR_BASE", "http://executor:8001")


def _price(symbol: str) -> float:
    with httpx.Client(timeout=4.0) as c:
        r = c.get(f"{EXECUTOR_BASE}/price", params={"symbol": symbol})
        r.raise_for_status()
        body = r.json()
        return float(body["price"])


def update_equity(mark_only: bool = False):
    """
    Update equity including unrealized PnL from open positions.
    Now uses the comprehensive position tracking system.
    """
    with psycopg.connect(PG_DSN) as conn:
        cur = conn.execute("select equity, high_water_mark, max_drawdown from equity_stats order by ts desc limit 1")
        row = cur.fetchone()
        equity = float(row[0]) if row else 10000.0
        hwm = float(row[1]) if row else equity
        mdd = float(row[2]) if row else 0.0

        # Update position prices and get unrealized PnL
        if not mark_only:
            update_position_prices(mark_only=False)
        
        # Get realized PnL from closed positions since last update
        cur = conn.execute(
            """
            SELECT COALESCE(SUM(realized_pnl), 0), COALESCE(SUM(fees_paid), 0)
            FROM positions
            WHERE closed_at IS NOT NULL
            AND closed_at > (SELECT MAX(ts) FROM equity_stats)
            """
        )
        realized_row = cur.fetchone()
        realized_pnl = float(realized_row[0]) if realized_row[0] else 0.0
        fees_paid = float(realized_row[1]) if realized_row[1] else 0.0

        # Get unrealized PnL from open positions
        open_positions = get_open_positions()
        unrealized_pnl = sum(pos["unrealized_pnl"] for pos in open_positions)
        total_fees = sum(pos["fees_paid"] for pos in open_positions)

        # Calculate new equity
        # Equity = previous equity + realized PnL + unrealized PnL - fees
        new_equity = equity + realized_pnl + unrealized_pnl - fees_paid - total_fees
        new_hwm = max(hwm, new_equity)
        new_mdd = max(mdd, new_hwm - new_equity)
        romad = (new_equity - 0.0) / new_mdd if new_mdd > 1e-9 else float("inf")

        # Get portfolio exposure
        exposure = get_portfolio_exposure()

        conn.execute(
            "insert into equity_stats (equity, high_water_mark, max_drawdown, romad, notes) values (%s,%s,%s,%s,%s)",
            (
                new_equity,
                new_hwm,
                new_mdd,
                (romad if math.isfinite(romad) else None),
                f"unrealized_pnl={unrealized_pnl:.2f} realized={realized_pnl:.2f} exposure={exposure.get('leverage', 0):.2f}x",
            ),
        )
        conn.commit()
        return {
            "equity": float(new_equity),
            "hwm": float(new_hwm),
            "mdd": float(new_mdd),
            "romad": (float(romad) if math.isfinite(romad) else None),
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_fees": fees_paid + total_fees,
            "leverage": exposure.get("leverage", 0.0),
        }

