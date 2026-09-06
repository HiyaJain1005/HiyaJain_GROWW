import { useState, useEffect } from 'react'

export default function AddStock({ onAdd, existingSymbols, availableSymbols = [] }) {
  const [selectedSymbol, setSelectedSymbol] = useState('')
  const [adding, setAdding] = useState(false)

  // Filter available symbols to only unadded ones
  const unaddedSymbols = availableSymbols.filter(
    sym => !existingSymbols.includes(sym.toUpperCase())
  )

  // Sync selected symbol when unaddedSymbols list updates
  useEffect(() => {
    if (unaddedSymbols.length > 0 && !unaddedSymbols.includes(selectedSymbol)) {
      setSelectedSymbol(unaddedSymbols[0])
    } else if (unaddedSymbols.length === 0) {
      setSelectedSymbol('')
    }
  }, [existingSymbols, availableSymbols])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!selectedSymbol || adding) return
    setAdding(true)
    try {
      await onAdd(selectedSymbol)
    } catch (err) {
      console.error('Failed to add stock:', err)
    } finally {
      setAdding(false)
    }
  }

  return (
    <form className="add-stock-bar" onSubmit={handleSubmit} id="add-stock-form">
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <select
          value={selectedSymbol}
          onChange={e => setSelectedSymbol(e.target.value)}
          disabled={adding || unaddedSymbols.length === 0}
          id="add-stock-select"
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-card)',
            color: 'var(--text-main)',
            fontSize: '1rem',
            outline: 'none',
            cursor: unaddedSymbols.length > 0 ? 'pointer' : 'not-allowed'
          }}
        >
          {unaddedSymbols.length > 0 ? (
            unaddedSymbols.map(sym => (
              <option key={sym} value={sym}>
                {sym}
              </option>
            ))
          ) : (
            <option value="">All available market stocks added</option>
          )}
        </select>
      </div>
      <button
        type="submit"
        className="btn btn-primary"
        disabled={!selectedSymbol || adding || unaddedSymbols.length === 0}
        id="add-stock-btn"
      >
        {adding ? 'Adding...' : '+ Add Stock'}
      </button>
    </form>
  )
}
