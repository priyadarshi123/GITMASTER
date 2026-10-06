"""Indicators matching TradingView Pine Script v6: ta.atr, UT Bot trailing stop, ta.linreg."""
from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """max(H-L, |H-prevC|, |L-prevC|); first bar is H-L (Pine ta.tr(true))."""
    h, l, c = (np.asarray(x, dtype=float) for x in (high, low, close))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return tr


def rma(x: np.ndarray, n: int) -> np.ndarray:
    """Wilder smoothing: seed with the SMA of the first n values, then (prev*(n-1)+x)/n."""
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    if n < 1 or len(x) < n:
        return out
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def atr(high, low, close, n: int) -> np.ndarray:
    """Pine ta.atr(n). With n=1 this equals the true range."""
    return rma(true_range(high, low, close), n)


def ut_trail(src: np.ndarray, nloss: np.ndarray) -> np.ndarray:
    """UT Bot ATR trailing stop. trail is 0 while nLoss is still NaN (warm-up)."""
    src = np.asarray(src, dtype=float)
    nloss = np.asarray(nloss, dtype=float)
    trail = np.zeros(len(src))
    for i in range(len(src)):
        nl = nloss[i]
        if np.isnan(nl):
            trail[i] = 0.0
            continue
        p = trail[i - 1] if i > 0 else 0.0
        s = src[i]
        s1 = src[i - 1] if i > 0 else np.nan  # comparisons with NaN are False, like Pine na
        if s > p and s1 > p:
            trail[i] = max(p, s - nl)
        elif s < p and s1 < p:
            trail[i] = min(p, s + nl)
        elif s > p:
            trail[i] = s - nl
        else:
            trail[i] = s + nl
    return trail


def ut_signals(src: np.ndarray, trail: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Crossovers evaluated on every bar (no lazy 'and'): close crossing the trailing stop."""
    src = np.asarray(src, dtype=float)
    prev_s = np.r_[np.nan, src[:-1]]
    prev_t = np.r_[np.nan, trail[:-1]]
    buy = (src > trail) & (prev_s <= prev_t)
    sell = (src < trail) & (prev_s >= prev_t)
    return buy, sell


def linreg_weights(n: int) -> np.ndarray:
    """Weights (oldest -> newest) whose dot product with the last n values = fitted value at newest bar."""
    xs = np.arange(n, dtype=float)
    xm = xs.mean()
    sxx = ((xs - xm) ** 2).sum()
    if sxx == 0:  # n == 1
        return np.ones(1)
    return 1.0 / n + (xs - xm) * (n - 1 - xm) / sxx


def linreg(x: np.ndarray, n: int) -> np.ndarray:
    """Pine ta.linreg(src, n, 0), vectorised with fixed convolution weights."""
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    w = linreg_weights(n)
    out[n - 1:] = np.convolve(x, w[::-1], mode="valid")
    return out


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


def linreg_trend(close: np.ndarray, sig_len: int, lr_len: int) -> tuple[np.ndarray, np.ndarray]:
    """LinReg Candles filter: bull = linreg(close) > SMA(linreg(close), sig_len)."""
    lr = linreg(close, lr_len)
    sig = sma(lr, sig_len)
    return lr > sig, lr < sig
