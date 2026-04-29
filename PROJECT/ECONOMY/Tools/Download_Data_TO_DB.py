import pandas as pd
import yfinance as yf
from fredapi import Fred
from dotenv import load_dotenv
from sqlalchemy import create_engine
import os
from sqlalchemy import text
load_dotenv()
fred_api_key = os.getenv('FRED_API_KEY')
fred = Fred(api_key=fred_api_key)
db_url = os.getenv('DATABASE_URL')
engine = create_engine(db_url)

startdate = '2026-01-01'

Stock_Instruments= {'Gold': 'GC=F',
                    'SP500': '^GSPC',
                    'Silver': 'SI=F',
                    'BitCoin': 'BTC-USD'}

Fed_Instruments = {'FEDFUNDS': 'FEDFUNDS',
                   'UNRATE': 'UNRATE'}


def fetch_price(symbol, name):
    df = yf.download(symbol, start=startdate, interval="1d", auto_adjust=True, progress=False)
    # ✅ Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[['Close']].copy()
    df.reset_index(inplace=True)
    df.rename(columns={"Date": "date", "Close": "close"}, inplace=True)
    df['symbol'] = name
    return df

def fetch_fred(symbol, name):
    df = fred.get_series(symbol, observation_start=startdate)

    # ✅ Convert Series → DataFrame properly
    df = df.reset_index()   # no inplace

    df.columns = ['date', 'value']
    df['indicator'] = name

    return df

if __name__ == "__main__":
    price_data = []
    for symbol,code in Stock_Instruments.items():
        df = fetch_price(code,symbol)
        price_data.append(df)

    price_df = pd.concat(price_data)
    with engine.begin() as conn:
        price_df.to_sql("prices_temp", conn, if_exists="replace", index=False)

        conn.execute(text("""
                          INSERT INTO prices (date, symbol, close)
                          SELECT date, symbol, close
                          FROM prices_temp
                          ON CONFLICT (date, symbol)
                          DO UPDATE SET close = EXCLUDED.close;
                          """))

        conn.execute(text("DROP TABLE prices_temp;"))


    macro_data = []

    for symbol, code in Fed_Instruments.items():
        df = fetch_fred(code, symbol)
        macro_data.append(df)

    macro_df = pd.concat(macro_data)
    with engine.begin() as conn:
        macro_df.to_sql("macro_temp", conn, if_exists="replace", index=False)

        conn.execute(text("""
                          INSERT INTO macro (date, indicator, value)
                          SELECT date, indicator, value
                          FROM macro_temp
                          ON CONFLICT (date, indicator)
                          DO UPDATE SET value = EXCLUDED.value;
                          """))

        conn.execute(text("DROP TABLE macro_temp;"))







