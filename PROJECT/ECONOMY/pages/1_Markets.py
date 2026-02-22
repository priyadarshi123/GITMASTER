import streamlit as st
import yfinance as yf
import plotly.express as px

st.title("📈 Markets Dashboard")

@st.cache_data(ttl=3600)  # 3600 sec = 1 hour
def load_data(ticker):
    return yf.download(ticker, start='2010-01-01', interval="1d")

ticker = st.selectbox(
    "Select Asset",
    ["^GSPC", "^IXIC", "GC=F", "CL=F", "^TNX"]
)

data =load_data(ticker)
data.columns = data.columns.get_level_values(0)
fig = px.line(data, y="Close", title=f"{ticker} Price")

st.plotly_chart(fig, use_container_width=True)