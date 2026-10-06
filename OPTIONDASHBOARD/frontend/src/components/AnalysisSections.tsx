import type { ReactNode } from "react";
import { fmtPrice, type Analysis, type Check, type PricePct, type Squeeze, type Zone } from "../api";
import { ana } from "../info";
import { PriceChart, RsiChart } from "./charts";
import InfoTip, { type Info } from "./InfoTip";

export function Card({ title, hint, right, info, children }: {
  title: ReactNode; hint?: string; right?: ReactNode; info?: Info; children: ReactNode;
}) {
  return (
    <section className="bg-white border border-slate-200 rounded-xl p-5 break-inside-avoid">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-4">
        <h2 className="text-sm font-semibold tracking-wide text-slate-700 uppercase">
          {title}{info && <> <InfoTip info={info} /></>}
        </h2>
        {hint && <span className="text-xs text-slate-400">{hint}</span>}
        {right && <div className="ml-auto">{right}</div>}
      </div>
      {children}
    </section>
  );
}

const ZONE_STYLE: Record<Zone, string> = {
  bearish: "bg-red-50 text-red-700",
  bullish: "bg-emerald-50 text-emerald-700",
  neutral: "bg-blue-50 text-blue-700",
};

export function ZoneChip({ zone }: { zone: Zone }) {
  return (
    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${ZONE_STYLE[zone]}`}>
      ● {zone[0].toUpperCase() + zone.slice(1)}
    </span>
  );
}

const pp = (v: PricePct) => (
  <>
    {fmtPrice(v.price)} <span className="text-slate-400">({v.pct > 0 ? "+" : ""}{v.pct}%)</span>
  </>
);

// ---- chart summary ----------------------------------------------------------------

export function ChartSummary({ a }: { a: Analysis }) {
  const s = a.summary;
  const bbRow = (label: string, bb: typeof s.bb_daily, info: Info) => (
    <Row label={label} info={info}>
      upper {pp(bb.upper)} · mid {pp(bb.mid)} · lower {pp(bb.lower)}
    </Row>
  );
  return (
    <Card title="Chart summary" hint="RSI zones · Bollinger Bands (20, 2σ) · previous month · confluence">
      <div className="space-y-2 mb-4">
        {(["weekly", "daily"] as const).map((tf) => (
          <div key={tf} className="flex items-center gap-6 bg-slate-50 rounded-lg px-4 py-2.5 text-sm">
            <span className="font-semibold w-20 capitalize">{tf} <InfoTip info={tf === "weekly" ? ana.rsiW(a) : ana.rsiD(a)} /></span>
            <span className="tabular-nums">RSI {s.rsi[tf].rsi}</span>
            <span className="text-slate-500">{s.rsi[tf].rule}</span>
            <span className="ml-auto"><ZoneChip zone={s.rsi[tf].zone} /></span>
          </div>
        ))}
      </div>
      <div className="text-sm space-y-1.5">
        {bbRow("BB weekly", s.bb_weekly, ana.bb(a, "weekly"))}
        {bbRow("BB daily", s.bb_daily, ana.bb(a, "daily"))}
        <Row label="Prev month" info={ana.prevMonth(a)}>
          high {pp(s.prev_month.high)} · low {pp(s.prev_month.low)} · {s.prev_month.month}
        </Row>
        <Row label="Confluence" info={ana.confluence(a)}>{s.confluence.score}/3 — {s.confluence.verdict.toLowerCase()}</Row>
      </div>
    </Card>
  );
}

function Row({ label, info, children }: { label: string; info?: Info; children: ReactNode }) {
  return (
    <div className="flex gap-4">
      <span className="w-32 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-400 pt-0.5">
        {label} {info && <InfoTip info={info} />}
      </span>
      <span className="text-slate-700">{children}</span>
    </div>
  );
}

// ---- RSI charts -----------------------------------------------------------------------

export function RsiCharts({ a }: { a: Analysis }) {
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <Card title="Weekly RSI (14) — 3 years" info={ana.rsiChart(a, "weekly")}>
        <RsiChart data={a.rsi_charts.weekly} color="#d97706" />
      </Card>
      <Card title="Daily RSI (14) — 2 years" info={ana.rsiChart(a, "daily")}>
        <RsiChart data={a.rsi_charts.daily} color="#2563eb" />
      </Card>
    </div>
  );
}

// ---- reversal confluence ----------------------------------------------------------------

function SqueezeBanner({ tf, sq, info }: { tf: string; sq: Squeeze; info: Info }) {
  if (sq.state === "fired")
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 text-red-800 px-4 py-2.5 text-sm font-semibold">
        <InfoTip info={info} /> 🔥 {tf.toUpperCase()} squeeze just FIRED ({sq.direction}) — the {tf} Bollinger Bands burst out of the
        Keltner Channels; a large multi-{tf === "weekly" ? "week" : "day"} move has likely begun.
      </div>
    );
  if (sq.state === "on")
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 text-amber-900 px-4 py-2.5 text-sm">
        <InfoTip info={info} /> ⏳ {tf[0].toUpperCase() + tf.slice(1)} squeeze ON for {sq.bars} bars — volatility is compressed; watch for a breakout.
      </div>
    );
  return null;
}

const CHECK_LABEL = { bollinger: "Bollinger Bands", divergence: "RSI divergence", candlestick: "Candlestick" };

export function Confluence({ a }: { a: Analysis }) {
  const c = a.confluence;
  return (
    <Card title="Reversal confluence" hint="BB exhaustion + RSI divergence + candlestick pattern" info={ana.confluence(a)}>
      <div className="space-y-3">
        <SqueezeBanner tf="weekly" sq={c.squeeze.weekly} info={ana.squeeze(a)} />
        <SqueezeBanner tf="daily" sq={c.squeeze.daily} info={ana.squeeze(a)} />
        <div className="flex items-center justify-between border border-slate-200 rounded-lg px-4 py-3">
          <div>
            <div className="font-medium text-slate-800">
              {c.score === 0 ? "— " : c.direction === "bullish" ? "▲ " : "▼ "}{c.verdict}
            </div>
            <div className="text-xs text-slate-500">{c.score}/3 signals agree</div>
          </div>
          <div className="text-3xl font-semibold text-slate-500 tabular-nums">{c.score}/3</div>
        </div>
        {(Object.keys(CHECK_LABEL) as (keyof typeof CHECK_LABEL)[]).map((k) => (
          <CheckRow key={k} label={CHECK_LABEL[k]} check={c.checks[k]} info={ana.check(a, k)} />
        ))}
        <div className="border-l-4 border-blue-500 bg-blue-50 rounded-r-lg px-4 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">What this means</div>
          <p className="text-sm text-slate-800">{c.meaning}</p>
        </div>
      </div>
    </Card>
  );
}

function CheckRow({ label, check, info }: { label: string; check: Check; info: Info }) {
  return (
    <div className="flex items-center gap-4 bg-slate-50 rounded-lg px-4 py-2.5">
      <span className="w-36 shrink-0 text-sm font-medium">{label} <InfoTip info={info} /></span>
      <span className={`text-xl w-6 ${check.pass ? "text-emerald-600" : "text-rose-400"}`}>{check.pass ? "✓" : "✕"}</span>
      <div className="min-w-0">
        <div className="text-sm text-slate-700">{check.title}</div>
        <div className="text-xs italic text-slate-500">{check.detail}</div>
      </div>
    </div>
  );
}

// ---- sector context -----------------------------------------------------------------------

export function SectorContext({ a, mode }: { a: Analysis; mode: "candle" | "line" }) {
  if (!a.sector) return null;
  return (
    <Card title={`Sector context — ${a.sector.sector}`} hint={`${a.sector.index} · monthly · Bollinger Bands`} info={ana.sector(a)}>
      <PriceChart candles={a.sector.candles} mode={mode} height={320} />
    </Card>
  );
}
