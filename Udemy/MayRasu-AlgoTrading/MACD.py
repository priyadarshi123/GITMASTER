import pandas

import yfinance as yf
from ReturnCalc import *

tickers =["AMZN"]
ohlcv_data={}

def Downloadfromyfinance(ticker,period="1mo",interval="1d"):
    temp = yf.download(ticker, period=period, interval=interval)
    temp.sort_index()
    temp.dropna(how="any", inplace=True)
    print(temp)
    return temp

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
    df = df.sort_index()
    df['MB'] = df['Close'].rolling(n).mean().squeeze()
    df['UB'] = df['MB'] + 2*df['Close'].rolling(n).std(ddof=0).squeeze()
    df['LB'] = df['MB'] - 2*df['Close'].rolling(n).std(ddof=0).squeeze()
    df['BB_WIDTH'] = df['UB'] - df['LB']
    return df[['MB','UB','LB','BB_WIDTH']]
'''
for ticker in tickers:
    ohlcv_data[ticker] = Downloadfromyfinance(ticker,"1mo","15m")
    ohlcv_data[ticker][["macd","macd_signal"]]=MACD(ohlcv_data[ticker])
    ohlcv_data[ticker]['ATR'] = ATR(ohlcv_data[ticker])
    ohlcv_data[ticker][['MB','UB','LB','BB_WIDTH']] = BollingerBand(ohlcv_data[ticker],20)
    print(ohlcv_data["AMZN"][["macd","macd_signal","ATR",'MB','UB','LB','BB_WIDTH']])
'''

for ticker in tickers:
    print("Calculating for:" + ticker)
    ohlcv_data[ticker] = Downloadfromyfinance(ticker,"1mo","1d")
    CAGR_calculated = CAGR(ohlcv_data[ticker])
    print("CAGR of {} is {}:".format(ticker,CAGR_calculated))
    volatility_calculated = volatility(ohlcv_data[ticker])
    Sharpe_calculated = Sharpe_ratio(ohlcv_data[ticker], 0.03)
    Sortino_calculated = Sortino_ratio(ohlcv_data[ticker],0.03)

    print("Volatility of {} is: {}".format(ticker,volatility_calculated))
    print('Sharpe ratio is {}'.format(Sharpe_calculated))
    print('Sortino ratio is {}'.format(Sortino_calculated))

print("Done...")




