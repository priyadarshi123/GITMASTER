"""Execution engine (stop-and-reverse, next-bar-open fills, daily square-off) and statistics."""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from . import indicators as ind


@dataclass(frozen=True)
class Params:
    a: float = 3.0
    c: int = 10
    sig_len: int = 7
    lr_len: int = 11
    use_filter: bool = True
    allow_short: bool = True
    entry_start: str = "09:20"
    entry_end: str = "14:45"
    squareoff: str = "15:15"
    lot: int = 65
    cost_per_order: float = 60.0
    slippage_pts: float = 1.0
    # Replicates the TradingView bug: square-off decided on the close of the first bar
    # starting at/after 15:15, filled at the NEXT bar's open (next morning on 15m bars).
    tv_squareoff: bool = False

    def with_(self, **kw) -> "Params":
        return replace(self, **kw)


TRADE_COLS = ["signal_time", "entry_time", "exit_time", "side", "entry", "exit", "points",
              "gross_pnl", "commission", "slippage_cost", "pnl", "reason"]


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def signals(df: pd.DataFrame, p: Params) -> dict[str, np.ndarray]:
    close = df["close"].to_numpy(float)
    nloss = p.a * ind.atr(df["high"].to_numpy(float), df["low"].to_numpy(float), close, p.c)
    trail = ind.ut_trail(close, nloss)
    buy, sell = ind.ut_signals(close, trail)
    bull, bear = ind.linreg_trend(close, p.sig_len, p.lr_len)
    return dict(buy=buy, sell=sell, bull=bull, bear=bear, trail=trail)


def run_engine(df: pd.DataFrame, buy: np.ndarray, sell: np.ndarray,
               bull: np.ndarray | None, bear: np.ndarray | None, p: Params) -> pd.DataFrame:
    """Run the trading rules on precomputed boolean signal arrays. Returns one row per trade."""
    t = df.index
    o = df["open"].to_numpy(float)
    cl = df["close"].to_numpy(float)
    n = len(df)
    tod = (t.hour * 60 + t.minute).to_numpy()
    day = (t.year * 10000 + t.month * 100 + t.day).to_numpy()
    e0, e1, sq = _minutes(p.entry_start), _minutes(p.entry_end), _minutes(p.squareoff)
    can_enter = (tod >= e0) & (tod <= e1)
    if bull is None:
        bull = np.ones(n, bool)
    if bear is None:
        bear = np.ones(n, bool)
    slip, lot, cpo = p.slippage_pts, p.lot, p.cost_per_order

    rows: list[tuple] = []
    pos, entry_px, entry_raw, entry_i, sig_i = 0, 0.0, 0.0, -1, -1

    def close_pos(i_fill: int, raw_px: float, reason: str) -> None:
        nonlocal pos
        exit_px = raw_px - slip if pos == 1 else raw_px + slip
        pts = (exit_px - entry_px) * pos
        gross = (raw_px - entry_raw) * pos * lot
        rows.append((t[sig_i], t[entry_i], t[i_fill], "Long" if pos == 1 else "Short",
                     entry_px, exit_px, pts, gross, 2 * cpo, 2 * slip * lot,
                     pts * lot - 2 * cpo, reason))
        pos = 0

    def open_pos(i_sig: int, i_fill: int, side: int) -> None:
        nonlocal pos, entry_px, entry_raw, entry_i, sig_i
        pos, entry_i, sig_i, entry_raw = side, i_fill, i_sig, o[i_fill]
        entry_px = o[i_fill] + slip if side == 1 else o[i_fill] - slip

    for i in range(n - 1):
        j = i + 1  # fill bar for a decision taken at bar i's close
        if p.tv_squareoff:
            if tod[i] >= sq:
                if pos != 0:
                    close_pos(j, o[j], "EOD")
                continue
        else:
            if day[j] != day[i]:
                # Day ended before the square-off bar (data gap): exit at the last close.
                if pos != 0:
                    close_pos(i, cl[i], "EOD-gap")
                continue  # never fill a decision on a different day
            if tod[j] >= sq:
                if pos != 0:
                    close_pos(j, o[j], "EOD")
                continue

        if buy[i]:
            if can_enter[i] and (not p.use_filter or bull[i]):
                if pos == -1:
                    close_pos(j, o[j], "Reverse")
                if pos == 0:
                    open_pos(i, j, 1)
            elif pos == -1:
                close_pos(j, o[j], "Signal")
        elif sell[i]:
            if can_enter[i] and p.allow_short and (not p.use_filter or bear[i]):
                if pos == 1:
                    close_pos(j, o[j], "Reverse")
                if pos == 0:
                    open_pos(i, j, -1)
            elif pos == 1:
                close_pos(j, o[j], "Signal")

    if pos != 0:
        close_pos(n - 1, cl[-1], "End")
    return pd.DataFrame(rows, columns=TRADE_COLS)


def backtest(df: pd.DataFrame, p: Params = Params()) -> pd.DataFrame:
    s = signals(df, p)
    return run_engine(df, s["buy"], s["sell"], s["bull"], s["bear"], p)


def grid_trades(df: pd.DataFrame, base: Params, a_vals, c_vals, filters) -> dict[tuple, pd.DataFrame]:
    """Run every (a, c, use_filter) once on the full history.

    Trades never span days and indicators are continuous, so sub-period results
    (in-sample, out-of-sample, walk-forward) are the full-history trades filtered by date.
    """
    close = df["close"].to_numpy(float)
    hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    bull, bear = ind.linreg_trend(close, base.sig_len, base.lr_len)
    out = {}
    for c in c_vals:
        atr_c = ind.atr(hi, lo, close, c)
        for a in a_vals:
            buy, sell = ind.ut_signals(close, ind.ut_trail(close, a * atr_c))
            for f in filters:
                p = base.with_(a=a, c=c, use_filter=f)
                out[(a, c, f)] = run_engine(df, buy, sell, bull, bear, p)
    return out


# ------------------------------------------------------------------- stats
def stats(tr: pd.DataFrame, capital: float = 1_000_000) -> dict:
    if tr.empty:
        return dict(trades=0, net=0.0, net_pct=0.0, win_pct=np.nan, pf=np.nan, avg=np.nan,
                    avg_win=np.nan, avg_loss=np.nan, max_win=np.nan, max_loss=np.nan,
                    maxdd=0.0, maxdd_pct=0.0, long_pnl=0.0, short_pnl=0.0,
                    commission=0.0, slippage=0.0, costs=0.0, gross=0.0)
    pnl = tr["pnl"]
    eq = capital + pnl.cumsum().to_numpy()
    eq = np.r_[capital, eq]
    peak = np.maximum.accumulate(eq)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    gp, gl = wins.sum(), -losses.sum()
    comm, slip = tr["commission"].sum(), tr["slippage_cost"].sum()
    return dict(
        trades=len(tr), net=pnl.sum(), net_pct=pnl.sum() / capital * 100,
        win_pct=(pnl > 0).mean() * 100,
        pf=gp / gl if gl > 0 else (np.inf if gp > 0 else np.nan),
        avg=pnl.mean(),
        avg_win=wins.mean() if len(wins) else np.nan,
        avg_loss=losses.mean() if len(losses) else np.nan,
        max_win=pnl.max(), max_loss=pnl.min(),
        maxdd=(peak - eq).max(), maxdd_pct=((peak - eq) / peak).max() * 100,
        long_pnl=pnl[tr.side == "Long"].sum(), short_pnl=pnl[tr.side == "Short"].sum(),
        commission=comm, slippage=slip, costs=comm + slip, gross=tr["gross_pnl"].sum(),
    )


def yearly(tr: pd.DataFrame, capital: float = 1_000_000) -> pd.DataFrame:
    if tr.empty:
        return pd.DataFrame()
    yrs = pd.DatetimeIndex(tr["entry_time"]).year
    rows = {y: stats(g, capital) for y, g in tr.groupby(yrs)}
    return pd.DataFrame(rows).T.rename_axis("year")


def buy_and_hold(df: pd.DataFrame, lot: int, capital: float = 1_000_000) -> dict:
    first, last = df["open"].iloc[0], df["close"].iloc[-1]
    pts = last - first
    return dict(start=df.index[0], end=df.index[-1], first=first, last=last, points=pts,
                index_pct=pts / first * 100, pnl_1lot=pts * lot, pnl_pct_capital=pts * lot / capital * 100)


def grid_values():
    return ([1, 1.5, 2, 2.5, 3, 3.5, 4, 5], [1, 5, 10, 14, 20], [True, False])
