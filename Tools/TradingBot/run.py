"""UT Bot + LinReg Candles NIFTY intraday backtester.

Examples
--------
  # Smoke test on Yahoo (~60 days of 5m bars), all experiments
  python run.py --yahoo --all

  # Full history from a CSV of 1m/5m bars, all experiments
  python run.py --csv data/NIFTY_1min.csv --all

  # One run with custom settings
  python run.py --csv data/NIFTY_1min.csv --tf 15 --a 3 --c 10 --nofilter
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime

from dotenv import load_dotenv

from src import data
from src.backtest import Params, yearly
from src.experiments import SHOW, Config, Runner, one_line


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="OHLC CSV (1m/5m/15m bars)")
    src.add_argument("--yahoo", action="store_true", help="Yahoo ^NSEI 5m, ~60 days (smoke test only)")
    ap.add_argument("--all", action="store_true", help="run every experiment in section 6")
    ap.add_argument("--tf", type=int, default=15, choices=[5, 15])
    ap.add_argument("--a", type=float, default=3.0)
    ap.add_argument("--c", type=int, default=10)
    ap.add_argument("--sig-len", type=int, default=7)
    ap.add_argument("--lr-len", type=int, default=11)
    ap.add_argument("--nofilter", action="store_true")
    ap.add_argument("--longonly", action="store_true")
    ap.add_argument("--lot", type=int, default=65)
    ap.add_argument("--cost", type=float, default=60.0, help="₹ per order")
    ap.add_argument("--slip", type=float, default=1.0, help="index points per fill")
    ap.add_argument("--capital", type=float, default=1_000_000)
    ap.add_argument("--tv-squareoff", action="store_true", help="replicate TradingView's overnight bug")
    ap.add_argument("--min-trades", type=int, help="min in-sample trades to select a setting "
                                                   "(default 100; 20 for --yahoo)")
    ap.add_argument("--wf-train-days", type=int, help="walk-forward train window (default 730; 28 for --yahoo)")
    ap.add_argument("--wf-test-days", type=int, help="walk-forward test window (default 182; 14 for --yahoo)")
    ap.add_argument("--tag", help="name used in output files for a single run")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raw = data.load_yahoo() if args.yahoo else data.load_csv(args.csv)
    raw = data.clean(raw)
    raw_tf = data.infer_bar_minutes(raw)
    tfs = [tf for tf in ((5, 15) if args.all else (args.tf,)) if tf >= raw_tf and tf % raw_tf == 0]
    if not tfs:
        raise SystemExit(f"Source bars are {raw_tf}m; can't build {args.tf}m bars from them")
    bars = {tf: data.resample(raw, tf) for tf in tfs}
    for tf, df in bars.items():
        print(data.summarize(df, tf))
    print()

    base = Params(a=args.a, c=args.c, sig_len=args.sig_len, lr_len=args.lr_len,
                  use_filter=not args.nofilter, allow_short=not args.longonly, lot=args.lot,
                  cost_per_order=args.cost, slippage_pts=args.slip, tv_squareoff=args.tv_squareoff)
    cfg = Config(capital=args.capital,
                 min_trades=args.min_trades or (20 if args.yahoo else 100),
                 wf_train_days=args.wf_train_days or (28 if args.yahoo else 730),
                 wf_test_days=args.wf_test_days or (14 if args.yahoo else 182))
    run = Runner(bars, base, cfg)

    if not args.all:
        tf = tfs[0]
        tag = args.tag or (f"{tf}m_a{args.a:g}_c{args.c}_{'nofilter' if args.nofilter else 'filter'}"
                           + ("_longonly" if args.longonly else "") + ("_tvbug" if args.tv_squareoff else ""))
        tr, s = run.run_one(tf, base, tag)
        print("ALL  ", one_line(s))
        print(f"      gross ₹{s['gross']:,.0f} | costs ₹{s['costs']:,.0f} | "
              f"long ₹{s['long_pnl']:,.0f} | short ₹{s['short_pnl']:,.0f}")
        y = yearly(tr, cfg.capital)
        if not y.empty:
            print("\n" + y[SHOW].to_string(float_format=lambda v: f"{v:,.2f}"))
        print(f"\nSaved results/trades_{tag}.csv, yearly_{tag}.csv, equity_{tag}.png")
        return

    source = "Yahoo ^NSEI 5m (~60 days, SMOKE TEST ONLY)" if args.yahoo else f"CSV {args.csv}"
    run.baselines()
    run.tv_bug_compare()
    run.say("\n## 2–3. Grid search and in-sample / out-of-sample\n")
    chosen = {}
    for tf in bars:
        g = run.grid(tf)
        chosen[tf] = run.is_oos(tf, g)
    run.say("\n## 4. Walk-forward\n")
    for tf in bars:
        run.walk_forward(tf)
    run.say("\n## 5. Cost sensitivity\n")
    if 15 in bars:
        run.cost_sensitivity(15, (3.0, 10, True), "TradingView best")
    for tf, setting in chosen.items():
        if setting and not (tf == 15 and setting == (3.0, 10, True)):
            run.cost_sensitivity(tf, setting, "in-sample choice")
    header = (f"# UT Bot + LinReg backtest results\n\nGenerated {datetime.now():%Y-%m-%d %H:%M}. "
              f"Source: {source}.\n\nDefaults: lot {base.lot}, ₹{base.cost_per_order:g}/order, "
              f"{base.slippage_pts:g} pt slippage per fill, capital ₹{cfg.capital:,.0f}, "
              f"entries 09:20–14:45, flat by 15:15.")
    path = run.write_md(header)
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
