from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class TradingApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self,self)

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson):
        print("Error occurred: {} -  {} - {}".format(reqId,errorCode,errorString, advancedOrderRejectJson))

    def contractDetails(self, reqId, contractDetails):
        print("reqID: {}, contract:{}".format(reqId, contractDetails))

    def historicalData(self, reqId, bar):
        print("HistoricalData - ReqId - {} BarData- {}",format(reqId,bar))





def websocket_con():
        app.run()
        #event.wait()
        #if event.is_set():
        #    app.disconnect()

event = threading.Event()
app = TradingApp()
app.connect("127.0.0.1", 7497, clientId=0)

con_thread = threading.Thread(target=websocket_con)
con_thread.start()
time.sleep(1)

contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.currency = "USD"
contract.exchange = "SMART"

app.reqContractDetails(1, contract)
time.sleep(5)
#event.set()
app.disconnect()