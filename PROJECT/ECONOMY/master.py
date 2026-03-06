import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta


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


def calculate_return(data, period):

    if period == "1d":
        start = data["Close"].iloc[-2].item()

    elif period == "1mo":
        start = data["Close"].iloc[-22].item()

    elif period == "6mo":
        start = data["Close"].iloc[-126].item()

    elif period == "1y":
        start = data["Close"].iloc[0].item()

    end = data["Close"].iloc[-1].item()

    return ((end / start) - 1) * 100

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

def load_all_data(all_data, period="1y"):

    rows = []

    for category, markets in MARKETS.items():

        for name, ticker in markets.items():

            series = all_data["Close"][ticker].dropna()

            if len(series) == 0:
                continue

            signal = momentum_signal(series)

            if period == "1d":
                start = series.iloc[-2]

            elif period == "1mo":
                start = series.iloc[-22]

            elif period == "1y":
                start = series.iloc[0]

            end = series.iloc[-1]

            ret = ((end / start) - 1) * 100

            rows.append({
                "Category": category,
                "Market": name,
                "Return %": ret,
                "Momentum Signal": signal
            })

    return rows


#st.title("Global Stock Markets")

period = st.selectbox(
    "Select Duration",
    [ "1d" ,"1mo", "1y",]
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
    st.dataframe(Tech_analysis)

with tab3:
    st.title("AI Analytics")


with tab4:
    st.title("Charts")
    tab4, tab5, tab6 = st.tabs(["Employment numbers", "Interest rate", "PMI"])

    with tab4:
        st.title("Employment numbers")

    with tab5:
        st.title("Interest rate")

    with tab6:
        st.title("PMI")