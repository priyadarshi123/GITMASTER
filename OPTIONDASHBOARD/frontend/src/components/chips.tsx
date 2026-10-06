import { EVENT_LABEL, type CorpEvent, type Signal } from "../api";

export const SIGNALS: Signal[] = ["Bear Call", "Bull Put", "Iron Condor", "Wait for confirmation"];

export const SIGNAL_STYLE: Record<Signal, { dot: string; chip: string }> = {
  "Bear Call": { dot: "bg-red-500", chip: "bg-red-50 text-red-700 ring-red-200" },
  "Bull Put": { dot: "bg-emerald-500", chip: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  "Iron Condor": { dot: "bg-blue-500", chip: "bg-blue-50 text-blue-700 ring-blue-200" },
  "Wait for confirmation": { dot: "bg-amber-500", chip: "bg-amber-50 text-amber-800 ring-amber-200" },
};

export function SignalChip({ signal }: { signal: Signal | null }) {
  if (!signal) return <span className="text-xs text-slate-400">no signal</span>;
  const s = SIGNAL_STYLE[signal];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5 rounded-full ring-1 ${s.chip}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {signal}
    </span>
  );
}

const SECTOR_PALETTE = [
  "bg-rose-50 text-rose-700", "bg-sky-50 text-sky-700", "bg-teal-50 text-teal-700",
  "bg-violet-50 text-violet-700", "bg-lime-50 text-lime-700", "bg-orange-50 text-orange-700",
  "bg-indigo-50 text-indigo-700", "bg-fuchsia-50 text-fuchsia-700", "bg-cyan-50 text-cyan-700",
  "bg-yellow-50 text-yellow-800", "bg-emerald-50 text-emerald-700", "bg-pink-50 text-pink-700",
];

export function sectorClass(sector: string) {
  if (sector === "Index") return "bg-slate-800 text-white";
  let h = 0;
  for (const c of sector) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return SECTOR_PALETTE[h % SECTOR_PALETTE.length];
}

export function SectorChip({ sector }: { sector: string }) {
  return <span className={`text-[11px] px-1.5 py-0.5 rounded ${sectorClass(sector)}`}>{sector}</span>;
}

const EVENT_STYLE: Record<CorpEvent["kind"], string> = {
  R: "bg-red-100 text-red-700",
  A: "bg-violet-100 text-violet-700",
  D: "bg-emerald-100 text-emerald-700",
  B: "bg-sky-100 text-sky-700",
};

export function EventBadges({ events }: { events: CorpEvent[] }) {
  const kinds = [...new Set(events.map((e) => e.kind))];
  return (
    <>
      {kinds.map((k) => {
        const tip = events
          .filter((e) => e.kind === k)
          .map((e) => `${EVENT_LABEL[k]} · ${new Date(e.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} — ${e.purpose}`)
          .join("\n");
        return (
          <span key={k} title={tip} className={`text-[10px] font-bold w-4 h-4 grid place-items-center rounded ${EVENT_STYLE[k]}`}>
            {k}
          </span>
        );
      })}
    </>
  );
}
