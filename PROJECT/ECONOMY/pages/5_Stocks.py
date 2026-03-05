import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta

@st.cache_data(ttl=3600)
def load_data(market_ticker):
    data = yf.download(
        ticker,
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False
    )
    return data


st.title("Global Stock Markets")

tab1 , tab2, tab3 = st.tabs(["Global Dashboard", "AI Analytics", "Charts"])

with tab1:
    st.title("Global Stock Market Performance")

    period = st.selectbox(
        "Select Duration",
        [ "1d" ,"1mo", "1y",]
    )

    # Market tickers
    markets = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Nikkei 225": "^N225",
        "Hang Seng": "^HSI",
        "Sensex": "^BSESN",
        "FTSE 100": "^FTSE"
    }

    returns=[]

    for name,ticker in markets.items():
        data = yf.download(ticker, period=period)

        if len(data) > 0:
            start = float(data["Close"].iloc[0])
            end = float(data["Close"].iloc[-1])

            ret = (end - start) * 100 / start

            ret = (end-start)*100/start

            returns.append({"Market":name,
                            "Return %":ret
                            })

    df = pd.DataFrame(returns)
    print(df)
    # sort markets
    df = df.sort_values("Return %")

    fig = px.bar(
        df,
        x="Market",
        y="Return %",
        color="Return %",
        text="Return %",
    )

    fig.update_traces(texttemplate='%{text:.2f}%')

    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.title("AI Analytics")

with tab3:
    st.title("Charts")
    tab4, tab5, tab6 = st.tabs(["Employment numbers", "Interest rate", "PMI"])

    with tab4:
        st.title("Employment numbers")

    with tab5:
        st.title("Interest rate")

    with tab6:
        st.title("PMI")