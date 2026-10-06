"""Loading, cleaning and resampling NIFTY OHLC bars (all timestamps in Asia/Kolkata)."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

IST = "Asia/Kolkata"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
log = logging.getLogger(__name__)

_TS_COLS = ("datetime", "timestamp", "date_time", "ts", "date", "time")


# ------------------------------------------------------------------ loaders
def load_csv(path: str | Path) -> pd.DataFrame:
    """Load a 1m/5m/15m OHLC CSV, detecting the timestamp and price columns."""
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in ("open", "high", "low", "close") if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing columns {missing}; found {list(df.columns)}")

    if "date" in df.columns and "time" in df.columns:
        ts = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str))
    else:
        tcol = next((c for c in _TS_COLS if c in df.columns), None)
        if tcol is None:
            raise ValueError(f"CSV needs a date/datetime/timestamp column; found {list(df.columns)}")
        ts = pd.to_datetime(df[tcol])
    # Naive timestamps are already IST
    ts = ts.dt.tz_localize(IST) if ts.dt.tz is None else ts.dt.tz_convert(IST)

    cols = ["open", "high", "low", "close"] + (["volume"] if "volume" in df.columns else [])
    out = df[cols].astype(float).set_index(pd.DatetimeIndex(ts, name="ts"))
    return out.sort_index()


def load_yahoo(ticker: str = "^NSEI", interval: str = "5m", period: str = "60d",
               cache: bool = True) -> pd.DataFrame:
    """Yahoo Finance intraday bars. Only ~60 days of 5m/15m history: smoke test only."""
    log.warning("Yahoo Finance only serves ~60 days of intraday bars for %s. "
                "Treat these results as a SMOKE TEST, not evidence of an edge.", ticker)
    import yfinance as yf

    d = yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=False)
    if d.empty:
        raise RuntimeError("Yahoo returned no data")
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d.columns = [str(c).lower() for c in d.columns]
    idx = d.index if d.index.tz is not None else d.index.tz_localize("UTC")
    d.index = pd.DatetimeIndex(idx.tz_convert(IST), name="ts")
    d = d[["open", "high", "low", "close", "volume"]].astype(float)
    if cache:
        DATA_DIR.mkdir(exist_ok=True)
        f = DATA_DIR / f"yahoo_{ticker.strip('^')}_{interval}_{d.index[-1]:%Y%m%d}.csv"
        d.to_csv(f)
        log.info("Cached Yahoo data to %s", f)
    return d


# ----------------------------------------------------------------- cleaning
def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Session filter, weekend/duplicate/invalid-bar removal. Logs what was dropped."""
    n0 = len(df)
    if df.index.tz is None:
        df = df.tz_localize(IST)
    else:
        df = df.tz_convert(IST)

    df = df[~df.index.duplicated(keep="first")]
    n_dup = n0 - len(df)

    n1 = len(df)
    df = df[df.index.dayofweek < 5]
    n_wkend = n1 - len(df)

    n2 = len(df)
    df = df.between_time("09:15", "15:29")
    n_session = n2 - len(df)

    n3 = len(df)
    df = df.dropna(subset=["open", "high", "low", "close"])
    bad = ((df.high < df.low)
           | (df.open > df.high) | (df.open < df.low)
           | (df.close > df.high) | (df.close < df.low))
    df = df[~bad]
    n_bad = n3 - len(df)

    log.info("Cleaning: %d rows in; dropped %d duplicates, %d weekend, %d outside 09:15-15:29, "
             "%d invalid/NaN bars; %d rows out", n0, n_dup, n_wkend, n_session, n_bad, len(df))
    return df


def resample(df: pd.DataFrame, tf_min: int) -> pd.DataFrame:
    """Resample to tf_min bars aligned to 09:15 (label/closed left)."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    out = df.resample(f"{tf_min}min", offset="15min", label="left", closed="left").agg(agg)
    out = out.dropna(subset=["open", "high", "low", "close"])
    # A bar must start inside the session (e.g. a 15:30 label can't appear after between_time)
    return out.between_time("09:15", "15:29")


def infer_bar_minutes(df: pd.DataFrame) -> int:
    d = pd.Series(df.index).diff().dt.total_seconds().div(60)
    return int(d[d > 0].mode().iloc[0])


def summarize(df: pd.DataFrame, tf_min: int) -> str:
    """Human-readable data summary: range, days, bars/day, short days and long gaps."""
    days = pd.Series(df.index.date)
    per_day = days.value_counts().sort_index()
    expected = int(np.ceil(375 / tf_min))  # 09:15-15:30 is 375 minutes
    short = per_day[per_day < 0.8 * expected]

    udays = pd.to_datetime(pd.Series(per_day.index))
    # weekdays with no bars between consecutive trading days
    bdays_gap = [np.busday_count(a.date(), b.date()) - 1 for a, b in zip(udays[:-1], udays[1:])]
    gaps = [(a.date(), b.date(), g) for a, b, g in zip(udays[:-1], udays[1:], bdays_gap) if g > 3]

    lines = [
        f"Data {tf_min}m: {df.index[0]:%Y-%m-%d %H:%M} -> {df.index[-1]:%Y-%m-%d %H:%M} IST",
        f"  trading days {len(per_day):,} | bars {len(df):,} | bars/day median {per_day.median():.0f} "
        f"(expected {expected})",
        f"  short days (<80% of expected bars): {len(short)}"
        + (f" e.g. {', '.join(f'{d}({n})' for d, n in short.head(5).items())}" if len(short) else ""),
        f"  gaps > 3 trading days: {len(gaps)}"
        + (f" e.g. {', '.join(f'{a}->{b}' for a, b, _ in gaps[:5])}" if gaps else ""),
    ]
    return "\n".join(lines)
