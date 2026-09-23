'''You receive a stream of order book updates:
("BID", 100.50, 200)  → price, qty
("ASK", 100.55, 150)
("BID", 100.50, 0)    → qty=0 means remove

Implement a class OrderBook with:
- update(side, price, qty)
- best_bid() → highest bid price
- best_ask() → lowest ask price
- spread() → best_ask - best_bid'''


class OrderBook():
    def __init__(self):
        self.bids = {}
        self.asks = {}


    def update(self, side, price, qty):

        if qty != 0:
            if side == "BID":
                self.bids[price] = qty
            else:
                self.asks[price] = qty
        else:
            if side == "BID":
                self.bids.pop(price,None)
            else:
                self.asks.pop(price, None)



    def best_bid(self):
        if not self.bids:
            return None
        return max(self.bids.keys())


    def best_ask(self):
        if not self.asks:
            return None
        return min(self.asks.keys())


    def spread(self):
        if not self.bids or not self.asks:
           return None
        return self.best_ask() - self.best_bid()

stream = [("BID", 100.50, 200),
("ASK", 100.55, 150),
("ASK", 100.54, 340),
("BID", 100.51, 340)]

ob = OrderBook()

for side, price, qty in stream:

    ob.update(side, price, qty)

    print("Bids:", ob.bids)
    print("Asks:", ob.asks)

    print("Best Bid:", ob.best_bid())
    print("Best Ask:", ob.best_ask())
    print("Spread:", ob.spread())

    print("------")