import { useEffect, useMemo, useState } from "react";
import { fmtPrice, type Analysis, type Leg, type SRLevel } from "../api";
import { Card } from "./AnalysisSections";
import { ana } from "../info";
import InfoTip from "./InfoTip";
import { LineStyle, PriceChart, type Band, type HLine } from "./charts";

const R_COLOR = "#6d28d9";
const S_COLOR = "#15803d";
const PM_COLOR = "#4338ca";
const CMP_COLOR = "#f59e0b";
const CALL_STRIKE = "#c026d3";
const PUT_STRIKE = "#0891b2";

interface Props {
  a: Analysis;
  mode: "candle" | "line";
  strikes: Leg[];
  tf: "D" | "W" | "M";
  years: 2 | 5;
  onTf: (tf: "D" | "W" | "M") => void;
  onYears: (y: 2 | 5) => void;
  loading: boolean;
}

export default function SRChart({ a, mode, strikes, tf, years, onTf, onYears, loading }: Props) {
  const { sr, summary } = a;
  const cmp = summary.cmp;
  const [zoneOn, setZoneOn] = useState(true);
  const [visible, setVisible] = useState<Record<number, boolean>>({});

  // default: ≥2-touch levels within 12% are drawn, single touches are legend-only
  useEffect(() => {
    setVisible(Object.fromEntries(sr.levels.map((l) => [l.price, l.drawn])));
  }, [sr.levels]);

  const lines = useMemo<HLine[]>(() => {
    const out: HLine[] = [
      { price: cmp, color: CMP_COLOR, style: LineStyle.Dashed, title: "CMP" },
      { price: summary.prev_month.high.price, color: PM_COLOR, title: "PM H" },
      { price: summary.prev_month.low.price, color: PM_COLOR, title: "PM L" },
    ];
    for (const l of sr.levels) {
      if (!visible[l.price]) continue;
      out.push({
        price: l.price,
        color: l.kind === "R" ? R_COLOR : S_COLOR,
        width: l.multi_tf ? 3 : 1,
        style: l.touches >= 2 ? LineStyle.Solid : LineStyle.Dashed,
      });
    }
    for (const l of strikes) {
      out.push({
        price: l.strike, color: l.kind === "CE" ? CALL_STRIKE : PUT_STRIKE, width: 2,
        style: l.side === "S" ? LineStyle.Solid : LineStyle.Dotted, title: `${l.side === "S" ? "S" : "B"} ${l.strike}${l.kind}`,
      });
    }
    return out;
  }, [sr.levels, visible, cmp, summary.prev_month, strikes]);

  const bands = useMemo<Band[]>(() => {
    const out: Band[] = [];
    if (zoneOn) {
      const [lo, hi] = sr.zone_pct;
      out.push({ from: cmp * (1 + lo / 100), to: cmp * (1 + hi / 100), color: "rgba(109,40,217,0.06)" });
      out.push({ from: cmp * (1 - hi / 100), to: cmp * (1 - lo / 100), color: "rgba(21,128,61,0.06)" });
    }
    // gaps start at the bar that contains the gap day (matters on W/M charts)
    const times = sr.candles.map((c) => c.time);
    for (const g of sr.gaps) {
      const start = [...times].reverse().find((t) => t <= g.date) ?? times[0];
      out.push({ from: g.bottom, to: g.top, startTime: start,
        color: g.kind === "up" ? "rgba(22,163,74,0.15)" : "rgba(220,38,38,0.15)" });
    }
    return out;
  }, [zoneOn, sr, cmp]);

  const setAll = (on: boolean) => setVisible(Object.fromEntries(sr.levels.map((l) => [l.price, on])));
  const btn = (active: boolean) =>
    `px-3 py-1 text-xs rounded-md border ${active ? "bg-blue-600 text-white border-blue-600" : "bg-white border-slate-200 text-slate-600 hover:border-slate-400"}`;

  return (
    <Card
      title="S/R analysis — levels & zones"
      info={ana.sr(a)}
      hint="D/W/M swing levels merged · ≥2-touch lines drawn, 1-touch in legend · within 12% of CMP · thick = multi-timeframe · shaded 5–12% option-selling zone · unfilled gaps ≥1.5%"
    >
      <div className="flex flex-wrap items-center gap-2 mb-3 no-print">
        {(["D", "W", "M"] as const).map((t) => (
          <button key={t} className={btn(tf === t)} onClick={() => onTf(t)}>
            {{ D: "Daily", W: "Weekly", M: "Monthly" }[t]}
          </button>
        ))}
        <span className="w-px h-5 bg-slate-200 mx-1" />
        {([2, 5] as const).map((y) => (
          <button key={y} className={btn(years === y)} onClick={() => onYears(y)}>{y}Y</button>
        ))}
        {loading && <span className="text-xs text-slate-400 ml-2">loading…</span>}
        <span className="ml-auto flex gap-2">
          <button className={btn(zoneOn)} onClick={() => setZoneOn(!zoneOn)}>5–12% zone: {zoneOn ? "ON" : "OFF"}</button>
          <button className={btn(false)} onClick={() => setAll(true)}>All levels on</button>
          <button className={btn(false)} onClick={() => setAll(false)}>All levels off</button>
        </span>
      </div>

      <div className="grid lg:grid-cols-[1fr_250px] gap-4">
        <PriceChart candles={sr.candles} mode={mode} lines={lines} bands={bands} height={520} />
        <div>
          <div className="text-[11px] text-slate-500 mb-1 px-1.5">
            Overlays <InfoTip info={ana.srOverlays(a)} /> · Levels <InfoTip info={ana.sr(a)} />
          </div>
          <Legend levels={sr.levels} visible={visible} toggle={(p) => setVisible((v) => ({ ...v, [p]: !v[p] }))}
            pm={summary.prev_month} gaps={sr.gaps.length} />
        </div>
      </div>

      <details className="mt-4 bg-slate-50 rounded-lg px-4 py-2">
        <summary className="cursor-pointer text-sm text-slate-700">Turning points · {sr.levels.length} levels</summary>
        <div className="mt-2 grid sm:grid-cols-2 gap-x-6 gap-y-1 text-xs">
          {sr.levels.map((l) => (
            <div key={l.price} className="flex gap-2">
              <span className={`font-semibold w-24 ${l.kind === "R" ? "text-violet-700" : "text-green-700"}`}>
                {l.kind} {fmtPrice(l.price)}
              </span>
              <span className="text-slate-500">{l.points.map((p) => `${p.date} (${p.tfs})`).join(", ")}</span>
            </div>
          ))}
        </div>
      </details>
    </Card>
  );
}

function Legend({ levels, visible, toggle, pm, gaps }: {
  levels: SRLevel[]; visible: Record<number, boolean>; toggle: (price: number) => void;
  pm: Analysis["summary"]["prev_month"]; gaps: number;
}) {
  return (
    <div className="text-xs space-y-0.5 max-h-[520px] overflow-y-auto pr-1">
      <LegendKey color="#60a5fa" dashed label="BB upper / lower" />
      <LegendKey color="#f59e0b" label="BB SMA20" />
      <LegendKey color={PM_COLOR} label={`Prev-month high ${fmtPrice(pm.high.price)}`} />
      <LegendKey color={PM_COLOR} label={`Prev-month low ${fmtPrice(pm.low.price)}`} />
      {gaps > 0 && <LegendKey color="#86efac" label={`${gaps} unfilled gap(s) ≥1.5%`} />}
      <LegendKey color={CALL_STRIKE} label="Your call strikes" />
      <LegendKey color={PUT_STRIKE} label="Your put strikes" />
      <div className="h-2" />
      {levels.map((l) => {
        const on = !!visible[l.price];
        const color = l.kind === "R" ? R_COLOR : S_COLOR;
        return (
          <button
            key={l.price}
            onClick={() => toggle(l.price)}
            title={l.points.map((p) => p.date).join(", ")}
            className={`w-full flex items-center gap-2 px-1.5 py-0.5 rounded hover:bg-slate-50 text-left ${on ? "" : "opacity-45"}`}
          >
            <span
              className="w-6 shrink-0"
              style={{ borderTop: `${l.multi_tf ? 3 : 1}px ${l.touches >= 2 ? "solid" : "dashed"} ${color}` }}
            />
            <span className="tabular-nums" style={{ color }}>
              {l.kind} {fmtPrice(l.price)} {l.pct > 0 ? "+" : ""}{l.pct}%
            </span>
            <span className="text-slate-400 ml-auto whitespace-nowrap">{l.tfs} · {l.touches}t</span>
          </button>
        );
      })}
    </div>
  );
}

function LegendKey({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <div className="flex items-center gap-2 px-1.5 py-0.5 text-slate-600">
      <span className="w-6 shrink-0" style={{ borderTop: `2px ${dashed ? "dashed" : "solid"} ${color}` }} />
      {label}
    </div>
  );
}
