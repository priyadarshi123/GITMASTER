import pandas as pd
import numpy as np

class Backtester:
    def __init__(self, data):
        self.data = data

    def apply_slippage(self, price, volatility):
        # simple slippage model
        spread = 0.0005   # 0.05%
        impact = volatility * 0.5

        slippage = spread + impact
        return price * (1 + slippage)

    def run(self, signals):
        trades = []

        for i in range(len(self.data)-1):
            signal = signals[i]
            if signal == 0:
                continue

            entry_price = self.data.iloc[i]['price']

            volatility = self.data['price'].pct_change().rolling(10).std().iloc[i]

            entry_price = self.apply_slippage(entry_price, volatility)

            exit_price = self.data.iloc[i+1]['price']
            exit_price = self.apply_slippage(exit_price, volatility)

            pnl = (exit_price - entry_price) * signal
            trades.append(pnl)

        return pd.Series(trades)