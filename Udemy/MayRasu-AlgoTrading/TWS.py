from ibapi.client import EClient
from ibapi.common import BarData
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

#Paper TWS	7497
#Live TWS	7496
#Paper Gateway	4002
#Live Gateway	4001

class TradingApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self,self)

    def error(self, reqId, errorCode, errorString):
        print("Error occurred: {} -  {} - {}".format(reqId,errorCode,errorString))

    def contractDetails(self, reqId, contractDetails):
        print("reqID: {}, contract:{}".format(reqId, contractDetails))

    def historicalData(self, reqId: int, bar: BarData):
        print("reqID: {}, bar:{}".format(reqId, bar))

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

contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.currency = "USD"
contract.exchange = "NASDAQ"

ContractDetails = app.reqContractDetails(1, contract)

Historical_data = app.reqHistoricalData(12,contract=contract, durationStr="1 W", barSizeSetting="1 day", whatToShow="TRADES", useRTH=True, endDateTime='', formatDate=1 , keepUpToDate=True, chartOptions=[])
#time.sleep(5)
#print(Historical_data)
#time.sleep(5)
#event.set()
time.sleep(30)
app.disconnect()