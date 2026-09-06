"""
Watchlist + Insights API routes.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from app.database import get_db
from app.models import Watchlist, WatchlistStock, MarketSnapshot, SectorIndex, User
from app.schemas.schemas import (
    WatchlistCreate,
    WatchlistResponse,
    StockAdd,
    WatchlistStockResponse,
    StockInsight,
    SignalBreakdown,
    InsightsResponse,
)
from app.services.significance import compute_significance
from app.services.change_detection import compute_return
from app.services.gemini import get_explanation, get_explanations_parallel, deterministic_explanation
from app.services.market_data import get_live_quote, get_live_quotes_batch

# Sector mapping — must match seed.py
SECTOR_MAP = {
    "RELIANCE": "ENERGY",
    "TCS": "IT",
    "INFY": "IT",
    "HDFCBANK": "BANKING",
    "ICICIBANK": "BANKING",
    "SBIN": "BANKING",
    "BHARTIARTL": "TELECOM",
    "ITC": "FMCG",
    "LT": "ENERGY",
    "HCLTECH": "IT",
}

DEMO_USER_ID = 1  # single hardcoded demo user

router = APIRouter()


# ---------- Watchlist CRUD ----------

@router.get("/watchlists", response_model=list[WatchlistResponse])
def list_watchlists(db: Session = Depends(get_db)):
    return db.query(Watchlist).filter(Watchlist.user_id == DEMO_USER_ID).all()


@router.post("/watchlists", response_model=WatchlistResponse, status_code=201)
def create_watchlist(body: WatchlistCreate, db: Session = Depends(get_db)):
    wl = Watchlist(user_id=DEMO_USER_ID, name=body.name)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


@router.delete("/watchlists/{watchlist_id}", status_code=204)
def delete_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    db.delete(wl)
    db.commit()
    return None


# ---------- Available Symbols ----------

@router.get("/symbols", response_model=list[str])
def list_available_symbols(watchlist_id: int = 0, db: Session = Depends(get_db)):
    """Return available stock symbols, optionally filtering out symbols already in watchlist_id."""
    all_symbols = [r[0] for r in db.query(MarketSnapshot.symbol).distinct().all()]
    
    if watchlist_id and watchlist_id > 0:
        existing = [
            r[0] for r in db.query(WatchlistStock.symbol)
            .filter(WatchlistStock.watchlist_id == watchlist_id)
            .all()
        ]
        available = [s for s in all_symbols if s not in existing]
        return sorted(available)
        
    return sorted(all_symbols)


# ---------- Stocks in watchlist ----------

@router.get("/watchlists/{watchlist_id}/stocks", response_model=list[WatchlistStockResponse])
def list_stocks(watchlist_id: int, db: Session = Depends(get_db)):
    _get_watchlist_or_404(watchlist_id, db)
    return (
        db.query(WatchlistStock)
        .filter(WatchlistStock.watchlist_id == watchlist_id)
        .all()
    )


@router.post("/watchlists/{watchlist_id}/stocks", response_model=WatchlistStockResponse, status_code=201)
def add_stock(watchlist_id: int, body: StockAdd, db: Session = Depends(get_db)):
    _get_watchlist_or_404(watchlist_id, db)
    symbol = body.symbol.upper().strip()

    # Validate symbol exists in market dataset
    valid_symbols = [r[0] for r in db.query(MarketSnapshot.symbol).distinct().all()]
    if valid_symbols and symbol not in valid_symbols:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{symbol}' is unsupported. Available symbols: {', '.join(sorted(valid_symbols))}"
        )

    # Idempotent: if already exists, return the existing row
    existing = (
        db.query(WatchlistStock)
        .filter(WatchlistStock.watchlist_id == watchlist_id, WatchlistStock.symbol == symbol)
        .first()
    )
    if existing:
        return existing

    stock = WatchlistStock(watchlist_id=watchlist_id, symbol=symbol)
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


@router.delete("/watchlists/{watchlist_id}/stocks/{symbol}", status_code=204)
def remove_stock(watchlist_id: int, symbol: str, db: Session = Depends(get_db)):
    _get_watchlist_or_404(watchlist_id, db)
    stock = (
        db.query(WatchlistStock)
        .filter(WatchlistStock.watchlist_id == watchlist_id, WatchlistStock.symbol == symbol.upper())
        .first()
    )
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found in watchlist")
    db.delete(stock)
    db.commit()
    return None


# ---------- Insights ----------

@router.get("/watchlists/{watchlist_id}/insights", response_model=InsightsResponse)
def get_insights(watchlist_id: int, db: Session = Depends(get_db)):
    import time
    import logging
    logger = logging.getLogger(__name__)

    t_total_start = time.perf_counter()

    wl = _get_watchlist_or_404(watchlist_id, db)
    stocks = db.query(WatchlistStock).filter(WatchlistStock.watchlist_id == watchlist_id).all()

    if not stocks:
        return InsightsResponse(top_insights=[], unremarkable_count=0, last_seen_at=None)

    # ── Phase 1: Batch yfinance fetch ──────────────────────────────────
    t0 = time.perf_counter()
    all_symbols = [ws.symbol for ws in stocks]
    live_quotes = get_live_quotes_batch(all_symbols)
    t_yf = time.perf_counter() - t0
    logger.info(f"[TIMING] yfinance batch ({len(all_symbols)} symbols): {t_yf:.3f}s")

    # ── Phase 2: Significance calculation (all stocks) ─────────────────
    t0 = time.perf_counter()

    # Pre-fetch NIFTY return once (shared across all stocks)
    nifty_entry = (
        db.query(SectorIndex)
        .filter(SectorIndex.name == "NIFTY")
        .order_by(SectorIndex.date.desc())
        .first()
    )
    nifty_return = nifty_entry.return_pct if nifty_entry else 0.0

    # Pre-fetch all sector returns once
    sector_returns = {}
    for sector_name in set(SECTOR_MAP.values()):
        entry = (
            db.query(SectorIndex)
            .filter(SectorIndex.name == sector_name)
            .order_by(SectorIndex.date.desc())
            .first()
        )
        sector_returns[sector_name] = entry.return_pct if entry else 0.0

    # Build per-stock significance results + metadata
    stock_results = []  # list of (ws, result, current_price, current_volume, is_stale, last_updated, latest)

    for ws in stocks:
        symbol = ws.symbol

        # Fetch latest synthetic snapshot in database for baseline
        latest = _get_latest_snapshot(symbol, db)
        if latest is None:
            stock_results.append((ws, None, 0.0, 0.0, False, None, None))
            continue

        # Use batched live quote
        live_quote = live_quotes.get(symbol.upper())
        if live_quote and live_quote.get("price"):
            current_price = live_quote["price"]
            current_volume = live_quote["volume"]
            is_stale = False
            last_updated = live_quote["timestamp"]
        else:
            current_price = latest.price
            current_volume = latest.volume
            is_stale = True
            last_updated = latest.timestamp

        # Gather historical returns (daily price changes)
        snapshots = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.timestamp.asc())
            .all()
        )

        historical_returns = []
        for i in range(1, len(snapshots)):
            r = compute_return(snapshots[i].price, snapshots[i - 1].price)
            historical_returns.append(r)

        # Average volume
        volumes = [s.volume for s in snapshots]
        avg_volume = sum(volumes) / len(volumes) if volumes else 1.0

        # Sector return for this symbol
        sector_name = SECTOR_MAP.get(symbol, "NIFTY")
        sector_return = sector_returns.get(sector_name, 0.0)

        # Compute significance
        result = compute_significance(
            symbol=symbol,
            current_price=current_price,
            current_volume=current_volume,
            last_seen_price=ws.last_seen_price,
            last_seen_volume=ws.last_seen_volume,
            historical_returns=historical_returns,
            average_volume=avg_volume,
            nifty_return=nifty_return,
            sector_return=sector_return,
        )

        stock_results.append((ws, result, current_price, current_volume, is_stale, last_updated, latest))

    t_sig = time.perf_counter() - t0
    logger.info(f"[TIMING] significance + DB queries ({len(stocks)} stocks): {t_sig:.3f}s")

    # ── Phase 3: Sort by significance, Gemini for top-3 only ──────────
    t0 = time.perf_counter()

    # Sort stock_results by significance score (descending), putting None results last
    stock_results.sort(key=lambda x: x[1].significance_score if x[1] else -1, reverse=True)

    # Determine which stocks get Gemini explanations (top 3 non-first-view)
    MAX_GEMINI_CALLS = 3
    gemini_candidates = []  # (index_in_stock_results, facts_dict)
    for idx, (ws, result, current_price, current_volume, is_stale, last_updated, latest) in enumerate(stock_results):
        if result is None or result.first_view:
            continue
        if len(gemini_candidates) >= MAX_GEMINI_CALLS:
            break
        sector_name = SECTOR_MAP.get(result.symbol, "NIFTY")
        sector_return = sector_returns.get(sector_name, 0.0)
        facts = {
            "symbol": result.symbol,
            "change_since_last_seen": result.change_pct,
            "nifty_change": nifty_return * 100,
            "sector_change": sector_return * 100,
            "volume_vs_normal": result.volume_ratio,
            "anomaly_score": result.significance_score,
            "event": "none",
        }
        gemini_candidates.append((idx, facts))

    # Call Gemini in parallel for top candidates — returned dict is explicitly keyed by symbol
    gemini_facts_list = [facts for _, facts in gemini_candidates]
    gemini_explanation_map = get_explanations_parallel(gemini_facts_list)

    logger.info(f"[TIMING] Gemini ({len(gemini_candidates)} parallel calls, top-3 only): "
                f"{time.perf_counter() - t0:.3f}s")

    # ── Phase 4: Build final insights ─────────────────────────────────
    insights: list[StockInsight] = []

    for idx, (ws, result, current_price, current_volume, is_stale, last_updated, latest) in enumerate(stock_results):
        if result is None:
            insights.append(StockInsight(
                symbol=ws.symbol,
                current_price=0.0,
                change_pct=0.0,
                significance_level="NORMAL",
                significance_score=0.0,
                signals=SignalBreakdown(price=0, volume=0, market=0, sector=0, event=0),
                market_relative_return=0.0,
                sector_relative_return=0.0,
                volume_ratio=1.0,
                is_stale=False,
                first_view=True,
                insufficient_history=True,
                last_updated=None,
            ))
            continue

        # Determine explanation text
        if result.first_view:
            explanation_text = f"{result.symbol}: Newly added stock. Baseline price set at ₹{current_price:,.2f}."
        elif result.symbol in gemini_explanation_map:
            # Top-3: use Gemini explanation (keyed explicitly by symbol)
            explanation = gemini_explanation_map[result.symbol]
            explanation_text = explanation.get("summary", explanation.get("headline", ""))
        else:
            # Non-top-3: use deterministic explanation
            sector_name = SECTOR_MAP.get(result.symbol, "NIFTY")
            sector_return = sector_returns.get(sector_name, 0.0)
            facts = {
                "symbol": result.symbol,
                "change_since_last_seen": result.change_pct,
                "nifty_change": nifty_return * 100,
                "sector_change": sector_return * 100,
                "volume_vs_normal": result.volume_ratio,
                "anomaly_score": result.significance_score,
                "event": "none",
            }
            explanation = deterministic_explanation(facts)
            explanation_text = explanation.get("summary", explanation.get("headline", ""))

        insights.append(StockInsight(
            symbol=result.symbol,
            current_price=result.current_price,
            change_pct=result.change_pct,
            significance_level=result.significance_level,
            significance_score=result.significance_score,
            signals=SignalBreakdown(**result.signals),
            market_relative_return=result.market_relative_return,
            sector_relative_return=result.sector_relative_return,
            volume_ratio=result.volume_ratio,
            is_stale=is_stale,
            first_view=result.first_view,
            insufficient_history=result.insufficient_history,
            last_updated=latest.timestamp if latest else None,
            explanation=explanation_text,
        ))

    # Already sorted by significance score from Phase 3

    # Split into top insights and unremarkable, ensuring exact total count math
    top = [i for i in insights if i.significance_level != "NORMAL"]
    top_insights = top if top else insights[:3]
    unremarkable_count = max(0, len(insights) - len(top_insights))

    # Find most recent last_seen_at across all stocks
    last_seen_times = [ws.last_seen_at for ws in stocks if ws.last_seen_at is not None]
    most_recent_seen = max(last_seen_times) if last_seen_times else None

    t_total = time.perf_counter() - t_total_start
    logger.info(f"[TIMING] TOTAL /insights: {t_total:.3f}s")

    return InsightsResponse(
        top_insights=top_insights,
        unremarkable_count=unremarkable_count,
        last_seen_at=most_recent_seen,
    )


# ---------- Mark Seen ----------

@router.post("/watchlists/{watchlist_id}/mark-seen", status_code=200)
def mark_seen(watchlist_id: int, db: Session = Depends(get_db)):
    _get_watchlist_or_404(watchlist_id, db)
    stocks = db.query(WatchlistStock).filter(WatchlistStock.watchlist_id == watchlist_id).all()
    now = datetime.now(timezone.utc)
    updated = 0

    for ws in stocks:
        latest = _get_latest_snapshot(ws.symbol, db)
        if latest:
            ws.last_seen_at = now
            ws.last_seen_price = latest.price
            ws.last_seen_volume = latest.volume
            updated += 1

    db.commit()
    return {"updated": updated, "timestamp": now.isoformat()}


# ---------- Helpers ----------

def _get_watchlist_or_404(watchlist_id: int, db: Session) -> Watchlist:
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return wl


def _get_latest_snapshot(symbol: str, db: Session):
    """Get the most recent MarketSnapshot for a symbol."""
    return (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == symbol)
        .order_by(MarketSnapshot.timestamp.desc())
        .first()
    )
