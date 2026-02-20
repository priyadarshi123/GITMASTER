import os

import streamlit as st
import yfinance as yf
from fredapi import Fred
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

fred_api_key=os.getenv('FRED_API_KEY')


st.title("S&P500 vs Chicago PMI")

# --- S&P500 ---
sp500 = yf.download("^GSPC",
                    start="2010-01-01",
                    end="2020-12-31")

# --- Chicago PMI ---
fred = Fred(api_key=fred_api_key)

pmi = fred.get_series("INDPRO")
pmi = pmi.loc["2010-01-01":"2020-12-31"]
pmi = pd.DataFrame(pmi, columns=["PMI"])

st.write(sp500.tail())
st.write(pmi.tail())