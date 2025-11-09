"""
Smart order routing - find the best exchange for execution.
Minimizes total cost (fees + slippage) across multiple venues.
"""

import os
from typing import Dict, List, Optional, Tuple
import httpx
from apps.executor.utils.fees import (
    calculate_fees,
    get_order_book_with_slippage,
    calculate_total_cost,
)


async def get_best_venue(
    symbol: str,
    side: str,
    quote_qty: float,
    available_venues: Optional[List[str]] = None,
) -> Dict:
    """
    Find the best exchange for executing an order.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        side: 'buy' or 'sell'
        quote_qty: Order size in quote currency
        available_venues: List of venues to consider (default: all)
    
    Returns:
        Dict with best venue, costs, and comparison
    """
    if available_venues is None:
        available_venues = ["binance", "kraken", "coinbase"]
    
    venue_costs = []
    
    for venue in available_venues:
        try:
            # Get order book and slippage estimate
            ob_data = await get_order_book_with_slippage(venue, symbol, side, quote_qty)
            
            slippage_bps = ob_data.get("slippage_bps", 10.0)
            fees = ob_data.get("fees", 0.0)
            total_cost = ob_data.get("total_cost", quote_qty * 0.002)
            
            # Calculate cost breakdown
            cost_breakdown = calculate_total_cost(
                venue, side, quote_qty, slippage_bps, is_maker=False
            )
            
            venue_costs.append({
                "venue": venue,
                "total_cost": total_cost,
                "fees": fees,
                "slippage_bps": slippage_bps,
                "cost_bps": cost_breakdown["cost_bps"],
                "avg_fill_price": ob_data.get("avg_fill_price"),
                "mid_price": ob_data.get("mid_price"),
                "available": True,
            })
        except Exception as e:
            # Venue unavailable or error
            venue_costs.append({
                "venue": venue,
                "total_cost": float("inf"),
                "available": False,
                "error": str(e),
            })
    
    # Filter available venues
    available = [v for v in venue_costs if v.get("available", False)]
    
    if not available:
        # Fallback to Binance
        return {
            "best_venue": "binance",
            "total_cost": quote_qty * 0.002,  # Estimate
            "cost_bps": 20.0,  # Conservative estimate
            "all_venues": venue_costs,
            "routing_reason": "fallback - no venues available",
        }
    
    # Find venue with lowest total cost
    best = min(available, key=lambda x: x["total_cost"])
    
    return {
        "best_venue": best["venue"],
        "total_cost": best["total_cost"],
        "fees": best["fees"],
        "slippage_bps": best["slippage_bps"],
        "cost_bps": best["cost_bps"],
        "avg_fill_price": best.get("avg_fill_price"),
        "all_venues": venue_costs,
        "routing_reason": f"lowest cost: {best['cost_bps']:.2f} bps",
        "savings_vs_worst": (
            max(v["cost_bps"] for v in available) - best["cost_bps"]
            if len(available) > 1
            else 0.0
        ),
    }


async def route_order(
    symbol: str,
    side: str,
    quote_qty: float,
    preferred_venue: Optional[str] = None,
) -> Tuple[str, Dict]:
    """
    Route order to best venue, with optional preferred venue override.
    
    Returns:
        Tuple of (selected_venue, routing_info)
    """
    # If preferred venue specified and available, use it
    if preferred_venue:
        try:
            ob_data = await get_order_book_with_slippage(
                preferred_venue, symbol, side, quote_qty
            )
            return (preferred_venue, {"routing_reason": "preferred_venue", **ob_data})
        except Exception:
            # Preferred venue failed, fall back to smart routing
            pass
    
    # Smart routing
    routing_info = await get_best_venue(symbol, side, quote_qty)
    return (routing_info["best_venue"], routing_info)

