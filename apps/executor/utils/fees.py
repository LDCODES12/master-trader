"""
Comprehensive fee and slippage modeling for accurate PnL calculation.
Supports multiple exchanges with tier-based fee structures.
"""

import os
from typing import Dict, Tuple, Optional
import httpx


# Exchange fee structures (maker/taker rates)
# Tier 0 = default, can be extended for VIP tiers
EXCHANGE_FEES: Dict[str, Dict[str, float]] = {
    "binance": {
        "maker": 0.001,  # 0.1%
        "taker": 0.001,  # 0.1% (can be 0.075% with BNB discount)
    },
    "kraken": {
        "maker": 0.0016,  # 0.16%
        "taker": 0.0026,  # 0.26%
    },
    "coinbase": {
        "maker": 0.004,  # 0.4%
        "taker": 0.006,  # 0.6%
    },
    "bybit": {
        "maker": 0.0001,  # 0.01%
        "taker": 0.0006,  # 0.06%
    },
    "okx": {
        "maker": 0.0008,  # 0.08%
        "taker": 0.001,   # 0.1%
    },
}


def get_fee_rate(exchange: str, is_maker: bool = False, tier: int = 0) -> float:
    """
    Get fee rate for exchange.
    
    Args:
        exchange: Exchange name (binance, kraken, etc.)
        is_maker: True for maker orders, False for taker
        tier: VIP tier (0 = default, higher = lower fees)
    
    Returns:
        Fee rate as decimal (e.g., 0.001 = 0.1%)
    """
    exchange_lower = exchange.lower()
    if exchange_lower not in EXCHANGE_FEES:
        # Default to conservative estimate
        return 0.002  # 0.2%
    
    fee_type = "maker" if is_maker else "taker"
    base_rate = EXCHANGE_FEES[exchange_lower].get(fee_type, 0.002)
    
    # Apply tier discounts (simplified - can be enhanced with actual tier data)
    if tier > 0:
        discount = min(0.5, tier * 0.1)  # Max 50% discount
        base_rate *= (1 - discount)
    
    return base_rate


def calculate_fees(
    exchange: str,
    side: str,
    quote_qty: float,
    is_maker: bool = False,
    tier: int = 0,
    use_bnb_discount: bool = False,
) -> float:
    """
    Calculate trading fees for an order.
    
    Args:
        exchange: Exchange name
        side: 'buy' or 'sell'
        quote_qty: Order size in quote currency (e.g., USDT)
        is_maker: True if maker order (adds liquidity)
        tier: VIP tier level
        use_bnb_discount: Use BNB discount (Binance only)
    
    Returns:
        Fee amount in quote currency
    """
    rate = get_fee_rate(exchange, is_maker, tier)
    
    # Binance BNB discount (25% off)
    if exchange.lower() == "binance" and use_bnb_discount:
        rate *= 0.75
    
    return quote_qty * rate


def estimate_slippage_from_orderbook(
    symbol: str,
    side: str,
    quote_qty: float,
    order_book: Dict,
    price_precision: int = 8,
) -> Tuple[float, float]:
    """
    Estimate slippage and average fill price from order book.
    
    Args:
        symbol: Trading pair symbol
        side: 'buy' or 'sell'
        quote_qty: Order size in quote currency
        order_book: Order book dict with 'bids' and 'asks' arrays
        price_precision: Price decimal precision
    
    Returns:
        Tuple of (slippage_bps, avg_fill_price)
    """
    if side.lower() == "buy":
        levels = order_book.get("asks", [])
        mid_price_idx = 0
    else:
        levels = order_book.get("bids", [])
        mid_price_idx = 0
    
    if not levels:
        return (0.0, 0.0)
    
    mid_price = (float(levels[0][0]) + float(levels[mid_price_idx][0])) / 2
    
    remaining_qty = quote_qty
    total_base_qty = 0.0
    total_cost = 0.0
    
    for level in levels:
        level_price = float(level[0])
        level_qty = float(level[1])
        level_notional = level_price * level_qty
        
        if remaining_qty <= 0:
            break
        
        if remaining_qty <= level_notional:
            # Partial fill at this level
            fill_notional = remaining_qty
            fill_base_qty = fill_notional / level_price
            total_base_qty += fill_base_qty
            total_cost += fill_notional
            remaining_qty = 0
        else:
            # Full fill at this level
            total_base_qty += level_qty
            total_cost += level_notional
            remaining_qty -= level_notional
    
    if total_base_qty == 0:
        return (0.0, mid_price)
    
    avg_fill_price = total_cost / total_base_qty
    
    # Calculate slippage in basis points
    slippage_bps = ((avg_fill_price - mid_price) / mid_price) * 10000
    
    return (abs(slippage_bps), round(avg_fill_price, price_precision))


async def get_order_book_with_slippage(
    exchange: str,
    symbol: str,
    side: str,
    quote_qty: float,
) -> Dict:
    """
    Get order book and calculate expected slippage.
    
    Args:
        exchange: Exchange name
        symbol: Trading pair
        side: 'buy' or 'sell'
        quote_qty: Order size
    
    Returns:
        Dict with order_book, slippage_bps, avg_fill_price, total_cost
    """
    base_urls = {
        "binance": os.getenv("BINANCE_BASE", "https://api.binance.com"),
        "kraken": os.getenv("KRAKEN_BASE", "https://api.kraken.com"),
        "coinbase": os.getenv("COINBASE_BASE", "https://api.exchange.coinbase.com"),
    }
    
    base_url = base_urls.get(exchange.lower(), "https://api.binance.com")
    
    # Fetch order book (limit 20 for better depth estimation)
    async with httpx.AsyncClient(timeout=10) as client:
        if exchange.lower() == "binance":
            url = f"{base_url}/api/v3/depth?symbol={symbol}&limit=20"
            r = await client.get(url)
            r.raise_for_status()
            ob_data = r.json()
            order_book = {"bids": ob_data["bids"], "asks": ob_data["asks"]}
        elif exchange.lower() == "kraken":
            # Kraken uses different symbol format and API
            url = f"{base_url}/0/public/Depth?pair={symbol}&count=20"
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            # Kraken returns different format - would need parsing
            order_book = {"bids": [], "asks": []}  # Placeholder
        else:
            order_book = {"bids": [], "asks": []}
    
    slippage_bps, avg_fill_price = estimate_slippage_from_orderbook(
        symbol, side, quote_qty, order_book
    )
    
    # Calculate total cost including fees
    fees = calculate_fees(exchange, side, quote_qty, is_maker=False)
    total_cost = quote_qty + fees
    
    return {
        "order_book": order_book,
        "slippage_bps": slippage_bps,
        "avg_fill_price": avg_fill_price,
        "mid_price": (float(order_book["bids"][0][0]) + float(order_book["asks"][0][0])) / 2 if order_book["bids"] and order_book["asks"] else avg_fill_price,
        "total_cost": total_cost,
        "fees": fees,
    }


def calculate_total_cost(
    exchange: str,
    side: str,
    quote_qty: float,
    slippage_bps: float = 0.0,
    is_maker: bool = False,
) -> Dict[str, float]:
    """
    Calculate total cost of trade including fees and slippage.
    
    Returns:
        Dict with fees, slippage_cost, total_cost, cost_bps
    """
    fees = calculate_fees(exchange, side, quote_qty, is_maker)
    slippage_cost = quote_qty * (slippage_bps / 10000)
    total_cost = fees + slippage_cost
    cost_bps = (total_cost / quote_qty) * 10000
    
    return {
        "fees": fees,
        "slippage_cost": slippage_cost,
        "total_cost": total_cost,
        "cost_bps": cost_bps,
    }

