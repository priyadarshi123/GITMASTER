import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fmtInr, fmtPrice, optionsApi, suggestApi,
  type Analysis, type Chain, type ChainLeg, type CorpEvent, type Leg, type Signal, type StrategyResult,
} from "../api";
import { Card } from "./AnalysisSections";
import OISummary from "./OIAnalytics";
import { oiInfo, opt } from "../info";
import InfoTip, { type Info } from "./InfoTip";

export type Structure = "Bear Call" | "Bull Put" | "Iron Condor";
const STRUCTURES: Structure[] = ["Bear Call", "Bull Put", "Iron Condor"];
const ZONE = [5, 12];
const MAX_SHORT_DELTA = 0.3;

interface Props {
  symbol: string;
  a: Analysis;
  events: CorpEvent[];
  legs: Leg[];
  setLegs: (legs: Leg[]) => void;
  expiry: string | null;
  setExpiry: (e: string) => void;
}

export default function OptionBuilder({ symbol, a, events, legs, setLegs, expiry, setExpiry }: Props) {
  const navigate = useNavigate();
  const [chain, setChain] = useState<Chain | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const signal = a.summary.signal;
  const [mode, setMode] = useState<Structure>(signal === "Wait for confirmation" ? "Iron Condor" : (signal as Structure));

  const load = (exp?: string | null) => {
    setLoading(true);
    optionsApi.chain(symbol, exp ?? undefined)
      .then((c) => { setChain(c); setError(""); if (c.expiry !== exp) setExpiry(c.expiry); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(expiry); }, [symbol, expiry]);   // eslint-disable-line react-hooks/exhaustive-deps

  const toggleLeg = (kind: Leg["kind"], side: Leg["side"], strike: number, leg: ChainLeg | null) => {
    const i = legs.findIndex((l) => l.kind === kind && l.side === side && l.strike === strike);
    if (i >= 0) setLegs(legs.filter((_, j) => j !== i));
    else setLegs([...legs, { kind, side, strike, price: leg?.ltp ?? 0, lots: 1 }]);
  };

  const header = chain && (
    <span className="text-xs text-slate-500">
      Expiry {fmtDate(chain.expiry)} · CMP {fmtPrice(chain.underlying)} · lot {chain.lot_size ?? "?"} · NSE {chain.timestamp}{" "}
      <InfoTip info={opt.chain(chain)} />
    </span>
  );

  return (
    <Card title="Option chain — build your position" right={header}>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="text-xs px-2.5 py-1 rounded-md bg-slate-100">RSI signal: <b>{signal}</b></span>
        <span className="text-xs text-slate-500 ml-2">VALIDATE AS:</span>
        {STRUCTURES.map((s) => (
          <button key={s} onClick={() => setMode(s)}
            className={`px-3 py-1 text-xs rounded-md border ${mode === s ? "border-blue-600 text-blue-700 bg-blue-50 font-semibold" : "border-slate-200 text-slate-600"}`}>
            {s}
          </button>
        ))}
        {chain && (
          <button onClick={async () => {
              try {
                const sug = await suggestApi.get(symbol, mode, chain.expiry);
                setLegs(sug.legs.map(({ kind, side, strike, price }) => ({ kind, side, strike, price, lots: 1 })));
                setError("");
              } catch (e) { setError(String(e)); }
            }}
            className="px-3 py-1 text-xs rounded-md bg-ink text-white" title="Short strike just beyond the nearest S/R level in the 5–12% zone (delta ≤ 0.30), hedge two strikes further">
            ✨ Suggest strikes
          </button>
        )}
        {chain && <InfoTip info={opt.suggest()} />}
        <span className="ml-auto flex items-center gap-2">
          {chain && (
            <select value={chain.expiry} onChange={(e) => { setLegs([]); setExpiry(e.target.value); }}
              className="text-xs border border-slate-200 rounded-md px-2 py-1">
              {chain.expiries.map((e) => <option key={e} value={e}>{fmtDate(e)}</option>)}
            </select>
          )}
          <button onClick={() => load(expiry)} className="text-xs px-2 py-1 border border-slate-200 rounded-md" disabled={loading}>
            {loading ? "…" : "↻"}
          </button>
        </span>
      </div>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
      {!chain ? (
        <p className="text-sm text-slate-500">{loading ? "Loading NSE option chain…" : ""}</p>
      ) : (
        <>
          <div className="mb-4"><OISummary chain={chain} /></div>
          <div className="grid xl:grid-cols-[1fr_360px] gap-4">
            <ChainTable chain={chain} legs={legs} onToggle={toggleLeg} />
            <div className="space-y-3">
              <LegsPanel symbol={symbol} chain={chain} legs={legs} setLegs={setLegs} mode={mode} signal={signal} a={a} events={events} />
              {legs.length > 0 && (
                <div className="flex gap-2">
                  {(["real", "paper"] as const).map((b) => (
                    <button key={b}
                      onClick={() => navigate(`/positions/${b}?from=${encodeURIComponent(symbol)}&strategy=${encodeURIComponent(mode)}`)}
                      className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium ${b === "real" ? "bg-emerald-600 text-white" : "border border-slate-300 text-slate-700"}`}>
                      {b === "real" ? "Record position →" : "Paper trade →"}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-3">
            Use <b className="text-red-600">S</b> / <b className="text-emerald-600">B</b> on a premium to add a sell leg or buy hedge;
            press again to remove. Greeks are Black-Scholes on NSE IV; margin is an estimate.
          </p>
        </>
      )}
    </Card>
  );
}

// ---- chain table ---------------------------------------------------------------------------

function ChainTable({ chain, legs, onToggle }: {
  chain: Chain; legs: Leg[];
  onToggle: (kind: Leg["kind"], side: Leg["side"], strike: number, leg: ChainLeg | null) => void;
}) {
  const [all, setAll] = useState(false);
  const [metric, setMetric] = useState<"oi" | "oi_change">("oi");
  const spot = chain.underlying;
  const an = chain.analytics;
  const atmIdx = chain.rows.findIndex((r) => r.strike === an.atm);
  const rows = all ? chain.rows : chain.rows.slice(Math.max(0, atmIdx - 15), atmIdx + 16);
  const maxBar = Math.max(1, ...rows.flatMap((r) => [Math.abs(r.ce?.[metric] ?? 0), Math.abs(r.pe?.[metric] ?? 0)]));
  const callWalls = new Set(an.top_ce_oi.map((t) => t.strike));
  const putWalls = new Set(an.top_pe_oi.map((t) => t.strike));
  const has = (kind: Leg["kind"], side: Leg["side"], strike: number) =>
    legs.some((l) => l.kind === kind && l.side === side && l.strike === strike);
  const rowHasLeg = (strike: number) => legs.some((l) => l.strike === strike);

  const sb = (kind: Leg["kind"], strike: number, leg: ChainLeg | null) => (
    <span className="inline-flex gap-1">
      {(["S", "B"] as const).map((side) => (
        <button key={side} disabled={!leg?.ltp} onClick={() => onToggle(kind, side, strike, leg)}
          className={`w-6 h-6 text-[11px] font-bold rounded-md border disabled:opacity-20 ${
            has(kind, side, strike)
              ? side === "S" ? "bg-red-700 border-red-700 text-white" : "bg-blue-700 border-blue-700 text-white"
              : side === "S" ? "border-red-200 text-red-700 hover:bg-red-50" : "border-blue-200 text-blue-700 hover:bg-blue-50"
          }`}>
          {side}
        </button>
      ))}
    </span>
  );

  // OI (or ΔOI) value with a bar growing toward the strike column
  const bar = (leg: ChainLeg | null, side: "ce" | "pe", wall: boolean) => {
    const v = leg?.[metric] ?? 0;
    const w = (Math.abs(v) / maxBar) * 100;
    const fill = side === "ce"
      ? v < 0 ? "bg-red-100" : wall ? "bg-red-300" : "bg-red-200/80"
      : v < 0 ? "bg-emerald-100" : wall ? "bg-emerald-300" : "bg-emerald-200/80";
    return (
      <div className={`relative h-6 flex items-center ${side === "ce" ? "justify-end" : "justify-start"}`}
        title={`${side === "ce" ? "Call" : "Put"} ${metric === "oi" ? "OI" : "ΔOI"} ${v.toLocaleString("en-IN")} · ${leg?.buildup ?? "no change"}`}>
        <div className={`absolute inset-y-1 rounded ${fill} ${side === "ce" ? "right-0" : "left-0"}`} style={{ width: `${w}%` }} />
        <span className={`relative px-1.5 ${wall ? "font-semibold text-slate-900" : "text-slate-600"} ${v < 0 ? "text-red-600" : ""}`}>{fmtK(v)}</span>
      </div>
    );
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-2 text-xs">
        <span className="text-slate-500">Bars:</span>
        {(["oi", "oi_change"] as const).map((m) => (
          <button key={m} onClick={() => setMetric(m)}
            className={`px-2.5 py-1 rounded-md border ${metric === m ? "bg-blue-600 border-blue-600 text-white" : "border-slate-200 text-slate-600"}`}>
            {m === "oi" ? "Open interest" : "Change in OI"}
          </button>
        ))}
        <InfoTip info={oiInfo.bars(chain)} />
        <span className="ml-auto text-slate-400">darker bar = call/put wall · ◆ = max pain · hover a bar for build-up</span>
      </div>
      <div className="overflow-x-auto border border-slate-200 rounded-lg">
        <table className="w-full text-xs tabular-nums">
          <thead className="text-slate-500 text-[11px] uppercase tracking-wide">
            <tr>
              <th colSpan={5} className="py-1.5 text-center font-semibold text-red-800 bg-red-50/70">Calls</th>
              <th className="bg-slate-100" />
              <th colSpan={5} className="py-1.5 text-center font-semibold text-emerald-800 bg-emerald-50/70">Puts</th>
            </tr>
            <tr className="border-b border-slate-200 bg-slate-50 [&>th]:py-1.5 [&>th]:px-2 [&>th]:font-medium">
              <th className="text-left">Δ <InfoTip info={opt.delta(chain)} /></th>
              <th className="text-right">IV <InfoTip info={opt.iv(chain)} /></th>
              <th className="text-right">LTP <InfoTip info={opt.ltp(chain)} /></th>
              <th />
              <th className="text-right w-[22%]">{metric === "oi" ? "OI" : "ΔOI"} <InfoTip info={metric === "oi" ? opt.oi(chain) : opt.doi(chain)} /></th>
              <th className="text-center bg-slate-100">Strike</th>
              <th className="text-left w-[22%]">{metric === "oi" ? "OI" : "ΔOI"}</th>
              <th />
              <th className="text-left">LTP</th>
              <th className="text-left">IV</th>
              <th className="text-right">Δ</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const pct = (r.strike / spot - 1) * 100;
              const inZone = Math.abs(pct) >= ZONE[0] && Math.abs(pct) <= ZONE[1];
              const atm = r.strike === an.atm;
              const ceItm = r.strike < spot, peItm = r.strike > spot;
              const ce = ceItm ? "bg-amber-50/50" : "", pe = peItm ? "bg-amber-50/50" : "";
              return (
                <tr key={r.strike}
                  className={`border-b border-slate-100 [&>td]:py-0.5 [&>td]:px-2 ${rowHasLeg(r.strike) ? "bg-blue-50/60" : ""} ${atm ? "outline outline-1 outline-amber-400" : ""}`}>
                  <td className={`text-slate-500 ${ce}`}>{r.ce?.delta?.toFixed(2) ?? "—"}</td>
                  <td className={`text-right text-slate-500 ${ce}`}>{r.ce?.iv?.toFixed(1) ?? "—"}</td>
                  <td className={`text-right font-medium text-slate-900 ${ce}`}>{r.ce?.ltp != null ? `₹${r.ce.ltp.toFixed(2)}` : "—"}</td>
                  <td className={ce}>{sb("CE", r.strike, r.ce)}</td>
                  <td className={ce}>{bar(r.ce, "ce", callWalls.has(r.strike))}</td>
                  <td className={`text-center font-semibold whitespace-nowrap ${inZone ? "bg-violet-50 text-violet-800" : "bg-slate-50 text-slate-900"}`}>
                    {r.strike}{r.strike === an.max_pain ? " ◆" : ""}
                    <span className="block text-[10px] font-normal text-slate-400">{pct > 0 ? "+" : ""}{pct.toFixed(1)}%</span>
                  </td>
                  <td className={pe}>{bar(r.pe, "pe", putWalls.has(r.strike))}</td>
                  <td className={pe}>{sb("PE", r.strike, r.pe)}</td>
                  <td className={`font-medium text-slate-900 ${pe}`}>{r.pe?.ltp != null ? `₹${r.pe.ltp.toFixed(2)}` : "—"}</td>
                  <td className={`text-slate-500 ${pe}`}>{r.pe?.iv?.toFixed(1) ?? "—"}</td>
                  <td className={`text-right text-slate-500 ${pe}`}>{r.pe?.delta?.toFixed(2) ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-4 mt-2 text-[11px] text-slate-500">
        <button onClick={() => setAll(!all)} className="underline">{all ? "Show ATM ±15" : `Show all ${chain.rows.length} strikes`}</button>
        <span><span className="inline-block w-3 h-3 bg-violet-50 border border-violet-200 align-middle" /> 5–12% selling zone</span>
        <span><span className="inline-block w-3 h-3 bg-amber-50 border border-amber-200 align-middle" /> in the money</span>
        <span><span className="inline-block w-3 h-3 bg-blue-50 border border-blue-200 align-middle" /> row with your leg</span>
      </div>
    </div>
  );
}

// ---- legs + metrics + validation ----------------------------------------------------------

function LegsPanel({ symbol, chain, legs, setLegs, mode, signal, a, events }: {
  symbol: string; chain: Chain; legs: Leg[]; setLegs: (l: Leg[]) => void;
  mode: Structure; signal: Signal; a: Analysis; events: CorpEvent[];
}) {
  const [res, setRes] = useState<StrategyResult | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!legs.length) { setRes(null); return; }
    const t = window.setTimeout(() => {
      optionsApi.evaluate(symbol, chain.expiry, legs, chain.lot_size)
        .then((r) => { setRes(r); setErr(""); })
        .catch((e) => setErr(String(e)));
    }, 250);
    return () => window.clearTimeout(t);
  }, [symbol, chain.expiry, chain.lot_size, legs]);

  const checks = useMemo(() => validate(mode, signal, legs, chain, a, events, res), [mode, signal, legs, chain, a, events, res]);
  const update = (i: number, patch: Partial<Leg>) => setLegs(legs.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  if (!legs.length)
    return (
      <div className="border border-dashed border-slate-300 rounded-lg p-6 text-sm text-slate-500 h-fit">
        No legs yet. Add a <b>sell</b> leg and a <b>buy</b> hedge from the chain, or press <b>Suggest strikes</b>.
      </div>
    );

  return (
    <div className="space-y-3 h-fit xl:sticky xl:top-4">
      <table className="w-full text-xs">
        <thead className="text-slate-500"><tr className="[&>th]:text-left [&>th]:font-medium [&>th]:pb-1">
          <th>Leg</th><th>Strike</th><th>Price</th><th>Lots</th><th /></tr></thead>
        <tbody>
          {legs.map((l, i) => (
            <tr key={`${l.kind}${l.side}${l.strike}`} className="[&>td]:py-0.5">
              <td className={l.side === "S" ? "text-red-600 font-semibold" : "text-emerald-700 font-semibold"}>
                {l.side === "S" ? "Sell" : "Buy"} {l.kind}
              </td>
              <td>{l.strike}</td>
              <td><input type="number" step="0.05" value={l.price} onChange={(e) => update(i, { price: +e.target.value })}
                className="w-20 border border-slate-200 rounded px-1 py-0.5" /></td>
              <td><input type="number" min={1} value={l.lots} onChange={(e) => update(i, { lots: Math.max(1, +e.target.value) })}
                className="w-12 border border-slate-200 rounded px-1 py-0.5" /></td>
              <td><button onClick={() => setLegs(legs.filter((_, j) => j !== i))} className="text-slate-400 hover:text-red-600">✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {err && <p className="text-xs text-red-600">{err}</p>}
      {res && (
        <>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Metric info={opt.netCredit(res)} label={res.net_premium >= 0 ? "Net credit / lot" : "Net debit / lot"}
              value={fmtInr(Math.abs(res.net_premium_lot))} sub={`₹${Math.abs(res.net_premium).toFixed(2)}/share × ${res.lot_size}`} />
            <Metric info={opt.pop(res)} label="POP" value={res.pop != null ? `${res.pop}%` : "—"} sub={res.iv_used ? `IV ${res.iv_used}%` : undefined} />
            <Metric info={opt.maxProfit(res)} label="Max profit" value={res.max_profit == null ? "Unlimited" : fmtInr(res.max_profit)} tone="good" />
            <Metric info={opt.maxLoss(res)} label="Max loss" value={res.unlimited_loss ? "Unlimited" : fmtInr(Math.abs(res.max_loss ?? 0))} tone="bad"
              sub={res.risk_reward != null ? `reward:risk ${res.risk_reward}` : undefined} />
            <Metric info={opt.breakeven(res)} label="Breakeven(s)" value={res.breakevens.map((b) => b.toFixed(1)).join(" / ") || "—"}
              sub={res.breakeven_pct.map((p) => `${p > 0 ? "+" : ""}${p}%`).join(" / ")} />
            <Metric info={opt.margin(res)} label="Margin (est.)" value={fmtInr(res.margin.amount)}
              tone={res.within_cap ? "good" : "bad"}
              sub={`cap ${fmtInr(res.margin_cap)} (${res.margin_cap_pct}% of ${fmtInr(res.capital)})`} />
          </div>
          <div className="relative">
            <span className="absolute right-2 top-1.5"><InfoTip info={opt.payoff(res)} /></span>
            <Payoff res={res} legs={legs} />
          </div>
        </>
      )}

      <div className="space-y-1">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Validate as {mode} <InfoTip info={opt.checklist()} /></div>
        {checks.map((c, i) => (
          <div key={i} className="flex gap-2 text-xs">
            <span className={c.ok ? "text-emerald-600" : "text-amber-600"}>{c.ok ? "✓" : "⚠"}</span>
            <span className="text-slate-700">{c.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value, sub, tone, info }: { label: string; value: string; sub?: string; tone?: "good" | "bad"; info?: Info }) {
  const cls = tone === "good" ? "text-emerald-700" : tone === "bad" ? "text-red-600" : "text-slate-900";
  return (
    <div className="bg-slate-50 rounded-lg px-3 py-2">
      <div className="text-[11px] text-slate-500">{label} {info && <InfoTip info={info} />}</div>
      <div className={`font-semibold ${cls}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-400">{sub}</div>}
    </div>
  );
}

function Payoff({ res, legs }: { res: StrategyResult; legs: Leg[] }) {
  const W = 360, H = 140, P = 4;
  const xs = res.payoff.map((p) => p.x), ys = res.payoff.map((p) => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const yMax = Math.max(...ys.map(Math.abs), 1);
  const sx = (x: number) => P + ((x - x0) / (x1 - x0)) * (W - 2 * P);
  const sy = (y: number) => H / 2 - (y / yMax) * (H / 2 - P);
  const path = res.payoff.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full bg-slate-50 rounded-lg" role="img" aria-label="Payoff at expiry">
      <line x1={0} x2={W} y1={H / 2} y2={H / 2} stroke="#cbd5e1" />
      <line x1={sx(res.spot)} x2={sx(res.spot)} y1={0} y2={H} stroke="#f59e0b" strokeDasharray="3 3" />
      {legs.map((l) => (
        <line key={`${l.kind}${l.side}${l.strike}`} x1={sx(l.strike)} x2={sx(l.strike)} y1={0} y2={H}
          stroke={l.kind === "CE" ? "#c026d3" : "#0891b2"} strokeOpacity={0.35} />
      ))}
      <path d={path} fill="none" stroke="#1e293b" strokeWidth={2} />
      <text x={sx(res.spot) + 3} y={11} fontSize={9} fill="#b45309">CMP</text>
      <text x={P} y={H - 4} fontSize={9} fill="#64748b">−20%</text>
      <text x={W - P} y={H - 4} fontSize={9} fill="#64748b" textAnchor="end">+20%</text>
    </svg>
  );
}

// ---- validation ---------------------------------------------------------------

function validate(mode: Structure, signal: Signal, legs: Leg[], chain: Chain, a: Analysis,
  events: CorpEvent[], res: StrategyResult | null): { ok: boolean; text: string }[] {
  const out: { ok: boolean; text: string }[] = [];
  const spot = chain.underlying;
  const shorts = (k: Leg["kind"]) => legs.filter((l) => l.side === "S" && l.kind === k);
  const longs = (k: Leg["kind"]) => legs.filter((l) => l.side === "B" && l.kind === k);

  out.push(signal === mode
    ? { ok: true, text: `Matches the RSI signal (${signal})` }
    : { ok: false, text: `RSI signal is ${signal}, not ${mode}` });

  const needCalls = mode !== "Bull Put", needPuts = mode !== "Bear Call";
  if (needCalls) {
    const s = shorts("CE"), b = longs("CE");
    const hedged = s.length > 0 && b.some((h) => h.strike > Math.max(...s.map((x) => x.strike)));
    out.push({ ok: hedged, text: hedged ? "Call side: short call with a higher-strike hedge" : "Call side needs a sold CE and a bought CE above it" });
  }
  if (needPuts) {
    const s = shorts("PE"), b = longs("PE");
    const hedged = s.length > 0 && b.some((h) => h.strike < Math.min(...s.map((x) => x.strike)));
    out.push({ ok: hedged, text: hedged ? "Put side: short put with a lower-strike hedge" : "Put side needs a sold PE and a bought PE below it" });
  }
  if (!needCalls && shorts("CE").length) out.push({ ok: false, text: "Extra short call — not part of a Bull Put" });
  if (!needPuts && shorts("PE").length) out.push({ ok: false, text: "Extra short put — not part of a Bear Call" });

  for (const s of legs.filter((l) => l.side === "S")) {
    const pct = Math.abs(s.strike / spot - 1) * 100;
    const row = chain.rows.find((r) => r.strike === s.strike);
    const delta = Math.abs((s.kind === "CE" ? row?.ce?.delta : row?.pe?.delta) ?? 0);
    out.push({ ok: pct >= ZONE[0] && pct <= ZONE[1],
      text: `Short ${s.strike} ${s.kind} is ${pct.toFixed(1)}% from CMP ${pct < ZONE[0] ? "(inside 5% — close)" : pct > ZONE[1] ? "(beyond 12% — thin premium)" : "(in 5–12% zone)"}` });
    out.push({ ok: delta <= MAX_SHORT_DELTA, text: `Short ${s.strike} ${s.kind} delta ${delta.toFixed(2)} ${delta <= MAX_SHORT_DELTA ? "≤" : ">"} ${MAX_SHORT_DELTA}` });
    const levels = a.sr.levels.filter((l) => l.drawn && (s.kind === "CE" ? l.kind === "R" && l.price < s.strike : l.kind === "S" && l.price > s.strike));
    out.push({ ok: levels.length > 0, text: levels.length
      ? `${levels.length} ${s.kind === "CE" ? "resistance" : "support"} level(s) between CMP and ${s.strike}`
      : `No drawn ${s.kind === "CE" ? "resistance" : "support"} protects ${s.strike}` });
  }

  if (res) out.push({ ok: res.within_cap, text: `Margin ≈ ${fmtInr(res.margin.amount)} ${res.within_cap ? "within" : "exceeds"} the ${res.margin_cap_pct}% cap (${fmtInr(res.margin_cap)})` });
  const before = events.filter((e) => e.date <= chain.expiry);
  if (before.length) out.push({ ok: false, text: `Event before expiry: ${before.map((e) => `${e.purpose} ${fmtDate(e.date)}`).join("; ")}` });
  return out;
}

// ---- formatting ----------------------------------------------------------------------------

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "2-digit" });

function fmtK(v: number | null | undefined) {
  if (v == null) return "—";
  const a = Math.abs(v);
  return a >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : a >= 1e3 ? `${(v / 1e3).toFixed(1)}k` : String(v);
}

