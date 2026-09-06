"""
Gemini explanation layer.

Takes facts about a stock's movement and asks Gemini to explain why it deserves attention.
Falls back to a deterministic template on ANY exception.
"""

import json
import logging
import time
from typing import Optional, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a financial information explanation component.
Use ONLY the supplied facts.
Rules:
1. Never invent numerical values.
2. Never calculate new financial metrics.
3. Never predict future prices.
4. Never give BUY, SELL, or HOLD recommendations.
5. Never invent news or events.
6. If evidence is insufficient, say "Insufficient evidence".
7. Return the requested JSON structure.
8. Keep the explanation concise."""


def deterministic_explanation(facts: dict) -> dict:
    """Fallback explanation using only the supplied facts. Never fails."""
    symbol = facts.get("symbol", "Unknown")
    change = facts.get("change_since_last_seen", 0)
    nifty = facts.get("nifty_change", 0)
    volume_ratio = facts.get("volume_vs_normal", 1.0)

    parts = [f"{symbol} moved {change:.1f}% since your last check."]
    parts.append(f"Market movement was {nifty:.1f}%.")

    if abs(volume_ratio - 1.0) > 0.5:
        parts.append(f"Trading volume is {volume_ratio:.1f}x the usual level.")

    return {
        "headline": f"{symbol}: {change:+.1f}% since last check",
        "summary": " ".join(parts),
        "confidence": "high",
    }


def get_explanation(facts: dict) -> dict:
    """
    Get a Gemini-generated explanation, or fall back to deterministic.
    Never raises. Never returns None.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "placeholder_set_your_real_key":
        return deterministic_explanation(facts)

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)

        user_prompt = f"""Explain why this stock deserves attention. Return JSON with keys: headline, summary, confidence (high/medium/low).

Facts:
- Symbol: {facts.get('symbol')}
- Change since last seen: {facts.get('change_since_last_seen', 0):.2f}%
- NIFTY change: {facts.get('nifty_change', 0):.2f}%
- Sector change: {facts.get('sector_change', 0):.2f}%
- Volume vs normal: {facts.get('volume_vs_normal', 1.0):.1f}x
- Anomaly score: {facts.get('anomaly_score', 0):.2f}
- Event: {facts.get('event', 'none')}"""

        t0 = time.perf_counter()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
            },
        )
        elapsed = time.perf_counter() - t0
        logger.info(f"Gemini call for {facts.get('symbol')}: {elapsed:.3f}s")

        # Parse the JSON response
        result = json.loads(response.text)

        # Validate required keys
        if "headline" not in result or "summary" not in result:
            return deterministic_explanation(facts)

        # Ensure confidence is valid
        if result.get("confidence") not in ("high", "medium", "low"):
            result["confidence"] = "medium"

        return result

    except Exception:
        # Any error at all — bad key, timeout, rate limit, malformed response —
        # fall back gracefully. Never crash the endpoint.
        return deterministic_explanation(facts)


def get_explanations_parallel(facts_list: List[dict]) -> Dict[str, dict]:
    """
    Call get_explanation for multiple stocks in parallel using ThreadPoolExecutor.
    Returns a dict mapping symbol -> explanation dict, ensuring race-condition safety.
    """
    if not facts_list:
        return {}

    t0 = time.perf_counter()
    results: Dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=min(len(facts_list), 5)) as executor:
        future_to_symbol = {
            executor.submit(get_explanation, facts): facts["symbol"]
            for facts in facts_list
        }
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                results[symbol] = future.result()
            except Exception:
                # Find matching facts for fallback
                matching_facts = next((f for f in facts_list if f["symbol"] == symbol), {"symbol": symbol})
                results[symbol] = deterministic_explanation(matching_facts)

    elapsed = time.perf_counter() - t0
    logger.info(f"Parallel Gemini batch ({len(facts_list)} calls): {elapsed:.3f}s total")

    return results

