"""
UT Bot + LinReg Candles backtester for NIFTY (intraday, square-off every day).

Same logic as the TradingView strategy "UT Bot + LinReg Backtest":
  - UT Bot trailing stop (Key Value a, ATR period c); Buy/Sell on crossovers
  - Optional filter: only trade in the direction of LinReg close vs its SMA
  - Stop-and-reverse, entries only 09:20-14:45 IST, flat by 15:15 IST
  - Signals on bar close, fills at NEXT bar open +/- slippage, cost per order

Usage
-----
  pip install pandas numpy matplotlib yfinance

  # 1) Quick run on free Yahoo data (only ~60 days of 15m bars available)
  python ut_linreg_backtest.py --yahoo

  # 2) Multi-year run on a CSV of 1-min / 5-min / 15-min bars
  #    (needs columns: date/datetime, open, high, low, close)
  python ut_linreg_backtest.py --csv NIFTY_1min.csv --tf 15

  # 3) Parameter grid + in-sample / out-of-sample check
  python ut_linreg_backtest.py --csv NIFTY_1min.csv --grid
"""
import argparse
import itertools
import sys

import numpy as np
import pandas as pd

IST = "Asia/Kolkata"


# ----------------------------------------------------------------- data
def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ("datetime", "date", "timestamp", "time") if c in df.columns), None)
    if tcol is None:
        sys.exit("CSV needs a date/datetime column")
    # Some files split date and time into two columns
    if tcol == "date" and "time" in df.columns:
        ts = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str))
    else:
        ts = pd.to_datetime(df[tcol])
    ts = ts.dt.tz_localize(IST) if ts.dt.tz is None else ts.dt.tz_convert(IST)
    df = df.assign(ts=ts).set_index("ts")[["open", "high", "low", "close"]].astype(float)
    return df.sort_index()


def load_yahoo(ticker="^NSEI", interval="15m", period="60d") -> pd.DataFrame:
    import yfinance as yf
    d = yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=False)
    if d.empty:
        sys.exit("Yahoo returned no data")
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d.columns = [c.lower() for c in d.columns]
    d.index = d.index.tz_convert(IST) if d.index.tz is not None else d.index.tz_localize("UTC").tz_convert(IST)
    return d[["open", "high", "low", "close"]].astype(float)


def resample(df: pd.DataFrame, tf_min: int) -> pd.DataFrame:
    """Resample to tf_min bars aligned to the 09:15 open."""
    df = df.between_time("09:15", "15:29")
    out = df.resample(f"{tf_min}min", offset="15min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    return out.dropna()


# ------------------------------------------------------------ indicators
def atr(df: pd.DataFrame, n: int) -> np.ndarray:
    """Same as Pine ta.atr: Wilder RMA of true range."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    tr[0] = h[0] - l[0]
    out = np.full(len(tr), np.nan)
    if len(tr) < n:
        return out
    out[n - 1] = tr[:n].mean()
    for i in range(n, len(tr)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def linreg_end(x: np.ndarray, n: int) -> np.ndarray:
    """Same as Pine ta.linreg(src, n, 0): fitted value at the latest bar."""
    xs = np.arange(n)
    xm = xs.mean()
    w = 1.0 / n + (xs - xm) * (n - 1 - xm) / ((xs - xm) ** 2).sum()  # weights, oldest -> newest
    out = np.full(len(x), np.nan)
    out[n - 1:] = np.convolve(x, w[::-1], mode="valid")
    return out


def ut_trail(src: np.ndarray, nloss: np.ndarray) -> np.ndarray:
    trail = np.zeros(len(src))
    for i in range(len(src)):
        p = trail[i - 1] if i > 0 else 0.0
        s, s1 = src[i], (src[i - 1] if i > 0 else np.nan)
        nl = nloss[i]
        if np.isnan(nl):
            trail[i] = 0.0 if i == 0 else p
            continue
        if s > p and s1 > p:
            trail[i] = max(p, s - nl)
        elif s < p and s1 < p:
            trail[i] = min(p, s + nl)
        elif s > p:
            trail[i] = s - nl
        else:
            trail[i] = s + nl
    return trail


# -------------------------------------------------------------- backtest
def backtest(df, a=3.0, c=10, sig_len=7, lr_len=11, use_filter=True, allow_short=True,
             lot=65, cost_per_order=60.0, slip_pts=1.0,
             entry_start="09:20", entry_end="14:45", squareoff="15:15"):
    o, cl = df["open"].values, df["close"].values
    src = cl
    trail = ut_trail(src, a * atr(df, c))
    prev_src, prev_tr = np.r_[np.nan, src[:-1]], np.r_[np.nan, trail[:-1]]
    ut_buy = (src > trail) & (prev_src <= prev_tr)
    ut_sell = (src < trail) & (prev_src >= prev_tr)

    lr = linreg_end(cl, lr_len)
    sig = pd.Series(lr).rolling(sig_len).mean().values
    bull, bear = lr > sig, lr < sig

    t = df.index
    tod = t.strftime("%H:%M")
    day = t.date
    can_enter = (tod >= entry_start) & (tod <= entry_end)

    trades, pos, entry_px, entry_t = [], 0, 0.0, None

    def close_pos(i_fill, px, reason):
        nonlocal pos
        exit_px = px - slip_pts if pos == 1 else px + slip_pts
        pts = (exit_px - entry_px) * pos
        trades.append(dict(entry_time=entry_t, exit_time=t[i_fill], side="Long" if pos == 1 else "Short",
                           entry=entry_px, exit=exit_px, points=pts,
                           pnl=pts * lot - 2 * cost_per_order, reason=reason))
        pos = 0

    def open_pos(i_fill, side):
        nonlocal pos, entry_px, entry_t
        pos, entry_t = side, t[i_fill]
        entry_px = o[i_fill] + slip_pts if side == 1 else o[i_fill] - slip_pts

    for i in range(len(df) - 1):
        j = i + 1  # fill bar
        # Data gap / day change with an open position: exit at this bar's close
        if pos != 0 and day[j] != day[i]:
            close_pos(i, cl[i], "EOD-gap")
            continue
        # Scheduled square-off: exit at the open of the first bar at/after 15:15
        if tod[j] >= squareoff:
            if pos != 0:
                close_pos(j, o[j], "EOD")
            continue
        if ut_buy[i]:
            if can_enter[i] and (not use_filter or bull[i]):
                if pos == -1:
                    close_pos(j, o[j], "Reverse")
                if pos == 0:
                    open_pos(j, 1)
            elif pos == -1:
                close_pos(j, o[j], "Signal")
        elif ut_sell[i]:
            if can_enter[i] and allow_short and (not use_filter or bear[i]):
                if pos == 1:
                    close_pos(j, o[j], "Reverse")
                if pos == 0:
                    open_pos(j, -1)
            elif pos == 1:
                close_pos(j, o[j], "Signal")
    if pos != 0:
        close_pos(len(df) - 1, cl[-1], "End")
    return pd.DataFrame(trades)


def stats(tr: pd.DataFrame, capital=1_000_000) -> dict:
    if tr.empty:
        return dict(trades=0, net=0.0, pf=np.nan, win=np.nan, maxdd=0.0, avg=0.0)
    eq = capital + tr["pnl"].cumsum()
    dd = (eq.cummax() - eq).max()
    gp, gl = tr.loc[tr.pnl > 0, "pnl"].sum(), -tr.loc[tr.pnl < 0, "pnl"].sum()
    return dict(trades=len(tr), net=tr.pnl.sum(), pf=gp / gl if gl else np.inf,
                win=(tr.pnl > 0).mean() * 100, maxdd=dd, avg=tr.pnl.mean(),
                long=tr.loc[tr.side == "Long", "pnl"].sum(), short=tr.loc[tr.side == "Short", "pnl"].sum())


def fmt(s: dict) -> str:
    return (f"trades {s['trades']:>4} | net Rs {s['net']:>11,.0f} | PF {s['pf']:.2f} | win {s['win']:.0f}% | "
            f"maxDD Rs {s['maxdd']:,.0f} | avg/trade Rs {s['avg']:,.0f}")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv"); ap.add_argument("--yahoo", action="store_true")
    ap.add_argument("--tf", type=int, default=15, help="bar size in minutes")
    ap.add_argument("--a", type=float, default=3.0); ap.add_argument("--c", type=int, default=10)
    ap.add_argument("--nofilter", action="store_true"); ap.add_argument("--longonly", action="store_true")
    ap.add_argument("--lot", type=int, default=65); ap.add_argument("--cost", type=float, default=60)
    ap.add_argument("--slip", type=float, default=1.0, help="slippage in index points per fill")
    ap.add_argument("--grid", action="store_true"); ap.add_argument("--oos", type=float, default=0.3,
                                                                    help="out-of-sample fraction for --grid")
    args = ap.parse_args()

    raw = load_yahoo(interval=f"{args.tf}m") if args.yahoo else load_csv(args.csv)
    df = resample(raw, args.tf)
    print(f"Data: {df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}, {len(df):,} bars of {args.tf}m\n")
    kw = dict(lot=args.lot, cost_per_order=args.cost, slip_pts=args.slip)

    if not args.grid:
        tr = backtest(df, a=args.a, c=args.c, use_filter=not args.nofilter,
                      allow_short=not args.longonly, **kw)
        s = stats(tr)
        print("ALL    ", fmt(s))
        print(f"        long Rs {s.get('long', 0):,.0f} | short Rs {s.get('short', 0):,.0f}")
        if not tr.empty:
            tr["year"] = pd.to_datetime(tr.exit_time).dt.year
            print("\nBy year:")
            for y, g in tr.groupby("year"):
                print(f"  {y}  ", fmt(stats(g)))
            tr.to_csv("trades.csv", index=False)
            try:
                import matplotlib.pyplot as plt
                ax = tr.set_index("exit_time")["pnl"].cumsum().plot(figsize=(10, 4), title="Cumulative P&L (Rs , 1 lot)")
                ax.axhline(0, color="grey", lw=0.8); plt.tight_layout(); plt.savefig("equity.png", dpi=120)
                print("\nSaved trades.csv and equity.png")
            except Exception:
                pass
        return

    # ---- grid search with in-sample / out-of-sample split ----
    cut = df.index[int(len(df) * (1 - args.oos))]
    ins, oos = df[df.index < cut], df[df.index >= cut]
    print(f"In-sample: -> {cut:%Y-%m-%d} | Out-of-sample: {cut:%Y-%m-%d} ->\n")
    rows = []
    for a, c, f in itertools.product([1, 1.5, 2, 2.5, 3, 3.5, 4, 5], [1, 5, 10, 14, 20], [True, False]):
        si = stats(backtest(ins, a=a, c=c, use_filter=f, **kw))
        so = stats(backtest(oos, a=a, c=c, use_filter=f, **kw))
        rows.append(dict(a=a, c=c, filter=f, is_net=si["net"], is_pf=si["pf"], is_trades=si["trades"],
                         oos_net=so["net"], oos_pf=so["pf"], oos_trades=so["trades"]))
    g = pd.DataFrame(rows).sort_values("is_pf", ascending=False)
    g.to_csv("grid_results.csv", index=False)
    pd.set_option("display.width", 160)
    print("Top 10 by in-sample profit factor (check they hold up out-of-sample):")
    print(g.head(10).to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print(f"\nShare of settings profitable in-sample: {(g.is_net > 0).mean():.0%}, "
          f"out-of-sample: {(g.oos_net > 0).mean():.0%}")
    print("Saved grid_results.csv")


if __name__ == "__main__":
    main()
