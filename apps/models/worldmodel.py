import statistics
from typing import List


def probability_drawdown_exceeds(returns: List[float], horizon_steps: int, dd_limit_bps: float) -> float:
    """Return probability proxy that drawdown exceeds limit.

    Uses a simple normal approximation on per-step returns to estimate a
    conservative drawdown magnitude over the horizon and compares it to a
    bps limit. Returns 1.0 if expected drawdown exceeds the limit, else 0.0.
    """
    if not returns:
        return 0.0
    mu = statistics.fmean(returns)
    sigma = statistics.pstdev(returns) or 1e-6
    import math
    expected_dd = abs(mu) * horizon_steps + 2 * sigma * math.sqrt(horizon_steps)
    return 1.0 if expected_dd * 1e4 > dd_limit_bps else 0.0

