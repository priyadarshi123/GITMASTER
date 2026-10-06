# Prompt: Build a Python backtester for the "UT Bot + LinReg Candles" NIFTY intraday strategy

Copy everything below the line into your VS Code AI assistant (Claude Code, Copilot Chat in Agent mode, Cursor, etc.).

---

You are helping me build and run a Python backtest of an intraday NIFTY strategy that I originally set up in TradingView. Build it as a small, clean project in this workspace, run it, and report results. Follow the specification below exactly. When a detail isn't specified, choose the more conservative (less optimistic) option and tell me what you chose.

## 1. Project setup

- Python 3.10+ with a virtual environment in `.venv`.
- Libraries: `pandas`, `numpy`, `matplotlib`, `yfinance`, `python-dotenv` (plus a broker SDK only if I choose one in section 2).
- Layout:
  ```
  data/            raw and cleaned OHLC files (git-ignored)
  src/data.py      loading, cleaning and resampling
  src/indicators.py ATR, UT Bot trailing stop, LinReg
  src/backtest.py  the execution engine and stats
  run.py           command-line entry point
  tests/           pytest checks for the indicators and engine
  results/         trades CSVs, charts, grid results
  ```
- Keep secrets (API keys) in `.env` and never print or commit them. Add `.env` and `data/` to `.gitignore`.

## 2. Data

The instrument is **NIFTY 50**. Futures (NIFTY continuous front month) are preferred; spot index data is acceptable for testing the signals. The target is **as many years of 1-minute (or 5-minute) bars as possible**, ideally 2015 to today.

Ask me which source to use, then write a loader for it:

1. **A local CSV I provide** (for example a Kaggle "NIFTY 50 minute data" dataset). Detect the column names automatically: `date`/`datetime`/`timestamp`, or separate `date` and `time` columns, plus `open`, `high`, `low`, `close` and optionally `volume`.
2. **A broker API**: Angel One SmartAPI, Upstox or Dhan historical candles, or Zerodha Kite Connect historical data (a paid add-on). These APIs limit how many days you can request per call, so loop over date chunks, respect rate limits, cache every chunk to `data/` and resume where it left off. For futures, stitch the monthly contracts into a continuous series and log the roll dates.
3. **Yahoo Finance fallback** (`yfinance`, ticker `^NSEI`). It only has about 60 days of 15-minute data, so use it only as a smoke test and warn me about that.

Cleaning rules:

- Convert every timestamp to `Asia/Kolkata`. Naive timestamps are already IST.
- Keep only regular session bars from 09:15 to 15:29 IST, and drop weekends and exchange holidays (days with no bars).
- Drop duplicate bars. Drop bars where high < low, or where open/close fall outside the high–low range, and log how many.
- Resample to the chosen timeframe with bars aligned to 09:15 (5m bars start at 09:15, 09:20, …; 15m at 09:15, 09:30, …). Use the resampling rule `offset="15min"`, `label="left"`, `closed="left"`, with first open, max high, min low, last close.
- Print a data summary: date range, number of trading days, bars per day (flag days with unusually few bars), and any gaps longer than 3 trading days.

## 3. Indicators

Match TradingView Pine Script v6 exactly. All indicators are calculated on the regular (not Heikin Ashi) close of the resampled bars.

### 3a. ATR (same as Pine `ta.atr(c)`)
- True range: `TR = max(high − low, |high − prev_close|, |low − prev_close|)`. On the first bar, `TR = high − low`.
- Wilder's smoothing (RMA): the first value is the simple average of the first `c` TR values; after that, `ATR[i] = (ATR[i−1]·(c−1) + TR[i]) / c`.
- When `c = 1`, ATR equals TR.

### 3b. UT Bot trailing stop (parameters: Key Value `a`, ATR period `c`)
```
src   = close
nLoss = a * ATR(c)
p     = trail[i-1] (0 on the first bar / while nLoss is NaN)
if   src[i] > p and src[i-1] > p:  trail[i] = max(p, src[i] - nLoss)
elif src[i] < p and src[i-1] < p:  trail[i] = min(p, src[i] + nLoss)
elif src[i] > p:                   trail[i] = src[i] - nLoss
else:                              trail[i] = src[i] + nLoss
```
- **UT Buy** on bar i: `src[i] > trail[i]` and `src[i-1] <= trail[i-1]` (close crosses above the trailing stop).
- **UT Sell** on bar i: `src[i] < trail[i]` and `src[i-1] >= trail[i-1]` (close crosses below the trailing stop).
- Calculate the crossovers on every bar. (In Pine v6, `and` is lazy, which broke the signals in my first TradingView version.)

### 3c. LinReg Candles trend filter (signal smoothing `sig_len`, regression length `lr_len`)
- `lr_close = linreg(close, lr_len, 0)`: the least-squares line fitted to the last `lr_len` closes, evaluated at the newest bar (same as Pine `ta.linreg(src, n, 0)`). Vectorise it with fixed convolution weights rather than calling polyfit in a loop.
- `lr_signal = SMA(lr_close, sig_len)`
- `bull = lr_close > lr_signal`, `bear = lr_close < lr_signal`

## 4. Trading rules (per bar, decided at the bar's close)

Parameters and defaults:

| Parameter | Default | Meaning |
|---|---|---|
| `timeframe` | 15 (minutes) | bar size; also test 5 |
| `a` | 3.0 | UT Key Value |
| `c` | 10 | UT ATR period |
| `sig_len` | 7 | LinReg signal smoothing |
| `lr_len` | 11 | LinReg length |
| `use_filter` | True | only enter in the LinReg trend direction |
| `allow_short` | True | if False, the strategy is long-only |
| `entry_window` | 09:20–14:45 IST | signal bar's start time must fall in this window to open a trade |
| `squareoff` | 15:15 IST | be flat at the open of the first bar starting at or after 15:15 |
| `lot` | 65 | NIFTY lot size, used for rupee P&L (1 lot per trade, no compounding) |
| `cost_per_order` | ₹60 | brokerage + STT + exchange fees + stamp duty, per order (each trade has 2 orders) |
| `slippage_pts` | 1.0 | index points against you on every fill |
| `capital` | ₹10,00,000 | starting equity, used for % returns and drawdown |

Logic (stop-and-reverse):

- **On a UT Buy:**
  - If the signal bar is inside the entry window and (`use_filter` is off, or `bull`): close any short and go long.
  - Otherwise, close any short but don't open a long.
- **On a UT Sell:**
  - If the signal bar is inside the entry window, `allow_short` is on, and (`use_filter` is off, or `bear`): close any long and go short.
  - Otherwise, close any long but don't open a short.
- **Only one position at a time**, always 1 lot, no pyramiding.
- **Fills:** a decision made at bar i's close fills at the **open of bar i+1**, adjusted by the slippage (buys at open + slippage, sells at open − slippage).
- **Square-off:** if bar i+1 starts at or after 15:15, close any open position at bar i+1's open and don't open anything new. **Never hold a position overnight.** If a day ends early (a data gap) with a position open, close it at the last bar's close and label the exit `EOD-gap`.
- Record every trade: entry/exit time, side, entry/exit price (after slippage), points, rupee P&L (`points × lot − 2 × cost_per_order`), and exit reason (`Reverse`, `Signal`, `EOD`, `EOD-gap`, `End`).

## 5. Results to report

For each run, report:

- Net P&L in ₹ and %, number of trades, win rate, profit factor, average P&L per trade.
- Average win vs average loss, largest win and largest loss.
- Maximum drawdown in ₹ and % (measured on closed-trade equity).
- Long vs short P&L.
- A **yearly breakdown** of every metric above.
- **Total costs** (commission + slippage) and **gross P&L before costs**, so I can see whether costs are what kill the edge.
- A buy-and-hold NIFTY comparison over the same period.

Save the following to `results/`:

- `trades_<tag>.csv`
- `equity_<tag>.png`: the cumulative P&L curve with drawdown shaded
- `yearly_<tag>.csv`

## 6. Experiments to run

1. **Baselines (full history):**
   - 5m, a=2, c=1, filter on (my original TradingView setting)
   - 5m, a=3, c=10, filter on
   - 15m, a=2, c=1, filter on
   - 15m, a=3, c=10, filter on (best in TradingView)
   - 15m, a=3, c=10, filter off
   - 15m, a=3, c=10, long-only
2. **Grid search** on 15m and on 5m:
   - `a` ∈ {1, 1.5, 2, 2.5, 3, 3.5, 4, 5}
   - `c` ∈ {1, 5, 10, 14, 20}
   - `use_filter` ∈ {True, False}
   - Save the results to `results/grid_<tf>.csv` and plot a heatmap of profit factor over `a` × `c` (filter on).
3. **In-sample / out-of-sample:** pick the best settings using only the first 70% of the history (ranked by profit factor, requiring at least 100 trades), then report those same settings on the last 30%, which they never saw. Also report what share of all grid settings are profitable in each period.
4. **Walk-forward:** use rolling 2-year windows to choose the best setting, then trade it for the following 6 months. Chain the out-of-sample 6-month results together and report them.
5. **Cost sensitivity** for the chosen setting: slippage 0.5, 1, 2 and 3 points, and cost per order ₹40, ₹60 and ₹100.

## 7. Correctness checks (write these as pytest tests)

- ATR with `c=1` equals the true range, and the RMA matches a hand-calculated example.
- `linreg` on a perfectly straight price series returns that series exactly.
- The UT trailing stop on a small hand-made series matches values calculated by hand.
- No trade enters with a signal bar outside 09:20–14:45, no position is ever held overnight, and every exit happens at or before 15:15.
- Entry and exit prices always equal the fill bar's open ± slippage (except `EOD-gap` and `End` exits).
- With zero costs and zero slippage, a strategy that buys and sells on random signals should have an average P&L close to zero.

## 8. Reference numbers from TradingView (NIFTY1! futures, 1 lot, ₹60 per order, 1-point slippage)

Use these as a sanity check. Don't expect an exact match: the data source differs, and TradingView's 15m results were affected by an overnight-hold bug (explained after the table).

| TF | a / c | Filter | Net P&L | PF | Win % | Trades | Period |
|---|---|---|---|---|---|---|---|
| 5m | 2 / 1 | on | −₹48,107 | 0.79 | 33% | 185 | Jun–Sep 2026 |
| 5m | 3 / 10 | on | −₹8,766 | 0.92 | 43% | 67 | Jun–Sep 2026 |
| 15m | 2 / 1 | on | +₹79,406 | 1.17 | 39% | 154 | Dec 2025–Sep 2026 |
| 15m | 3 / 10 | on | +₹1,81,304 | 1.91 | 53% | 92 | Dec 2025–Sep 2026 |
| 15m | 3 / 10 | off | +₹2,03,280 | 1.87 | 54% | 97 | Dec 2025–Sep 2026 |

**Known issue in the TradingView version:** its square-off window was 15:15–15:30. On 15-minute bars, the `close_all` order placed on the 15:15 bar filled at the **next morning's open**, so some 15m positions were held overnight. The Python version must square off at the 15:15 bar's open (section 4). Point out how much this change moves the 15m results.

## 9. Final output

Finish with a short written summary:

- Is there evidence of a real edge after costs?
- Do the out-of-sample and walk-forward results hold up?
- Which settings are robust, which are fragile, and how dependent are the results on market direction (trending vs choppy years, long vs short)?
- Include the key tables.

Don't overstate the conclusions: this is research, not a recommendation to trade.
