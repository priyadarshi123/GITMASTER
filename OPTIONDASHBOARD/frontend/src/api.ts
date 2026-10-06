export type Signal = "Bear Call" | "Bull Put" | "Iron Condor" | "Wait for confirmation";

export interface CorpEvent {
  kind: "R" | "A" | "D" | "B";
  date: string;
  purpose: string;
}

export interface Item {
  rank: number;
  symbol: string;
  name: string;
  sector: string;
  kind: "index" | "stock";
  ltp: number | null;
  change_pct: number | null;
  rsi_w: number | null;
  rsi_d: number | null;
  signal: Signal | null;
  events: CorpEvent[];
  bookmarked: boolean;
  notes: number;
  source: string;
  quote_at: string | null;
  last_bar: string | null;
  signal_at: string | null;
}

export interface RefreshState {
  running: boolean;
  step: string;
  error: string;
}

export interface Dashboard {
  items: Item[];
  expiry: string;
  asof: string | null;
  provider: { name: string; live: boolean; note: string };
  refresh: RefreshState;
  market_open: boolean;
  fetched: { events: string | null; expiries: string | null };
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  dashboard: () => call<Dashboard>("/api/dashboard"),
  status: () => call<{ refresh: RefreshState; asof: string | null }>("/api/status"),
  refresh: () => call<{ started: boolean; reason?: string }>("/api/refresh", { method: "POST" }),
  toggleBookmark: (symbol: string) =>
    call<{ bookmarked: boolean }>(`/api/bookmarks/${encodeURIComponent(symbol)}`, { method: "POST" }),
};

export const EVENT_LABEL: Record<CorpEvent["kind"], string> = {
  R: "Results",
  A: "AGM / EGM",
  D: "Dividend",
  B: "Bonus / Split",
};

export const fmtPrice = (v: number | null) =>
  v == null ? "—" : "₹" + v.toLocaleString("en-IN", { maximumFractionDigits: v >= 1000 ? 1 : 2 });

export const fmtTime = (iso: string | null) =>
  iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false }) : "—";

// ---- analysis (Step 2) -----------------------------------------------------------

export interface PricePct { price: number; pct: number }
export type Zone = "bearish" | "bullish" | "neutral";

export interface Check {
  pass: boolean;
  direction: "bullish" | "bearish" | null;
  title: string;
  detail: string;
  items?: unknown[];
}

export interface Squeeze { state: "off" | "on" | "fired"; direction?: "up" | "down"; bars?: number }

export interface SRLevel {
  price: number;
  kind: "R" | "S";
  pct: number;
  tfs: string;
  touches: number;
  multi_tf: boolean;
  drawn: boolean;
  points: { date: string; price: number; tfs: string }[];
}

export interface Gap { date: string; kind: "up" | "down"; bottom: number; top: number }

export interface Candle {
  time: string; open: number; high: number; low: number; close: number;
  bb_upper: number | null; bb_mid: number | null; bb_lower: number | null;
}

export interface Analysis {
  instrument: { symbol: string; name: string; sector: string; kind: string };
  quote: { ltp: number; change_pct: number; updated_at: string } | null;
  summary: {
    cmp: number;
    date: string;
    signal: Signal;
    rsi: Record<"weekly" | "daily", { rsi: number; zone: Zone; rule: string }>;
    bb_weekly: Record<"upper" | "mid" | "lower", PricePct>;
    bb_daily: Record<"upper" | "mid" | "lower", PricePct>;
    prev_month: { month: string; high: PricePct; low: PricePct };
    confluence: { score: number; verdict: string };
  };
  confluence: {
    score: number;
    direction: "bullish" | "bearish" | null;
    verdict: string;
    checks: Record<"bollinger" | "divergence" | "candlestick", Check>;
    squeeze: Record<"weekly" | "daily", Squeeze>;
    meaning: string;
  };
  rsi_charts: Record<"weekly" | "daily", { time: string; value: number }[]>;
  sr: { tf: "D" | "W" | "M"; years: number; candles: Candle[]; levels: SRLevel[]; gaps: Gap[]; zone_pct: [number, number] };
  sector: { sector: string; index: string; candles: Candle[]; fetched_at: string | null; last_bar: string } | null;
  meta: { source: string; last_bar: string; first_bar: string; bars: number; refreshed_at: string | null; computed_at: string };
}

export interface Note { id: number; symbol: string; note_date: string; text: string; updated_at: string }

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const analysisApi = {
  get: (symbol: string, years: number, tf: string) =>
    call<Analysis>(`/api/analysis/${encodeURIComponent(symbol)}?years=${years}&tf=${tf}`),
  notes: (symbol: string) => call<Note[]>(`/api/notes/${encodeURIComponent(symbol)}`),
  addNote: (symbol: string, text: string) =>
    call<{ id: number }>(`/api/notes/${encodeURIComponent(symbol)}`, { method: "POST", ...json({ text }) }),
  editNote: (id: number, text: string) => call(`/api/notes/id/${id}`, { method: "PUT", ...json({ text }) }),
  deleteNote: (id: number) => call(`/api/notes/id/${id}`, { method: "DELETE" }),
};

// ---- option chain + strategy (phase 3) ------------------------------------------------

export interface ChainLeg {
  ltp: number | null; change: number | null; bid: number | null; ask: number | null;
  iv: number | null; oi: number | null; oi_change: number | null; volume: number | null;
  delta?: number | null; gamma?: number | null; theta?: number | null; vega?: number | null;
  buildup?: string | null;
}

export interface ChainRow { strike: number; ce: ChainLeg | null; pe: ChainLeg | null }

export interface Chain {
  symbol: string;
  expiry: string;
  expiries: string[];
  underlying: number;
  timestamp: string;
  lot_size: number | null;
  is_index: boolean;
  fetched_at: string;
  rows: ChainRow[];
  analytics: {
    spot: number; atm: number; atm_iv: number | null; pcr_oi: number | null; pcr_volume: number | null;
    max_pain: number | null; total_ce_oi: number; total_pe_oi: number;
    top_ce_oi: { strike: number; oi: number }[]; top_pe_oi: { strike: number; oi: number }[];
    days_to_expiry: number;
  };
}

export interface Leg { kind: "CE" | "PE"; side: "S" | "B"; strike: number; price: number; lots: number }

export interface StrategyResult {
  net_premium: number; net_premium_lot: number;
  max_profit: number | null; max_loss: number | null; unlimited_loss: boolean;
  breakevens: number[]; breakeven_pct: number[];
  pop: number | null; risk_reward: number | null;
  margin: { amount: number; method: string };
  payoff: { x: number; y: number }[];
  spot: number; iv_used: number | null; lot_size: number;
  capital: number; margin_cap: number; margin_cap_pct: number; within_cap: boolean;
  computed_at: string; chain_fetched_at: string; chain_timestamp: string;
}

export const optionsApi = {
  chain: (symbol: string, expiry?: string) =>
    call<Chain>(`/api/chain/${encodeURIComponent(symbol)}${expiry ? `?expiry=${expiry}` : ""}`),
  evaluate: (symbol: string, expiry: string, legs: Leg[], lot_size?: number | null) =>
    call<StrategyResult>(`/api/strategy/${encodeURIComponent(symbol)}`,
      { method: "POST", ...json({ expiry, legs, lot_size }) }),
};

export const fmtInr = (v: number | null | undefined) =>
  v == null ? "—" : "₹" + (Math.round(v) || 0).toLocaleString("en-IN");   // || 0 avoids "-0"

// ---- positions (phase 4) -----------------------------------------------------------------

export type Book = "real" | "paper";
export type StopRule = "1x" | "2x" | "3x" | "breach";

export interface PosLeg {
  id: number; kind: "CE" | "PE"; side: "S" | "B"; strike: number; entry_price: number;
  exit_price: number | null; closed_at: string | null; ltp?: number | null; pnl?: number;
}

export interface Position {
  id: number; book: Book; symbol: string; strategy: string; expiry: string;
  lots: number; lot_size: number; capital: number | null; risk_pct: number | null;
  stop_rule: StopRule; note: string | null; entry_spot: number | null; entry_pop: number | null;
  margin: number | null; status: "open" | "closed"; opened_at: string; closed_at: string | null;
  realized_pnl: number | null; legs: PosLeg[];
  credit_share: number; credit_lot: number; credit_total: number; max_loss_total: number | null;
  breakevens: number[]; stop_loss: number | null; realized_legs: number;
  spot?: number | null; unrealized?: number; pnl?: number; spot_move_pct?: number;
  stop_used_pct?: number | null; nearest_short_pct?: number; pop_now?: number | null;
  expired?: boolean; error?: string; chain_fetched_at?: string; chain_timestamp?: string;
}

export interface RoiRow {
  month?: string; year?: string; margin: number; realized: number; unrealized: number;
  total: number; roi_pct: number | null; trades: number;
}

export interface PositionBook {
  open: Position[]; closed: Position[];
  roi: { monthly: RoiRow[]; annual: RoiRow[] };
  freshness: { tag: string; updated: string };
  valued_at: string;
  capital: { default?: number; risk_per_trade_pct?: number; margin_cap_pct?: number };
}

export interface PositionInput {
  book: Book; symbol: string; strategy: string; expiry: string; lots: number; lot_size: number;
  capital: number | null; risk_pct: number | null; stop_rule: StopRule; note: string | null;
  margin?: number | null; opened_at?: string | null;
  legs: { kind: "CE" | "PE"; side: "S" | "B"; strike: number; price: number }[];
}

export const positionsApi = {
  book: (book: Book) => call<PositionBook>(`/api/positions?book=${book}`),
  contract: (symbol: string) =>
    call<{ symbol: string; expiries: { date: string; lot_size: number | null }[] }>(`/api/contract/${encodeURIComponent(symbol)}`),
  create: (p: PositionInput) => call<{ id: number }>("/api/positions", { method: "POST", ...json(p) }),
  update: (id: number, p: PositionInput) => call(`/api/positions/${id}`, { method: "PUT", ...json(p) }),
  close: (id: number, realized_pnl: number) =>
    call(`/api/positions/${id}/close`, { method: "POST", ...json({ realized_pnl }) }),
  closeLegs: (id: number, exits: Record<number, number>) =>
    call(`/api/positions/${id}/close-legs`, { method: "POST", ...json({ exits }) }),
  remove: (id: number) => call(`/api/positions/${id}`, { method: "DELETE" }),
  analyse: (id: number) => call<PositionAnalysis>(`/api/positions/${id}/analyse`),
  analyseDraft: (symbol: string, d: Pick<PositionInput, "expiry" | "lots" | "lot_size" | "strategy" | "legs">) =>
    call<PositionAnalysis>(`/api/analyse/${encodeURIComponent(symbol)}`, { method: "POST", ...json(d) }),
};

export interface PositionAnalysis {
  id: number | null; book: Book | null; symbol: string; strategy: string | null; expiry: string; expiry_at: string;
  lots: number; lot_size: number; qty: number; spot: number; atm_iv: number | null; r: number;
  realized_legs: number;
  legs: { id: number; kind: "CE" | "PE"; side: "S" | "B"; strike: number; entry_price: number; ltp: number | null; iv: number | null }[];
  chain_timestamp: string; chain_fetched_at: string;
}

export interface SuggestedLeg extends Leg { delta: number | null; iv: number | null; oi: number | null; pct: number }

export interface Suggestion {
  symbol: string; strategy: string; expiry: string; spot: number; lot_size: number | null;
  legs: SuggestedLeg[]; notes: string[]; chain_fetched_at: string; chain_timestamp: string;
}

export const suggestApi = {
  get: (symbol: string, strategy: string, expiry?: string | null) =>
    call<Suggestion>(`/api/suggest/${encodeURIComponent(symbol)}?strategy=${encodeURIComponent(strategy)}${expiry ? `&expiry=${expiry}` : ""}`),
};

// ---- alerts (phase 5) ------------------------------------------------------------------------

export interface AlertLog { at: string; kind: "summary" | "stop" | "test"; ok: boolean; error: string | null; text: string }

export interface AlertStatus {
  enabled: boolean; configured: boolean; token_set: boolean; chat_id: string | null;
  summary_times: string[]; stop_levels: number[]; stop_check_min: number; books: Book[];
  log: AlertLog[];
}

export const alertsApi = {
  status: () => call<AlertStatus>("/api/alerts"),
  test: () => call<{ ok: boolean; error: string | null }>("/api/alerts/test", { method: "POST" }),
  summary: () => call<{ ok: boolean; error: string | null }>("/api/alerts/summary", { method: "POST" }),
  checkStops: () => call<{ sent: { id: number; level: number; ok: boolean; error: string | null }[] }>("/api/alerts/check-stops", { method: "POST" }),
};
