"""
Change detection: computes returns and volume ratios relative to last-seen state.
"""

from typing import Optional


def compute_return(current_price: float, last_seen_price: float) -> float:
    """Simple return since last seen."""
    if last_seen_price == 0:
        return 0.0
    return (current_price - last_seen_price) / last_seen_price


def compute_change_pct(current_price: float, last_seen_price: float) -> float:
    """Return as a percentage."""
    return compute_return(current_price, last_seen_price) * 100


def compute_volume_ratio(current_volume: float, average_volume: float) -> float:
    """How many times current volume exceeds the average."""
    if average_volume == 0:
        return 1.0
    return current_volume / average_volume


def compute_rolling_stats(returns: list[float]) -> tuple[float, float]:
    """Mean and std dev of a list of returns."""
    if not returns:
        return 0.0, 0.0
    n = len(returns)
    mean = sum(returns) / n
    if n < 2:
        return mean, 0.0
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = variance ** 0.5
    return mean, std


def compute_z_score(
    current_return: float,
    rolling_mean: float,
    rolling_std: float,
) -> float:
    """Z-score of the current return vs rolling history. Returns 0 if std is 0."""
    if rolling_std == 0:
        return 0.0
    return (current_return - rolling_mean) / rolling_std
