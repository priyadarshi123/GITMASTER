import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import indicators as ind  # noqa: E402
from src.backtest import Params, backtest, run_engine  # noqa: E402
from src.data import resample  # noqa: E402

IST = "Asia/Kolkata"


def synthetic_bars(days=60, tf=5, seed=0, drift=0.0, vol=6.0, short_day=None) -> pd.DataFrame:
    """Random-walk session bars 09:15 -> 15:29 on weekdays. short_day ends that day at 13:00."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=days)
    idx = []
    for i, d in enumerate(dates):
        times = pd.date_range(d + pd.Timedelta("09:15:00"), d + pd.Timedelta("15:29:00"), freq=f"{tf}min")
        if short_day is not None and i == short_day:
            times = times[times.hour < 13]
        idx.append(times)
    idx = pd.DatetimeIndex(np.concatenate(idx)).tz_localize(IST)
    n = len(idx)
    close = 20000 + np.cumsum(rng.normal(drift, vol, n))
    open_ = np.r_[close[0], close[:-1]] + rng.normal(0, 1, n)
    high = np.maximum(open_, close) + rng.uniform(0, 4, n)
    low = np.minimum(open_, close) - rng.uniform(0, 4, n)
    return pd.DataFrame(dict(open=open_, high=high, low=low, close=close), index=idx)


# ------------------------------------------------------------------ indicators
def test_atr_c1_equals_true_range():
    h = np.array([10.0, 12, 11]); l = np.array([8.0, 9, 7]); c = np.array([9.0, 11, 8])
    expected_tr = [2, 3, 4]  # H-L; max(3,|12-9|,|9-9|); max(4,|11-11|,|7-11|)
    np.testing.assert_allclose(ind.true_range(h, l, c), expected_tr)
    np.testing.assert_allclose(ind.atr(h, l, c, 1), expected_tr)


def test_atr_rma_hand_calculated():
    h = np.array([10.0, 12, 11]); l = np.array([8.0, 9, 7]); c = np.array([9.0, 11, 8])
    out = ind.atr(h, l, c, 2)
    assert np.isnan(out[0])
    assert out[1] == pytest.approx(2.5)            # SMA seed of TR [2, 3]
    assert out[2] == pytest.approx((2.5 * 1 + 4) / 2)  # Wilder: (prev*(n-1)+TR)/n
    np.testing.assert_allclose(ind.rma(np.array([2.0, 4, 6, 8]), 3)[2:], [4.0, 16 / 3])


def test_linreg_straight_line_is_exact():
    x = 100 + 2.5 * np.arange(50)
    for n in (2, 5, 11, 20):
        out = ind.linreg(x, n)
        assert np.isnan(out[: n - 1]).all()
        np.testing.assert_allclose(out[n - 1:], x[n - 1:])


def test_linreg_matches_polyfit():
    x = np.random.default_rng(1).normal(size=40).cumsum()
    n = 11
    out = ind.linreg(x, n)
    for i in range(n - 1, len(x)):
        coef = np.polyfit(np.arange(n), x[i - n + 1:i + 1], 1)
        assert out[i] == pytest.approx(np.polyval(coef, n - 1))


def test_ut_trail_hand_example():
    src = np.array([10.0, 11, 12, 11, 9, 8])
    nloss = np.ones(6)
    # i0 p=0: s>p, s1 NaN -> s-nl=9 | i1 both>9 -> max(9,10)=10 | i2 -> max(10,11)=11
    # i3 s==p (11): neither branch -> s+nl=12 | i4 both<12 -> min(12,10)=10 | i5 -> min(10,9)=9
    trail = ind.ut_trail(src, nloss)
    np.testing.assert_allclose(trail, [9, 10, 11, 12, 10, 9])
    buy, sell = ind.ut_signals(src, trail)
    assert list(np.where(sell)[0]) == [3] and not buy.any()


def test_ut_trail_zero_during_warmup():
    src = np.array([10.0, 11, 12, 13])
    trail = ind.ut_trail(src, np.array([np.nan, np.nan, 1.0, 1.0]))
    np.testing.assert_allclose(trail, [0, 0, 11, 12])


# ---------------------------------------------------------------------- engine
@pytest.mark.parametrize("tf", [5, 15])
def test_session_rules(tf):
    bars = resample(synthetic_bars(days=80, tf=5, seed=tf, short_day=10), tf)
    tr = backtest(bars, Params(a=1, c=1, use_filter=False))
    assert len(tr) > 50
    sig_min = pd.DatetimeIndex(tr.signal_time).hour * 60 + pd.DatetimeIndex(tr.signal_time).minute
    assert ((sig_min >= 9 * 60 + 20) & (sig_min <= 14 * 60 + 45)).all()
    ent, ext = pd.DatetimeIndex(tr.entry_time), pd.DatetimeIndex(tr.exit_time)
    assert (ent.date == ext.date).all(), "position held overnight"
    ext_min = ext.hour * 60 + ext.minute
    assert (ext_min <= 15 * 60 + 15).all()


def test_eod_gap_exit_on_short_day():
    bars = resample(synthetic_bars(days=30, tf=5, seed=3, short_day=5), 15)
    tr = backtest(bars, Params(a=1, c=1, use_filter=False))
    gap = tr[tr.reason == "EOD-gap"]
    short_date = pd.bdate_range("2024-01-01", periods=30)[5].date()
    assert all(pd.Timestamp(t).date() == short_date for t in gap.exit_time)


@pytest.mark.parametrize("tf", [5, 15])
def test_fill_prices_are_open_plus_minus_slippage(tf):
    bars = resample(synthetic_bars(days=60, tf=5, seed=7), tf)
    slip = 1.5
    tr = backtest(bars, Params(a=1.5, c=5, use_filter=True, slippage_pts=slip))
    o = bars["open"]
    sign = np.where(tr.side == "Long", 1, -1)
    np.testing.assert_allclose(tr.entry, o.loc[pd.DatetimeIndex(tr.entry_time)].to_numpy() + sign * slip)
    normal = ~tr.reason.isin(["EOD-gap", "End"])
    ex = tr[normal]
    np.testing.assert_allclose(ex.exit, o.loc[pd.DatetimeIndex(ex.exit_time)].to_numpy() - sign[normal] * slip)


def test_pnl_formula():
    bars = resample(synthetic_bars(days=20, tf=5, seed=11), 15)
    p = Params(a=1, c=1, lot=65, cost_per_order=60, slippage_pts=1)
    tr = backtest(bars, p)
    np.testing.assert_allclose(tr.pnl, tr.points * 65 - 120)
    np.testing.assert_allclose(tr.gross_pnl - tr.commission - tr.slippage_cost, tr.pnl)


def test_long_only_has_no_shorts():
    bars = resample(synthetic_bars(days=40, tf=5, seed=5), 15)
    tr = backtest(bars, Params(a=1, c=1, allow_short=False))
    assert len(tr) and (tr.side == "Long").all()


def test_random_signals_zero_cost_average_near_zero():
    bars = synthetic_bars(days=500, tf=5, seed=42, drift=0.0)
    rng = np.random.default_rng(123)
    n = len(bars)
    buy = rng.random(n) < 0.05
    sell = ~buy & (rng.random(n) < 0.05)
    p = Params(use_filter=False, cost_per_order=0, slippage_pts=0)
    tr = run_engine(bars, buy, sell, None, None, p)
    assert len(tr) > 1000
    sem = tr.points.std(ddof=1) / np.sqrt(len(tr))
    assert abs(tr.points.mean()) < 3 * sem


def test_tv_bug_mode_holds_overnight_on_15m():
    bars = resample(synthetic_bars(days=60, tf=5, seed=9), 15)
    fixed = backtest(bars, Params(a=1, c=1, use_filter=False))
    bug = backtest(bars, Params(a=1, c=1, use_filter=False, tv_squareoff=True))
    same_day = lambda t: pd.DatetimeIndex(t.entry_time).date == pd.DatetimeIndex(t.exit_time).date  # noqa: E731
    assert same_day(fixed).all()
    assert (~same_day(bug)).any()
