// Source / fetch time / calculation text behind every ⓘ icon.
// Keep in sync with the backend: analysis.py, signals.py, options.py, positions.py.
import type { Analysis, Chain, Dashboard, Item, Position, PositionBook, StrategyResult } from "./api";
import type { Info } from "./components/InfoTip";

const NSE_CHAIN = "NSE option chain (nseindia.com) — free, about 1–3 min delayed; cached 60 s by the portal";
const CALC_LOCAL = (from: string) => `Calculated by the portal from ${from}`;
const chainFetched = (c: Pick<Chain, "fetched_at" | "timestamp">) => [
  { label: "Fetched from NSE", at: c.fetched_at },
  { label: "NSE data time", at: c.timestamp },
];

// ---- dashboard -----------------------------------------------------------------------------

export const dash = {
  price: (i: Item): Info => ({
    title: "Price & % change",
    source: i.source,
    fetched: [{ label: "Quote", at: i.quote_at }, { label: "Latest daily candle", at: i.last_bar }],
    calc: "Last traded price (during market hours, today's forming candle). % change = (price ÷ previous close − 1) × 100. Outside market hours it is the last close.",
  }),
  rsi: (i: Item): Info => ({
    title: "Weekly / daily RSI and signal",
    source: CALC_LOCAL(`daily candles (${i.source}), up to 5 years stored in the local database`),
    fetched: [{ label: "Computed", at: i.signal_at }, { label: "Candles", at: i.last_bar }],
    calc: "Wilder RSI(14) on daily closes (D) and on weekly bars Mon–Fri, current week included (W). Zones: < 40 bearish, > 60 bullish, else neutral. Signal: daily bearish & weekly not bullish → Bear Call; daily bullish & weekly not bearish → Bull Put; both neutral → Iron Condor; otherwise Wait for confirmation.",
  }),
  events: (d: Dashboard): Info => ({
    title: "Event badges",
    source: "NSE event calendar (board meetings) + NSE corporate actions",
    fetched: d.fetched.events ?? "once a day during the first refresh",
    calc: `Events dated between today and the next monthly expiry (${d.expiry}). R = results, A = AGM/EGM, D = dividend, B = bonus/split — matched by keywords in the NSE purpose text.`,
  }),
  page: (d: Dashboard): Info => ({
    title: "Dashboard data",
    source: `${d.provider.note}. Events and expiries from NSE.`,
    fetched: [{ label: "Last refresh", at: d.asof }, { label: "Expiry calendar", at: d.fetched.expiries }],
    calc: "Auto-refresh every 15 min during market hours (09:15–15:30) plus once after the close. Refresh now fetches immediately (returns cached data if under 2 min old). Next expiry comes from NSE's contract list.",
  }),
};

// ---- analysis ------------------------------------------------------------------------------

const candles = (a: Analysis) => [
  { label: "Last refresh", at: a.meta.refreshed_at },
  { label: "Candles", at: a.meta.last_bar },
  { label: "Computed", at: a.meta.computed_at },
];
const candleSrc = (a: Analysis) => CALC_LOCAL(`${a.meta.bars} daily candles ${a.meta.first_bar} → ${a.meta.last_bar} (${a.meta.source})`);

export const ana = {
  cmp: (a: Analysis): Info => ({
    title: "CMP",
    source: a.meta.source,
    fetched: [{ label: "Quote", at: a.quote?.updated_at }, { label: "Candles", at: a.meta.last_bar }],
    calc: "Latest traded price from the last refresh; the sub-line shows % change vs previous close and the date of the latest daily candle.",
  }),
  rsiW: (a: Analysis): Info => ({ title: "Weekly RSI (14)", source: candleSrc(a), fetched: candles(a),
    calc: "Daily candles grouped into Mon–Fri weeks (current week included), then Wilder's RSI over 14 weeks: 100 − 100 / (1 + avg gain / avg loss) with exponential (1/14) smoothing. Zone: < 40 bearish, > 60 bullish." }),
  rsiD: (a: Analysis): Info => ({ title: "Daily RSI (14)", source: candleSrc(a), fetched: candles(a),
    calc: "Wilder's RSI over the last 14 daily closes (same formula as TradingView). Zone: < 40 bearish, > 60 bullish." }),
  signal: (a: Analysis): Info => ({ title: "Signal", source: CALC_LOCAL("weekly and daily RSI"), fetched: candles(a),
    calc: "Daily zone triggers, weekly must not oppose: daily < 40 & weekly < 60 → Bear Call; daily > 60 & weekly > 40 → Bull Put; both 40–60 → Iron Condor; anything else → Wait for confirmation. Thresholds in config/settings.yaml." }),
  bb: (a: Analysis, tf: "weekly" | "daily"): Info => ({ title: `Bollinger Bands — ${tf}`, source: candleSrc(a), fetched: candles(a),
    calc: `On ${tf} closes: middle = 20-period simple average; upper/lower = middle ± 2 × standard deviation (population). % = (band ÷ CMP − 1) × 100.` }),
  prevMonth: (a: Analysis): Info => ({ title: "Previous month high / low", source: candleSrc(a), fetched: candles(a),
    calc: "Highest high and lowest low of the last completed calendar month (daily candles grouped by month). % from CMP alongside." }),
  confluence: (a: Analysis): Info => ({ title: "Reversal confluence score", source: candleSrc(a), fetched: candles(a),
    calc: "Counts how many of the 3 checks (Bollinger exhaustion, RSI divergence, candlestick pattern) are active in the same direction. 0 = no reversal evidence, 3 = strong." }),
  rsiChart: (a: Analysis, tf: "weekly" | "daily"): Info => ({ title: `${tf} RSI chart`, source: candleSrc(a), fetched: candles(a),
    calc: `RSI(14) on ${tf} bars; ${tf === "weekly" ? "3" : "2"} years shown. Green band above 60, red band below 40.` }),
  check: (a: Analysis, k: "bollinger" | "divergence" | "candlestick"): Info => ({
    title: { bollinger: "Bollinger exhaustion", divergence: "RSI divergence", candlestick: "Candlestick pattern" }[k],
    source: candleSrc(a), fetched: candles(a),
    calc: {
      bollinger: "Active if any of the last 3 daily closes is at/below the lower band (bullish exhaustion) or at/above the upper band (bearish). Bands: 20-day SMA ± 2σ. Intraday wicks don't count.",
      divergence: "Swing lows/highs = bar is the extreme of 5 bars before and 3 after. Bullish: price lower low but RSI(14) higher low between consecutive swings 5–60 bars apart; bearish: mirror. Active only if the second swing is within the last 20 bars; older ones (last 2 years) are counted.",
      candlestick: "Scans the last 10 days for hammer, shooting star, bullish/bearish engulfing, morning/evening star, piercing line, dark cloud cover. 'Quality' = after a 5-day move the other way and within 2% of the outer Bollinger Band.",
    }[k],
  }),
  squeeze: (a: Analysis): Info => ({ title: "Volatility squeeze (TTM-style)", source: candleSrc(a), fetched: candles(a),
    calc: "Squeeze ON when Bollinger Bands (20, 2σ) sit inside Keltner Channels (20-EMA ± 1.5 × ATR20). FIRED when the bands move back outside within the last 2 bars; direction = close above/below the 20-SMA. Checked on weekly and daily bars." }),
  sector: (a: Analysis): Info => ({ title: "Sector context",
    source: `NSE index history for ${a.sector?.index} (nseindia.com), mapped in config/settings.yaml → sector_indices`,
    fetched: [{ label: "Fetched from NSE", at: a.sector?.fetched_at }, { label: "Candles", at: a.sector?.last_bar }],
    calc: "Daily index candles grouped into months; Bollinger Bands (20, 2σ) on monthly closes; last 5 years shown. Refetched at most every 6 hours." }),
  sr: (a: Analysis): Info => ({ title: "Support / resistance levels", source: candleSrc(a), fetched: candles(a),
    calc: `Swing highs/lows on daily (3 bars each side), weekly (2) and monthly (2) bars over the selected ${a.sr.years}Y window. Swings within 0.3% are merged into one level (average price). Touches = distinct turning points (a daily and weekly swing within 10 days count once). Drawn if ≥ 2 touches and within 12% of CMP; legend lists levels within 15%. R = above CMP, S = below.` }),
  srOverlays: (a: Analysis): Info => ({ title: "Zone, gaps & lines", source: candleSrc(a), fetched: candles(a),
    calc: "5–12% zone = CMP × (1 ± 5%) to CMP × (1 ± 12%). Unfilled gap = a day whose low is ≥ 1.5% above the previous high (or high ≥ 1.5% below the previous low) and later prices never closed the gap; the box shows the unfilled part. Prev-month lines as in the chart summary. Strike lines come from the builder." }),
  notes: (): Info => ({ title: "Notes", source: "Your entries, stored in the local SQLite database (data/optiondash.db)", calc: "Shown newest first; the count appears as ✎ on the dashboard card." }),
};

// ---- option chain & builder ----------------------------------------------------------------

export const opt = {
  chain: (c: Chain): Info => ({ title: "Option chain", source: NSE_CHAIN, fetched: chainFetched(c),
    calc: `Expiry ${c.expiry}, lot size ${c.lot_size ?? "?"} from NSE's F&O market-lots file. Underlying ${c.underlying} as reported in the chain. ATM = strike closest to it.` }),
  oi: (c: Chain): Info => ({ title: "OI — open interest", source: NSE_CHAIN, fetched: chainFetched(c), calc: "Outstanding contracts at this strike, as published by NSE (no calculation)." }),
  doi: (c: Chain): Info => ({ title: "ΔOI — change in OI", source: NSE_CHAIN, fetched: chainFetched(c), calc: "Change in open interest versus the previous day's close, as published by NSE. Green = added, red = reduced." }),
  iv: (c: Chain): Info => ({ title: "IV — implied volatility", source: NSE_CHAIN, fetched: chainFetched(c), calc: "Annualised implied volatility (%) published by NSE for this option. Blank when the option hasn't traded." }),
  delta: (c: Chain): Info => ({ title: "Δ — delta", source: CALC_LOCAL("the NSE chain"), fetched: chainFetched(c),
    calc: "Black-Scholes delta: N(d1) for calls, N(d1) − 1 for puts, using the option's NSE IV (ATM IV if blank), the underlying price, time to expiry (to 15:30 on expiry day, calendar days ÷ 365) and a 6.5% risk-free rate (settings.yaml). Roughly the chance of finishing in the money." }),
  ltp: (c: Chain): Info => ({ title: "LTP — last traded price", source: NSE_CHAIN, fetched: chainFetched(c), calc: "Last traded premium per share, as published by NSE. Used as the default leg price (editable)." }),
  netCredit: (r: StrategyResult): Info => ({ title: "Net credit / debit", source: "Your leg prices", fetched: r.computed_at,
    calc: `Σ(sold premiums) − Σ(bought premiums) per share × lots; × lot size (${r.lot_size}) for the per-lot figure.` }),
  pop: (r: StrategyResult): Info => ({ title: "POP — probability of profit", source: CALC_LOCAL("the NSE chain"), fetched: [{ label: "Computed", at: r.computed_at }, { label: "Chain", at: r.chain_fetched_at }],
    calc: `Probability the underlying ends in the profitable range at expiry, assuming a lognormal price (Black-Scholes world) with volatility = average IV of the short strikes (${r.iv_used ?? "?"}%) and 6.5% drift. Model estimate, not a guarantee.` }),
  maxProfit: (r: StrategyResult): Info => ({ title: "Max profit", source: "Your legs", fetched: r.computed_at, calc: "Highest P&L of the expiry payoff (evaluated at every strike and far out). For credit spreads it equals the net credit." }),
  maxLoss: (r: StrategyResult): Info => ({ title: "Max loss", source: "Your legs", fetched: r.computed_at, calc: "Lowest P&L of the expiry payoff. For a spread = (strike gap − credit) × lot size × lots. 'Unlimited' if a short leg is unhedged on that side." }),
  breakeven: (r: StrategyResult): Info => ({ title: "Breakeven(s)", source: "Your legs", fetched: r.computed_at, calc: "Underlying prices at expiry where P&L crosses zero (linear interpolation between strikes). % = distance from the current price." }),
  margin: (r: StrategyResult): Info => ({ title: "Margin (estimate)", source: CALC_LOCAL("your legs; percentages in settings.yaml → options.margin"), fetched: r.computed_at,
    calc: `${r.margin.method}. Hedged structures ≈ |max loss| × 1.10; naked shorts ≈ (SPAN + exposure)% of notional (stocks 18% + 3.5%, indices 9% + 2%). The lower applicable figure is used. Cap = ${r.margin_cap_pct}% of capital ₹${r.capital.toLocaleString("en-IN")}.`,
    note: "Brokers compute margin with exact SPAN files — check yours before trading." }),
  payoff: (r: StrategyResult): Info => ({ title: "Payoff chart", source: "Your legs", fetched: r.computed_at, calc: "P&L at expiry (₹, all lots) for underlying prices from −20% to +20% of CMP. Orange = CMP; vertical lines = your strikes." }),
  suggest: (): Info => ({ title: "Suggest strikes", source: CALC_LOCAL("the NSE chain and the S/R levels"), calc: "For each side needed: the first OTM strike ≥ 5% from CMP that lies beyond the nearest drawn S/R level inside the 5–12% zone and has |delta| ≤ 0.30; hedge = two strikes further out." }),
  checklist: (): Info => ({ title: "Validation checklist", source: CALC_LOCAL("your legs, the chain, the S/R levels and NSE events"), calc: "Checks: RSI signal matches the structure · each short leg has a further-OTM hedge · short strikes 5–12% from CMP · short |delta| ≤ 0.30 · at least one drawn S/R level between CMP and the short strike · estimated margin within the cap · no corporate event on or before expiry." }),
};

export const oiInfo = {
  pcr: (c: Chain): Info => ({ title: "PCR (OI)", source: CALC_LOCAL("the NSE chain"), fetched: chainFetched(c), calc: "Total put OI ÷ total call OI across all strikes of this expiry. < 0.7 call-heavy (bearish tilt), > 1.3 put-heavy (bullish tilt)." }),
  pcrVol: (c: Chain): Info => ({ title: "PCR (volume)", source: CALC_LOCAL("the NSE chain"), fetched: chainFetched(c), calc: "Total put volume ÷ total call volume traded today for this expiry." }),
  maxPain: (c: Chain): Info => ({ title: "Max pain", source: CALC_LOCAL("the NSE chain"), fetched: chainFetched(c), calc: "For each strike K: Σ call OI × max(0, K − strike) + Σ put OI × max(0, strike − K). Max pain = the K with the smallest total (where option buyers lose most)." }),
  atmIv: (c: Chain): Info => ({ title: "ATM IV", source: NSE_CHAIN, fetched: chainFetched(c), calc: "Average of the call and put IV at the strike closest to the underlying." }),
  walls: (c: Chain): Info => ({ title: "Call / put walls", source: NSE_CHAIN, fetched: chainFetched(c), calc: "The three strikes with the highest call OI (resistance) and highest put OI (support)." }),
  dte: (c: Chain): Info => ({ title: "Days to expiry", source: "Expiry from NSE", fetched: chainFetched(c), calc: "Calendar days from now to 15:30 on expiry day." }),
  bars: (c: Chain): Info => ({ title: "OI by strike", source: NSE_CHAIN, fetched: chainFetched(c), calc: "Bars inside the chain: call OI grows left from the strike, put OI grows right, scaled to the largest value among the strikes shown (contracts, as published by NSE). Darker bar = one of the top-3 call/put walls; switch to Change in OI to see today's additions (light bar = reduced). Build-up on hover: price ↑ & OI ↑ long build-up, price ↓ & OI ↑ short build-up, price ↑ & OI ↓ short covering, price ↓ & OI ↓ long unwinding." }),
};

// ---- positions -----------------------------------------------------------------------------

const posFetched = (p: Position) => [
  { label: "Chain from NSE", at: p.chain_fetched_at },
  { label: "NSE data time", at: p.chain_timestamp },
];

export const posInfo = {
  pnl: (p: Position): Info => ({ title: "P&L", source: `${NSE_CHAIN}; entry prices from your record`, fetched: posFetched(p),
    calc: `Open legs: sold (entry − LTP) or bought (LTP − entry) × lot size ${p.lot_size} × lots ${p.lots}. Plus realised P&L of legs already closed. If a strike has no LTP, intrinsic value is used. Excludes brokerage and taxes.` }),
  stop: (p: Position): Info => ({ title: "% of stop used", source: CALC_LOCAL("live P&L / spot"), fetched: posFetched(p),
    calc: p.stop_rule === "breach"
      ? "Strike-breach rule: how far spot has travelled from the entry price toward the trigger (short strike − 0.5% for calls, + 0.5% for puts), worst short leg shown."
      : `Unrealised loss ÷ stop amount. Stop amount = ${p.stop_rule[0]} × credit of the open legs × lot size × lots. 0% while in profit.` }),
  credit: (p: Position): Info => ({ title: "Credit", source: "Your recorded entry prices", calc: "Σ sold − Σ bought entry prices of the open legs, per share; × lot size × lots for the total. Recomputed after Close legs." }),
  margin: (p: Position): Info => ({ title: "Margin", source: "Portal estimate saved at entry (editable via Edit entry)", fetched: p.opened_at, calc: "Same estimate as the builder: hedged ≈ |max loss| × 1.10, naked ≈ (SPAN + exposure)% of notional. Used for ROI." }),
  pop: (p: Position): Info => ({ title: "POP now / at entry", source: CALC_LOCAL("the NSE chain"), fetched: posFetched(p), calc: "Probability of profit at expiry (lognormal, short-strike IV) for the open legs at their entry prices — 'now' uses today's spot and IV, 'entry' was saved when recorded. Red if it dropped > 10 points." }),
  breakeven: (p: Position): Info => ({ title: "Breakevens", source: "Your open legs", calc: "Underlying prices at expiry where the open legs' P&L is zero." }),
  spot: (p: Position): Info => ({ title: "Spot", source: NSE_CHAIN, fetched: posFetched(p), calc: "Underlying price reported in the NSE chain; move % = (spot ÷ spot at entry − 1) × 100. Nearest short = smallest distance from spot to a short strike." }),
  roi: (b: PositionBook): Info => ({ title: "ROI", source: "Your positions (local database) + live P&L of open ones", fetched: b.valued_at,
    calc: "Per month: realised = P&L of positions closed that month; unrealised = live P&L of open positions (current month); margin = margin of those positions. ROI = (realised + unrealised) ÷ margin. Year = sum of its months. Excludes charges." }),
};
