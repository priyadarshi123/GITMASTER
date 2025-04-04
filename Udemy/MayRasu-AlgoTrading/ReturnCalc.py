import numpy as np
import pandas as pd


def CAGR(DF):
    df = DF.copy()
    df["return"]=df["Close"].pct_change()
    df["cum_return"]=(1+df["return"]).cumprod()
    n=len(df)/252
    print("Number of days: {}".format(n))
    CAGR_calculated = (df["cum_return"].iloc[-1])**(1/n) - 1
    return CAGR_calculated


def volatility(DF):
    df = DF.copy()
    df['dailychange'] = DF['Close'].pct_change()
    vol = df['dailychange'].std() * np.sqrt(252)
    return vol

def Sharpe_ratio(DF,rf=0.03):
    df=DF.copy()
    return ((CAGR(df)-0.03)/volatility(df))


def Sortino_ratio(DF,rf=0.03):
    df=DF.copy()
    CAGR_calc = CAGR(df)
    df['return'] = df['Close'].pct_change()
    neg_return = np.where(df["return"]>0,0,df["return"])
    neg_vol= pd.Series(neg_return[neg_return!=0]).std() ** np.sqrt(252)
    print("neg_vol is: {}",format(neg_vol))
    return (CAGR_calc - rf)/neg_vol

