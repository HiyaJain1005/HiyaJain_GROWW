"""
Significance engine: scores how "notable" a stock's movement is.

Combines price z-score, volume anomaly, market-relative divergence,
sector-relative divergence, and an event signal (always 0 for now).
"""

from dataclasses import dataclass
from typing import Optional

from app.services.change_detection import (
    compute_return,
    compute_change_pct,
    compute_volume_ratio,
    compute_rolling_stats,
    compute_z_score,
)


# ---------- Normalization functions ----------

def normalize_z_score(z: float) -> float:
    """Map abs(z) into [0, 1]. z=4 → 1.0."""
    return min(abs(z) / 4.0, 1.0)


def normalize_volume_ratio(ratio: float) -> float:
    """Map volume ratio into [0, 1]. ratio=4 → 1.0, ratio<=1 → 0."""
    return min(max((ratio - 1.0) / 3.0, 0.0), 1.0)


def normalize_divergence(divergence: float) -> float:
    """Map abs(divergence) into [0, 1]. 5% divergence → 1.0."""
    return min(abs(divergence) / 0.05, 1.0)


# ---------- Weights ----------

WEIGHT_PRICE = 0.30
WEIGHT_VOLUME = 0.20
WEIGHT_MARKET = 0.20
WEIGHT_SECTOR = 0.15
WEIGHT_EVENT = 0.15


# ---------- Thresholds ----------

THRESHOLD_NORMAL = 0.35
THRESHOLD_WATCH = 0.60
THRESHOLD_SIGNIFICANT = 0.80


def classify_level(score: float) -> str:
    """Map a score to a human-readable significance level."""
    if score < THRESHOLD_NORMAL:
        return "NORMAL"
    elif score < THRESHOLD_WATCH:
        return "WATCH"
    elif score < THRESHOLD_SIGNIFICANT:
        return "SIGNIFICANT"
    else:
        return "ATTENTION"


# ---------- Result dataclass ----------

@dataclass
class SignificanceResult:
    symbol: str
    current_price: float
    change_pct: float
    significance_level: str
    significance_score: float
    signals: dict  # {price, volume, market, sector, event}
    market_relative_return: float
    sector_relative_return: float
    volume_ratio: float
    z_score: float
    first_view: bool = False
    insufficient_history: bool = False


# ---------- Main scoring function ----------

def compute_significance(
    symbol: str,
    current_price: float,
    current_volume: float,
    last_seen_price: Optional[float],
    last_seen_volume: Optional[float],
    historical_returns: list[float],
    average_volume: float,
    nifty_return: float,
    sector_return: float,
) -> SignificanceResult:
    """
    Compute the significance score for a single stock.

    Args:
        symbol: Stock ticker
        current_price: Latest price
        current_volume: Latest volume
        last_seen_price: Price when user last checked (None if never seen)
        last_seen_volume: Volume when user last checked (unused directly, kept for API)
        historical_returns: List of daily returns for rolling stats (at least 10 needed)
        average_volume: Average daily volume over the history window
        nifty_return: NIFTY return for the same period
        sector_return: Sector return for the same period

    Returns:
        SignificanceResult with all signals and the final score/level.
    """

    first_view = (last_seen_price is None or last_seen_price == 0)

    # Guard: insufficient history
    if len(historical_returns) < 10:
        return SignificanceResult(
            symbol=symbol,
            current_price=current_price,
            change_pct=0.0,
            significance_level="NORMAL",
            significance_score=0.0,
            signals={"price": 0, "volume": 0, "market": 0, "sector": 0, "event": 0},
            market_relative_return=0.0,
            sector_relative_return=0.0,
            volume_ratio=1.0,
            z_score=0.0,
            first_view=first_view,
            insufficient_history=True,
        )

    # If user has never seen this stock, use current price as baseline
    if first_view:
        last_seen_price = current_price  # no change to report

    # Core calculations
    current_return = compute_return(current_price, last_seen_price)
    change_pct = compute_change_pct(current_price, last_seen_price)

    rolling_mean, rolling_std = compute_rolling_stats(historical_returns)
    z_score = compute_z_score(current_return, rolling_mean, rolling_std)

    volume_ratio = compute_volume_ratio(current_volume, average_volume)

    market_relative_return = current_return - nifty_return
    sector_relative_return = current_return - sector_return

    # Normalize into [0, 1] signals
    price_signal = normalize_z_score(z_score)
    volume_signal = normalize_volume_ratio(volume_ratio)
    market_signal = normalize_divergence(market_relative_return)
    sector_signal = normalize_divergence(sector_relative_return)
    event_signal = 0.0  # no news integration in this build

    # Weighted composite score
    score = (
        WEIGHT_PRICE * price_signal
        + WEIGHT_VOLUME * volume_signal
        + WEIGHT_MARKET * market_signal
        + WEIGHT_SECTOR * sector_signal
        + WEIGHT_EVENT * event_signal
    )

    level = classify_level(score)

    return SignificanceResult(
        symbol=symbol,
        current_price=current_price,
        change_pct=round(change_pct, 2),
        significance_level=level,
        significance_score=round(score, 4),
        signals={
            "price": round(price_signal, 2),
            "volume": round(volume_signal, 2),
            "market": round(market_signal, 2),
            "sector": round(sector_signal, 2),
            "event": round(event_signal, 2),
        },
        market_relative_return=round(market_relative_return * 100, 2),
        sector_relative_return=round(sector_relative_return * 100, 2),
        volume_ratio=round(volume_ratio, 2),
        z_score=round(z_score, 2),
        first_view=first_view,
    )
