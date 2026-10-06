"""Section-6 experiments: baselines, grid, in/out-of-sample, walk-forward, cost sensitivity."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import plots
from .backtest import Params, backtest, buy_and_hold, grid_trades, grid_values, stats, yearly

RESULTS = Path(__file__).resolve().parent.parent / "results"

SHOW = ["trades", "net", "net_pct", "win_pct", "pf", "avg", "avg_win", "avg_loss", "max_win",
        "max_loss", "maxdd", "maxdd_pct", "long_pnl", "short_pnl", "gross", "costs"]


@dataclass
class Config:
    capital: float = 1_000_000
    is_frac: float = 0.70
    min_trades: int = 100
    wf_train_days: int = 730   # calendar days (~2 years)
    wf_test_days: int = 182    # calendar days (~6 months)


# ------------------------------------------------------------- formatting
def _fmt(v, col=""):
    if isinstance(v, (bool, np.bool_)):
        return "on" if v else "off"
    if isinstance(v, (int, np.integer)):
        return f"{v:,}"
    if isinstance(v, (float, np.floating)):
        if not np.isfinite(v):
            return "∞" if v == np.inf else "–"
        if col.endswith("pct") or col in ("pf",):
            return f"{v:.2f}"
        if abs(v) < 10 and v != int(v):
            return f"{v:g}"
        return f"{v:,.0f}"
    if isinstance(v, pd.Timestamp):
        return f"{v:%Y-%m-%d}"
    return str(v)


def md_table(df: pd.DataFrame, index=True) -> str:
    d = df.reset_index() if index else df
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join(_fmt(r[c], str(c)) for c in d.columns) + " |")
    return "\n".join(lines)


def one_line(s: dict) -> str:
    return (f"trades {s['trades']:>4} | net ₹{s['net']:>11,.0f} ({s['net_pct']:+.2f}%) | "
            f"PF {s['pf']:.2f} | win {s['win_pct']:.0f}% | maxDD ₹{s['maxdd']:,.0f}")


# ------------------------------------------------------------ experiments
class Runner:
    def __init__(self, bars: dict[int, pd.DataFrame], base: Params, cfg: Config, out=RESULTS):
        self.bars, self.base, self.cfg, self.out = bars, base, cfg, Path(out)
        self.out.mkdir(exist_ok=True)
        self.md: list[str] = []
        self.grids: dict[int, dict] = {}

    def say(self, text: str = "") -> None:
        print(text)
        self.md.append(text)

    # -- single run with all outputs saved
    def run_one(self, tf: int, p: Params, tag: str) -> tuple[pd.DataFrame, dict]:
        df = self.bars[tf]
        tr = backtest(df, p)
        s = stats(tr, self.cfg.capital)
        y = yearly(tr, self.cfg.capital)
        tr.to_csv(self.out / f"trades_{tag}.csv", index=False)
        y.to_csv(self.out / f"yearly_{tag}.csv")
        plots.equity_chart(tr, f"{tag}: cumulative P&L, 1 lot, after costs", self.out / f"equity_{tag}.png")
        return tr, s

    def baselines(self) -> pd.DataFrame:
        self.say("## 1. Baselines\n")
        specs = [
            (5, dict(a=2, c=1), "5m_a2_c1_filter"),
            (5, dict(a=3, c=10), "5m_a3_c10_filter"),
            (15, dict(a=2, c=1), "15m_a2_c1_filter"),
            (15, dict(a=3, c=10), "15m_a3_c10_filter"),
            (15, dict(a=3, c=10, use_filter=False), "15m_a3_c10_nofilter"),
            (15, dict(a=3, c=10, allow_short=False), "15m_a3_c10_longonly"),
        ]
        rows, yearly_md = {}, []
        for tf, kw, tag in specs:
            if tf not in self.bars:
                continue
            tr, s = self.run_one(tf, self.base.with_(**kw), tag)
            rows[tag] = s
            print(f"  {tag:<22} {one_line(s)}")
            y = yearly(tr, self.cfg.capital)
            if not y.empty:
                yearly_md.append(f"**{tag}**\n\n" + md_table(y[SHOW]))
        tab = pd.DataFrame(rows).T[SHOW]
        self.md.append(md_table(tab.rename_axis("run")))
        self.say("\nYearly breakdown per baseline:\n")
        self.md.append("\n\n".join(yearly_md))

        # Buy-and-hold comparison over the same data
        self.say("\n**Buy-and-hold NIFTY over the same period (1 lot, no costs):**\n")
        bh = {f"{tf}m": buy_and_hold(df, self.base.lot, self.cfg.capital) for tf, df in self.bars.items()}
        self.md.append(md_table(pd.DataFrame(bh).T.rename_axis("bars")))
        print(pd.DataFrame(bh).T.to_string())
        return tab

    def tv_bug_compare(self) -> None:
        """How much the TradingView overnight-hold square-off bug moves the 15m numbers."""
        if 15 not in self.bars:
            return
        self.say("\n## TradingView square-off bug: effect on 15m\n")
        self.say("`fixed` = flat at the 15:15 bar's open (this backtester). "
                 "`tv_bug` = close decided on the 15:15 bar, filled at the next bar's open "
                 "(next morning on 15m), as in the TradingView version.\n")
        rows = {}
        for kw, name in [(dict(a=2, c=1), "a2_c1_filter"), (dict(a=3, c=10), "a3_c10_filter"),
                         (dict(a=3, c=10, use_filter=False), "a3_c10_nofilter")]:
            for bug in (False, True):
                tr = backtest(self.bars[15], self.base.with_(tv_squareoff=bug, **kw))
                s = stats(tr, self.cfg.capital)
                overnight = int((pd.DatetimeIndex(tr.entry_time).date != pd.DatetimeIndex(tr.exit_time).date).sum()) \
                    if len(tr) else 0
                rows[f"15m_{name}_{'tv_bug' if bug else 'fixed'}"] = {**s, "overnight_holds": overnight}
        tab = pd.DataFrame(rows).T[["trades", "overnight_holds", "net", "pf", "win_pct", "maxdd"]]
        self.md.append(md_table(tab.rename_axis("run")))
        print(tab.to_string())

    # -- grid + IS/OOS
    def grid(self, tf: int) -> pd.DataFrame:
        df = self.bars[tf]
        a_vals, c_vals, filters = grid_values()
        print(f"  running {len(a_vals) * len(c_vals) * len(filters)} settings on {tf}m ...")
        trades = grid_trades(df, self.base, a_vals, c_vals, filters)
        self.grids[tf] = trades
        days = np.array(sorted(set(df.index.date)))
        cut = pd.Timestamp(days[int(len(days) * self.cfg.is_frac)], tz=df.index.tz)
        rows = []
        for (a, c, f), tr in trades.items():
            et = pd.DatetimeIndex(tr.entry_time) if len(tr) else pd.DatetimeIndex([], tz=df.index.tz)
            s_all = stats(tr, self.cfg.capital)
            s_is = stats(tr[et < cut], self.cfg.capital)
            s_oos = stats(tr[et >= cut], self.cfg.capital)
            rows.append(dict(a=a, c=c, filter=f,
                             trades=s_all["trades"], net=s_all["net"], pf=s_all["pf"],
                             win_pct=s_all["win_pct"], maxdd=s_all["maxdd"],
                             is_trades=s_is["trades"], is_net=s_is["net"], is_pf=s_is["pf"],
                             oos_trades=s_oos["trades"], oos_net=s_oos["net"], oos_pf=s_oos["pf"]))
        g = pd.DataFrame(rows)
        g.to_csv(self.out / f"grid_{tf}m.csv", index=False)
        plots.pf_heatmap(g, f"{tf}m profit factor, full history, filter on", self.out / f"heatmap_pf_{tf}m.png")
        g.attrs["cut"] = cut
        return g

    def is_oos(self, tf: int, g: pd.DataFrame) -> tuple | None:
        cut = g.attrs["cut"]
        df = self.bars[tf]
        self.say(f"\n### {tf}m: in-sample {df.index[0]:%Y-%m-%d} → {cut:%Y-%m-%d} | "
                 f"out-of-sample {cut:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}\n")
        eligible = g[g.is_trades >= self.cfg.min_trades]
        if eligible.empty:
            self.say(f"No setting reaches {self.cfg.min_trades} in-sample trades; "
                     f"falling back to the best PF with any trade count (unreliable).")
            eligible = g[g.is_trades > 0]
        top = eligible.sort_values(["is_pf", "is_net"], ascending=False).head(10)
        self.md.append(md_table(top[["a", "c", "filter", "is_trades", "is_net", "is_pf",
                                     "oos_trades", "oos_net", "oos_pf"]], index=False))
        print(top.to_string(index=False))
        best = top.iloc[0]
        self.say(f"\nChosen in-sample: a={best.a:g}, c={best.c}, filter {'on' if best['filter'] else 'off'} "
                 f"→ IS PF {best.is_pf:.2f} ({best.is_trades} trades, ₹{best.is_net:,.0f}); "
                 f"**OOS PF {best.oos_pf:.2f} ({best.oos_trades} trades, ₹{best.oos_net:,.0f})**")
        rank = int((g.oos_pf.rank(ascending=False, method="min")[best.name]))
        self.say(f"Its out-of-sample PF rank among all {len(g)} settings: {rank}")
        self.say(f"Share of grid settings profitable: in-sample {(g.is_net > 0).mean():.0%}, "
                 f"out-of-sample {(g.oos_net > 0).mean():.0%}, full history {(g.net > 0).mean():.0%}")
        return (float(best.a), int(best.c), bool(best["filter"]))

    # -- walk-forward
    def walk_forward(self, tf: int) -> None:
        trades = self.grids[tf]
        df = self.bars[tf]
        tz = df.index.tz
        start, end = df.index[0].normalize(), df.index[-1]
        train, test = pd.Timedelta(days=self.cfg.wf_train_days), pd.Timedelta(days=self.cfg.wf_test_days)
        self.say(f"\n### {tf}m walk-forward (train {self.cfg.wf_train_days}d → test {self.cfg.wf_test_days}d, "
                 f"min {self.cfg.min_trades} training trades)\n")
        if start + train >= end:
            self.say("Not enough history for a single walk-forward window.")
            return
        entry = {k: pd.DatetimeIndex(v.entry_time) if len(v) else pd.DatetimeIndex([], tz=tz)
                 for k, v in trades.items()}
        rows, chained = [], []
        s = start
        while s + train < end:
            tr_end, te_end = s + train, min(s + train + test, end + pd.Timedelta(minutes=1))
            best, best_key = None, None
            for k, tr in trades.items():
                m = (entry[k] >= s) & (entry[k] < tr_end)
                st = stats(tr[m], self.cfg.capital)
                if st["trades"] < self.cfg.min_trades:
                    continue
                score = (st["pf"], st["net"])
                if best is None or score > best:
                    best, best_key = score, k
            if best_key is None:
                rows.append(dict(train_start=s, test_start=tr_end, test_end=te_end, a=np.nan, c=np.nan,
                                 filter="", train_pf=np.nan, test_trades=0, test_net=0.0, test_pf=np.nan))
            else:
                tr = trades[best_key]
                m = (entry[best_key] >= tr_end) & (entry[best_key] < te_end)
                test_tr = tr[m]
                chained.append(test_tr)
                st = stats(test_tr, self.cfg.capital)
                rows.append(dict(train_start=s, test_start=tr_end, test_end=te_end, a=best_key[0],
                                 c=best_key[1], filter=best_key[2], train_pf=best[0],
                                 test_trades=st["trades"], test_net=st["net"], test_pf=st["pf"]))
            s = s + test
        wf = pd.DataFrame(rows)
        wf.to_csv(self.out / f"walkforward_{tf}m.csv", index=False)
        self.md.append(md_table(wf, index=False))
        print(wf.to_string(index=False))
        if chained:
            ch = pd.concat(chained, ignore_index=True)
            ch.to_csv(self.out / f"trades_wf_{tf}m.csv", index=False)
            plots.equity_chart(ch, f"{tf}m walk-forward, chained out-of-sample", self.out / f"equity_wf_{tf}m.png")
            self.say(f"\n**Chained out-of-sample:** {one_line(stats(ch, self.cfg.capital))}")

    # -- cost sensitivity
    def cost_sensitivity(self, tf: int, setting: tuple, label: str) -> None:
        a, c, f = setting
        self.say(f"\n### Cost sensitivity: {tf}m a={a:g} c={c} filter {'on' if f else 'off'} ({label})\n")
        rows = []
        for slip in (0.5, 1, 2, 3):
            for cost in (40, 60, 100):
                s = stats(backtest(self.bars[tf], self.base.with_(a=a, c=c, use_filter=f,
                                                                  slippage_pts=slip, cost_per_order=cost)),
                          self.cfg.capital)
                rows.append(dict(slippage_pts=slip, cost_per_order=cost, trades=s["trades"], gross=s["gross"],
                                 costs=s["costs"], net=s["net"], pf=s["pf"]))
        tab = pd.DataFrame(rows)
        self.md.append(md_table(tab, index=False))
        print(tab.to_string(index=False))

    def write_md(self, header: str) -> Path:
        path = self.out / "summary.md"
        path.write_text(header + "\n\n" + "\n".join(self.md) + "\n", encoding="utf-8")
        return path
