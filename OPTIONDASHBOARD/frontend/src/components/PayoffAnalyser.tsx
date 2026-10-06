import { useEffect, useMemo, useRef, useState } from "react";
import { fmtInr, fmtPrice, positionsApi, type PositionAnalysis } from "../api";

// ---- option maths (mirrors backend/options.py) -----------------------------------------------

const YEAR_MS = 365 * 86400_000;
const MIN_T = 1 / (365 * 24);           // one hour, as on the backend

function erf(x: number): number {       // Abramowitz–Stegun 7.1.26, |err| < 1.5e-7
  const s = Math.sign(x), a = Math.abs(x), t = 1 / (1 + 0.3275911 * a);
  const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-a * a);
  return s * y;
}
const ncdf = (x: number) => 0.5 * (1 + erf(x / Math.SQRT2));
const npdf = (x: number) => Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);

type ALeg = PositionAnalysis["legs"][number];

function bs(s: number, k: number, t: number, sigma: number, r: number, kind: "CE" | "PE") {
  if (sigma <= 0 || s <= 0) {
    const intr = kind === "CE" ? Math.max(0, s - k) : Math.max(0, k - s);
    return { price: intr, delta: kind === "CE" ? (s > k ? 1 : 0) : (s < k ? -1 : 0), gamma: 0, theta: 0, vega: 0 };
  }
  const st = sigma * Math.sqrt(t);
  const d1 = (Math.log(s / k) + (r + sigma * sigma / 2) * t) / st, d2 = d1 - st;
  const disc = Math.exp(-r * t);
  const decay = -s * npdf(d1) * sigma / (2 * Math.sqrt(t));
  return kind === "CE"
    ? { price: s * ncdf(d1) - k * disc * ncdf(d2), delta: ncdf(d1), gamma: npdf(d1) / (s * st),
        theta: (decay - r * k * disc * ncdf(d2)) / 365, vega: s * npdf(d1) * Math.sqrt(t) / 100 }
    : { price: k * disc * ncdf(-d2) - s * ncdf(-d1), delta: ncdf(d1) - 1, gamma: npdf(d1) / (s * st),
        theta: (decay + r * k * disc * ncdf(-d2)) / 365, vega: s * npdf(d1) * Math.sqrt(t) / 100 };
}

const pnlSign = (l: ALeg) => (l.side === "S" ? 1 : -1);          // + when the option falls in value
const intrinsic = (l: ALeg, s: number) => (l.kind === "CE" ? Math.max(0, s - l.strike) : Math.max(0, l.strike - s));
const expiryPnl = (legs: ALeg[], s: number, qty: number) =>
  legs.reduce((a, l) => a + pnlSign(l) * (l.entry_price - intrinsic(l, s)) * qty, 0);
const targetPnl = (legs: ALeg[], s: number, t: number, r: number, ivFallback: number, qty: number) =>
  legs.reduce((a, l) => a + pnlSign(l) * (l.entry_price - bs(s, l.strike, t, (l.iv ?? ivFallback) / 100, r, l.kind).price) * qty, 0);

/** Max profit / loss, breakevens and POP at expiry — same method as options.evaluate. */
function expiryMetrics(legs: ALeg[], spot: number, iv: number | null, t: number, r: number, qty: number) {
  const strikes = [...new Set(legs.map((l) => l.strike))].sort((a, b) => a - b);
  const farHi = Math.max(strikes[strikes.length - 1], spot) * 3;
  const xs = [0, ...strikes, farHi];
  const ys = xs.map((x) => expiryPnl(legs, x, 1));
  const slope = expiryPnl(legs, farHi + 1, 1) - ys[ys.length - 1];
  const unlimitedLoss = slope < -1e-9;
  const unlimitedProfit = slope > 1e-9;
  const breakevens: number[] = [];
  for (let i = 0; i < xs.length - 1; i++) {
    const [x1, y1, x2, y2] = [xs[i], ys[i], xs[i + 1], ys[i + 1]];
    if ((y1 < 0 && y2 >= 0) || (y1 > 0 && y2 <= 0)) if (y2 !== y1) breakevens.push(x1 + (-y1) * (x2 - x1) / (y2 - y1));
  }
  const bes = [...new Set(breakevens.map((b) => Math.round(b * 100) / 100))].sort((a, b) => a - b);
  let pop: number | null = null;
  if (iv) {
    const sigma = iv / 100, st = sigma * Math.sqrt(t), mu = Math.log(spot) + (r - sigma * sigma / 2) * t;
    const cdf = (x: number) => (x <= 0 ? 0 : !isFinite(x) ? 1 : ncdf((Math.log(x) - mu) / st));
    const edges = [0, ...bes, Infinity];
    pop = 0;
    for (let i = 0; i < edges.length - 1; i++) {
      const lo = edges[i], hi = edges[i + 1];
      const mid = isFinite(hi) ? (lo + hi) / 2 : lo * 1.5 + 1;
      if (expiryPnl(legs, mid, 1) > 0) pop += Math.max(0, cdf(hi) - cdf(lo));
    }
    pop = Math.round(pop * 1000) / 10;
  }
  return {
    maxProfit: unlimitedProfit ? null : Math.max(...ys) * qty,
    maxLoss: unlimitedLoss ? null : Math.min(...ys) * qty,
    breakevens: bes,
    pop,
  };
}

// ---- target dates ------------------------------------------------------------------------------

function targetDates(expiryAt: Date): { label: string; at: Date }[] {
  const now = new Date();
  const out = [{ label: "Now", at: now }];
  const d = new Date(now);
  d.setHours(15, 30, 0, 0);
  if (d <= now) d.setDate(d.getDate() + 1);
  while (d <= expiryAt) {
    out.push({ label: d.toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" }), at: new Date(d) });
    d.setDate(d.getDate() + 1);
  }
  return out;
}

// ---- component -------------------------------------------------------------------------------------

/** `id` analyses a recorded position; `load` analyses anything else (e.g. unsaved form legs). */
export default function PayoffAnalyser({ id, load, onClose }: {
  id?: number; load?: () => Promise<PositionAnalysis>; onClose: () => void;
}) {
  const [a, setA] = useState<PositionAnalysis | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    (load ? load() : positionsApi.analyse(id!)).then(setA).catch((e) => setError(String(e)));
  }, [id]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-start justify-center overflow-y-auto p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-5xl my-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-5 py-3 border-b border-slate-200">
          <h2 className="font-semibold text-slate-900">
            Analyse {a ? [a.symbol, a.strategy].filter(Boolean).join(" · ") : ""}
            {a && a.id == null && <span className="ml-2 text-xs font-normal px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">not saved</span>}
          </h2>
          {a && <span className="text-xs text-slate-500">exp {a.expiry} · {a.lots} × {a.lot_size} · chain {a.chain_timestamp}</span>}
          <button onClick={onClose} aria-label="Close" className="ml-auto w-8 h-8 rounded-full border border-slate-200 text-slate-600 hover:bg-slate-100">✕</button>
        </div>
        {error && <p className="p-5 text-sm text-red-600">{error}</p>}
        {!a && !error && <p className="p-5 text-sm text-slate-500">Loading live chain…</p>}
        {a && <Body a={a} />}
      </div>
    </div>
  );
}

type Tab = "summary" | "greeks" | "ivs";

function Body({ a }: { a: PositionAnalysis }) {
  const [on, setOn] = useState<Record<number, boolean>>(() => Object.fromEntries(a.legs.map((l) => [l.id, true])));
  const legs = a.legs.filter((l) => on[l.id]);
  const expiryAt = useMemo(() => new Date(a.expiry_at), [a.expiry_at]);
  const dates = useMemo(() => targetDates(expiryAt), [expiryAt]);
  const [dateIdx, setDateIdx] = useState(0);
  const [target, setTarget] = useState(a.spot);
  const [tab, setTab] = useState<Tab>("summary");

  const ivFallback = a.atm_iv ?? 20;
  const shortIvs = legs.filter((l) => l.side === "S" && l.iv).map((l) => l.iv!);
  const popIv = shortIvs.length ? shortIvs.reduce((x, y) => x + y, 0) / shortIvs.length : a.atm_iv;
  const tNow = Math.max((expiryAt.getTime() - Date.now()) / YEAR_MS, MIN_T);
  const tTarget = Math.max((expiryAt.getTime() - dates[dateIdx].at.getTime()) / YEAR_MS, MIN_T);
  const daysLeft = Math.max(0, Math.round((expiryAt.getTime() - dates[dateIdx].at.getTime()) / 86400_000));

  // price range: strikes and spot with some room either side
  const strikes = a.legs.map((l) => l.strike);
  const lo = Math.floor(Math.min(...strikes, a.spot) * 0.96);
  const hi = Math.ceil(Math.max(...strikes, a.spot) * 1.04);
  const step = Math.max(0.05, Math.round((hi - lo) / 400 * 20) / 20);

  const metrics = legs.length ? expiryMetrics(legs, a.spot, popIv, tNow, a.r, a.qty) : null;
  const atTarget = legs.length ? targetPnl(legs, target, tTarget, a.r, ivFallback, a.qty) : 0;
  const atExpiry = legs.length ? expiryPnl(legs, target, a.qty) : 0;
  const greeks = legs.reduce((g, l) => {
    const x = bs(target, l.strike, tTarget, (l.iv ?? ivFallback) / 100, a.r, l.kind);
    const m = -pnlSign(l) * a.qty;                         // long +qty, short −qty
    return { delta: g.delta + x.delta * m, gamma: g.gamma + x.gamma * m, theta: g.theta + x.theta * m, vega: g.vega + x.vega * m };
  }, { delta: 0, gamma: 0, theta: 0, vega: 0 });

  return (
    <div className="grid md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-5 p-5">
      <div className="space-y-4 min-w-0">
        <div className="flex items-baseline justify-between rounded-lg border border-slate-200 px-3 py-2">
          <span className="font-medium text-slate-800">{a.symbol} {fmtPrice(a.spot)}</span>
          <span className="text-xs text-slate-500">ATM IV {a.atm_iv ?? "—"}%</span>
        </div>

        <table className="w-full text-sm tabular-nums">
          <thead className="text-xs text-slate-500">
            <tr className="[&>th]:font-medium [&>th]:pb-1 [&>th]:text-left">
              <th>Leg</th><th className="!text-right">Entry</th><th className="!text-right">LTP</th>
            </tr>
          </thead>
          <tbody>
            {a.legs.map((l) => (
              <tr key={l.id} className={`[&>td]:py-1 ${on[l.id] ? "" : "text-slate-400"}`}>
                <td>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={on[l.id]} onChange={(e) => setOn({ ...on, [l.id]: e.target.checked })} />
                    <span className={`text-[11px] font-semibold px-1.5 rounded ${l.side === "S" ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700"}`}>{l.side}</span>
                    <span>{a.lots} × {l.strike} {l.kind}</span>
                  </label>
                </td>
                <td className="text-right">{l.entry_price.toFixed(2)}</td>
                <td className="text-right">{l.ltp?.toFixed(2) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {Object.values(on).some((v) => !v) && (
          <p className="text-xs text-amber-700">What-if: unticked legs are left out of the curves and numbers.</p>
        )}

        <div>
          <div className="flex border-b border-slate-200 text-sm">
            {(["summary", "greeks", "ivs"] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-3 py-1.5 -mb-px border-b-2 ${tab === t ? "border-blue-600 text-blue-700 font-medium" : "border-transparent text-slate-500"}`}>
                {t === "ivs" ? "IVs" : t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          <dl className="text-sm divide-y divide-slate-100 [&>div]:flex [&>div]:justify-between [&>div]:py-1.5 [&_dt]:text-slate-500 [&_dd]:tabular-nums">
            {tab === "summary" && (metrics ? (
              <>
                <div><dt>Max profit</dt><dd className="text-emerald-700">{metrics.maxProfit == null ? "Unlimited" : signed(metrics.maxProfit)}</dd></div>
                <div><dt>Max loss</dt><dd className="text-red-600">{metrics.maxLoss == null ? "Unlimited" : signed(metrics.maxLoss)}</dd></div>
                <div><dt>Breakeven at expiry</dt><dd>{metrics.breakevens.map((b) => b.toFixed(0)).join(", ") || "—"}</dd></div>
                <div><dt>Probability of profit</dt><dd>{metrics.pop != null ? `${metrics.pop}%` : "—"}</dd></div>
                <div><dt>P&L at {target.toFixed(0)} · {dates[dateIdx].label}</dt><dd className={tone(atTarget)}>{signed(atTarget)}</dd></div>
                {a.realized_legs !== 0 && <div><dt>Realised on closed legs</dt><dd className={tone(a.realized_legs)}>{signed(a.realized_legs)}</dd></div>}
              </>
            ) : <div><dt>Tick at least one leg</dt><dd /></div>)}
            {tab === "greeks" && (
              <>
                <div><dt>Delta (shares)</dt><dd>{greeks.delta.toFixed(1)}</dd></div>
                <div><dt>Gamma</dt><dd>{greeks.gamma.toFixed(3)}</dd></div>
                <div><dt>Theta (₹/day)</dt><dd className={tone(greeks.theta)}>{signed(greeks.theta)}</dd></div>
                <div><dt>Vega (₹ per 1 IV pt)</dt><dd className={tone(greeks.vega)}>{signed(greeks.vega)}</dd></div>
                <div><dt className="text-xs">at {target.toFixed(0)}, {daysLeft}d to expiry</dt><dd /></div>
              </>
            )}
            {tab === "ivs" && a.legs.map((l) => (
              <div key={l.id}><dt>{l.side === "S" ? "Sell" : "Buy"} {l.strike} {l.kind}</dt><dd>{l.iv != null ? `${l.iv.toFixed(1)}%` : "—"}</dd></div>
            ))}
          </dl>
        </div>
      </div>

      <div className="space-y-4 min-w-0">
        <div className="rounded-lg border border-slate-200 p-2">
          {legs.length
            ? <Chart legs={legs} a={a} lo={lo} hi={hi} t={tTarget} ivFallback={ivFallback} target={target}
                breakevens={metrics?.breakevens ?? []} atTarget={atTarget} atExpiry={atExpiry} />
            : <p className="text-sm text-slate-500 text-center py-24">Tick at least one leg.</p>}
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-600">{a.symbol} target</span>
            <button onClick={() => setTarget(a.spot)} className="text-xs text-blue-600">Reset</button>
            <span className="ml-auto text-xs text-slate-500 tabular-nums">{pct(target / a.spot - 1)}</span>
            <div className="flex items-center border border-slate-200 rounded">
              <button onClick={() => setTarget((v) => Math.max(lo, v - a.spot * 0.005))} className="px-2 text-slate-600">−</button>
              <input type="number" value={Math.round(target * 100) / 100} step={step}
                onChange={(e) => { const v = parseFloat(e.target.value); if (!Number.isNaN(v)) setTarget(v); }}
                className="w-24 text-center text-sm py-0.5 border-x border-slate-200 tabular-nums" />
              <button onClick={() => setTarget((v) => Math.min(hi, v + a.spot * 0.005))} className="px-2 text-slate-600">+</button>
            </div>
          </div>
          <input type="range" min={lo} max={hi} step={step} value={target}
            onChange={(e) => setTarget(parseFloat(e.target.value))} className="w-full accent-blue-600" />
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-600">Target date: {daysLeft}d to expiry</span>
            <button onClick={() => setDateIdx(0)} className="text-xs text-blue-600">Reset</button>
            <div className="ml-auto flex items-center gap-1">
              <button onClick={() => setDateIdx((i) => Math.max(0, i - 1))} className="px-1.5 border border-slate-200 rounded text-slate-600">‹</button>
              <span className="w-28 text-center tabular-nums">{dates[dateIdx].label}</span>
              <button onClick={() => setDateIdx((i) => Math.min(dates.length - 1, i + 1))} className="px-1.5 border border-slate-200 rounded text-slate-600">›</button>
            </div>
          </div>
          <input type="range" min={0} max={dates.length - 1} step={1} value={dateIdx}
            onChange={(e) => setDateIdx(parseInt(e.target.value))} className="w-full accent-blue-600" />
        </div>
        <p className="text-[11px] text-slate-400">
          Target-date curve is Black-Scholes with each leg's live IV held constant (r {(a.r * 100).toFixed(1)}%). Expiry curve is exact.
        </p>
      </div>
    </div>
  );
}

// ---- chart ---------------------------------------------------------------------------------------

const W = 640, H = 340, PL = 64, PR = 12, PT = 16, PB = 30;

function niceTicks(min: number, max: number, n: number): number[] {
  const raw = (max - min) / n;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const stepN = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out = [];
  for (let v = Math.ceil(min / stepN) * stepN; v <= max; v += stepN) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

function Chart({ legs, a, lo, hi, t, ivFallback, target, breakevens, atTarget, atExpiry }: {
  legs: ALeg[]; a: PositionAnalysis; lo: number; hi: number; t: number; ivFallback: number; target: number;
  breakevens: number[]; atTarget: number; atExpiry: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const N = 240;
  const xs = Array.from({ length: N + 1 }, (_, i) => lo + (hi - lo) * i / N);
  const exp = xs.map((x) => expiryPnl(legs, x, a.qty));
  const tgt = xs.map((x) => targetPnl(legs, x, t, a.r, ivFallback, a.qty));
  const all = [...exp, ...tgt, 0];
  let yMin = Math.min(...all), yMax = Math.max(...all);
  const pad = (yMax - yMin || 1) * 0.08;
  yMin -= pad; yMax += pad;

  const sx = (x: number) => PL + (x - lo) / (hi - lo) * (W - PL - PR);
  const sy = (y: number) => PT + (yMax - y) / (yMax - yMin) * (H - PT - PB);
  const line = (ys: number[]) => xs.map((x, i) => `${i ? "L" : "M"}${sx(x).toFixed(1)},${sy(ys[i]).toFixed(1)}`).join("");
  const area = `${line(exp)}L${sx(hi)},${sy(0)}L${sx(lo)},${sy(0)}Z`;
  const zeroY = sy(0);

  const px = hover ?? target;
  const hExp = hover == null ? atExpiry : expiryPnl(legs, px, a.qty);
  const hTgt = hover == null ? atTarget : targetPnl(legs, px, t, a.r, ivFallback, a.qty);

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = svgRef.current!.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width * W;
    if (x < PL || x > W - PR) return setHover(null);
    setHover(lo + (x - PL) / (W - PL - PR) * (hi - lo));
  };

  const cx = sx(px);
  const boxX = cx > W - 190 ? cx - 176 : cx + 8;

  return (
    <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full select-none" role="img"
      aria-label="Position payoff: on target date and at expiry" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <defs>
        <clipPath id="pa-above"><rect x={PL} y={0} width={W} height={Math.max(0, zeroY)} /></clipPath>
        <clipPath id="pa-below"><rect x={PL} y={zeroY} width={W} height={Math.max(0, H - zeroY)} /></clipPath>
      </defs>

      {niceTicks(yMin, yMax, 5).map((v) => (
        <g key={`y${v}`}>
          <line x1={PL} x2={W - PR} y1={sy(v)} y2={sy(v)} stroke={v === 0 ? "#94a3b8" : "#f1f5f9"} />
          <text x={PL - 6} y={sy(v) + 3} fontSize={10} fill="#64748b" textAnchor="end">{compact(v)}</text>
        </g>
      ))}
      {niceTicks(lo, hi, 6).map((v) => (
        <g key={`x${v}`}>
          <line x1={sx(v)} x2={sx(v)} y1={PT} y2={H - PB} stroke="#f1f5f9" />
          <text x={sx(v)} y={H - PB + 14} fontSize={10} fill="#64748b" textAnchor="middle">{v.toLocaleString("en-IN")}</text>
        </g>
      ))}
      <text x={12} y={(H - PB) / 2} fontSize={10} fill="#64748b" textAnchor="middle" transform={`rotate(-90 12 ${(H - PB) / 2})`}>P&L (₹)</text>

      <path d={area} fill="#16a34a" fillOpacity={0.12} clipPath="url(#pa-above)" />
      <path d={area} fill="#dc2626" fillOpacity={0.12} clipPath="url(#pa-below)" />

      {/* current spot */}
      <line x1={sx(a.spot)} x2={sx(a.spot)} y1={PT} y2={H - PB} stroke="#f59e0b" strokeDasharray="3 3" />
      <text x={sx(a.spot) + 3} y={PT + 9} fontSize={9} fill="#b45309">spot {a.spot.toFixed(0)}</text>
      {breakevens.filter((b) => b > lo && b < hi).map((b) => (
        <g key={`be${b}`}>
          <circle cx={sx(b)} cy={zeroY} r={3} fill="#fff" stroke="#475569" />
          <text x={sx(b)} y={zeroY - 6} fontSize={9} fill="#475569" textAnchor="middle">{b.toFixed(0)}</text>
        </g>
      ))}

      <path d={line(exp)} fill="none" stroke="#92400e" strokeWidth={2} strokeDasharray="7 3 2 3" />
      <path d={line(tgt)} fill="none" stroke="#3b82f6" strokeWidth={2} />

      {/* readout at hover (or target price) */}
      <line x1={cx} x2={cx} y1={PT} y2={H - PB} stroke="#334155" strokeWidth={1} />
      <circle cx={cx} cy={sy(hTgt)} r={3.5} fill="#3b82f6" />
      <circle cx={cx} cy={sy(hExp)} r={3.5} fill="#92400e" />
      <g transform={`translate(${boxX},${PT + 18})`}>
        <rect width={168} height={52} rx={4} fill="#fff" stroke="#e2e8f0" />
        <text x={8} y={16} fontSize={11} fill="#334155" fontWeight={600}>@ {px.toFixed(0)} ({pct(px / a.spot - 1)})</text>
        <text x={8} y={31} fontSize={11} fill="#3b82f6">Target date {signed(hTgt)}</text>
        <text x={8} y={45} fontSize={11} fill="#92400e">On expiry {signed(hExp)}</text>
      </g>
      <rect x={cx - 26} y={H - PB + 2} width={52} height={16} rx={3} fill="#334155" />
      <text x={cx} y={H - PB + 14} fontSize={10} fill="#fff" textAnchor="middle">{px.toFixed(0)}</text>
    </svg>
  );
}

// ---- formatting ------------------------------------------------------------------------------------

const signed = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${fmtInr(Math.abs(v))}`;
const tone = (v: number) => (v > 0 ? "text-emerald-700" : v < 0 ? "text-red-600" : "");
const pct = (v: number) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
const compact = (v: number) => (Math.abs(v) >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : Math.abs(v) >= 1e3 ? `${(v / 1e3).toFixed(1)}k` : v.toFixed(0));
