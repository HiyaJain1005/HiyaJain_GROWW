"""
Pydantic schemas for API request/response shapes.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Watchlist ---

class WatchlistCreate(BaseModel):
    name: str


class WatchlistResponse(BaseModel):
    id: int
    user_id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Stock ---

class StockAdd(BaseModel):
    symbol: str


class WatchlistStockResponse(BaseModel):
    id: int
    watchlist_id: int
    symbol: str
    added_at: datetime
    last_seen_at: Optional[datetime] = None
    last_seen_price: Optional[float] = None
    last_seen_volume: Optional[float] = None

    model_config = {"from_attributes": True}


# --- Insights ---

class SignalBreakdown(BaseModel):
    price: float
    volume: float
    market: float
    sector: float
    event: float


class StockInsight(BaseModel):
    symbol: str
    current_price: float
    change_pct: float
    significance_level: str
    significance_score: float
    signals: SignalBreakdown
    market_relative_return: float
    sector_relative_return: float
    volume_ratio: float
    is_stale: bool = False
    first_view: bool = False
    insufficient_history: bool = False
    last_updated: Optional[datetime] = None
    explanation: Optional[str] = None


class InsightsResponse(BaseModel):
    top_insights: list[StockInsight]
    unremarkable_count: int
    last_seen_at: Optional[datetime] = None
