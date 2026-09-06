import { useState, useEffect, useCallback } from 'react'
import { fetchInsights, fetchWatchlists, createWatchlist, addStock, removeStock, markSeen, getStocks, fetchAvailableSymbols } from './api'
import MarketStatus from './components/MarketStatus'
import AttentionCard from './components/AttentionCard'
import AddStock from './components/AddStock'

function formatTimeSince(dateStr) {
  if (!dateStr) return 'never'
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  const mins = Math.floor((diff % 3600000) / 60000)
  if (hours > 24) return `${Math.floor(hours / 24)}d ago`
  if (hours > 0) return `${hours}h ${mins}m ago`
  if (mins > 0) return `${mins}m ago`
  return 'just now'
}

export default function App() {
  const [watchlistId, setWatchlistId] = useState(null)
  const [insights, setInsights] = useState(null)
  const [isOffline, setIsOffline] = useState(false)
  const [cachedAt, setCachedAt] = useState(null)
  const [loading, setLoading] = useState(true)
  const [stocks, setStocks] = useState([])
  const [availableSymbols, setAvailableSymbols] = useState([])
  const [expandUnremarkable, setExpandUnremarkable] = useState(false)
  const [error, setError] = useState(null)

  // Load watchlists on mount
  useEffect(() => {
    loadWatchlists()
  }, [])

  async function loadSymbols(targetWatchlistId = watchlistId) {
    const symbols = await fetchAvailableSymbols(targetWatchlistId)
    setAvailableSymbols(symbols)
  }

  // Load insights and symbols when watchlist changes
  useEffect(() => {
    if (watchlistId) {
      loadInsights()
      loadStocks()
      loadSymbols(watchlistId)
    }
  }, [watchlistId])

  async function loadWatchlists() {
    const result = await fetchWatchlists()
    if (result.data.length > 0) {
      setWatchlistId(result.data[0].id)
    }
    setIsOffline(result.isOffline)
  }

  async function loadInsights() {
    setLoading(true)
    setError(null)
    const result = await fetchInsights(watchlistId)
    if (result) {
      setInsights(result)
      setIsOffline(result.isOffline)
      setCachedAt(result.cachedAt)
    } else {
      setError('No data available. Please make sure the backend is running.')
    }
    setLoading(false)
  }

  async function loadStocks() {
    try {
      const data = await getStocks(watchlistId)
      setStocks(data)
    } catch {
      // use cached insights as fallback
    }
  }

  async function handleAddStock(symbol) {
    let targetWlId = watchlistId
    if (!targetWlId) {
      // Create default watchlist first
      const wl = await createWatchlist('My Watchlist')
      targetWlId = wl.id
      setWatchlistId(wl.id)
      await addStock(wl.id, symbol)
    } else {
      await addStock(targetWlId, symbol)
    }
    await loadInsights()
    await loadStocks()
    await loadSymbols(targetWlId)
  }

  async function handleRemoveStock(symbol) {
    if (!watchlistId) return
    await removeStock(watchlistId, symbol)
    await loadInsights()
    await loadStocks()
    await loadSymbols(watchlistId)
  }

  async function handleMarkSeen() {
    if (!watchlistId) return
    await markSeen(watchlistId)
    await loadInsights()
  }

  // Separate top insights from unremarkable
  const topInsights = insights?.top_insights || []
  const unremarkableCount = insights?.unremarkable_count || 0
  const lastSeenAt = insights?.last_seen_at

  // Existing symbols for duplicate guard
  const existingSymbols = stocks.map(s => s.symbol.toUpperCase())

  return (
    <div className="app">
      {/* Offline Banner */}
      {isOffline && (
        <div className="offline-banner" id="offline-banner">
          <span className="icon">&#x26A0;</span>
          <span className="text">
            Offline — showing data as of {cachedAt ? new Date(cachedAt).toLocaleString() : 'last session'}
          </span>
          <span className="timestamp">Backend unreachable</span>
        </div>
      )}

      {/* Header */}
      <header className="header">
        <div className="header-left">
          <h1>Smart Market Watchlist</h1>
          <p className="subtitle">
            Welcome back — last checked {formatTimeSince(lastSeenAt)}
          </p>
        </div>
        <div className="header-right">
          <MarketStatus isOffline={isOffline} />
          {!isOffline && (
            <button className="btn btn-primary" onClick={handleMarkSeen} id="mark-seen-btn">
              Mark All Seen
            </button>
          )}
        </div>
      </header>

      {/* Add Stock */}
      {!isOffline && (
        <AddStock
          onAdd={handleAddStock}
          existingSymbols={existingSymbols}
          availableSymbols={availableSymbols}
        />
      )}

      {/* Loading */}
      {loading && (
        <div className="loading">
          <div className="spinner"></div>
        </div>
      )}

      {/* Error / Empty State */}
      {!loading && error && (
        <div className="empty-state" id="empty-state">
          <div className="icon">&#x1F4E1;</div>
          <h2>Cannot reach the server</h2>
          <p>{error}</p>
        </div>
      )}

      {/* Insights */}
      {!loading && !error && insights && (
        <>
          {topInsights.length > 0 ? (
            <section className="insights-section">
              <div className="section-label">Stocks That Need Your Attention</div>
              {topInsights.map((stock, i) => (
                <AttentionCard
                  key={stock.symbol}
                  stock={stock}
                  index={i}
                  onRemove={handleRemoveStock}
                  isOffline={isOffline}
                />
              ))}
            </section>
          ) : (
            <div className="empty-state">
              <div className="icon">&#x2705;</div>
              <h2>All clear</h2>
              <p>Nothing materially changed since your last check.</p>
            </div>
          )}

          {/* Unremarkable section */}
          {unremarkableCount > 0 && (
            <div className="unremarkable">
              <div
                className="unremarkable-header"
                onClick={() => setExpandUnremarkable(!expandUnremarkable)}
                id="unremarkable-toggle"
              >
                <span className="text">
                  {unremarkableCount} other stock{unremarkableCount > 1 ? 's' : ''} — nothing materially changed
                </span>
                <span className={`chevron ${expandUnremarkable ? 'open' : ''}`}>
                  &#x25BC;
                </span>
              </div>
              {expandUnremarkable && (
                <div className="unremarkable-list">
                  {/* Unremarkable stocks would be fetched separately in a full impl.
                      For now, we show a summary. */}
                  <div className="unremarkable-item" style={{ justifyContent: 'center', color: 'var(--text-muted)' }}>
                    <span>All within normal range. Check back later.</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* No data at all — first load with no connection */}
      {!loading && !error && !insights && (
        <div className="empty-state" id="first-load-empty">
          <div className="icon">&#x1F4CA;</div>
          <h2>No data yet</h2>
          <p>
            This appears to be your first visit and the server is unreachable.
            Please start the backend and refresh.
          </p>
        </div>
      )}
    </div>
  )
}
