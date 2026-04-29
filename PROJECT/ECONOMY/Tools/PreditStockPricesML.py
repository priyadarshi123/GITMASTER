import pandas as pd
import yfinance as yf


df = yf.download('TSLA', period='1d', start='2026-01-01', end='2026-04-27')


