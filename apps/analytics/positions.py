"""
Comprehensive position tracking and portfolio management.
Tracks open positions, calculates PnL, and manages portfolio exposure.
"""

import os
import psycopg
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import httpx
from apps.executor.utils.market_data import get_latest_close_http


PG_DSN = os.getenv("PG_DSN", "postgresql://trader:traderpw@db:5432/mastertrader")
EXECUTOR_BASE = os.getenv("EXECUTOR_BASE", "http://executor:8001")


def _get_price(symbol: str) -> float:
    """Get current market price for symbol."""
    try:
        with httpx.Client(timeout=4.0) as c:
            r = c.get(f"{EXECUTOR_BASE}/price", params={"symbol": symbol})
            r.raise_for_status()
            body = r.json()
            return float(body["price"])
    except Exception:
        # Fallback to direct API call
        import asyncio
        try:
            return asyncio.run(get_latest_close_http(symbol, "1m"))
        except Exception:
            return 0.0


def open_position(
    symbol: str,
    side: str,
    base_qty: float,
    quote_qty: float,
    entry_price: float,
    execution_id: Optional[str] = None,
    venue: str = "binance",
    fees_paid: float = 0.0,
) -> str:
    """
    Open a new position.
    
    Returns:
        Position ID
    """
    with psycopg.connect(PG_DSN) as conn:
        cur = conn.execute(
            """
            INSERT INTO positions 
            (symbol, side, base_qty, quote_qty, entry_price, execution_id, venue, fees_paid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (symbol, side, base_qty, quote_qty, entry_price, execution_id, venue, fees_paid),
        )
        position_id = cur.fetchone()[0]
        conn.commit()
        return str(position_id)


def close_position(
    position_id: str,
    exit_price: float,
    realized_pnl: float,
    fees_paid: float = 0.0,
) -> bool:
    """
    Close an existing position.
    
    Returns:
        True if successful
    """
    with psycopg.connect(PG_DSN) as conn:
        conn.execute(
            """
            UPDATE positions
            SET closed_at = NOW(),
                current_price = %s,
                realized_pnl = %s,
                fees_paid = fees_paid + %s
            WHERE id = %s AND closed_at IS NULL
            """,
            (exit_price, realized_pnl, fees_paid, position_id),
        )
        conn.commit()
        return True


def update_position_prices(mark_only: bool = False) -> Dict[str, int]:
    """
    Update current prices and unrealized PnL for all open positions.
    
    Returns:
        Dict with counts of updated positions
    """
    with psycopg.connect(PG_DSN) as conn:
        # Get all open positions
        cur = conn.execute(
            """
            SELECT id, symbol, side, base_qty, entry_price
            FROM positions
            WHERE closed_at IS NULL
            """
        )
        positions = cur.fetchall()
        
        updated = 0
        errors = 0
        
        for pos_id, symbol, side, base_qty, entry_price in positions:
            try:
                current_price = _get_price(symbol)
                if current_price == 0.0:
                    errors += 1
                    continue
                
                # Calculate unrealized PnL
                if side.lower() == "buy":
                    unrealized_pnl = (current_price - float(entry_price)) * float(base_qty)
                else:  # sell/short
                    unrealized_pnl = (float(entry_price) - current_price) * float(base_qty)
                
                conn.execute(
                    """
                    UPDATE positions
                    SET current_price = %s, unrealized_pnl = %s
                    WHERE id = %s
                    """,
                    (current_price, unrealized_pnl, pos_id),
                )
                updated += 1
            except Exception as e:
                errors += 1
                continue
        
        conn.commit()
        
        return {
            "updated": updated,
            "errors": errors,
            "total": len(positions),
        }


def get_open_positions() -> List[Dict]:
    """Get all open positions with current PnL."""
    with psycopg.connect(PG_DSN) as conn:
        cur = conn.execute(
            """
            SELECT 
                id, symbol, side, base_qty, quote_qty, 
                entry_price, current_price, unrealized_pnl,
                fees_paid, opened_at, venue
            FROM positions
            WHERE closed_at IS NULL
            ORDER BY opened_at DESC
            """
        )
        rows = cur.fetchall()
        
        positions = []
        for row in rows:
            positions.append({
                "id": str(row[0]),
                "symbol": row[1],
                "side": row[2],
                "base_qty": float(row[3]),
                "quote_qty": float(row[4]),
                "entry_price": float(row[5]),
                "current_price": float(row[6]) if row[6] else None,
                "unrealized_pnl": float(row[7]) if row[7] else 0.0,
                "fees_paid": float(row[8]) if row[8] else 0.0,
                "opened_at": row[9].isoformat() if row[9] else None,
                "venue": row[10],
            })
        
        return positions


def get_portfolio_exposure() -> Dict:
    """
    Calculate total portfolio exposure and risk metrics.
    
    Returns:
        Dict with exposure metrics
    """
    positions = get_open_positions()
    
    total_long_exposure = 0.0
    total_short_exposure = 0.0
    total_unrealized_pnl = 0.0
    total_fees = 0.0
    symbols = set()
    
    for pos in positions:
        symbols.add(pos["symbol"])
        exposure = pos["quote_qty"]
        total_unrealized_pnl += pos["unrealized_pnl"]
        total_fees += pos["fees_paid"]
        
        if pos["side"].lower() == "buy":
            total_long_exposure += exposure
        else:
            total_short_exposure += exposure
    
    # Get current equity
    from apps.analytics.equity import update_equity
    equity_data = update_equity(mark_only=True)
    current_equity = equity_data.get("equity", 10000.0)
    
    total_exposure = total_long_exposure + total_short_exposure
    net_exposure = total_long_exposure - total_short_exposure
    
    # Calculate leverage (exposure / equity)
    leverage = total_exposure / current_equity if current_equity > 0 else 0.0
    
    # Store exposure snapshot
    with psycopg.connect(PG_DSN) as conn:
        conn.execute(
            """
            INSERT INTO portfolio_exposure
            (total_exposure, long_exposure, short_exposure, net_exposure, leverage, symbols_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (total_exposure, total_long_exposure, total_short_exposure, net_exposure, leverage, len(symbols)),
        )
        conn.commit()
    
    return {
        "total_exposure": total_exposure,
        "long_exposure": total_long_exposure,
        "short_exposure": total_short_exposure,
        "net_exposure": net_exposure,
        "leverage": leverage,
        "unrealized_pnl": total_unrealized_pnl,
        "total_fees": total_fees,
        "symbols_count": len(symbols),
        "symbols": list(symbols),
        "current_equity": current_equity,
        "exposure_pct": (total_exposure / current_equity * 100) if current_equity > 0 else 0.0,
    }


def check_position_limits(
    symbol: str,
    side: str,
    quote_qty: float,
    max_position_size_pct: float = 20.0,
    max_portfolio_exposure_pct: float = 200.0,
) -> Tuple[bool, Optional[str]]:
    """
    Check if new position would exceed limits.
    
    Args:
        symbol: Trading symbol
        side: 'buy' or 'sell'
        quote_qty: Proposed position size
        max_position_size_pct: Max position as % of equity
        max_portfolio_exposure_pct: Max total exposure as % of equity
    
    Returns:
        Tuple of (allowed, reason_if_denied)
    """
    from apps.analytics.equity import update_equity
    equity_data = update_equity(mark_only=True)
    current_equity = equity_data.get("equity", 10000.0)
    
    # Check individual position size
    position_pct = (quote_qty / current_equity) * 100 if current_equity > 0 else 0.0
    if position_pct > max_position_size_pct:
        return (False, f"Position size {position_pct:.2f}% exceeds limit {max_position_size_pct}%")
    
    # Check total portfolio exposure
    exposure = get_portfolio_exposure()
    new_total_exposure = exposure["total_exposure"] + quote_qty
    new_exposure_pct = (new_total_exposure / current_equity) * 100 if current_equity > 0 else 0.0
    
    if new_exposure_pct > max_portfolio_exposure_pct:
        return (False, f"Portfolio exposure {new_exposure_pct:.2f}% exceeds limit {max_portfolio_exposure_pct}%")
    
    return (True, None)

