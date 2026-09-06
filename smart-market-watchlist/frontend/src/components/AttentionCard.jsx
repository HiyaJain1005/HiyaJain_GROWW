function getSignalLevel(value) {
  if (value < 0.25) return 'low'
  if (value < 0.5) return 'medium'
  if (value < 0.75) return 'high'
  return 'critical'
}

function SignalBar({ label, value }) {
  return (
    <div className="signal-bar">
      <div className="label">{label}</div>
      <div className="bar-track">
        <div
          className={`bar-fill ${getSignalLevel(value)}`}
          style={{ width: `${Math.max(value * 100, 2)}%` }}
        ></div>
      </div>
      <div className="value">{(value * 100).toFixed(0)}%</div>
    </div>
  )
}

export default function AttentionCard({ stock, index, onRemove, isOffline }) {
  const {
    symbol,
    current_price,
    change_pct,
    significance_level,
    significance_score,
    signals,
    market_relative_return,
    sector_relative_return,
    volume_ratio,
    is_stale,
    last_updated,
    explanation,
  } = stock

  const changeClass = change_pct > 0 ? 'positive' : change_pct < 0 ? 'negative' : 'neutral'
  const changeSign = change_pct > 0 ? '+' : ''

  return (
    <div
      className={`attention-card ${significance_level} card-animate`}
      style={{ animationDelay: `${index * 0.08}s` }}
      id={`card-${symbol}`}
    >
      <div className="card-header">
        <div>
          <div className="card-symbol">
            {symbol}
            {!isOffline && (
              <button
                className="remove-stock-btn"
                onClick={() => onRemove(symbol)}
                title="Remove from watchlist"
              >
                &times;
              </button>
            )}
          </div>
          <span className={`sig-badge ${significance_level}`}>
            {significance_level} &middot; {(significance_score * 100).toFixed(0)}
          </span>
        </div>
        <div className="card-price">
          <div className="price">&#x20B9;{current_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
          {stock.first_view ? (
            <div className="change neutral" style={{ fontWeight: 600, color: 'var(--yellow)' }}>
              NEW (FIRST VIEW)
            </div>
          ) : (
            <div className={`change ${changeClass}`}>
              {changeSign}{change_pct.toFixed(2)}%
            </div>
          )}
        </div>
      </div>

      <div className="signal-bars">
        <SignalBar label="Price" value={signals.price} />
        <SignalBar label="Volume" value={signals.volume} />
        <SignalBar label="Market" value={signals.market} />
        <SignalBar label="Sector" value={signals.sector} />
      </div>

      {explanation && (
        <div className="card-explanation">{explanation}</div>
      )}

      <div className="card-freshness">
        <span className={`freshness-dot ${is_stale ? 'stale' : 'live'}`}></span>
        <span>
          {is_stale ? 'Stale data' : 'Live'} &middot;{' '}
          {last_updated ? new Date(last_updated).toLocaleString() : 'unknown'}
        </span>
        {volume_ratio > 1.5 && (
          <span style={{ marginLeft: '8px', color: 'var(--yellow)', fontWeight: 600 }}>
            {volume_ratio.toFixed(1)}x vol
          </span>
        )}
      </div>
    </div>
  )
}
