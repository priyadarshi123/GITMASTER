import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()




#Market tickers
MARKETS = {

    "Equities": {
        "S&P 500 (US)": "^GSPC",
        "NASDAQ (US)": "^IXIC",
        "Nikkei (Japan)": "^N225",
        "Hang Seng (HK)": "^HSI",
        "Sensex (India)": "^BSESN",
        "FTSE (UK)": "^FTSE"
    },

    "Commodities": {
        "Gold": "GC=F",
        "Oil": "CL=F"
    },

    "Crypto": {
        "Bitcoin": "BTC-USD"
    }
}

@st.cache_data(ttl=3600)
def download_all_markets():
    #if period == "1d":
    #    data = yf.download(ticker, period="2d", interval="1d", progress=False)
    #else:
    #    data = yf.download(ticker, period=period, progress=False)
    tickers = [t for cat in MARKETS.values() for t in cat.values()]
    data = yf.download(tickers, period="1y",interval="1d", progress=False)

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
        return  f"Need at least {period + 1} data points"

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

    if period == "1d":
        start = series.iloc[-2].item()
    elif period == "1mo":
        start = series.iloc[-22].item()
    elif period == "6mo":
        start = series.iloc[-126].item()
    elif period == "1y":
        start = series.iloc[0].item()

    end = series.iloc[-1]

    ret = ((end / start) - 1) * 100
    mom_signal = momentum_signal(series)
    rsi_signal = calculate_rsi(series)
    market_regime_signal = market_regime(series)

    return ret, mom_signal,rsi_signal,market_regime_signal

def load_all_data(all_data, period="1y"):

    rows = []

    for category, markets in MARKETS.items():

        for name, ticker in markets.items():

            series = all_data["Close"][ticker].dropna()

            if len(series) == 0:
                continue

            ret, mom_signal,rsi_signal,market_regime_signal = calculate_metrics(series, period)

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


#st.title("Global Stock Markets")

period = st.selectbox(
    "Select Duration",
    [ "1d","1mo", "1y",]
)

all_data = download_all_markets()

tab1 , tab2, tab3, tab4 = st.tabs(["Global Dashboard", "Technical", "AI Analytics", "Charts"])

with tab1:
    st.title("Global Stock Market Performance")
    Tickers_return_data = load_all_data(all_data,period)
    hist_compare = pd.DataFrame(Tickers_return_data)
    # sort markets
    hist_compare = hist_compare.sort_values("Return %")
    fig = px.bar(
        hist_compare,
        x="Market",
        y="Return %",
        color="Return %",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        text="Return %"
    )

    fig.update_traces(texttemplate='%{text:.2f}%')
    st.plotly_chart(fig, use_container_width=True)


with tab2:

    Tickers_analysis_data = load_all_data(all_data,period)
    Tech_analysis = pd.DataFrame(Tickers_analysis_data)
    st.title("Global Stock Market Performance")

    st.subheader("Market Momentum Signals")
    print(Tech_analysis)
    st.dataframe(Tech_analysis,hide_index=True)

with tab3:

    st.title("AI Market Commentary")

    df = pd.DataFrame(load_all_data(all_data, period))

    summary = prepare_market_summary(df)

    prompt = build_ai_prompt(summary)

    if st.button("Generate AI Commentary"):

        commentary, usage = generate_ai_commentary(prompt)

        st.write(commentary)

        st.divider()

        st.write("Token Usage")

        st.write("Prompt Tokens:", usage.prompt_tokens)
        st.write("Completion Tokens:", usage.completion_tokens)
        st.write("Total Tokens:", usage.total_tokens)


with tab4:
    st.title("Charts")
    tab4, tab5, tab6 = st.tabs(["Employment numbers", "Interest rate", "PMI"])

    with tab4:
        st.title("Employment numbers")

    with tab5:
        st.title("Interest rate")

    with tab6:
        st.title("PMI")