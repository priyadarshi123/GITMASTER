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

st.title("🇺🇸 US Economy")

indicator_map = {
    "Unemployment Rate": "UNRATE",
    "CPI": "CPIAUCSL",
    "Core CPI": "CPILFESL",
    "Industrial Production": "INDPRO"
}

selected_label = st.selectbox(
    "Select Indicator",
    list(indicator_map.keys())
)

indicator = indicator_map[selected_label]

data = fred.get_series(indicator)

fig = px.line(
    x=data.index,
    y=data.values,
    title=selected_label
)

st.plotly_chart(fig, use_container_width=True)