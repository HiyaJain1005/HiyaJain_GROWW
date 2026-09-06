from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    watchlists = relationship("Watchlist", back_populates="user")


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="watchlists")
    stocks = relationship("WatchlistStock", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistStock(Base):
    __tablename__ = "watchlist_stocks"

    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), nullable=False)
    symbol = Column(String, nullable=False)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, nullable=True)
    last_seen_price = Column(Float, nullable=True)
    last_seen_volume = Column(Float, nullable=True)

    watchlist = relationship("Watchlist", back_populates="stocks")


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)


class SectorIndex(Base):
    """Stores daily aggregate return for NIFTY and each sector."""
    __tablename__ = "sector_indices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)  # e.g. "NIFTY", "IT", "BANKING"
    date = Column(DateTime, nullable=False)
    return_pct = Column(Float, nullable=False)  # daily return as decimal (e.g. 0.012 = 1.2%)
