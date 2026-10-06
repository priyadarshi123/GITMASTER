from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

from ..config import Instrument


@dataclass
class Quote:
    ltp: float
    prev_close: float

    @property
    def change_pct(self) -> float:
        return (self.ltp / self.prev_close - 1) * 100 if self.prev_close else 0.0


class Provider(Protocol):
    name: str
    live: bool          # True = real-time broker data; False = delayed/public

    def daily_candles(self, instruments: list[Instrument], start: date) -> dict[str, pd.DataFrame]:
        """symbol -> DataFrame(index=date, open/high/low/close/volume) from `start` to today."""

    def quotes(self, instruments: list[Instrument]) -> dict[str, Quote]:
        """symbol -> latest price and previous close."""
