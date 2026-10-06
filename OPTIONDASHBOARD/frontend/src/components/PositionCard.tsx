import { useState } from "react";
import { fmtInr, fmtPrice, positionsApi, type Position } from "../api";
import { posInfo } from "../info";
import InfoTip, { type Info } from "./InfoTip";
import PayoffAnalyser from "./PayoffAnalyser";

interface Props {
  p: Position;
  onChanged: () => void;
  onEdit: () => void;
}

type Mode = null | "close" | "legs" | "delete";

export default function PositionCard({ p, onChanged, onEdit }: Props) {
  const [mode, setMode] = useState<Mode>(null);
  const [realized, setRealized] = useState(String(Math.round(p.pnl ?? 0)));
  const openLegs = p.legs.filter((l) => l.exit_price == null);
  const [exits, setExits] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [analysing, setAnalysing] = useState(false);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); setMode(null); onChanged(); } finally { setBusy(false); }
  };

  const pnl = p.pnl ?? 0;
  const stopPct = p.stop_used_pct ?? 0;
  const stopTone = stopPct >= 100 ? "bg-red-600" : stopPct >= 80 ? "bg-orange-500" : stopPct >= 50 ? "bg-amber-400" : "bg-emerald-500";

  return (
    <div className={`bg-white border rounded-xl p-4 space-y-3 ${stopPct >= 95 ? "border-red-400" : "border-slate-200"}`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-semibold text-slate-900">{p.symbol}</span>
        <span className="text-sm text-slate-600">{p.strategy}</span>
        <span className="text-xs text-slate-400">exp {p.expiry} · {p.lots} × {p.lot_size} · opened {p.opened_at}</span>
        {p.expired && <span className="text-xs px-2 rounded bg-red-100 text-red-700">EXPIRED — close it</span>}
        <span className={`ml-auto text-lg font-semibold tabular-nums ${pnl >= 0 ? "text-emerald-600" : "text-red-600"}`}>
          {pnl >= 0 ? "+" : "−"}{fmtInr(Math.abs(pnl))}
        </span>
        <InfoTip info={posInfo.pnl(p)} />
      </div>
      {p.error && <p className="text-xs text-amber-700">⚠ {p.error}</p>}

      {p.stop_used_pct != null && (
        <div>
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span><InfoTip info={posInfo.stop(p)} /> {stopPct.toFixed(0)}% of stop used ({p.stop_rule === "breach" ? "strike breach" : `${p.stop_rule} credit = ${fmtInr(p.stop_loss)}`})</span>
            {p.nearest_short_pct != null && <span>nearest short strike {p.nearest_short_pct}% away</span>}
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full ${stopTone}`} style={{ width: `${Math.min(100, stopPct)}%` }} />
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
        <Stat info={posInfo.credit(p)} label="Credit" value={fmtInr(p.credit_total)} sub={`₹${p.credit_share}/share`} />
        <Stat info={posInfo.margin(p)} label="Margin" value={fmtInr(p.margin)} />
        <Stat info={posInfo.pop(p)} label="POP now / entry" value={`${p.pop_now ?? "—"}% / ${p.entry_pop ?? "—"}%`}
          tone={p.pop_now != null && p.entry_pop != null && p.pop_now < p.entry_pop - 10 ? "bad" : undefined} />
        <Stat info={posInfo.breakeven(p)} label="Breakevens" value={p.breakevens.map((b) => b.toFixed(0)).join(" / ") || "—"} />
        <Stat info={posInfo.spot(p)} label="Spot" value={fmtPrice(p.spot ?? null)}
          sub={p.spot_move_pct != null ? `${p.spot_move_pct > 0 ? "+" : ""}${p.spot_move_pct}% since entry (${fmtPrice(p.entry_spot)})` : undefined} />
      </div>

      <table className="w-full text-xs tabular-nums">
        <thead className="text-slate-500"><tr className="[&>th]:text-left [&>th]:font-medium">
          {mode === "legs" && <th />}<th>Leg</th><th>Entry</th><th>LTP / exit</th><th className="text-right">P&L</th></tr></thead>
        <tbody>
          {p.legs.map((l) => {
            const closed = l.exit_price != null;
            return (
              <tr key={l.id} className={`[&>td]:py-0.5 ${closed ? "text-slate-400 line-through" : ""}`}>
                {mode === "legs" && (
                  <td>
                    {!closed && (
                      <input type="checkbox" checked={l.id in exits}
                        onChange={(e) => {
                          const next = { ...exits };
                          if (e.target.checked) next[l.id] = String(l.ltp ?? l.entry_price);
                          else delete next[l.id];
                          setExits(next);
                        }} />
                    )}
                  </td>
                )}
                <td className={l.side === "S" ? "text-red-600" : "text-emerald-700"}>
                  {l.side === "S" ? "Sell" : "Buy"} {l.strike} {l.kind}
                </td>
                <td>{l.entry_price.toFixed(2)}</td>
                <td>
                  {mode === "legs" && l.id in exits ? (
                    <input type="number" step="0.05" value={exits[l.id]}
                      onChange={(e) => setExits({ ...exits, [l.id]: e.target.value })}
                      className="w-20 border border-slate-200 rounded px-1" />
                  ) : closed ? `${l.exit_price!.toFixed(2)} (closed)` : l.ltp?.toFixed(2) ?? "—"}
                </td>
                <td className={`text-right ${(l.pnl ?? 0) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                  {l.pnl != null ? fmtInr(l.pnl) : ""}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {p.realized_legs !== 0 && <p className="text-xs text-slate-500">Realised on closed legs: {fmtInr(p.realized_legs)}</p>}
      {p.note && <p className="text-xs text-slate-500 italic">{p.note}</p>}

      <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-slate-100">
        {mode === null && (
          <>
            <Btn primary onClick={() => setAnalysing(true)} disabled={p.expired || !openLegs.length}>Analyse</Btn>
            <Btn onClick={() => setMode("close")}>Close</Btn>
            {openLegs.length > 1 && <Btn onClick={() => setMode("legs")}>Close legs</Btn>}
            <Btn onClick={onEdit}>Edit entry</Btn>
            <Btn onClick={() => setMode("delete")} danger>Delete</Btn>
          </>
        )}
        {mode === "close" && (
          <>
            <span className="text-xs text-slate-600">Realised P&L ₹</span>
            <input type="number" value={realized} onChange={(e) => setRealized(e.target.value)}
              className="w-28 border border-slate-200 rounded px-2 py-1 text-sm" />
            <Btn primary disabled={busy} onClick={() => act(() => positionsApi.close(p.id, parseFloat(realized) || 0))}>Confirm close</Btn>
            <Btn onClick={() => setMode(null)}>Cancel</Btn>
          </>
        )}
        {mode === "legs" && (
          <>
            <span className="text-xs text-slate-600">Tick legs and set exit prices — credit, max loss and stop are recalculated.</span>
            <Btn primary disabled={busy || !Object.keys(exits).length}
              onClick={() => act(() => positionsApi.closeLegs(p.id,
                Object.fromEntries(Object.entries(exits).map(([k, v]) => [Number(k), parseFloat(v) || 0]))))}>
              Close selected
            </Btn>
            <Btn onClick={() => { setMode(null); setExits({}); }}>Cancel</Btn>
          </>
        )}
        {mode === "delete" && (
          <>
            <span className="text-xs text-red-700">Delete this position permanently?</span>
            <Btn danger disabled={busy} onClick={() => act(() => positionsApi.remove(p.id))}>Yes, delete</Btn>
            <Btn onClick={() => setMode(null)}>Cancel</Btn>
          </>
        )}
      </div>
      {analysing && <PayoffAnalyser id={p.id} onClose={() => setAnalysing(false)} />}
    </div>
  );
}

function Stat({ label, value, sub, tone, info }: { label: string; value: string; sub?: string; tone?: "bad"; info?: Info }) {
  return (
    <div className="bg-slate-50 rounded-lg px-2.5 py-1.5">
      <div className="text-[10px] text-slate-500">{label} {info && <InfoTip info={info} />}</div>
      <div className={`font-semibold ${tone === "bad" ? "text-red-600" : "text-slate-800"}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-400">{sub}</div>}
    </div>
  );
}

function Btn({ children, onClick, primary, danger, disabled }: {
  children: React.ReactNode; onClick: () => void; primary?: boolean; danger?: boolean; disabled?: boolean;
}) {
  const cls = primary ? "bg-blue-600 text-white border-blue-600"
    : danger ? "border-red-200 text-red-600 hover:bg-red-50" : "border-slate-200 text-slate-700 hover:border-slate-400";
  return (
    <button onClick={onClick} disabled={disabled} className={`px-3 py-1 text-xs rounded-md border disabled:opacity-50 ${cls}`}>
      {children}
    </button>
  );
}
