from ibapi.client import EClient
from ibapi.common import BarData
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

#Paper TWS	7497
#Live TWS	7496
#Paper Gateway	4002l
#Live Gateway	4001

class TradingApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self,self)
        #self.historical_list = []
        self.historical_dict = {}
        self.reqId_to_symbol = {}

    def error(self, reqId, errorCode, errorString):
        print("Error occurred: {} -  {} - {}".format(reqId,errorCode,errorString))

    def contractDetails(self, reqId, contractDetails):
        print("reqID: {}, contract:{}".format(reqId, contractDetails))

    #{'AAPL': [{'AAPL', 6, 5}, {'AAPL', 4, 2}, {'AAPL', 7, 9}],
    # 'MSFT': [{'MSFT', 45, 65}, {'MSFT', 56, 25}, {'MSFT', 75, 96}] }

    def historicalData(self, reqId: int, bar: BarData):
        symbol = self.reqId_to_symbol[reqId]
        print(f"{symbol} -> {bar.date} Close: {bar.close}")

        if symbol not in self.historical_dict:
            self.historical_dict[symbol] = [{
                "reqId": reqId,
                "date": bar.date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume
            }]
        else:
            self.historical_dict[symbol].append({
                "reqId": reqId,
                "date": bar.date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume
            })


def stk_contract(symbol):
    contract_instance = Contract()
    contract_instance.symbol = symbol
    contract_instance.secType = "STK"
    contract_instance.currency = "USD"
    contract_instance.exchange = "NASDAQ"
    return contract_instance



def websocket_con():
        app.run()
        #print(app.isConnected())
        #event.wait()
        #if event.is_set():
        #    app.disconnect()

#event = threading.Event()
app = TradingApp()
#app.connect("127.0.0.1", 7497, clientId=0)
app.connect("127.0.0.1", 4002, clientId=0)

con_thread = threading.Thread(target=websocket_con)
con_thread.start()
time.sleep(2)


tickers = ["META","AAPL","INTC"]
for i,ticker in enumerate(tickers):
    reqId = i
    contract = stk_contract(ticker)
    app.reqId_to_symbol[reqId] = ticker
    app.reqContractDetails(reqId, contract)
    app.reqHistoricalData(reqId,contract=contract, durationStr="1 W", barSizeSetting="1 day", whatToShow="ADJUSTED_LAST", useRTH=True, endDateTime='', formatDate=1 , keepUpToDate=False, chartOptions=[])
    app.reqHistoricalData(reqId=reqId,
                          contract=contract,
                          endDateTime='',
                          durationStr='3600 S',
                          barSizeSetting='30 secs',
                          whatToShow='ADJUSTED_LAST',
                          useRTH=1,
                          formatDate=1,
                          keepUpToDate=0,
                          chartOptions=[])

#time.sleep(5)
#print(Historical_data)
#time.sleep(5)
#event.set()
print("All done")
time.sleep(5)

hist = app.historical_dict
print(hist)

app.disconnect()