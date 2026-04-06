import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from my_functions import *
from fredapi import Fred
from dotenv import load_dotenv
import os

st.set_page_config(layout="wide")

# -----------------------------
# ENV
# -----------------------------
load_dotenv()
fred_api_key = os.getenv('FRED_API_KEY')

if not fred_api_key:
    st.error("FRED API Key not found!")
    st.stop()

fred = Fred(api_key=fred_api_key)

# -----------------------------
# HEADER
# -----------------------------
st.title("🌍 Global Macro Dashboard")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()

# -----------------------------
# LOAD DATA
# -----------------------------
MARKETS = {
    "Equities": {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Nikkei": "^N225",
        "Hang Seng": "^HSI",
        "Sensex": "^BSESN",
        "FTSE": "^FTSE",
        "STI": "^STI"
    },
    "Commodities": {
        "Gold": "GC=F",
        "Oil": "CL=F"
    },
    "Crypto": {
        "Bitcoin": "BTC-USD"
    }
}

all_data = download_all_markets(MARKETS)
print(all_data.head(5))
# -----------------------------
# KPI ROW
# -----------------------------
st.subheader("📊 Market Snapshot")

def calc_metric(series):
    last = series.iloc[-1]
    prev = series.iloc[-2]
    change = ((last / prev) - 1) * 100
    return last, change

spx = all_data["Close"]["^GSPC"]
nasdaq = all_data["Close"]["^IXIC"]
gold = all_data["Close"]["GC=F"]
btc = all_data["Close"]["BTC-USD"]
sensex = all_data["Close"]["^BSESN"]

col1, col2, col3, col4, col5 = st.columns(5)


for col, (name, series) in zip([col1, col2, col3, col4, col5],[("S&P 500", spx), ("NASDAQ", nasdaq), ("Gold", gold), ("Bitcoin", btc), ("Sensex", sensex)]):
    last, change = calc_metric(series)
    col.metric(name, f"{last:,.0f}", f"{change:.2f}%")

# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    st.header("⚙️ Controls")
    period = st.selectbox("Select Period", ["1mo", "3mo", "6mo", "1y", "3y"], index=3)

# -----------------------------
# TABS
# -----------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Overview", "💼 Portfolio", "🌍 Macro", "🤖 AI Insights"]
)

# -----------------------------
# OVERVIEW TAB
# -----------------------------
with tab1:
    st.subheader("Market Performance")

    market_data = load_all_data(all_data, MARKETS, period)
    df = pd.DataFrame(market_data)

    fig = px.bar(
        df,
        x="Market",
        y="Return %",
        color="Return %",
        color_continuous_scale="RdYlGn"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Growth of $100 Investment")

    prices = all_data["Close"]
    prices = prices / prices.iloc[0] * 100

    fig2 = px.line(prices)
    st.plotly_chart(fig2, use_container_width=True)

# -----------------------------
# PORTFOLIO TAB
# -----------------------------
with tab2:
    st.subheader("Portfolio Analysis")

    tickers = st.text_input("Tickers (comma separated)", "AAPL,MSFT,GOOG")
    weights = st.text_input("Weights (comma separated)", "0.3,0.3,0.4")

    if st.button("Analyze Portfolio"):
        tickers_list = [t.strip() for t in tickers.split(",")]
        weights_list = np.array([float(w) for w in weights.split(",")])

        if len(tickers_list) != len(weights_list):
            st.error("Tickers and weights must match!")
            st.stop()

        data = download_all_markets({"P": {t: t for t in tickers_list}})

        returns = data["Close"].pct_change().dropna()

        port_ret = (returns.mean() * weights_list).sum() * 252
        port_vol = np.sqrt(np.dot(weights_list.T, np.dot(returns.cov() * 252, weights_list)))
        sharpe = port_ret / port_vol

        col1, col2, col3 = st.columns(3)
        col1.metric("Return", f"{port_ret:.2%}")
        col2.metric("Volatility", f"{port_vol:.2%}")
        col3.metric("Sharpe Ratio", f"{sharpe:.2f}")

# -----------------------------
# MACRO TAB
# -----------------------------
with tab3:
    st.subheader("🌍 Macro Dashboard")

    subtab1, subtab2, subtab3 = st.tabs(
        ["⚠️ Recession", "🇺🇸 Economy", "🌍 PMI"]
    )

    # ---------- RECESSION ----------
    with subtab1:
        st.subheader("Yield Curve (10Y–2Y Spread)")

        spread = fred.get_series("T10Y2Y")

        fig = px.line(spread, title="10Y - 2Y Spread")
        st.plotly_chart(fig, use_container_width=True)

        if spread.iloc[-1] < 0:
            st.error("🔴 Yield Curve Inverted → Recession Risk HIGH")
        else:
            st.success("🟢 Yield Curve Normal")

    # ---------- ECONOMY ----------
    with subtab2:
        indicator_map = {
            "Unemployment Rate": "UNRATE",
            "CPI": "CPIAUCSL",
            "Core CPI": "CPILFESL",
            "Industrial Production": "INDPRO"
        }

        selected = st.selectbox("Select Indicator", list(indicator_map.keys()))

        data = fred.get_series(indicator_map[selected])

        fig = px.line(
            x=data.index,
            y=data.values,
            title=selected
        )

        st.plotly_chart(fig, use_container_width=True)

    # ---------- PMI ----------
    with subtab3:
        st.subheader("US Manufacturing PMI")

        pmi = fred.get_series("IPMAN")

        fig = px.line(pmi, title="PMI")
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# AI TAB
# -----------------------------
with tab4:
    st.subheader("🤖 AI Market Commentary")

    df = pd.DataFrame(market_data)
    summary = prepare_market_summary(df)
    prompt = build_ai_prompt(summary)

    if st.button("Generate AI Commentary"):
        try:
            commentary, usage = generate_ai_commentary(prompt)
            st.write(commentary)
            st.caption(f"Tokens Used: {usage.total_tokens}")
        except Exception as e:
            st.error(str(e))