# Smart Market Watchlist

> A significance-driven stock watchlist that tells you **what changed and why it matters** — moving away from raw, noisy ticker streams to prioritized, attention-based insights powered by Gemini AI.

Built for the **Groww "Code" Hackathon**.

---

## 🌟 Key Features

1. **Significance Engine**: Analyzes price z-scores, volume anomalies, market-relative divergence, and sector-relative divergence to compute a 0–1 anomaly score for each stock.
2. **Attention-Driven UI**: Automatically surface high-impact stocks ("Needs Attention", "Significant", "Watch") while hiding unremarkable market noise.
3. **Gemini AI Explanations**: Context-aware AI summaries explaining *why* a stock moved and *how* it compares to broader indices like NIFTY.
4. **Resilient Offline Architecture**: Built-in `localStorage` caching and degraded state indicators if the backend or market data feed becomes unreachable.
5. **Delta Tracking**: Track changes since **your last visit** with the "Mark All Seen" feature.

---

## 🏗️ Architecture & Tech Stack

- **Backend**: Python 3.10+ with [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/), [SQLite](https://www.sqlite.org/), and [Pydantic v2](https://docs.pydantic.dev/).
- **Frontend**: React 18, Vite, Vanilla CSS with custom glassmorphism design tokens.
- **AI / LLM Layer**: Google Gemini API (`google-genai` SDK) with deterministic template fallbacks.
- **Testing**: `pytest` suite for core mathematical models and edge cases.

---

## 📐 Significance Engine Formula

$$\text{Score} = 0.30 \cdot S_{\text{price}} + 0.20 \cdot S_{\text{volume}} + 0.20 \cdot S_{\text{market}} + 0.15 \cdot S_{\text{sector}} + 0.15 \cdot S_{\text{event}}$$

- **Price Signal ($S_{\text{price}}$)**: Normalized Z-Score ($Z / 4.0$).
- **Volume Signal ($S_{\text{volume}}$)**: Anomaly ratio normalized above baseline ($(V_{\text{ratio}} - 1.0) / 3.0$).
- **Market Divergence ($S_{\text{market}}$)**: Stock Return vs. NIFTY Return ($|\Delta_{\text{market}}| / 0.05$).
- **Sector Divergence ($S_{\text{sector}}$)**: Stock Return vs. Sector Index Return ($|\Delta_{\text{sector}}| / 0.05$).

### Significance Levels

| Level | Score Range | Description |
| :--- | :--- | :--- |
| **NORMAL** | $< 0.35$ | Unremarkable movement within standard variance |
| **WATCH** | $0.35 - 0.59$ | Mild volume spike or slight divergence |
| **SIGNIFICANT** | $0.60 - 0.79$ | High divergence from market/sector |
| **ATTENTION** | $\ge 0.80$ | Extreme movement requiring immediate review |

---

## 🚀 Quickstart Guide

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment (optional)
python -m venv venv
# On Windows: venv\Scripts\activate
# On macOS/Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Set your Gemini API Key in .env
cp .env.example .env
# Edit .env and paste: GEMINI_API_KEY=your_actual_key

# Seed synthetic market data (30 days history for 10 NIFTY stocks)
python -m app.seed

# Run FastAPI server
uvicorn app.main:app --reload --port 8000
```

The backend API will be available at `http://localhost:8000`. API Documentation is accessible at `http://localhost:8000/docs`.

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run Vite development server
npm run dev
```

The frontend will run at `http://localhost:5173`.

---

## 🧪 Running Unit Tests

```bash
cd backend
python -m pytest tests/test_significance.py -v
```

All 7 mathematical test cases (Normal movement, Stock-specific shock, Whole-market move dampening, Volume anomaly, Zero standard deviation guard, Insufficient history fallback, Duplicate add prevention) will run and verify accuracy.

---

## 🔌 API Endpoints Reference

- `GET /health` — API health check
- `GET /symbols` — List available stock tickers with historical market data
- `GET /watchlists` — List user watchlists
- `POST /watchlists` — Create a new watchlist
- `GET /watchlists/{id}/stocks` — Fetch stocks in a watchlist
- `POST /watchlists/{id}/stocks` — Add a stock symbol to watchlist (validated against available symbols)
- `DELETE /watchlists/{id}/stocks/{symbol}` — Remove a stock from watchlist
- `GET /watchlists/{id}/insights` — Compute composite significance scores & return AI summaries
- `POST /watchlists/{id}/mark-seen` — Update snapshot markers for delta tracking

---

## 🚫 What We Deliberately Did Not Build

- Current prices are fetched live via Yahoo Finance (`yfinance` with unofficial `.NS` NSE ticker data with a 3-minute in-memory cache), while 30-day historical baselines are simulated for this build. The provider is fully swappable per the `MarketDataProvider` abstraction — this is a deliberate architecture scoping choice rather than an oversight.
- Focus is exclusively on significance-driven intelligence, anomaly detection, and notification triage rather than trade execution or order placement.

