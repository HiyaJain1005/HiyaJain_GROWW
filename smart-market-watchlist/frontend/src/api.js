/**
 * API client with resilience: localStorage caching + offline fallback.
 */

const API_BASE = 'http://localhost:8000';
const CACHE_KEY = 'cached_insights';
const WATCHLIST_CACHE_KEY = 'cached_watchlists';

export async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  // 204 No Content has no body — don't try to parse it
  if (res.status === 204) return null;
  return res.json();
}

/**
 * Fetch insights with localStorage caching.
 * On success: caches the response.
 * On failure: returns cached data with isOffline flag.
 * If no cache at all: returns null.
 */
export async function fetchInsights(watchlistId) {
  try {
    const data = await fetchJSON(`/watchlists/${watchlistId}/insights`);
    // Cache on success
    const cached = {
      data,
      timestamp: new Date().toISOString(),
      watchlistId,
    };
    localStorage.setItem(CACHE_KEY, JSON.stringify(cached));
    return { ...data, isOffline: false, cachedAt: null };
  } catch (err) {
    // Try localStorage fallback
    const raw = localStorage.getItem(CACHE_KEY);
    if (raw) {
      try {
        const cached = JSON.parse(raw);
        return { ...cached.data, isOffline: true, cachedAt: cached.timestamp };
      } catch {
        return null;
      }
    }
    return null;
  }
}

export async function fetchWatchlists() {
  try {
    const data = await fetchJSON('/watchlists');
    localStorage.setItem(WATCHLIST_CACHE_KEY, JSON.stringify({
      data,
      timestamp: new Date().toISOString(),
    }));
    return { data, isOffline: false };
  } catch {
    const raw = localStorage.getItem(WATCHLIST_CACHE_KEY);
    if (raw) {
      try {
        const cached = JSON.parse(raw);
        return { data: cached.data, isOffline: true };
      } catch {
        return { data: [], isOffline: true };
      }
    }
    return { data: [], isOffline: true };
  }
}

export async function createWatchlist(name) {
  return fetchJSON('/watchlists', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

export async function addStock(watchlistId, symbol) {
  return fetchJSON(`/watchlists/${watchlistId}/stocks`, {
    method: 'POST',
    body: JSON.stringify({ symbol: symbol.toUpperCase().trim() }),
  });
}

export async function removeStock(watchlistId, symbol) {
  return fetchJSON(`/watchlists/${watchlistId}/stocks/${symbol}`, {
    method: 'DELETE',
  });
}

export async function markSeen(watchlistId) {
  return fetchJSON(`/watchlists/${watchlistId}/mark-seen`, {
    method: 'POST',
  });
}

export async function getStocks(watchlistId) {
  return fetchJSON(`/watchlists/${watchlistId}/stocks`);
}

export async function fetchAvailableSymbols(watchlistId) {
  try {
    const url = watchlistId ? `/symbols?watchlist_id=${watchlistId}` : '/symbols';
    return await fetchJSON(url);
  } catch {
    return [
      "BHARTIARTL", "HCLTECH", "HDFCBANK", "ICICIBANK",
      "INFY", "ITC", "LT", "RELIANCE", "SBIN", "TCS"
    ];
  }
}
