"""
Seed script: generates 30 days of synthetic but realistic market data.

Usage:
    cd backend/
    python -m app.seed
"""

import random
import math
from datetime import datetime, timedelta, timezone

from app.database import engine, SessionLocal, Base
from app.models import User, Watchlist, WatchlistStock, MarketSnapshot, SectorIndex

# ---------- Config ----------

SYMBOLS = {
    # symbol: (base_price, avg_daily_volume, sector)
    "RELIANCE":   (2450.0,  15_000_000, "ENERGY"),
    "TCS":        (3800.0,   4_000_000, "IT"),
    "INFY":       (1550.0,  10_000_000, "IT"),
    "HDFCBANK":   (1650.0,   8_000_000, "BANKING"),
    "ICICIBANK":  (1100.0,  12_000_000, "BANKING"),
    "SBIN":       ( 620.0,  25_000_000, "BANKING"),
    "BHARTIARTL": (1500.0,   6_000_000, "TELECOM"),
    "ITC":        ( 450.0,  18_000_000, "FMCG"),
    "LT":         (3400.0,   3_000_000, "ENERGY"),
    "HCLTECH":    (1400.0,   5_000_000, "IT"),
}

SECTORS = ["BANKING", "IT", "ENERGY", "TELECOM", "FMCG"]
DAYS = 30
DAILY_STD_DEV = 0.015  # ~1.5% daily volatility
VOLUME_SPIKE_PROBABILITY = 0.10  # 10% of days have 2-3x volume spikes

# Fix seed for reproducibility during development (remove for prod)
random.seed(42)


def generate_daily_return(std_dev: float = DAILY_STD_DEV) -> float:
    """Random-walk return with slight mean-reversion bias."""
    return random.gauss(0.0002, std_dev)  # tiny positive drift


def generate_volume(base_volume: float, is_spike: bool) -> float:
    """Normal volume jitter, or a 2-3x spike on ~10% of days."""
    if is_spike:
        multiplier = random.uniform(2.0, 3.0)
    else:
        multiplier = random.uniform(0.7, 1.3)
    return round(base_volume * multiplier)


def seed_database():
    """Drop and recreate all tables, then populate with synthetic data."""
    # Recreate tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # --- 1. Generate per-day returns for NIFTY and each sector ---
        today = datetime.now(timezone.utc).replace(hour=15, minute=30, second=0, microsecond=0)
        dates = [today - timedelta(days=(DAYS - 1 - i)) for i in range(DAYS)]

        # NIFTY daily returns (market-wide)
        nifty_returns = [generate_daily_return(0.012) for _ in range(DAYS)]
        for i, d in enumerate(dates):
            db.add(SectorIndex(name="NIFTY", date=d, return_pct=nifty_returns[i]))

        # Sector daily returns — correlated with NIFTY but with sector-specific noise
        sector_returns: dict[str, list[float]] = {}
        for sector in SECTORS:
            returns = []
            for i in range(DAYS):
                # 60% correlated with NIFTY, 40% independent sector noise
                r = 0.6 * nifty_returns[i] + 0.4 * generate_daily_return(0.013)
                returns.append(r)
            sector_returns[sector] = returns
            for i, d in enumerate(dates):
                db.add(SectorIndex(name=sector, date=d, return_pct=returns[i]))

        # --- 2. Generate stock price + volume snapshots ---
        for symbol, (base_price, base_volume, sector) in SYMBOLS.items():
            price = base_price
            for i, d in enumerate(dates):
                # Stock return: correlated with its sector + idiosyncratic component
                sector_r = sector_returns[sector][i]
                idiosyncratic = generate_daily_return(0.01)
                stock_return = 0.5 * sector_r + 0.5 * idiosyncratic

                price = price * (1 + stock_return)
                price = round(max(price, 1.0), 2)  # floor at ₹1

                is_spike = random.random() < VOLUME_SPIKE_PROBABILITY
                volume = generate_volume(base_volume, is_spike)

                db.add(MarketSnapshot(
                    symbol=symbol,
                    price=price,
                    volume=volume,
                    timestamp=d,
                ))

        # --- 3. Demo user ---
        demo_user = User(email="demo@groww.in")
        db.add(demo_user)
        db.flush()  # get the id

        # --- 4. Demo watchlist with all 10 symbols ---
        demo_watchlist = Watchlist(
            user_id=demo_user.id,
            name="My Watchlist",
        )
        db.add(demo_watchlist)
        db.flush()

        for symbol in SYMBOLS:
            # last_seen = data from ~1 day ago so there's always a delta to show
            latest_snapshot = (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == symbol)
                .order_by(MarketSnapshot.timestamp.desc())
                .first()
            )
            # Use second-to-last snapshot as "last seen" so change_pct is non-zero
            second_latest = (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == symbol)
                .order_by(MarketSnapshot.timestamp.desc())
                .offset(1)
                .first()
            )
            db.add(WatchlistStock(
                watchlist_id=demo_watchlist.id,
                symbol=symbol,
                last_seen_at=second_latest.timestamp if second_latest else None,
                last_seen_price=second_latest.price if second_latest else None,
                last_seen_volume=second_latest.volume if second_latest else None,
            ))

        db.commit()

        # --- Print summary ---
        snapshot_count = db.query(MarketSnapshot).count()
        index_count = db.query(SectorIndex).count()
        stock_count = db.query(WatchlistStock).count()
        print(f"[OK] Seeded successfully:")
        print(f"   {snapshot_count} market snapshots ({len(SYMBOLS)} symbols x {DAYS} days)")
        print(f"   {index_count} sector/NIFTY index entries")
        print(f"   1 demo user, 1 watchlist, {stock_count} stocks")

        # Show a sample of price movement for RELIANCE
        reliance_snaps = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == "RELIANCE")
            .order_by(MarketSnapshot.timestamp)
            .all()
        )
        print(f"\n   RELIANCE price walk (first 5 -> last 5):")
        for s in reliance_snaps[:5]:
            print(f"     {s.timestamp.strftime('%Y-%m-%d')}  Rs.{s.price:>10.2f}  vol={s.volume:>12,.0f}")
        print(f"     ...")
        for s in reliance_snaps[-5:]:
            print(f"     {s.timestamp.strftime('%Y-%m-%d')}  Rs.{s.price:>10.2f}  vol={s.volume:>12,.0f}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
