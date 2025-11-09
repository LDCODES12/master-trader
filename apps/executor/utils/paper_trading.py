"""
Paper trading mode - simulate trades with real market data but no real capital risk.
Perfect for testing strategies before going live.
"""

import os
import time
from typing import Dict, Optional
from datetime import datetime
import httpx
from apps.executor.utils.market_data import get_latest_close_http
from apps.executor.utils.fees import calculate_fees, estimate_slippage_from_orderbook, get_order_book_with_slippage
from apps.analytics.positions import open_position, close_position


class PaperTradingAccount:
    """Manages paper trading account state."""
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Dict] = {}
        self.trades = []
    
    def get_balance(self) -> float:
        """Get current account balance."""
        return self.capital
    
    def can_trade(self, quote_qty: float) -> bool:
        """Check if we have enough capital for trade."""
        return quote_qty <= self.capital


async def simulate_paper_fill(
    symbol: str,
    side: str,
    quote_qty: float,
    venue: str = "binance",
    order_id: Optional[str] = None,
) -> Dict:
    """
    Simulate a paper trade fill using real market data.
    
    Returns:
        Simulated execution result matching real exchange format
    """
    # Get current market price
    try:
        price = await get_latest_close_http(symbol, "1m")
    except Exception:
        # Fallback to mid-price estimation
        price = 50000.0  # Placeholder
    
    # Get order book for realistic slippage
    try:
        ob_data = await get_order_book_with_slippage(venue, symbol, side, quote_qty)
        avg_fill_price = ob_data.get("avg_fill_price", price)
        slippage_bps = ob_data.get("slippage_bps", 5.0)
    except Exception:
        # Fallback with estimated slippage
        slippage_bps = 5.0  # 5 bps default
        if side.lower() == "buy":
            avg_fill_price = price * (1 + slippage_bps / 10000)
        else:
            avg_fill_price = price * (1 - slippage_bps / 10000)
    
    # Calculate quantities
    base_qty = quote_qty / avg_fill_price
    
    # Calculate fees
    fees = calculate_fees(venue, side, quote_qty, is_maker=False)
    
    # Generate order ID
    if not order_id:
        order_id = f"paper-{symbol}-{int(time.time())}"
    
    # Create fill
    fill = {
        "price": round(avg_fill_price, 8),
        "qty": round(base_qty, 8),
        "quote_qty": round(quote_qty, 8),
        "commission": fees,
        "commissionAsset": "USDT",
    }
    
    result = {
        "status": "paper_filled",
        "symbol": symbol,
        "orderId": order_id,
        "clientOrderId": order_id,
        "transactTime": int(time.time() * 1000),
        "price": str(avg_fill_price),
        "origQty": str(base_qty),
        "executedQty": str(base_qty),
        "cummulativeQuoteQty": str(quote_qty),
        "status": "FILLED",
        "timeInForce": "GTC",
        "type": "MARKET",
        "side": side.upper(),
        "fills": [fill],
        "avg_price": avg_fill_price,
        "slippage_bps": slippage_bps,
        "fees": fees,
    }
    
    return result


async def execute_paper_trade(
    symbol: str,
    side: str,
    quote_qty: float,
    venue: str = "binance",
    execution_id: Optional[str] = None,
) -> Dict:
    """
    Execute a paper trade and track it in positions.
    
    Returns:
        Execution result with position tracking
    """
    # Simulate fill
    fill_result = await simulate_paper_fill(symbol, side, quote_qty, venue)
    
    # Track position
    try:
        base_qty = float(fill_result["executedQty"])
        entry_price = float(fill_result["avg_price"])
        fees = fill_result.get("fees", 0.0)
        
        position_id = open_position(
            symbol=symbol,
            side=side,
            base_qty=base_qty,
            quote_qty=quote_qty,
            entry_price=entry_price,
            execution_id=execution_id,
            venue=venue,
            fees_paid=fees,
        )
        
        fill_result["position_id"] = position_id
    except Exception as e:
        # Log error but don't fail the trade
        fill_result["position_error"] = str(e)
    
    return fill_result

