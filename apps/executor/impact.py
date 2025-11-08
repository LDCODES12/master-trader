def estimate_slippage_bps(spread_bps: float, depth_ratio: float, notional: float) -> float:
    # Simple impact proxy: spread + market impact diminishing with depth
    depth_term = 100 / max(1.0, depth_ratio)  # higher depth -> lower impact
    return max(0.0, float(spread_bps) + depth_term)


def choose_strategy(spread_bps: float, depth_ratio: float, notional: float) -> dict:
    impact = estimate_slippage_bps(spread_bps, depth_ratio, notional)
    # Thresholds can be tuned; start with 15 bps cutoff for MARKET
    if impact <= 15:
        return {"style": "MARKET", "impact_bps": impact, "slices": 1, "pov": None}
    # POV 10% of top-5 bid depth equivalent
    return {"style": "POV", "impact_bps": impact, "slices": 5, "pov": 0.1}


