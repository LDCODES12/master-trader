import math
import os


def estimate_slippage_bps(spread_bps: float, depth_ratio: float, notional: float, volatility: float = 0.02) -> float:
    """
    Advanced slippage estimation with volatility adjustment.
    
    Args:
        spread_bps: Current bid-ask spread in basis points
        depth_ratio: Order book depth ratio (available liquidity / order size)
        notional: Order size in quote currency
        volatility: Current volatility (default 2%)
    
    Returns:
        Estimated slippage in basis points
    """
    # Base slippage from spread
    spread_cost = spread_bps / 2  # Pay half spread on average
    
    # Market impact (diminishes with depth)
    depth_term = 100 / max(1.0, depth_ratio)  # Higher depth -> lower impact
    
    # Volatility adjustment (higher vol = more slippage)
    vol_adjustment = volatility * 10000 * 0.5  # Scale volatility to bps
    
    # Size impact (larger orders = more impact)
    size_impact = math.log10(max(1.0, notional / 1000)) * 2  # Logarithmic scaling
    
    total_impact = spread_cost + depth_term + vol_adjustment + size_impact
    
    return max(0.0, float(total_impact))


def calculate_optimal_slices(notional: float, volatility: float, depth_ratio: float, target_impact_bps: float = 10.0) -> int:
    """
    Calculate optimal number of slices for TWAP/VWAP execution.
    
    Args:
        notional: Total order size
        volatility: Current volatility
        depth_ratio: Order book depth ratio
        target_impact_bps: Target impact per slice in bps
    
    Returns:
        Optimal number of slices
    """
    # Estimate impact for full order
    spread_bps = 5.0  # Estimate
    full_impact = estimate_slippage_bps(spread_bps, depth_ratio, notional, volatility)
    
    # Calculate slices needed to achieve target impact
    if full_impact <= target_impact_bps:
        return 1
    
    # More volatile = more slices needed
    vol_multiplier = max(1.0, volatility * 50)
    slices = math.ceil((full_impact / target_impact_bps) * vol_multiplier)
    
    # Cap at reasonable maximum
    return min(max(1, slices), 20)


def choose_strategy(
    spread_bps: float,
    depth_ratio: float,
    notional: float,
    volatility: float = 0.02,
    max_impact_bps: float = 15.0,
) -> dict:
    """
    Advanced execution strategy selection with volatility awareness.
    
    Args:
        spread_bps: Current spread in bps
        depth_ratio: Order book depth ratio
        notional: Order size
        volatility: Current volatility
        max_impact_bps: Maximum acceptable impact in bps
    
    Returns:
        Execution strategy dict
    """
    impact = estimate_slippage_bps(spread_bps, depth_ratio, notional, volatility)
    
    # Volatility-adjusted threshold (higher vol = wider threshold)
    threshold = max_impact_bps * (1 + volatility * 10)
    
    if impact <= threshold:
        return {
            "style": "MARKET",
            "impact_bps": impact,
            "slices": 1,
            "pov": None,
            "duration_minutes": 0,
        }
    
    # Calculate optimal slicing
    optimal_slices = calculate_optimal_slices(notional, volatility, depth_ratio, target_impact_bps=max_impact_bps)
    
    # Choose between TWAP and VWAP based on volatility
    if volatility > 0.03:  # High volatility
        style = "TWAP"  # Time-weighted more stable
        duration_minutes = optimal_slices * 2  # 2 min per slice
    else:
        style = "VWAP"  # Volume-weighted better in normal markets
        duration_minutes = optimal_slices * 1  # 1 min per slice
    
    # POV (Percentage of Volume) calculation
    # Use 5-10% of average volume per slice
    pov = max(0.05, min(0.15, 10.0 / optimal_slices / 10))
    
    return {
        "style": style,
        "impact_bps": impact,
        "slices": optimal_slices,
        "pov": pov,
        "duration_minutes": duration_minutes,
        "estimated_impact_per_slice": impact / optimal_slices,
    }


