import streamlit as st
from fredapi import Fred
import plotly.express as px
from dotenv import load_dotenv
import os

load_dotenv()
fred_api_key=os.getenv('FRED_API_KEY')

# 1. Verify the key actually exists

if not fred_api_key:
    st.error("API Key not found! Make sure FRED_API_KEY is set in your environment variables.")
else:
    fred = Fred(api_key=fred_api_key)

st.title("⚠️ Recession Risk")

spread = fred.get_series("T10Y2Y")  # 10Y-2Y yield spread

fig = px.line(spread, title="Yield Curve (10Y–2Y)")

st.plotly_chart(fig, use_container_width=True)

if spread.iloc[-1] < 0:
    st.error("Yield Curve Inverted — Recession Risk Elevated")
else:
    st.success("Yield Curve Normal")