import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from fredapi import Fred
import os
from my_functions import *
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "datasource" / "fred_yields.csv"
print(DATA_FILE)
data = pd.read_csv(DATA_FILE)
#Market tickers
MARKETS = {

    "Equities": {
        "S&P 500 (US)": "^GSPC",
        "NASDAQ (US)": "^IXIC",
        "Nikkei (Japan)": "^N225",
        "Hang Seng (HK)": "^HSI",
        "Sensex (India)": "^BSESN",
        "FTSE (UK)": "^FTSE",
        "STI Singapore": "^STI"
    },

    "Commodities": {
        "Gold": "GC=F",
        "Oil": "CL=F"
    },

    "Crypto": {
        "Bitcoin": "BTC-USD"
    }
}



#st.title("Global Stock Markets")



all_data = download_all_markets(MARKETS)

tab1 , tab2, tab3, tab4, tab5 = st.tabs(["Global Dashboard", "Technical", "AI Analytics", "Charts", "Bond Market"])

with tab1:

    spx=all_data["Close"]["^GSPC"]
    nasdaq=all_data["Close"]["^IXIC"]

    spx_last = spx.iloc[-1]
    spx_prev = spx.iloc[-2]
    nasdaq_last = nasdaq.iloc[-1]
    nasdaq_prev = nasdaq.iloc[-2]
    spx_change = ((spx_last / spx_prev) - 1) * 100
    nasdaq_change = ((nasdaq_last / nasdaq_prev) - 1) * 100

    col1, col2 = st.columns(2)
    #Show S&P500 latest close
    col1.metric(
        "S&P 500",
        f"{spx_last:,.0f}",
        f"{spx_change:.2f}%",
        delta_color="normal"
    )

    col2.metric(
        "NASDAQ",
        f"{nasdaq_last:,.0f}",
        f"{nasdaq_change:.2f}%",
        delta_color = "normal"
    )

    st.markdown("---")


    period = st.select_slider(
        "Select Duration",
        options=["1d", "1wk", "1mo", "3mo", "6mo", "1y", "2y", "3y"],
        value="1mo"
    )

    market_data = load_all_data(all_data, MARKETS, period)
    st.title("Global Stock Market Performance")
    hist_compare = pd.DataFrame(market_data)
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
    line_graph(all_data["Close"], period)


with tab2:
    period2="3y"
    Tickers_analysis_data = load_all_data(all_data, MARKETS, period2)
    Tech_analysis = pd.DataFrame(Tickers_analysis_data)
    st.title("Global Stock Market Performance")

    st.subheader("Market Momentum Signals")
    st.dataframe(Tech_analysis,hide_index=True)

with tab3:

    st.title("AI Market Commentary")

    df = pd.DataFrame(market_data)

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
    tab11, tab12, tab13 = st.tabs(["Employment numbers", "Interest rate", "PMI"])

    with tab11:
        st.title("Employment numbers")

    with tab12:
        st.title("Interest rate")

    with tab13:
        st.title("PMI")

with tab5:
    st.title("Bond market Stats")
    #Download data  until 2025 from file
    data_hist = pd.read_csv(DATA_FILE, index_col="Date",parse_dates=True)
    print("data_hist: ", data_hist)

    #Download data from 2026 using api call
    current_date = str(datetime.now().date())
    print(current_date)
    data_current = get_yield_data(observation_start='2026-01-01',observation_end = current_date)

    print("data_current: ", data_current)


    #Combine both data and datahist dataframe in to one dataframe

    data = pd.concat([data_hist, data_current])
    data = data.sort_index()
    data = data[~data.index.duplicated()]


    st.subheader("US Treasury Yields")
    fig, ax = plt.subplots(figsize=(10,5))
    for col in data.columns:
        ax.plot(data.index, data[col], label=col)
    ax.set_xlabel("Date")
    ax.set_ylabel("Yield (%)")
    ax.legend()
    ax.grid(alpha=0.3)
    st.pyplot(fig)
    latest_date = data.dropna(how='all').index[-1]

    plot_yield_curve(str(latest_date.date()), data)


