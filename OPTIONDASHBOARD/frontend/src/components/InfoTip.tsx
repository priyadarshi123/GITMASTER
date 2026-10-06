import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** Provenance for one piece of data: where it comes from, when it was fetched,
 *  and how it is calculated. Shown in a popover behind a small ⓘ icon. */
export interface Info {
  title?: string;
  source: ReactNode;
  /** ISO datetime, YYYY-MM-DD (data up to), free text, or a list of labelled times */
  fetched?: string | null | { label: string; at: string | null | undefined }[];
  calc: ReactNode;
  note?: ReactNode;
}

const W = 300;

export default function InfoTip({ info, className = "" }: { info: Info; className?: string }) {
  const btn = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number; above: boolean } | null>(null);

  useLayoutEffect(() => {
    if (!open || !btn.current) return;
    const r = btn.current.getBoundingClientRect();
    const left = Math.min(Math.max(8, r.left + r.width / 2 - W / 2), window.innerWidth - W - 8);
    const above = r.bottom + 220 > window.innerHeight && r.top > 240;
    setPos({ left, top: above ? r.top - 6 : r.bottom + 6, above });
  }, [open]);

  useLayoutEffect(() => {
    if (!pinned) return;
    const close = (e: Event) => {
      if (btn.current?.contains(e.target as Node)) return;
      setPinned(false);
      setOpen(false);
    };
    document.addEventListener("mousedown", close);
    window.addEventListener("scroll", close, true);
    return () => {
      document.removeEventListener("mousedown", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [pinned]);

  return (
    <>
      <button
        ref={btn}
        type="button"
        aria-label={`About ${info.title ?? "this data"}`}
        onClick={(e) => { e.stopPropagation(); setPinned(!pinned); setOpen(!pinned); }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => !pinned && setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => !pinned && setOpen(false)}
        className={`no-print inline-grid place-items-center w-3.5 h-3.5 rounded-full border border-slate-300 text-[9px] font-semibold
          leading-none text-slate-400 hover:text-blue-600 hover:border-blue-400 align-middle normal-case tracking-normal ${className}`}
      >
        i
      </button>
      {open && pos && createPortal(
        <div
          role="tooltip"
          onMouseDown={(e) => e.stopPropagation()}
          style={{ left: pos.left, top: pos.top, width: W, transform: pos.above ? "translateY(-100%)" : undefined }}
          className="fixed z-[100] bg-white border border-slate-200 rounded-lg shadow-xl p-3 text-xs text-slate-700 space-y-2 normal-case tracking-normal font-normal text-left"
        >
          {info.title && <div className="font-semibold text-slate-900 text-[13px]">{info.title}</div>}
          <Row label="Source">{info.source}</Row>
          {info.fetched !== undefined && <Row label="Last fetched">{renderFetched(info.fetched)}</Row>}
          <Row label="How it's calculated">{info.calc}</Row>
          {info.note && <div className="text-[11px] text-amber-700 bg-amber-50 rounded px-2 py-1">{info.note}</div>}
        </div>,
        document.body,
      )}
    </>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</div>
      <div className="leading-snug">{children}</div>
    </div>
  );
}

function renderFetched(f: Info["fetched"]): ReactNode {
  if (f == null) return "not fetched yet";
  if (Array.isArray(f))
    return (
      <ul className="space-y-0.5">
        {f.map((x) => <li key={x.label}><span className="text-slate-500">{x.label}:</span> {fmtWhen(x.at)}</li>)}
      </ul>
    );
  return fmtWhen(f);
}

/** "04 Oct, 17:48 IST · 3 h ago" for datetimes; "data up to 01 Oct 2026" for dates. */
export function fmtWhen(v: string | null | undefined): string {
  if (!v) return "not fetched yet";
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const d = new Date(v + "T00:00:00");
    return `data up to ${d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}`;
  }
  const d = new Date(v);
  if (isNaN(d.getTime())) return v;     // already human text (e.g. NSE timestamp)
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  const ago = mins < 1 ? "just now" : mins < 60 ? `${mins} min ago` : mins < 48 * 60 ? `${Math.round(mins / 60)} h ago` : `${Math.round(mins / 1440)} days ago`;
  return `${d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}, ${d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })} IST · ${ago}`;
}
