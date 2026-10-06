import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { EVENT_LABEL, fmtTime, type CorpEvent, type Item } from "../api";
import StockCard from "../components/StockCard";
import { SIGNALS, SIGNAL_STYLE } from "../components/chips";
import { useDashboard } from "../useDashboard";
import { dash } from "../info";
import InfoTip from "../components/InfoTip";

type EventFilter = "all" | "none" | CorpEvent["kind"];

const SELECTION_KEY = "od.selected";

function loadSelection(): string[] {
  try {
    return JSON.parse(sessionStorage.getItem(SELECTION_KEY) || "[]");
  } catch {
    return [];
  }
}

export default function DashboardPage() {
  const { data, toggleBookmark } = useDashboard();
  const navigate = useNavigate();

  const [eventF, setEventF] = useState<EventFilter>("all");
  const [signalF, setSignalF] = useState<string>("all");
  const [sectorF, setSectorF] = useState<string>("all");
  const [watchOnly, setWatchOnly] = useState(false);
  const [selected, setSelected] = useState<string[]>(loadSelection);

  const setSel = (next: string[]) => {
    setSelected(next);
    try { sessionStorage.setItem(SELECTION_KEY, JSON.stringify(next)); } catch { /* storage unavailable */ }
  };
  const toggle = (s: string) => setSel(selected.includes(s) ? selected.filter((x) => x !== s) : [...selected, s]);

  const items = data?.items ?? [];
  const matchEvent = (i: Item, f: EventFilter) =>
    f === "all" || (f === "none" ? i.events.length === 0 : i.events.some((e) => e.kind === f));

  const visible = useMemo(
    () => items.filter((i) =>
      matchEvent(i, eventF)
      && (signalF === "all" || i.signal === signalF)
      && (sectorF === "all" || i.sector === sectorF)
      && (!watchOnly || i.bookmarked)),
    [items, eventF, signalF, sectorF, watchOnly],
  );

  const count = (pred: (i: Item) => boolean) => items.filter(pred).length;
  const eventKinds = (["R", "A", "D", "B"] as const).filter((k) => count((i) => matchEvent(i, k)) > 0);
  const sectors = [...new Set(items.map((i) => i.sector))];

  if (!data) return <p className="text-slate-500">Loading…</p>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Step 1 — Select instruments to analyse</h1>
          <p className="text-sm text-slate-500">
            {items.length} instruments · next monthly expiry{" "}
            {new Date(data.expiry).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
            {" "}· event badges cover results/AGM/dividend/bonus up to expiry ·{" "}
            <Link to="/guide" className="text-blue-600 hover:underline">How to use this →</Link>
          </p>
        </div>
        <button
          disabled={!selected.length}
          onClick={() => navigate(`/analyse?symbols=${selected.map(encodeURIComponent).join(",")}`)}
          className="px-4 py-2 rounded-lg font-medium bg-blue-600 text-white disabled:bg-slate-200 disabled:text-slate-500"
        >
          Analyse {selected.length || ""} selected ↗
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl px-4 py-3 flex flex-wrap items-center gap-2 text-sm">
        {selected.length === 0 ? (
          <span className="text-slate-500">No instruments selected yet — click cards to select.</span>
        ) : (
          selected.map((s) => (
            <button key={s} onClick={() => toggle(s)} className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 ring-1 ring-blue-200">
              {s} ✕
            </button>
          ))
        )}
        {selected.length > 0 && (
          <button onClick={() => setSel([])} className="ml-auto text-xs text-slate-500 hover:text-slate-800">Clear all</button>
        )}
      </div>

      <div className="space-y-2">
        <FilterRow>
          <Pill active={eventF === "all"} onClick={() => setEventF("all")}>All events</Pill>
          {eventKinds.map((k) => (
            <Pill key={k} active={eventF === k} onClick={() => setEventF(k)}>
              {EVENT_LABEL[k]} ({count((i) => matchEvent(i, k))})
            </Pill>
          ))}
          <Pill active={eventF === "none"} onClick={() => setEventF("none")}>
            No events ({count((i) => i.events.length === 0)})
          </Pill>
          <span className="w-px h-5 bg-slate-200 mx-1" />
          <Pill active={watchOnly} onClick={() => setWatchOnly(!watchOnly)}>
            ★ Watchlist ({count((i) => i.bookmarked)})
          </Pill>
        </FilterRow>

        <FilterRow>
          <Pill active={signalF === "all"} onClick={() => setSignalF("all")}>All signals</Pill>
          {SIGNALS.filter((s) => count((i) => i.signal === s) > 0).map((s) => (
            <Pill key={s} active={signalF === s} onClick={() => setSignalF(s)}>
              <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${SIGNAL_STYLE[s].dot}`} />
              {s} ({count((i) => i.signal === s)})
            </Pill>
          ))}
          <span className="text-xs text-slate-400 ml-2">
            signals as of {fmtTime(data.asof)}{data.market_open ? "" : " · market closed"} <InfoTip info={dash.page(data)} />
          </span>
        </FilterRow>

        <FilterRow>
          <Pill active={sectorF === "all"} onClick={() => setSectorF("all")} dark>All</Pill>
          {sectors.map((s) => (
            <Pill key={s} active={sectorF === s} onClick={() => setSectorF(s)} dark>{s}</Pill>
          ))}
        </FilterRow>
      </div>

      {visible.length === 0 ? (
        <p className="text-center text-slate-500 py-16">No instruments match these filters.</p>
      ) : (
        <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visible.map((i) => (
            <StockCard
              key={i.symbol}
              item={i}
              eventsInfo={dash.events(data)}
              selected={selected.includes(i.symbol)}
              onSelect={() => toggle(i.symbol)}
              onBookmark={() => toggleBookmark(i.symbol)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterRow({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2">{children}</div>;
}

function Pill({ active, onClick, dark, children }: {
  active: boolean; onClick: () => void; dark?: boolean; children: React.ReactNode;
}) {
  const on = dark ? "bg-ink text-white border-ink" : "bg-white text-slate-900 border-slate-800 font-medium";
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded-full border text-xs transition ${
        active ? on : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
      }`}
    >
      {children}
    </button>
  );
}
