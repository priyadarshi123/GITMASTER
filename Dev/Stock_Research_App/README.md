# StockLens India 📊
### A Screener.in-style stock research platform for NSE/BSE

---

## Features

- **Stock Analysis** — Price chart (candlestick + MA20/MA50 + volume), full P&L, Balance Sheet, Cash Flow, 20+ key ratios
- **Screener** — Filter Nifty 50 stocks by PE, ROE, D/E, Market Cap, Sector with interactive bubble chart
- **Compare** — Side-by-side fundamentals + normalised 1Y price performance for up to 4 stocks
- **Dark theme** — Professional trading terminal aesthetic

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
streamlit run app.py
```

### 3. Open in browser
```
http://localhost:8501
```

---

## How to use

### Stock Analysis
- Type a stock symbol in the search box: `RELIANCE`, `HDFCBANK`, `INFY`, `TCS`
- Or use the quick-pick dropdown
- Symbols auto-resolve to NSE (`.NS` suffix). For BSE, add `.BO`: `RELIANCE.BO`

### Screener
- Click **Load Screener Data** (fetches live Nifty 50 data, ~30 seconds)
- Filter by Max P/E, Min ROE, Max D/E, Market Cap, Sector
- ROE vs PE bubble chart shows value vs growth positioning

### Compare
- Enter 2–4 stock symbols
- View side-by-side ratios table
- See normalised 1-year price chart (base = 100)

---

## Data Source
All data via **Yahoo Finance** (yfinance library) — free, no API key required.

Refresh rates:
- Price data: real-time (15-min delay for NSE)
- Financials: cached 5 minutes
- Screener: cached 10 minutes

---

## Extending the app

### Add more Nifty 50 stocks to screener
Edit `NIFTY50_TICKERS` list in `app.py`

### Add BSE stocks
Use `.BO` suffix: `RELIANCE.BO`, `TCS.BO`

### Deploy online
```bash
# Streamlit Cloud (free)
# Push to GitHub → connect at share.streamlit.io

# Or deploy on your existing pdeconomyresearch.com server:
streamlit run app.py --server.port 8502 --server.headless true
```

---

*Built with Streamlit + yfinance + Plotly. For informational purposes only — not investment advice.*
