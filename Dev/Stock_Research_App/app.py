import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StockLens India",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:        #0d0f14;
    --surface:   #141720;
    --border:    #1e2330;
    --accent:    #4ade80;
    --accent2:   #38bdf8;
    --red:       #f87171;
    --muted:     #4b5563;
    --text:      #e2e8f0;
    --subtext:   #94a3b8;
    --gold:      #fbbf24;
}

html, body, [class*="css"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
}

.stApp { background-color: var(--bg) !important; }

/* Hide streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.5rem 2rem 2rem !important; max-width: 1400px !important; }

/* ── Header ── */
.app-header {
    display: flex; align-items: center; gap: 1rem;
    margin-bottom: 2rem; padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
}
.app-logo {
    font-family: 'DM Serif Display', serif;
    font-size: 1.8rem; color: var(--accent);
    letter-spacing: -0.02em; line-height: 1;
}
.app-tagline { font-size: 0.75rem; color: var(--muted); font-weight: 300; }

/* ── Search ── */
.stTextInput input {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1rem !important;
}
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(74,222,128,0.15) !important;
}

/* ── Company name block ── */
.company-header {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
}
.company-name {
    font-family: 'DM Serif Display', serif;
    font-size: 2rem; font-weight: 400;
    color: var(--text); line-height: 1.2;
}
.company-meta { font-size: 0.8rem; color: var(--subtext); margin-top: 0.25rem; }
.price-big {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem; color: var(--text);
}
.price-change-pos { color: var(--accent); font-size: 1rem; font-weight: 500; }
.price-change-neg { color: var(--red); font-size: 1rem; font-weight: 500; }

/* ── KPI Cards ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem; margin-bottom: 1.5rem;
}
.kpi-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    transition: border-color 0.2s;
}
.kpi-card:hover { border-color: var(--accent); }
.kpi-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.3rem; }
.kpi-value { font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; color: var(--text); font-weight: 500; }
.kpi-sub { font-size: 0.7rem; color: var(--subtext); margin-top: 0.15rem; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.2rem !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom-color: var(--accent) !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 1.2rem 0 0 !important; }

/* ── Tables ── */
.stDataFrame { background: var(--surface) !important; border-radius: 10px !important; }
.stDataFrame [data-testid="stDataFrameResizable"] { border: 1px solid var(--border) !important; border-radius: 10px !important; }

/* ── Section headers ── */
.section-title {
    font-family: 'DM Serif Display', serif;
    font-size: 1.1rem; color: var(--subtext);
    margin: 1.5rem 0 0.75rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
}

/* ── Buttons ── */
.stButton button {
    background: var(--surface) !important;
    color: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    border-radius: 6px !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    padding: 0.35rem 0.9rem !important;
    transition: all 0.15s !important;
}
.stButton button:hover {
    background: rgba(74,222,128,0.1) !important;
}

/* ── Selectbox ── */
.stSelectbox [data-baseweb="select"] {
    background: var(--surface) !important;
    border-color: var(--border) !important;
}
.stSelectbox [data-baseweb="select"] * { color: var(--text) !important; }

/* ── Metric ── */
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem !important;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.75rem !important; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-family: 'JetBrains Mono', monospace !important; }
[data-testid="stMetricDelta"] svg { display: none; }

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1rem 0 !important; }

/* ── Plotly chart bg ── */
.js-plotly-plot { border-radius: 10px; }

/* ── Screener filters ── */
.filter-chip {
    display: inline-block;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 0.2rem 0.7rem;
    font-size: 0.75rem; color: var(--subtext);
    margin: 0.2rem;
    cursor: pointer;
}
.filter-chip.active { border-color: var(--accent); color: var(--accent); }

/* ── Tag ── */
.tag {
    display: inline-block;
    background: rgba(74,222,128,0.1);
    color: var(--accent);
    border-radius: 4px;
    padding: 0.1rem 0.5rem;
    font-size: 0.7rem; font-weight: 600;
    letter-spacing: 0.05em; margin-left: 0.5rem;
}
.tag-red { background: rgba(248,113,113,0.1); color: var(--red); }

/* Highlight row */
.pos { color: var(--accent) !important; }
.neg { color: var(--red) !important; }

/* ── Expander ── */
.streamlit-expanderHeader {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border) !important; }

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--accent) !important; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────────────────────

PLOT_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='DM Sans', color='#94a3b8', size=11),
    xaxis=dict(gridcolor='#1e2330', zerolinecolor='#1e2330', showgrid=True),
    yaxis=dict(gridcolor='#1e2330', zerolinecolor='#1e2330', showgrid=True),
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(bgcolor='rgba(0,0,0,0)', bordercolor='#1e2330'),
    hovermode='x unified',
)

GREEN = '#4ade80'
RED   = '#f87171'
BLUE  = '#38bdf8'
GOLD  = '#fbbf24'

def fmt_cr(val):
    """Format large numbers in Indian Crore/Lakh notation."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    try:
        val = float(val)
        if abs(val) >= 1e12:  return f"₹{val/1e12:.2f}L Cr"
        if abs(val) >= 1e9:   return f"₹{val/1e7:.0f} Cr"  # 1 Cr = 1e7
        if abs(val) >= 1e7:   return f"₹{val/1e7:.2f} Cr"
        if abs(val) >= 1e5:   return f"₹{val/1e5:.2f} L"
        return f"₹{val:,.0f}"
    except: return "—"

def fmt_num(val, decimals=2, suffix=""):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    try: return f"{float(val):,.{decimals}f}{suffix}"
    except: return "—"

def fmt_pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    try: return f"{float(val)*100:.2f}%"
    except: return "—"

def color_val(val, positive_good=True):
    try:
        v = float(val)
        if v > 0: return GREEN if positive_good else RED
        if v < 0: return RED if positive_good else GREEN
    except: pass
    return '#94a3b8'

NSE_POPULAR = {
    "Reliance Industries": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Infosys": "INFY.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "Wipro": "WIPRO.NS",
    "HUL": "HINDUNILVR.NS",
    "Axis Bank": "AXISBANK.NS",
    "Kotak Bank": "KOTAKBANK.NS",
    "SBI": "SBIN.NS",
    "L&T": "LT.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "M&M": "M&M.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "Asian Paints": "ASIANPAINT.NS",
    "Maruti Suzuki": "MARUTI.NS",
    "HCL Tech": "HCLTECH.NS",
    "ITC": "ITC.NS",
    "Titan": "TITAN.NS",
    "NTPC": "NTPC.NS",
    "Power Grid": "POWERGRID.NS",
    "Tech Mahindra": "TECHM.NS",
    "Nestle India": "NESTLEIND.NS",
}

@st.cache_data(ttl=300, show_spinner=False)
def load_ticker(symbol):
    t = yf.Ticker(symbol)
    info = t.info
    hist_1y  = t.history(period="1y")
    hist_5y  = t.history(period="5y")
    fin      = t.financials       # annual P&L
    bal      = t.balance_sheet    # annual BS
    cf       = t.cashflow         # annual CF
    qfin     = t.quarterly_financials
    qbal     = t.quarterly_balance_sheet
    return dict(info=info, hist_1y=hist_1y, hist_5y=hist_5y,
                fin=fin, bal=bal, cf=cf, qfin=qfin, qbal=qbal)

def resolve_symbol(raw):
    """Convert user input to Yahoo Finance symbol."""
    raw = raw.strip().upper()
    if raw.endswith(".NS") or raw.endswith(".BO"):
        return raw
    # Check popular map (case-insensitive key match)
    for name, sym in NSE_POPULAR.items():
        if raw == name.upper() or raw == sym.replace(".NS",""):
            return sym
    return raw + ".NS"

# ── SCREENER data (index constituents with ratios) ────────────────────────────
NIFTY50_TICKERS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
    "BHARTIARTL.NS","HINDUNILVR.NS","AXISBANK.NS","WIPRO.NS","KOTAKBANK.NS",
    "LT.NS","SBIN.NS","SUNPHARMA.NS","BAJFINANCE.NS","HCLTECH.NS",
    "ASIANPAINT.NS","MARUTI.NS","ITC.NS","TITAN.NS","NTPC.NS",
    "TECHM.NS","NESTLEIND.NS","POWERGRID.NS","M&M.NS","ULTRACEMCO.NS",
]

@st.cache_data(ttl=600, show_spinner=False)
def load_screener_data(tickers):
    rows = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            rows.append({
                "Symbol":     t.replace(".NS",""),
                "Company":    info.get("shortName",""),
                "Sector":     info.get("sector",""),
                "Price":      info.get("currentPrice") or info.get("regularMarketPrice"),
                "Mkt Cap(Cr)": round(info.get("marketCap",0)/1e7, 0),
                "PE":         round(info.get("trailingPE",0) or 0, 1),
                "PB":         round(info.get("priceToBook",0) or 0, 2),
                "ROE(%)":     round((info.get("returnOnEquity",0) or 0)*100, 1),
                "ROCE(%)":    round((info.get("returnOnAssets",0) or 0)*100, 1),
                "D/E":        round(info.get("debtToEquity",0) or 0, 2),
                "52W High":   info.get("fiftyTwoWeekHigh"),
                "52W Low":    info.get("fiftyTwoWeekLow"),
                "Div Yield(%)": round((info.get("dividendYield",0) or 0)*100, 2),
            })
        except:
            pass
    return pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div class="app-header">
  <div>
    <div class="app-logo">StockLens <span style="color:#38bdf8">India</span></div>
    <div class="app-tagline">NSE · BSE  · Fundamental Research Platform</div>
  </div>
</div>
""", unsafe_allow_html=True)

# Nav tabs
main_tab, screener_tab, compare_tab = st.tabs(["🔍  Stock Analysis", "📋  Screener", "⚖️  Compare"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — STOCK ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
with main_tab:

    col_search, col_quick = st.columns([3, 2])
    with col_search:
        query = st.text_input("", placeholder="Enter NSE symbol or company name  e.g. RELIANCE, INFY, TCS ...",
                              label_visibility="collapsed")
    with col_quick:
        quick = st.selectbox("", ["— Quick pick —"] + list(NSE_POPULAR.keys()),
                             label_visibility="collapsed")

    symbol = None
    if query:
        symbol = resolve_symbol(query)
    elif quick != "— Quick pick —":
        symbol = NSE_POPULAR[quick]

    if not symbol:
        # Landing state
        st.markdown('<div class="section-title">Popular Stocks</div>', unsafe_allow_html=True)
        cols = st.columns(5)
        popular_list = list(NSE_POPULAR.items())[:10]
        for i, (name, sym) in enumerate(popular_list):
            with cols[i % 5]:
                if st.button(name, key=f"pop_{i}"):
                    symbol = sym
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 Type a stock symbol above (e.g. RELIANCE, HDFCBANK) or pick from the dropdown to begin analysis.")
        st.stop()

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner(f"Loading {symbol} ..."):
        try:
            data = load_ticker(symbol)
        except Exception as e:
            st.error(f"Could not load {symbol}: {e}")
            st.stop()

    info    = data["info"]
    hist_1y = data["hist_1y"]
    hist_5y = data["hist_5y"]
    fin     = data["fin"]
    bal     = data["bal"]
    cf      = data["cf"]
    qfin    = data["qfin"]

    if not info or not info.get("shortName"):
        st.error(f"No data found for **{symbol}**. Check the symbol and try again.")
        st.stop()

    name     = info.get("longName") or info.get("shortName","")
    price    = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    prev     = info.get("previousClose") or price
    chg      = price - prev
    chg_pct  = (chg / prev * 100) if prev else 0
    sector   = info.get("sector","")
    industry = info.get("industry","")
    exchange = info.get("exchange","NSE")

    # ── Company header ────────────────────────────────────────────────────────
    chg_cls = "price-change-pos" if chg >= 0 else "price-change-neg"
    chg_sym = "▲" if chg >= 0 else "▼"
    st.markdown(f"""
    <div class="company-header">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:1rem;">
        <div>
          <div class="company-name">{name}</div>
          <div class="company-meta">{symbol} &nbsp;·&nbsp; {sector} &nbsp;·&nbsp; {industry}</div>
        </div>
        <div style="text-align:right;">
          <div class="price-big">₹{price:,.2f}</div>
          <div class="{chg_cls}">{chg_sym} ₹{abs(chg):.2f} ({abs(chg_pct):.2f}%)</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI bar ───────────────────────────────────────────────────────────────
    mktcap   = info.get("marketCap")
    pe       = info.get("trailingPE")
    pb       = info.get("priceToBook")
    roe      = info.get("returnOnEquity")
    eps      = info.get("trailingEps")
    div_yld  = info.get("dividendYield")
    week52h  = info.get("fiftyTwoWeekHigh")
    week52l  = info.get("fiftyTwoWeekLow")
    de       = info.get("debtToEquity")
    rev      = info.get("totalRevenue")

    kpis = [
        ("Market Cap",    fmt_cr(mktcap),          ""),
        ("P/E Ratio",     fmt_num(pe),               "Trailing"),
        ("P/B Ratio",     fmt_num(pb),               "Price/Book"),
        ("ROE",           fmt_pct(roe),              "Return on Equity"),
        ("EPS (TTM)",     f"₹{fmt_num(eps)}",        "Earnings/Share"),
        ("52W High",      f"₹{fmt_num(week52h)}",    ""),
        ("52W Low",       f"₹{fmt_num(week52l)}",    ""),
        ("Div Yield",     fmt_pct(div_yld),          "Annual"),
        ("Debt/Equity",   fmt_num(de),               ""),
        ("Revenue",       fmt_cr(rev),               "TTM"),
    ]
    kpi_html = '<div class="kpi-grid">'
    for label, val, sub in kpis:
        kpi_html += f"""
        <div class="kpi-card">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{val}</div>
          {"" if not sub else f'<div class="kpi-sub">{sub}</div>'}
        </div>"""
    kpi_html += "</div>"
    st.markdown(kpi_html, unsafe_allow_html=True)

    # ── Analysis sub-tabs ─────────────────────────────────────────────────────
    t1, t2, t3, t4, t5 = st.tabs([
        "📈 Price Chart",
        "📊 Financials",
        "⚖️ Balance Sheet",
        "💰 Cash Flow",
        "ℹ️ About",
    ])

    # ── CHART ─────────────────────────────────────────────────────────────────
    with t1:
        period_col, _ = st.columns([2, 4])
        with period_col:
            period = st.selectbox("Period", ["1 Month","3 Months","6 Months","1 Year","3 Years","5 Years"],
                                  index=3, label_visibility="collapsed")

        period_map = {
            "1 Month": (hist_1y, 21),
            "3 Months": (hist_1y, 63),
            "6 Months": (hist_1y, 126),
            "1 Year": (hist_1y, None),
            "3 Years": (hist_5y, 756),
            "5 Years": (hist_5y, None),
        }
        df_hist, n_rows = period_map[period]
        df_plot = df_hist.iloc[-n_rows:] if n_rows else df_hist

        if df_plot.empty:
            st.warning("No price history available.")
        else:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                row_heights=[0.75, 0.25], vertical_spacing=0.04)

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df_plot.index,
                open=df_plot["Open"], high=df_plot["High"],
                low=df_plot["Low"],  close=df_plot["Close"],
                increasing_line_color=GREEN, decreasing_line_color=RED,
                increasing_fillcolor=GREEN, decreasing_fillcolor=RED,
                name="Price"
            ), row=1, col=1)

            # 20 & 50 MA
            df_plot = df_plot.copy()
            df_plot["MA20"] = df_plot["Close"].rolling(20).mean()
            df_plot["MA50"] = df_plot["Close"].rolling(50).mean()
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["MA20"],
                line=dict(color=GOLD, width=1.2, dash="dot"), name="MA 20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["MA50"],
                line=dict(color=BLUE, width=1.2, dash="dot"), name="MA 50"), row=1, col=1)

            # Volume
            colors_vol = [GREEN if c >= o else RED
                          for c, o in zip(df_plot["Close"], df_plot["Open"])]
            fig.add_trace(go.Bar(x=df_plot.index, y=df_plot["Volume"],
                marker_color=colors_vol, opacity=0.6, name="Volume"), row=2, col=1)

            fig.update_layout(**PLOT_LAYOUT, height=520, showlegend=True,
                              xaxis_rangeslider_visible=False)
            fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
            fig.update_yaxes(title_text="Volume", row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)

    # ── FINANCIALS ────────────────────────────────────────────────────────────
    with t2:
        if fin is not None and not fin.empty:
            # Annual P&L
            st.markdown('<div class="section-title">Annual P&L Statement</div>', unsafe_allow_html=True)
            fin_t = fin.T.copy()
            fin_t.index = [str(d)[:10] for d in fin_t.index]
            fin_t = fin_t / 1e7  # convert to Crores
            fin_t = fin_t.round(2)
            st.dataframe(fin_t.style.format("₹{:,.2f} Cr", na_rep="—"), use_container_width=True)

            # Revenue & PAT chart
            key_rows = {}
            for row_name in ["Total Revenue", "Net Income", "Operating Income", "Gross Profit"]:
                if row_name in fin.index:
                    key_rows[row_name] = fin.loc[row_name] / 1e7

            if key_rows:
                st.markdown('<div class="section-title">Revenue & Profit Trend (₹ Cr)</div>', unsafe_allow_html=True)
                fig2 = go.Figure()
                colors_chart = [GREEN, BLUE, GOLD, RED]
                for i, (k, v) in enumerate(key_rows.items()):
                    dates = [str(d)[:7] for d in v.index]
                    fig2.add_trace(go.Bar(x=dates[::-1], y=v.values[::-1],
                        name=k, marker_color=colors_chart[i % len(colors_chart)], opacity=0.85))
                fig2.update_layout(**PLOT_LAYOUT, height=380, barmode="group")
                st.plotly_chart(fig2, use_container_width=True)

            # Quarterly revenue
            if qfin is not None and not qfin.empty and "Total Revenue" in qfin.index:
                st.markdown('<div class="section-title">Quarterly Revenue (₹ Cr)</div>', unsafe_allow_html=True)
                qrev = qfin.loc["Total Revenue"] / 1e7
                dates_q = [str(d)[:10] for d in qrev.index]
                fig3 = go.Figure(go.Bar(
                    x=dates_q[::-1], y=qrev.values[::-1],
                    marker_color=BLUE, opacity=0.85
                ))
                if "Net Income" in qfin.index:
                    qpat = qfin.loc["Net Income"] / 1e7
                    fig3.add_trace(go.Bar(x=dates_q[::-1], y=qpat.values[::-1],
                        name="Net Income", marker_color=GREEN, opacity=0.85))
                fig3.update_layout(**PLOT_LAYOUT, height=320, barmode="group",
                                   title="Quarterly Revenue vs Net Income")
                st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Financial data not available for this ticker.")

    # ── BALANCE SHEET ─────────────────────────────────────────────────────────
    with t3:
        if bal is not None and not bal.empty:
            st.markdown('<div class="section-title">Annual Balance Sheet (₹ Cr)</div>', unsafe_allow_html=True)
            bal_t = bal.T.copy()
            bal_t.index = [str(d)[:10] for d in bal_t.index]
            bal_t = bal_t / 1e7
            bal_t = bal_t.round(2)
            st.dataframe(bal_t.style.format("₹{:,.2f}", na_rep="—"), use_container_width=True)

            # Assets vs Liabilities
            asset_cols = [c for c in bal.index if "Asset" in c or "Cash" in c]
            liab_cols  = [c for c in bal.index if "Liabilit" in c or "Debt" in c]
            if asset_cols and liab_cols:
                st.markdown('<div class="section-title">Assets vs Liabilities (₹ Cr)</div>', unsafe_allow_html=True)
                dates_b = [str(d)[:10] for d in bal.columns]
                total_assets = bal.loc[asset_cols].sum() / 1e7
                total_liabs  = bal.loc[liab_cols].sum() / 1e7
                fig4 = go.Figure()
                fig4.add_trace(go.Bar(x=dates_b[::-1], y=total_assets.values[::-1],
                    name="Total Assets", marker_color=GREEN, opacity=0.85))
                fig4.add_trace(go.Bar(x=dates_b[::-1], y=total_liabs.values[::-1],
                    name="Total Liabilities", marker_color=RED, opacity=0.85))
                fig4.update_layout(**PLOT_LAYOUT, height=340, barmode="group")
                st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("Balance sheet data not available for this ticker.")

    # ── CASH FLOW ──────────────────────────────────────────────────────────────
    with t4:
        if cf is not None and not cf.empty:
            st.markdown('<div class="section-title">Annual Cash Flow Statement (₹ Cr)</div>', unsafe_allow_html=True)
            cf_t = cf.T.copy()
            cf_t.index = [str(d)[:10] for d in cf_t.index]
            cf_t = cf_t / 1e7
            cf_t = cf_t.round(2)
            st.dataframe(cf_t.style.format("₹{:,.2f}", na_rep="—"), use_container_width=True)

            # FCF chart
            ocf_key = next((k for k in cf.index if "Operating" in k and "Cash" in k), None)
            capex_key = next((k for k in cf.index if "Capital" in k), None)
            if ocf_key and capex_key:
                dates_cf = [str(d)[:10] for d in cf.columns]
                ocf   = cf.loc[ocf_key] / 1e7
                capex = cf.loc[capex_key] / 1e7
                fcf   = ocf + capex  # capex is usually negative

                fig5 = go.Figure()
                fig5.add_trace(go.Bar(x=dates_cf[::-1], y=ocf.values[::-1],
                    name="Operating CF", marker_color=BLUE, opacity=0.85))
                fig5.add_trace(go.Bar(x=dates_cf[::-1], y=capex.values[::-1],
                    name="CapEx", marker_color=GOLD, opacity=0.85))
                fig5.add_trace(go.Scatter(x=dates_cf[::-1], y=fcf.values[::-1],
                    name="Free Cash Flow", line=dict(color=GREEN, width=2),
                    mode="lines+markers"))
                fig5.update_layout(**PLOT_LAYOUT, height=360,
                                   barmode="group", title="Cash Flow Analysis (₹ Cr)")
                st.plotly_chart(fig5, use_container_width=True)
        else:
            st.info("Cash flow data not available for this ticker.")

    # ── ABOUT ─────────────────────────────────────────────────────────────────
    with t5:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="section-title">Company Details</div>', unsafe_allow_html=True)
            details = {
                "Full Name":     info.get("longName","—"),
                "Sector":        info.get("sector","—"),
                "Industry":      info.get("industry","—"),
                "Country":       info.get("country","—"),
                "Employees":     f"{info.get('fullTimeEmployees',0):,}" if info.get('fullTimeEmployees') else "—",
                "Website":       info.get("website","—"),
                "Exchange":      info.get("exchange","—"),
                "Currency":      info.get("currency","—"),
            }
            for k, v in details.items():
                st.markdown(f"**{k}:** {v}")
        with c2:
            st.markdown('<div class="section-title">Key Ratios</div>', unsafe_allow_html=True)
            ratios = {
                "Market Cap":         fmt_cr(info.get("marketCap")),
                "Enterprise Value":   fmt_cr(info.get("enterpriseValue")),
                "P/E (Trailing)":     fmt_num(info.get("trailingPE")),
                "P/E (Forward)":      fmt_num(info.get("forwardPE")),
                "PEG Ratio":          fmt_num(info.get("pegRatio")),
                "Price/Book":         fmt_num(info.get("priceToBook")),
                "Price/Sales":        fmt_num(info.get("priceToSalesTrailing12Months")),
                "EV/EBITDA":          fmt_num(info.get("enterpriseToEbitda")),
                "ROE":                fmt_pct(info.get("returnOnEquity")),
                "ROA":                fmt_pct(info.get("returnOnAssets")),
                "Profit Margin":      fmt_pct(info.get("profitMargins")),
                "Operating Margin":   fmt_pct(info.get("operatingMargins")),
                "Gross Margin":       fmt_pct(info.get("grossMargins")),
                "Dividend Yield":     fmt_pct(info.get("dividendYield")),
                "Payout Ratio":       fmt_pct(info.get("payoutRatio")),
                "Beta":               fmt_num(info.get("beta")),
                "52W High":           f"₹{fmt_num(info.get('fiftyTwoWeekHigh'))}",
                "52W Low":            f"₹{fmt_num(info.get('fiftyTwoWeekLow'))}",
                "Avg Volume (3M)":    f"{info.get('averageVolume',0):,}",
                "Debt/Equity":        fmt_num(info.get("debtToEquity")),
                "Current Ratio":      fmt_num(info.get("currentRatio")),
                "Quick Ratio":        fmt_num(info.get("quickRatio")),
            }
            for k, v in ratios.items():
                st.markdown(f"**{k}:** {v}")

        desc = info.get("longBusinessSummary","")
        if desc:
            st.markdown('<div class="section-title">Business Description</div>', unsafe_allow_html=True)
            with st.expander("Read more"):
                st.write(desc)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SCREENER
# ═══════════════════════════════════════════════════════════════════════════════
with screener_tab:
    st.markdown('<div class="section-title">Nifty 50 Screener</div>', unsafe_allow_html=True)
    st.caption("Filter and rank Nifty 50 stocks by fundamental ratios. Data refreshes every 10 minutes.")

    col_load, _ = st.columns([2, 6])
    with col_load:
        load_scr = st.button("🔄 Load Screener Data")

    if load_scr or "screener_df" in st.session_state:
        if load_scr or "screener_df" not in st.session_state:
            with st.spinner("Fetching Nifty 50 data (this takes ~30s)..."):
                df_scr = load_screener_data(tuple(NIFTY50_TICKERS))
                st.session_state["screener_df"] = df_scr
        df_scr = st.session_state["screener_df"]

        if df_scr.empty:
            st.warning("Could not load screener data.")
        else:
            # Filters
            st.markdown("**Filters**")
            f1, f2, f3, f4, f5 = st.columns(5)
            with f1:
                max_pe = st.number_input("Max P/E", min_value=0.0, value=100.0, step=5.0)
            with f2:
                min_roe = st.number_input("Min ROE (%)", min_value=0.0, value=0.0, step=1.0)
            with f3:
                max_de = st.number_input("Max D/E", min_value=0.0, value=10.0, step=0.5)
            with f4:
                min_mktcap = st.number_input("Min Mkt Cap (Cr)", min_value=0.0, value=0.0, step=10000.0)
            with f5:
                sectors = ["All"] + sorted(df_scr["Sector"].dropna().unique().tolist())
                sel_sector = st.selectbox("Sector", sectors)

            # Apply filters
            mask = (
                (df_scr["PE"].fillna(999) <= max_pe) &
                (df_scr["ROE(%)"].fillna(0) >= min_roe) &
                (df_scr["D/E"].fillna(0) <= max_de) &
                (df_scr["Mkt Cap(Cr)"].fillna(0) >= min_mktcap)
            )
            if sel_sector != "All":
                mask = mask & (df_scr["Sector"] == sel_sector)

            df_filtered = df_scr[mask].copy()
            st.caption(f"Showing {len(df_filtered)} of {len(df_scr)} stocks")

            # Colour-code numeric cols
            def style_df(df):
                def color_col(s, positive_good=True):
                    def c(v):
                        if pd.isna(v): return ""
                        if positive_good:
                            if v > df[s.name].median(): return "color: #4ade80"
                            else: return "color: #f87171"
                        else:
                            if v < df[s.name].median(): return "color: #4ade80"
                            else: return "color: #f87171"
                    return s.map(c)
                return df.style\
                    .apply(color_col, subset=["ROE(%)"], positive_good=True)\
                    .apply(color_col, subset=["D/E"], positive_good=False)\
                    .apply(color_col, subset=["PE"], positive_good=False)\
                    .format({
                        "Price": "₹{:,.1f}", "Mkt Cap(Cr)": "{:,.0f}",
                        "PE": "{:.1f}", "PB": "{:.2f}",
                        "ROE(%)": "{:.1f}%", "ROCE(%)": "{:.1f}%",
                        "D/E": "{:.2f}", "Div Yield(%)": "{:.2f}%",
                        "52W High": "₹{:.1f}", "52W Low": "₹{:.1f}",
                    }, na_rep="—")

            st.dataframe(style_df(df_filtered), use_container_width=True, height=500)

            # Chart: ROE vs PE bubble
            st.markdown('<div class="section-title">ROE vs P/E (bubble = Market Cap)</div>', unsafe_allow_html=True)
            df_bubble = df_filtered.dropna(subset=["ROE(%)","PE","Mkt Cap(Cr)"])
            if not df_bubble.empty:
                fig_b = px.scatter(df_bubble, x="PE", y="ROE(%)",
                    size="Mkt Cap(Cr)", color="Sector", hover_name="Company",
                    size_max=50,
                    color_discrete_sequence=px.colors.qualitative.Vivid)
                fig_b.update_layout(**PLOT_LAYOUT, height=420)
                st.plotly_chart(fig_b, use_container_width=True)
    else:
        st.info("Click **Load Screener Data** to fetch live Nifty 50 fundamentals.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — COMPARE
# ═══════════════════════════════════════════════════════════════════════════════
with compare_tab:
    st.markdown('<div class="section-title">Compare Up to 4 Stocks</div>', unsafe_allow_html=True)

    sym_cols = st.columns(4)
    symbols_cmp = []
    for i, col in enumerate(sym_cols):
        with col:
            s = st.text_input(f"Stock {i+1}", placeholder=f"e.g. {'TCS' if i==0 else 'INFY' if i==1 else ''}",
                              key=f"cmp_{i}", label_visibility="collapsed")
            if s:
                symbols_cmp.append(resolve_symbol(s))

    if len(symbols_cmp) >= 2:
        with st.spinner("Loading comparison data..."):
            cmp_rows = []
            price_hist = {}
            for sym in symbols_cmp:
                try:
                    d = load_ticker(sym)
                    inf = d["info"]
                    label = inf.get("shortName", sym)
                    price_hist[label] = d["hist_1y"]["Close"]
                    cmp_rows.append({
                        "Company":         label,
                        "Symbol":          sym,
                        "Price (₹)":       inf.get("currentPrice") or inf.get("regularMarketPrice"),
                        "Mkt Cap":         fmt_cr(inf.get("marketCap")),
                        "P/E":             fmt_num(inf.get("trailingPE")),
                        "P/B":             fmt_num(inf.get("priceToBook")),
                        "ROE":             fmt_pct(inf.get("returnOnEquity")),
                        "ROA":             fmt_pct(inf.get("returnOnAssets")),
                        "Profit Margin":   fmt_pct(inf.get("profitMargins")),
                        "Revenue":         fmt_cr(inf.get("totalRevenue")),
                        "D/E":             fmt_num(inf.get("debtToEquity")),
                        "Div Yield":       fmt_pct(inf.get("dividendYield")),
                        "Beta":            fmt_num(inf.get("beta")),
                        "52W High (₹)":    fmt_num(inf.get("fiftyTwoWeekHigh")),
                        "52W Low (₹)":     fmt_num(inf.get("fiftyTwoWeekLow")),
                    })
                except Exception as e:
                    st.warning(f"Could not load {sym}: {e}")

        if cmp_rows:
            df_cmp = pd.DataFrame(cmp_rows).set_index("Company")
            st.markdown('<div class="section-title">Fundamentals Comparison</div>', unsafe_allow_html=True)
            st.dataframe(df_cmp.T, use_container_width=True)

            # Normalised price chart
            if price_hist:
                st.markdown('<div class="section-title">Normalised Price Performance (1Y, base=100)</div>', unsafe_allow_html=True)
                fig_cmp = go.Figure()
                palette = [GREEN, BLUE, GOLD, RED]
                for i, (label, series) in enumerate(price_hist.items()):
                    norm = series / series.iloc[0] * 100
                    fig_cmp.add_trace(go.Scatter(x=norm.index, y=norm.values,
                        name=label, line=dict(color=palette[i % 4], width=2)))
                fig_cmp.add_hline(y=100, line_dash="dot", line_color="#4b5563")
                fig_cmp.update_layout(**PLOT_LAYOUT, height=400)
                st.plotly_chart(fig_cmp, use_container_width=True)
    else:
        st.info("Enter at least 2 stock symbols above to compare them side by side.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:3rem; padding-top:1rem; border-top:1px solid #1e2330;
     text-align:center; font-size:0.72rem; color:#4b5563;">
  StockLens India &nbsp;·&nbsp; Data via Yahoo Finance &nbsp;·&nbsp;
  For informational purposes only. Not investment advice.
</div>
""", unsafe_allow_html=True)
