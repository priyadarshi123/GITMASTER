import pandas as pd
import yfinance as yf
import ibapi
import requests
from io import StringIO
pd.set_option('display.max_columns', None)

url= "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)
html = StringIO(response.text)
tables = pd.read_html(html)
dow_table = tables[2]
print(dow_table[['Symbol','Company']])
dow_list = dow_table['Symbol'].tolist()

print(dow_list)
data = []
for i in dow_list:
    TickerInfo = yf.Ticker(i).get_fast_info()
    print(TickerInfo)
    price =  TickerInfo['last_price']
    LastClose = TickerInfo['regular_market_previous_close']
    PercentChange = price/LastClose - 1
    #print(i)
    #print(PercentChange)
    #print((price/LastClose - 1)*100)
    #print("----------------------------")
    data.append({"Ticker": i,
                   "Price": price,
                   "LastClose": LastClose,
                   "PercentChange": PercentChange,})

print("Download Complete!!")
print(data)

df = pd.DataFrame(data)
#print(df)
df = df.sort_values(by=['PercentChange'], ascending=False)
#print(df)

Worst_return = df[-2:]['Ticker'].tolist()
print("Worst return Ticker list: ",Worst_return)

Best_return = df[0:2]['Ticker'].tolist()
print("Best return Ticker list: ", Best_return)


from ib_async import *
ib = IB()
ib.connect('127.0.0.1', 7497,10)
position = ib.positions()
print(position)
df=util.df(position)
print(df)
if df is not None:
    df['symbol'] = df['contract'].apply(lambda x: x.symbol)
    df['conId'] = df['contract'].apply(lambda x: x.conId)
else:
    df = pd.DataFrame(columns=['symbol', 'position'])
print(df[['symbol','conId','position','avgCost']])
ib.disconnect()


