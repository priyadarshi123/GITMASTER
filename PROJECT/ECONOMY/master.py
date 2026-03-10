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
from my_functions import *

load_dotenv()

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

period = st.select_slider(
    "Select Duration",
    options=["1d", "1wk", "1mo", "3mo", "6mo", "1y", "2y", "3y"],
    value="1mo"
)

all_data = download_all_markets(MARKETS)

tab1 , tab2, tab3, tab4 = st.tabs(["Global Dashboard", "Technical", "AI Analytics", "Charts"])

with tab1:
    st.title("Global Stock Market Performance")
    market_data = load_all_data(all_data,MARKETS, period)
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

    Tickers_analysis_data = load_all_data(all_data, MARKETS, period)
    Tech_analysis = pd.DataFrame(market_data)
    st.title("Global Stock Market Performance")

    st.subheader("Market Momentum Signals")
    print(Tech_analysis)
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
    tab4, tab5, tab6 = st.tabs(["Employment numbers", "Interest rate", "PMI"])

    with tab4:
        st.title("Employment numbers")

    with tab5:
        st.title("Interest rate")

    with tab6:
        st.title("PMI")