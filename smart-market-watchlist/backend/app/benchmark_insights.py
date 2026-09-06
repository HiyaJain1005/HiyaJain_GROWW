"""
Comprehensive benchmark for /insights latency optimization steps.
"""
import time
import sys
import os
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import WatchlistStock
from app.services.market_data import get_live_quote, get_live_quotes_batch, _QUOTE_CACHE
from app.services.gemini import get_explanation, get_explanations_parallel

def benchmark_all():
    db = SessionLocal()
    stocks = db.query(WatchlistStock).filter(WatchlistStock.watchlist_id == 1).all()
    symbols = [ws.symbol for ws in stocks]
    print(f"Watchlist contains {len(symbols)} stocks: {symbols}\n")

    # -------------------------------------------------------------
    # 1. yfinance: Sequential vs Batched
    # -------------------------------------------------------------
    print("=== Sub-step 2: yfinance Fetch Performance ===")
    _QUOTE_CACHE.clear()
    
    # Sequential
    t0 = time.perf_counter()
    for sym in symbols:
        get_live_quote(sym)
    t_seq_yf = time.perf_counter() - t0
    print(f"Sequential yfinance (10 calls): {t_seq_yf:.3f}s")

    _QUOTE_CACHE.clear()
    # Batched
    t0 = time.perf_counter()
    get_live_quotes_batch(symbols)
    t_batch_yf = time.perf_counter() - t0
    print(f"Batched yfinance (yf.download 1 call): {t_batch_yf:.3f}s")
    print(f"yfinance Speedup: {t_seq_yf / t_batch_yf:.2f}x faster\n")

    # -------------------------------------------------------------
    # 2. Cache Hit Verification
    # -------------------------------------------------------------
    print("=== Sub-step 3: Cache Hit Verification ===")
    # _QUOTE_CACHE is already populated from the batched call above
    t0 = time.perf_counter()
    quotes_cached = get_live_quotes_batch(symbols)
    t_cache_hit = time.perf_counter() - t0
    print(f"Second call within 3 mins (Cache Hit): {t_cache_hit:.4f}s")
    print(f"Cached items count: {len(quotes_cached)}\n")

    # -------------------------------------------------------------
    # 3 & 4. Gemini Call Reduction & Parallelization
    # -------------------------------------------------------------
    print("=== Sub-step 4 & 5: Gemini Call Count & Parallel Execution ===")
    sample_facts = [
        {"symbol": sym, "change_since_last_seen": 2.5, "nifty_change": 0.5, "sector_change": 1.2, "volume_vs_normal": 1.5, "anomaly_score": 0.8, "event": "none"}
        for sym in symbols[:8] # 8 non-first-view stocks
    ]

    print(f"BEFORE: Gemini called sequentially for ALL 8 non-first-view stocks")
    t0 = time.perf_counter()
    for facts in sample_facts:
        get_explanation(facts)
    t_seq_gemini = time.perf_counter() - t0
    print(f"Sequential Gemini (8 calls): {t_seq_gemini:.3f}s")

    top3_facts = sample_facts[:3]
    print(f"\nAFTER: Gemini called ONLY for top 3 stocks in PARALLEL")
    t0 = time.perf_counter()
    get_explanations_parallel(top3_facts)
    t_par_gemini = time.perf_counter() - t0
    print(f"Parallel Gemini (3 calls): {t_par_gemini:.3f}s")
    print(f"Gemini Speedup: {t_seq_gemini / t_par_gemini:.2f}x faster\n")

    db.close()

if __name__ == "__main__":
    benchmark_all()
