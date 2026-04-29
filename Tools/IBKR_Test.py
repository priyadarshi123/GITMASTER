from ib_insync import *

ib = IB()

# Connect to TWS (paper trading)
ib.connect('127.0.0.1', 4002, clientId=1)

print("Connected:", ib.isConnected())

#contract = Stock('AAPL', 'SMART', 'USD')
contract = Future('MCL', '202606', 'NYMEX')
#contract = ContFuture('MCL', 'NYMEX')

ib.qualifyContracts(contract)
ib.reqMarketDataType(3)
ticker = ib.reqMktData(contract)
ib.sleep(2)
print(ticker)
print(f"Price for {contract.symbol}:", ticker.last)

depth = ib.reqMktDepth(contract, numRows=10)
print(depth)



# Create order
#order = MarketOrder('BUY', 1)   # Buy 1 share

#trade = ib.placeOrder(contract, order)
#print(trade)
#print(trade.orderStatus.status)

ib.disconnect()