"""Weekly + daily RSI strategy signal."""
from __future__ import annotations

import math

import pandas as pd

from .indicators import resample, rsi

BEAR_CALL = "Bear Call"
BULL_PUT = "Bull Put"
IRON_CONDOR = "Iron Condor"
WAIT = "Wait for confirmation"


def zone(value: float, bear: float, bull: float) -> str:
    if value < bear:
        return "bearish"
    if value > bull:
        return "bullish"
    return "neutral"


def classify(rsi_w: float, rsi_d: float, bear: float = 40, bull: float = 60) -> str:
    """The daily zone triggers the trade; the weekly must not oppose it.

    daily bearish + weekly bearish/neutral -> Bear Call
    daily bullish + weekly bullish/neutral -> Bull Put
    daily neutral + weekly neutral         -> Iron Condor
    anything else (weekly trending but daily not yet confirming, or the two
    pointing in opposite directions)       -> Wait for confirmation
    """
    zw, zd = zone(rsi_w, bear, bull), zone(rsi_d, bear, bull)
    if zd == "bearish" and zw != "bullish":
        return BEAR_CALL
    if zd == "bullish" and zw != "bearish":
        return BULL_PUT
    if zd == "neutral" and zw == "neutral":
        return IRON_CONDOR
    return WAIT


def compute(daily: pd.DataFrame, cfg: dict) -> dict | None:
    """Latest weekly/daily RSI and the resulting signal for one symbol."""
    period = int(cfg.get("rsi_period", 14))
    if len(daily) < period * 6:
        return None
    rd = rsi(daily.close, period).iloc[-1]
    rw = rsi(resample(daily, "W-FRI").close, period).iloc[-1]
    if any(math.isnan(x) for x in (rd, rw)):
        return None
    bear, bull = float(cfg.get("bearish_below", 40)), float(cfg.get("bullish_above", 60))
    return {"rsi_w": round(float(rw), 1), "rsi_d": round(float(rd), 1),
            "signal": classify(rw, rd, bear, bull)}
