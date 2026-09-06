"""
Market Data Provider Layer.

Abstraction for fetching live price/volume data from external providers (e.g. Yahoo Finance).
Includes an in-memory cache (3 min TTL) and graceful exception handling.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 3 minutes cache TTL (180 seconds)
CACHE_TTL_SECONDS = 180

# In-memory quote cache: { symbol: (timestamp_epoch, quote_dict) }
_QUOTE_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}


class MarketDataProvider(ABC):
    """Abstract interface for stock market data providers."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current price and volume for a symbol.
        Returns dict: {"price": float, "volume": float, "is_live": True, "timestamp": datetime}
        or None if fetch fails.
        """
        pass

    @abstractmethod
    def get_quotes_batch(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch current price and volume for multiple symbols in a single batch call.
        Returns dict mapping symbol -> quote_dict or None.
        """
        pass


class YFinanceMarketDataProvider(MarketDataProvider):
    """Live market data provider using yfinance (.NS suffix for NSE stocks)."""

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        symbol_upper = symbol.upper().strip()
        
        # Check cache first
        now_epoch = time.time()
        if symbol_upper in _QUOTE_CACHE:
            cached_time, cached_quote = _QUOTE_CACHE[symbol_upper]
            if now_epoch - cached_time < CACHE_TTL_SECONDS:
                logger.info(f"CACHE HIT for {symbol_upper} (age: {now_epoch - cached_time:.0f}s)")
                return cached_quote

        logger.info(f"CACHE MISS for {symbol_upper} — fetching from yfinance")

        # Live fetch with yfinance
        try:
            import yfinance as yf

            ticker_symbol = f"{symbol_upper}.NS" if not symbol_upper.endswith(".NS") else symbol_upper
            ticker = yf.Ticker(ticker_symbol)

            price = None
            volume = None

            # 1. Try fast_info
            try:
                fast = ticker.fast_info
                price = fast.get("lastPrice") or fast.get("last_price") or fast.get("previousClose")
                volume = fast.get("lastVolume") or fast.get("last_volume") or fast.get("threeMonthAverageVolume")
            except Exception:
                pass

            # 2. Fallback to 1-day history if fast_info incomplete
            if price is None or price <= 0:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    volume = float(hist["Volume"].iloc[-1])

            if price is None or price <= 0:
                return None

            quote = {
                "price": round(float(price), 2),
                "volume": float(volume) if volume else 1_000_000.0,
                "is_live": True,
                "timestamp": datetime.now(timezone.utc),
            }

            # Update cache
            _QUOTE_CACHE[symbol_upper] = (now_epoch, quote)
            return quote

        except Exception:
            # Any error (timeout, rate limit, invalid ticker) returns None for fallback handling
            return None

    def get_quotes_batch(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch quotes for all symbols using a single batched yf.download() call.
        Symbols with valid cache entries are returned from cache without hitting the network.
        """
        now_epoch = time.time()
        results: Dict[str, Optional[Dict[str, Any]]] = {}
        symbols_to_fetch: List[str] = []

        # Check cache first for all symbols
        for symbol in symbols:
            symbol_upper = symbol.upper().strip()
            if symbol_upper in _QUOTE_CACHE:
                cached_time, cached_quote = _QUOTE_CACHE[symbol_upper]
                if now_epoch - cached_time < CACHE_TTL_SECONDS:
                    logger.info(f"CACHE HIT for {symbol_upper} (age: {now_epoch - cached_time:.0f}s)")
                    results[symbol_upper] = cached_quote
                    continue
            logger.info(f"CACHE MISS for {symbol_upper} — will batch fetch")
            symbols_to_fetch.append(symbol_upper)

        if not symbols_to_fetch:
            logger.info("All symbols served from cache — no yfinance call needed")
            return results

        # Batch fetch all uncached symbols at once
        try:
            import yfinance as yf

            ticker_symbols = [f"{s}.NS" for s in symbols_to_fetch]
            tickers_str = " ".join(ticker_symbols)

            logger.info(f"Batch fetching {len(symbols_to_fetch)} symbols from yfinance: {symbols_to_fetch}")
            t0 = time.perf_counter()

            # Use yf.download for batch — single network round-trip
            data = yf.download(
                tickers=tickers_str,
                period="1d",
                group_by="ticker",
                progress=False,
                threads=True,
            )

            elapsed = time.perf_counter() - t0
            logger.info(f"yf.download batch completed in {elapsed:.3f}s")

            now_epoch = time.time()
            for symbol_upper in symbols_to_fetch:
                try:
                    ticker_sym = f"{symbol_upper}.NS"
                    if len(symbols_to_fetch) == 1:
                        # Single ticker: data columns are flat (Close, Volume, ...)
                        if not data.empty:
                            price = float(data["Close"].iloc[-1])
                            volume = float(data["Volume"].iloc[-1])
                        else:
                            results[symbol_upper] = None
                            continue
                    else:
                        # Multiple tickers: data is grouped by ticker
                        if ticker_sym in data.columns.get_level_values(0):
                            ticker_data = data[ticker_sym]
                            if not ticker_data.empty and not ticker_data["Close"].isna().all():
                                price = float(ticker_data["Close"].dropna().iloc[-1])
                                volume = float(ticker_data["Volume"].dropna().iloc[-1])
                            else:
                                results[symbol_upper] = None
                                continue
                        else:
                            results[symbol_upper] = None
                            continue

                    if price is None or price <= 0:
                        results[symbol_upper] = None
                        continue

                    quote = {
                        "price": round(float(price), 2),
                        "volume": float(volume) if volume else 1_000_000.0,
                        "is_live": True,
                        "timestamp": datetime.now(timezone.utc),
                    }
                    _QUOTE_CACHE[symbol_upper] = (now_epoch, quote)
                    results[symbol_upper] = quote

                except Exception as e:
                    logger.warning(f"Failed to parse batch data for {symbol_upper}: {e}")
                    results[symbol_upper] = None

        except Exception as e:
            logger.warning(f"Batch yfinance download failed: {e}")
            # Fill all unfetched symbols with None
            for symbol_upper in symbols_to_fetch:
                if symbol_upper not in results:
                    results[symbol_upper] = None

        return results


# Default provider instance
_default_provider: MarketDataProvider = YFinanceMarketDataProvider()


def get_live_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Convenience function fetching live quote using default MarketDataProvider."""
    return _default_provider.get_quote(symbol)


def get_live_quotes_batch(symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Convenience function fetching live quotes for multiple symbols in a single batch."""
    return _default_provider.get_quotes_batch(symbols)
