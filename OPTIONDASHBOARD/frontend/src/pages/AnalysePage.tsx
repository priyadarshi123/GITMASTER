import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { analysisApi, fmtPrice, type Analysis, type Leg } from "../api";
import { ChartSummary, Confluence, RsiCharts, SectorContext } from "../components/AnalysisSections";
import Notes from "../components/Notes";
import OptionBuilder from "../components/OptionBuilder";
import SRChart from "../components/SRChart";
import { SignalChip } from "../components/chips";
import { useDashboard } from "../useDashboard";
import { ana } from "../info";
import InfoTip, { type Info } from "../components/InfoTip";

// legs + expiry per symbol survive tab switches and reloads (and seed Positions in phase 4)
const draftKey = (symbol: string) => `od.draft.${symbol}`;

function loadDraft(symbol: string): { legs: Leg[]; expiry: string | null } {
  try {
    return JSON.parse(sessionStorage.getItem(draftKey(symbol)) || "");
  } catch {
    return { legs: [], expiry: null };
  }
}

export default function AnalysePage() {
  const [params, setParams] = useSearchParams();
  const symbols = (params.get("symbols") || "").split(",").filter(Boolean);
  const active = params.get("tab") || symbols[0];
  const [mode, setMode] = useState<"candle" | "line">("candle");

  if (!symbols.length)
    return <p>No symbols selected. <Link className="text-blue-600 underline" to="/">Back to selector</Link></p>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 no-print">
        {symbols.map((s) => (
          <button
            key={s}
            onClick={() => setParams({ symbols: symbols.join(","), tab: s })}
            className={`px-4 py-2 text-sm -mb-px border-b-2 ${
              s === active ? "border-blue-600 text-blue-700 font-medium" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {s}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3">
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
            {(["candle", "line"] as const).map((m) => (
              <button key={m} onClick={() => setMode(m)}
                className={`px-3 py-1.5 capitalize ${mode === m ? "bg-ink text-brand" : "bg-white text-slate-600"}`}>
                {m}
              </button>
            ))}
          </div>
          <Link to="/" className="text-sm text-slate-500 hover:text-slate-800">← Back to selector</Link>
        </div>
      </div>

      {/* key: remount per symbol so chart/timeframe state resets */}
      <SymbolAnalysis key={active} symbol={active} mode={mode} />
    </div>
  );
}

function SymbolAnalysis({ symbol, mode }: { symbol: string; mode: "candle" | "line" }) {
  const [tf, setTf] = useState<"D" | "W" | "M">("W");
  const [years, setYears] = useState<2 | 5>(2);
  const [data, setData] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState(() => loadDraft(symbol));
  const { data: dash } = useDashboard();
  const events = dash?.items.find((i) => i.symbol === symbol)?.events ?? [];

  const saveDraft = (next: { legs: Leg[]; expiry: string | null }) => {
    setDraft(next);
    try { sessionStorage.setItem(draftKey(symbol), JSON.stringify(next)); } catch { /* storage unavailable */ }
  };

  useEffect(() => {
    let live = true;
    setLoading(true);
    analysisApi.get(symbol, years, tf)
      .then((d) => { if (live) { setData(d); setError(""); } })
      .catch((e) => live && setError(String(e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [symbol, years, tf]);

  if (error) return <p className="text-red-600">Could not load {symbol}: {error}</p>;
  if (!data) return <p className="text-slate-500">Loading {symbol}… (first open of a sector index takes a few seconds)</p>;

  const s = data.summary;
  const ltp = data.quote?.ltp ?? s.cmp;
  return (
    <div className="space-y-5">
      <div className="bg-white border border-slate-200 rounded-xl p-5 grid grid-cols-2 md:grid-cols-5 gap-4">
        <Stat label="Symbol" value={<span className="text-xl font-semibold">{symbol}</span>} sub={data.instrument.name} />
        <Stat label="CMP" info={ana.cmp(data)} value={<span className="text-xl">{fmtPrice(ltp)}</span>}
          sub={data.quote ? `${data.quote.change_pct > 0 ? "+" : ""}${data.quote.change_pct}% · close ${s.date}` : s.date} />
        <Stat label="Weekly RSI" info={ana.rsiW(data)} value={<Rsi v={s.rsi.weekly.rsi} />} />
        <Stat label="Daily RSI" info={ana.rsiD(data)} value={<Rsi v={s.rsi.daily.rsi} />} />
        <Stat label="Signal" info={ana.signal(data)} value={<SignalChip signal={s.signal} />} />
      </div>

      <ChartSummary a={data} />

      <OptionBuilder
        symbol={symbol} a={data} events={events}
        legs={draft.legs} setLegs={(legs) => saveDraft({ ...draft, legs })}
        expiry={draft.expiry} setExpiry={(expiry) => saveDraft({ ...draft, expiry })}
      />

      <RsiCharts a={data} />
      <Confluence a={data} />
      <SectorContext a={data} mode={mode} />
      <SRChart a={data} mode={mode} strikes={draft.legs} tf={tf} years={years} onTf={setTf} onYears={setYears} loading={loading} />
      <Notes symbol={symbol} />

      <div className="flex justify-end no-print">
        <button onClick={() => window.print()} className="px-4 py-2 rounded-lg bg-ink text-white text-sm">
          ⎙ Save as PDF
        </button>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, info }: { label: string; value: React.ReactNode; sub?: string; info?: Info }) {
  return (
    <div>
      <div className="text-xs text-slate-500 mb-1">{label} {info && <InfoTip info={info} />}</div>
      {value}
      {sub && <div className="text-xs text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function Rsi({ v }: { v: number | null }) {
  const cls = v == null ? "" : v < 40 ? "text-red-600" : v > 60 ? "text-emerald-600" : "text-blue-600";
  return <span className={`text-xl font-medium ${cls}`}>{v?.toFixed(1) ?? "—"}</span>;
}
