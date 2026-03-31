import streamlit as st
from fredapi import Fred
import plotly.express as px
from dotenv import load_dotenv
import os
#from PROJECT.ECONOMY import my_functions

load_dotenv()
fred_api_key=os.getenv('FRED_API_KEY')

# 1. Verify the key actually exists

if not fred_api_key:
    st.error("API Key not found! Make sure FRED_API_KEY is set in your environment variables.")
else:
    fred = Fred(api_key=fred_api_key)
    st.title("🌍 Global PMI")

    # 2. Perform the search

    pmi = fred.get_series("IPMAN")  # ISM Manufacturing PMI

    fig = px.line(pmi, title="US Manufacturing PMI")

    st.plotly_chart(fig, use_container_width=True)
