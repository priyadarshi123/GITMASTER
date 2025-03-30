import pandas

import yfinance as yf

tickers =["AMZN"]
ohlcv_data={}

def MACD(DF,fast=12,slow=26,sig=9):
    df=DF.copy()
    df["ma_sma_fast"]=df["Close"].rolling(12).mean() # for simple moving avg
    df["ma_ema_fast"] = df["Close"].ewm(span=fast, min_periods=fast).mean()
    df["ma_ema_slow"] = df["Close"].ewm(span=slow, min_periods=slow).mean()
    df["macd"] = df["ma_ema_fast"] - df["ma_ema_slow"]
    df["signal"] = df["macd"].ewm(span=sig,min_periods=sig).mean()
    return df.loc[:,["macd","signal"]]


def ATR(DF,n=14):
    df = DF.copy()
    df['H-L'] = df['High'] - df['Low']
    df['H-C'] = df['High'] - df['Close'].shift(1)
    df['L-C'] = df['Low'] - df['Close'].shift(1)
    df['maxDiff']=df[['H-L','H-C','L-C']].max(axis=1,skipna=False)
    df['ATR']=df['maxDiff'].ewm(com=n,min_periods=n).mean()
    return df['ATR']


def BollingerBand(DF,n=14):
    df = DF.copy()



for ticker in  tickers:
    temp = yf.download(ticker,period="1mo",interval="15m")
    temp.dropna(how="any",inplace=True)
    ohlcv_data[ticker] = temp
    ohlcv_data[ticker][["macd","macd_signal"]]=MACD(ohlcv_data[ticker])
    ohlcv_data[ticker]['ATR'] = ATR(ohlcv_data[ticker])


print(ohlcv_data["AMZN"][["macd","macd_signal","ATR"]])


print("Done...")

