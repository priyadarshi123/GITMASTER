from ib_insync import *

class Execution:
    def __init__(self, ib, contract, config):
        self.ib = ib
        self.contract = contract
        self.sl_pct = config['risk']['stop_loss']
        self.tp_pct = config['risk']['take_profit']

    def place_bracket_order(self, signal, price):
        qty = 1

        if signal == "LONG":
            action = "BUY"
            tp_price = price * (1 + self.tp_pct)
            sl_price = price * (1 - self.sl_pct)

        elif signal == "SHORT":
            action = "SELL"
            tp_price = price * (1 - self.tp_pct)
            sl_price = price * (1 + self.sl_pct)

        else:
            return

        bracket = self.ib.bracketOrder(
            action=action,
            quantity=qty,
            limitPrice=price,
            takeProfitPrice=tp_price,
            stopLossPrice=sl_price
        )

        for order in bracket:
            #self.ib.placeOrder(self.contract, order)
            print(order)