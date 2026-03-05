import os
import streamlit as st
import yfinance as yf
import pandas as pd
from dotenv import load_dotenv



st.set_page_config(page_title="Macro Dashboard", layout="wide")

st.title("🌍 Global Macro Dashboard")
st.markdown("### Market Snapshot")

@st.cache_data(ttl=3600)
def load_data(ticker):
    data = yf.download(
        ticker,
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False
    )
    return data


def latest_close(df):
    if df is None or df.empty:
        return "No data"
    return round(df["Close"].iloc[-1], 2)


# --- S&P500 ---
sp500 = load_data("^GSPC") # S&P 500 - Large US companies (all sectors)
nasdaq = load_data("^IXIC") #NASDAQ Composite - Tech-heavy growth stocks
vix = load_data("^VIX")   #VIX Level - Below 15 - Very calm, 15–20 - Normal, 20–30 - Rising fear,

col1,col2,col3 = st.columns(3)

col1.metric("S&P 500", latest_close(sp500))
col2.metric("Nasdaq", latest_close(nasdaq))
col3.metric("VIX", latest_close(vix))

st.markdown("---")
#st.markdown("Use the sidebar to navigate dashboards.")

