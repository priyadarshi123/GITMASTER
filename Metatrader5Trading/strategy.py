from dataclasses import dataclass
from typing import Optional

import pandas as pd

from orders import BUY, SELL

HOLD = "HOLD"


@dataclass
class Signal:
    """What a strategy wants to do on the latest bar."""
    action: str                     # BUY, SELL or HOLD
    sl: Optional[float] = None      # stop-loss price
    tp: Optional[float] = None      # take-profit price
    reason: str = ""


class Strategy:
    """
    Base class for strategies. Subclass it and implement generate_signal().
    `df` is the OHLC DataFrame from market_data.to_sgt_dataframe (columns: open,
    high, low, close, tick_volume, ...), indexed by SGT timestamp, oldest first.
    """
    name = "base"

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        raise NotImplementedError


class SmaCrossStrategy(Strategy):
    """
    Placeholder example so the pipeline can run end to end - replace with your
    own strategy. BUY when the fast SMA crosses above the slow SMA, SELL on the
    opposite cross; SL/TP are set as multiples of ATR.
    """
    name = "sma_cross"

    def __init__(self, fast=20, slow=50, atr_period=14, sl_atr=1.5, tp_atr=3.0):
        self.fast, self.slow = fast, slow
        self.atr_period, self.sl_atr, self.tp_atr = atr_period, sl_atr, tp_atr

    def generate_signal(self, df):
        if len(df) < self.slow + 2:
            return Signal(HOLD, reason="not enough bars")

        close = df["close"]
        fast = close.rolling(self.fast).mean()
        slow = close.rolling(self.slow).mean()
        prev_close = close.shift()
        true_range = pd.concat([df["high"] - df["low"],
                                (df["high"] - prev_close).abs(),
                                (df["low"] - prev_close).abs()], axis=1).max(axis=1)
        atr = true_range.rolling(self.atr_period).mean().iloc[-1]
        price = close.iloc[-1]

        crossed_up = fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
        crossed_down = fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]

        if crossed_up:
            return Signal(BUY, sl=price - self.sl_atr * atr, tp=price + self.tp_atr * atr,
                          reason=f"SMA{self.fast} crossed above SMA{self.slow}")
        if crossed_down:
            return Signal(SELL, sl=price + self.sl_atr * atr, tp=price - self.tp_atr * atr,
                          reason=f"SMA{self.fast} crossed below SMA{self.slow}")
        return Signal(HOLD, reason="no crossover on latest bar")
