import pandas

import yfinance as yf

tickers =["AMZN","GOOG"]
ohlcv_data={}

def MACD(DF,slow=12,fast=26,sig=9):
    df=DF.copy()
    df["ma_sma_fast"]=df["Close"].rolling(12).mean() # for simple moving avg
    df["ma_ema_fast"] = df["Close"].ewm(span=fast, min_periods=fast).mean()
    df["ma_ema_slow"] = df["Close"].ewm(span=slow, min_periods=slow).mean()
    df["macd"] = df["ma_ema_fast"] - df["ma_ema_slow"]
    df["signal"] = df["macd"].ewm(span=sig,min_periods=sig).mean()
    return df.loc[:,["macd","signal"]]


for ticker in  tickers:
    temp = yf.download(ticker,period="1mo",interval="15m")
    temp.dropna(how="any",inplace=True)
    ohlcv_data[ticker] = temp
    ohlcv_data[ticker][["macd","signal"]]=MACD(ohlcv_data[ticker])

print(ohlcv_data["AMZN"][["macd","signal"]])

