"""Technical indicators on OHLC DataFrames (index = date)."""
from __future__ import annotations

import numpy as np
import pandas as pd

OHLC_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def resample(daily: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Daily -> weekly ('W-FRI') or monthly ('MS'). The current, still-forming
    period is kept, matching how charting platforms show live weekly RSI."""
    return daily.resample(rule).agg(OHLC_AGG).dropna(subset=["close"])


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI (same as TradingView / most broker charts)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    return out.where(avg_loss != 0, 100.0)


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)
    return pd.DataFrame({"bb_mid": mid, "bb_upper": mid + k * sd, "bb_lower": mid - k * sd})


def atr(df: pd.DataFrame, n: int = 20) -> pd.Series:
    prev = df.close.shift()
    tr = pd.concat([df.high - df.low, (df.high - prev).abs(), (df.low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def keltner(df: pd.DataFrame, n: int = 20, mult: float = 1.5) -> pd.DataFrame:
    mid = df.close.ewm(span=n, adjust=False, min_periods=n).mean()
    a = atr(df, n)
    return pd.DataFrame({"kc_mid": mid, "kc_upper": mid + mult * a, "kc_lower": mid - mult * a})


def pivots(df: pd.DataFrame, left: int, right: int) -> tuple[pd.Series, pd.Series]:
    """Boolean masks of swing highs / swing lows: the bar's high (low) is the
    extreme of the `left` bars before and `right` bars after it."""
    win = left + right + 1
    hmax = df.high.rolling(win, center=False).max().shift(-right)
    lmin = df.low.rolling(win, center=False).min().shift(-right)
    highs = (df.high == hmax) & hmax.notna()
    lows = (df.low == lmin) & lmin.notna()
    return highs, lows


def safe(v) -> float | None:
    """float for JSON, None for NaN/inf."""
    if v is None:
        return None
    v = float(v)
    return None if np.isnan(v) or np.isinf(v) else v
