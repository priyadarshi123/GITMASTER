"""Yahoo Finance fallback: free, ~15 min delayed, no option chains.
Used until Angel One credentials are configured."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from ..config import Instrument
from .base import Quote

log = logging.getLogger(__name__)


class YahooProvider:
    name = "yahoo"
    live = False

    def daily_candles(self, instruments: list[Instrument], start: date) -> dict[str, pd.DataFrame]:
        if not instruments:
            return {}
        by_ticker = {i.yahoo: i.symbol for i in instruments}
        raw = yf.download(
            list(by_ticker), start=start.isoformat(),
            end=(date.today() + timedelta(days=1)).isoformat(),
            interval="1d", auto_adjust=False, group_by="ticker",
            progress=False, threads=True,
        )
        out: dict[str, pd.DataFrame] = {}
        for ticker, symbol in by_ticker.items():
            try:
                df = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                log.warning("yahoo: no data for %s (%s)", symbol, ticker)
                continue
            df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
            df = df.dropna(subset=["close"])
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            if not df.empty:
                out[symbol] = df
        return out

    def quotes(self, instruments: list[Instrument]) -> dict[str, Quote]:
        # The last two daily bars give LTP (today's forming bar) and previous close.
        bars = self.daily_candles(instruments, date.today() - timedelta(days=10))
        out = {}
        for symbol, df in bars.items():
            if len(df) >= 2:
                out[symbol] = Quote(ltp=float(df.close.iloc[-1]), prev_close=float(df.close.iloc[-2]))
        return out
