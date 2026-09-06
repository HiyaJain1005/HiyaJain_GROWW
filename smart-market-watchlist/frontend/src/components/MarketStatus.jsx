export default function MarketStatus({ isOffline }) {
  return (
    <div className={`market-status ${isOffline ? 'offline' : 'live'}`} id="market-status">
      <span className="status-dot"></span>
      {isOffline ? 'Offline' : 'Live'}
    </div>
  )
}
