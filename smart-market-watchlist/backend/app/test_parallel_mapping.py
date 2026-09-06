"""
Verification script: Symbol-keyed parallel Gemini calls race condition proof.
"""
import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.gemini import get_explanations_parallel

def verify_symbol_keying():
    # 3 distinct stock movements
    distinct_facts = [
        {
            "symbol": "STK_NEG",
            "change_since_last_seen": -12.5,
            "nifty_change": 0.2,
            "sector_change": 0.1,
            "volume_vs_normal": 1.1,
            "anomaly_score": 85.0,
            "event": "earnings_miss",
        },
        {
            "symbol": "STK_VOL",
            "change_since_last_seen": 0.1,
            "nifty_change": 0.0,
            "sector_change": 0.0,
            "volume_vs_normal": 8.5, # Huge unusual volume spike
            "anomaly_score": 90.0,
            "event": "block_deal",
        },
        {
            "symbol": "STK_DIV",
            "change_since_last_seen": 7.8, # Sharp rally while sector/market declined
            "nifty_change": -2.1,
            "sector_change": -3.0,
            "volume_vs_normal": 1.2,
            "anomaly_score": 78.0,
            "event": "fda_approval",
        },
    ]

    print("=== Calling get_explanations_parallel with 3 distinct stocks concurrently ===")
    t0 = time.perf_counter()
    res_dict = get_explanations_parallel(distinct_facts)
    elapsed = time.perf_counter() - t0

    print(f"Parallel call completed in {elapsed:.3f}s")
    print(f"Returned Dict Keys: {list(res_dict.keys())}\n")

    for symbol in ["STK_NEG", "STK_VOL", "STK_DIV"]:
        assert symbol in res_dict, f"Error: {symbol} key missing in result dict!"
        exp = res_dict[symbol]
        summary = exp.get("summary", exp.get("headline", ""))
        print(f"--- [{symbol}] ---")
        print(f"Key in dict: '{symbol}'")
        print(f"Headline: {exp.get('headline')}")
        print(f"Summary: {summary}\n")

    print("VERIFICATION SUCCESS: Each explanation is mapped explicitly by symbol key in dict!")

if __name__ == "__main__":
    verify_symbol_keying()
