# AGENTS.md - AI Coding Agent Guide for GITMASTER

## Project Overview
**GITMASTER** is a **Streamlit-based Global Macro Dashboard** that aggregates market data from multiple sources (Yahoo Finance, FRED API, OpenAI) to provide real-time financial analysis, technical indicators, and AI-powered market commentary.

**Key Domain**: Quantitative finance, macroeconomic analysis, global market surveillance
**Primary Stack**: Python, Streamlit, yfinance, pandas, FRED API

---

## Architecture & Data Flow

### Core Structure: `PROJECT/ECONOMY/`
```
PROJECT/ECONOMY/
├── master.py              # Main Streamlit app (entry point)
├── my_functions.py        # Reusable finance/utility functions (230+ lines)
├── pages/                 # Multi-page Streamlit app (numbered tabs)
│   ├── 1_Markets.py       # Current market snapshot
│   ├── 2_Global_PMI.py    # Purchasing Manager Index
│   ├── 3_US_Economy.py    # US econ indicators
│   ├── 4_Recession.py     # Recession signals
│   └── 5_Stocks.py        # Stock-specific analysis
├── Tools/
│   └── DownloadFredData.py # Batch FRED data export
└── requirements.txt       # Dependencies
```

### Data Pipeline
1. **Data Sources**:
   - `yfinance`: Market tickers (equities, commodities, crypto)
   - `Fred API`: US Treasury yields, economic indicators
   - `OpenAI API`: GPT-4o-mini for macro commentary generation
   
2. **Processing Flow** (`master.py` → `my_functions.py`):
   - Fetch market data → Calculate technical indicators (RSI, moving averages, momentum)
   - Prepare summaries → Generate AI prompt → Query OpenAI
   - Visualize with Plotly (bar charts) and Matplotlib (line graphs)

3. **Caching Strategy** (`@st.cache_data(ttl=3600)`):
   - All data fetches cached for 1 hour to avoid API rate limits
   - Critical for yfinance and FRED calls

---

## Essential Code Patterns & Conventions

### Market Tickers Registry
**Location**: `master.py` lines 18-32
```python
MARKETS = {
    "Equities": {"S&P 500 (US)": "^GSPC", ...},
    "Commodities": {"Gold": "GC=F", ...},
    "Crypto": {"Bitcoin": "BTC-USD"}
}
```
**Convention**: Category → Display Name → Yahoo Finance ticker. Add new markets here only; downstream functions iterate over this.

### Technical Indicator Functions (`my_functions.py`)
**Key Functions**:
- `momentum_signal(series)` - Returns emoji-based signal (🟢🟡🔴) with SMA20/50 logic
- `calculate_rsi(series, period=14)` - RSI with overbought/oversold thresholds (80/20)
- `market_regime(series)` - Bull/bear based on SMA50/200 crossover
- `calculate_metrics(series, period)` - Wraps above three + return calculation

**Pattern**: All take pandas Series, return either signal string or numeric metric. Handle `NaN` gracefully.

### Environment Variables (`.env` required)
```
OPENAI_API_KEY=sk-...        # ChatGPT access
FRED_API_KEY=abcd1234...     # Federal Reserve Economic Data
```
Loaded via `python-dotenv`. Check these before API calls in `generate_ai_commentary()`.

### Streamlit App Structure (`master.py`)
- **Single entry point**: `streamlit run master.py` from `/PROJECT/ECONOMY/`
- **Tab architecture**: Each tab isolates feature (Dashboard, Technical, AI Analytics, Charts, Bond Market)
- **Widget pattern**: `st.select_slider()` for period selection (1d, 1wk, 1mo, 3mo, 6mo, 1y, 2y, 3y)
- **Period mapping**: Used in multiple functions via `period_days` dict in `calculate_metrics()`

### FRED API Usage Pattern (`get_yield_data()`)
```python
series_ids = {"1M": "DGS1MO", "3M": "DGS3MO", ..., "30Y": "DGS30"}
for tenor, fredcode in series_ids.items():
    fred = Fred(api_key=os.getenv('FRED_API_KEY'))
    data[tenor] = fred.get_series(fredcode, observation_start, observation_end)
```
**Note**: Creates new Fred instance per iteration (inefficient—consider caching client in real production).

---

## Critical Integration Points

### 1. **Yahoo Finance Batch Download** → DataFrame Transform
- `download_all_markets(MARKETS)` returns MultiIndex DataFrame: `data['Close'][ticker]`
- Used by all analysis functions; cache prevents hammering yfinance
- Data cleanup: `ffill().bfill()` for missing values

### 2. **AI Commentary Pipeline**
```
Market Summary (text) → OpenAI Prompt Builder → gpt-4o-mini API → Token Usage Display
```
**Pattern**: Build descriptive text from DataFrame, wrap in system + user message roles, log token usage.

### 3. **Cross-Module Imports**
- `Tools/DownloadFredData.py` imports from parent: `sys.path.append(...)` then `from my_functions import *`
- **Convention**: Avoid circular imports; functions are exported for reuse via `import *`

---

## Developer Workflows

### Running the Dashboard
```powershell
cd D:\Study\GITMASTER\PROJECT\ECONOMY
streamlit run master.py
```
Opens http://localhost:8501 with live reload on file changes.

### Adding a New Market
1. Add entry to `MARKETS` dict in `master.py` (ticker format: `^GSPC` for indices, `CL=F` for futures)
2. Add optional plot line to `line_graph()` if visualizing in tab1
3. Test: select period, verify data loads and calculations complete

### Adding a New Technical Indicator
1. Implement function in `my_functions.py` (accept pandas Series, return signal/value)
2. Integrate into `calculate_metrics()` if combining with other metrics
3. Display in appropriate tab (tab2 for technical analysis)
4. Test with data from `load_all_data()`

### Debugging Data Issues
- Check `.env` variables exist: `print(os.getenv('OPENAI_API_KEY'))`
- Verify ticker symbols: `yf.Ticker("^GSPC").info` to validate
- Monitor FRED: Series IDs must match Federal Reserve registry
- View cache: `streamlit cache clear` if stale data suspected

### Batch Export FRED Data
```powershell
python Tools/DownloadFredData.py
```
Uses `get_yield_data()` to export US Treasury yields to DataFrame (currently prints to console).

---

## Project-Specific Dependencies & External Constraints

| Library | Purpose | API Key Required? |
|---------|---------|------------------|
| `yfinance` | Market data | No |
| `fredapi` | Economic indicators | Yes (`FRED_API_KEY`) |
| `openai` | AI commentary | Yes (`OPENAI_API_KEY`) |
| `streamlit` | Web UI framework | No |
| `pandas`, `numpy` | Data manipulation | No |
| `plotly`, `matplotlib` | Visualization | No |

**Rate Limits**:
- FRED: ~20 requests/second
- OpenAI: Varies by account (watch token usage in UI)
- yfinance: Unofficial, ~2000 calls/hour

**Known Issues**:
- `get_yield_data()` creates new Fred client per loop (inefficient)
- Tab5 (Bond Market) has duplicate `get_yield_data()` definition—refactor to use shared function
- No error handling for API failures (add try/except for robustness)

---

## Testing & Validation Hints

- **Quick test**: `python -c "from my_functions import calculate_rsi; import yfinance as yf; yf.download('^GSPC').Close.pipe(calculate_rsi)"`
- **Data integrity**: Verify no NaN returns in technical signals; check emoji output
- **Cache validation**: Modify a ticker, clear cache, rerun to ensure fresh data
- **API integration**: Test OpenAI key validity before running AI Analytics tab

---

## File Organization Rationale

- **`my_functions.py`**: Centralized analytics library for code reuse (Tools, pages, master all import it)
- **Numbered pages/**: Streamlit multi-page convention; execution order doesn't matter
- **Tools/**: One-off utilities (batch exports, manual calculations)
- **`master.py`**: App orchestration (never import from pages; pages import from master via functions)


