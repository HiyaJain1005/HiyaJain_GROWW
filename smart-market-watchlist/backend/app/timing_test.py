"""
Timing diagnostic for /insights endpoint with optimizations.
Run from backend/ directory: python -m app.timing_test
"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import WatchlistStock
from app.routes.watchlist import get_insights
from app.services.market_data import get_live_quotes_batch, _QUOTE_CACHE

def run_test():
    print("--- 1. Testing GET /watchlists/1/insights directly in code ---")
    db = SessionLocal()
    
    # Measure cold call
    _QUOTE_CACHE.clear()
    t0 = time.perf_counter()
    res1 = get_insights(1, db)
    t_cold = time.perf_counter() - t0
    print(f"COLD GET /insights call: {t_cold:.3f}s")
    print(f"Top insights count: {len(res1.top_insights)}")
    for insight in res1.top_insights[:5]:
        exp = insight.explanation if hasattr(insight, 'explanation') else getattr(insight, 'summary', '')
        print(f"  [{insight.symbol}] score={insight.significance_score:.2f}")
    
    print("\n--- 2. Testing WARM call (using cache) ---")
    t0 = time.perf_counter()
    res2 = get_insights(1, db)
    t_warm = time.perf_counter() - t0
    print(f"WARM GET /insights call: {t_warm:.3f}s")
    
    db.close()

if __name__ == "__main__":
    run_test()
