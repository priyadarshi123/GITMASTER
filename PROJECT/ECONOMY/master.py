import os

import streamlit as st
import yfinance as yf
from fredapi import Fred
import pandas as pd
from dotenv import load_dotenv
import os
import plotly.graph_objects as go

load_dotenv()




st.title("S&P 500 vs Chicago PMI")

# --- S&P 500 ---
@st.cache_data(ttl=3600)
def load_sp500():
    return yf.download("^GSPC",
                       start="2010-01-01",
                       end="2020-12-31")


sp500 = load_sp500()
if "Adj Close" in sp500.columns:
    sp500 = sp500["Adj Close"]
else:
    sp500 = sp500["Close"]
#sp500 = sp500.resample("M").last()  # Monthly to match PMI
sp500 = pd.DataFrame(sp500)
sp500.columns = ["S&P500"]

# --- Chicago PMI ---

@st.cache_data(ttl=1000)
def load_fred():
    fred_api_key = os.getenv('FRED_API_KEY')
    fred = Fred(api_key=fred_api_key)
    return fred.get_series("INDPRO")


pmi = load_fred()
pmi = pmi.loc["2010-01-01":"2020-12-31"]
pmi = pd.DataFrame(pmi, columns=["PMI"])

# --- Merge data ---
data = pd.concat([sp500, pmi], axis=1,join="inner")
print(data)
# --- Plot ---


fig = go.Figure()

fig.add_trace(go.Scatter(
    x=data.index,
    y=data["S&P500"],
    name="S&P 500",
    yaxis="y1"
))

fig.add_trace(go.Scatter(
    x=data.index,
    y=data["PMI"],
    name="PMI",
    yaxis="y2"
))

fig.update_layout(
    title="S&P 500 vs PMI",
    yaxis=dict(title="S&P 500"),
    yaxis2=dict(
        title="PMI",
        overlaying="y",
        side="right"
    )
)

st.plotly_chart(fig)


