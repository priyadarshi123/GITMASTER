import streamlit as st
import os
import pandas as pd
import yfinance as yf
import numpy as np
from openai import OpenAI
import matplotlib.pyplot as plt

@st.cache_data(ttl=3600)
def download_all_markets(markets_all):
    # if period == "1d":
    #    data = yf.download(ticker, period="2d", interval="1d", progress=False)
    # else:
    #    data = yf.download(ticker, period=period, progress=False)
    tickers = [t for cat in markets_all.values() for t in cat.values()]
    data = yf.download(tickers, period="3y", interval="1d", progress=False)
    data = data.ffill().bfill()

    return data


def momentum_signal(series):
    series = series.dropna()

    if len(series) < 50:
        return "⚪ No Data"

    ma20 = series.rolling(20).mean().iloc[-1]
    ma50 = series.rolling(50).mean().iloc[-1]
    price = series.iloc[-1]

    if price > ma20 > ma50:
        return "🟢 Bullish"

    elif price < ma20 < ma50:
        return "🔴 Bearish"

    else:
        return "🟡 Neutral"


def calculate_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.where(avg_loss != 0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    # Get the most recent RSI value
    latest_rsi = rsi.iloc[-1]

    # Determine signal with more nuance
    if pd.isna(latest_rsi):
        return f"Need at least {period + 1} data points"

    elif latest_rsi < 30:
        signal = 'Oversold'
        emoji = '🟢'
    elif latest_rsi > 70:
        signal = 'Overbought'
        emoji = '🔴'
    else:
        signal = 'Neutral'
        emoji = '🟡'

    # Add stronger signals for extreme levels
    if latest_rsi < 20:
        signal = 'Strongly Oversold'
        emoji = '💚'
    elif latest_rsi > 80:
        signal = 'Strongly Overbought'
        emoji = '💔'

    return f"{emoji} RSI: {latest_rsi:.2f} - {signal}"


def market_regime(series):
    ma50 = series.rolling(50).mean().iloc[-1]
    ma200 = series.rolling(200).mean().iloc[-1]

    if ma50 > ma200:
        return "🟢 Bull Market"
    else:
        return "🔴 Bear Market"


def calculate_metrics(series, period):
    series = series.dropna()

    period_days = {
        "1d": 2,
        "1wk": 5,
        "1mo": 22,
        "3mo": 66,
        "6mo": 126,
        "1y": 252,
        "2y": 504,
        "3y": 756
    }

    lookback = period_days.get(period, 22)

    if len(series) > lookback:
        start = series.iloc[-lookback]
    else:
        start = series.iloc[0]

    end = series.iloc[-1]

    ret = ((end / start) - 1) * 100
    mom_signal = momentum_signal(series)
    rsi_signal = calculate_rsi(series)
    market_regime_signal = market_regime(series)

    return ret, mom_signal, rsi_signal, market_regime_signal


def load_all_data(all_data, markets_all, period="1y"):
    rows = []

    for category, market in markets_all.items():
        for name, ticker in market.items():
            series = all_data["Close"][ticker].dropna()
            if len(series) == 0:
                continue
            ret, mom_signal, rsi_signal, market_regime_signal  = calculate_metrics(series, period)
            rows.append({
                "Category": category,
                "Market": name,
                "Return %": ret,
                "Momentum Signal": mom_signal,
                "RSI Signal": rsi_signal,
                "Market Regime Signal": market_regime_signal
            })
    return rows


def prepare_market_summary(mkt_summary):
    summary = ""

    for _, row in mkt_summary.iterrows():
        summary += f"""
                    Market: {row['Market']}
                    Return: {row['Return %']:.2f}%
                    Momentum: {row['Momentum Signal']}
                    RSI: {row['RSI Signal']}
                    Regime: {row['Market Regime Signal']}
                    ---------------------
                    """

    return summary


def build_ai_prompt(summary):
    prompt = f"""
    You are a global macro strategist.

    Below is a snapshot of global markets.

    {summary}

    Based on this data:

    1. Explain the current global market sentiment
    2. Identify risk-on or risk-off environment
    3. Mention important signals from equities, commodities and crypto
    4. Give a short 5 sentence macro commentary
    """

    return prompt


def generate_ai_commentary(prompt):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        st.error("API Key not found! Make sure OPENAI_API_KEY is set in your environment variables.")
    else:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional macro strategist."},
                {"role": "user", "content": prompt}
            ]
        )

        commentary = response.choices[0].message.content

        usage = response.usage

        return commentary, usage

def line_graph(hist_compare_local, period):
    st.subheader("Growth of $100 Investment")
    print("hist_compare_local:", hist_compare_local)

    period_days = {
        "1d": 1,
        "1wk": 5,
        "1mo": 22,
        "3mo": 66,
        "6mo": 126,
        "1y": 252,
        "2y": 504,
        "3y": 756
    }

    lookback = period_days.get(period, 22)

    if len(hist_compare_local) > lookback:
        hist_compare_local = hist_compare_local.iloc[-lookback:]

    hist_compare_local = hist_compare_local.div(hist_compare_local.iloc[0]) * 100


    hist_compare_local = hist_compare_local.div(hist_compare_local.iloc[0]) * 100
    fig, ax = plt.subplots(figsize=(10,5))

    ax.plot(hist_compare_local["^BSESN"], label="SENSEX India")
    ax.plot(hist_compare_local["^FTSE"], label="FTSE UK")
    ax.plot(hist_compare_local["^GSPC"], label="S&P500")
    ax.plot(hist_compare_local["^HSI"], label="Hang Seng HK")
    ax.plot(hist_compare_local["^IXIC"], label="NASDAQ")
    ax.plot(hist_compare_local["^N225"], label="Nikkei Japan")
    ax.plot(hist_compare_local["^STI"], label="STI Singapore")
    ax.plot(hist_compare_local["CL=F"], label="Oil")
    ax.plot(hist_compare_local["GC=F"], label="Gold Futures")
    ax.plot(hist_compare_local["BTC-USD"], label="Bitcoin")
    ax.grid(alpha=0.3)
    ax.legend()

    st.pyplot(fig)

