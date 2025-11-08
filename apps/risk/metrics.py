from typing import List, Tuple


def compute_fractional_kelly(edge: float, variance: float, k_cap: float, equity: float) -> float:
    if variance <= 0:
        return 0.0
    k = max(0.0, min(edge / variance, k_cap))
    return k * equity


def update_ath_metrics(prev_equity: float, prev_hwm: float, prev_mdd: float, equity_t: float) -> Tuple[float, float, float, float]:
    hwm = max(prev_hwm, equity_t)
    mdd = max(prev_mdd, hwm - equity_t)
    gain = equity_t - prev_equity
    romad = (equity_t - prev_equity + (prev_equity - (prev_hwm - prev_mdd))) / (mdd if mdd > 0 else 1.0)
    return hwm, mdd, romad, gain


def deflated_sharpe_ratio(returns: List[float]) -> float:
    # Placeholder: return simple Sharpe-like scaled; replace with robust DSR later
    if not returns:
        return 0.0
    n = len(returns)
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    if var <= 0:
        return 0.0
    sharpe = mean / (var ** 0.5)
    return max(0.0, sharpe * 0.8)


