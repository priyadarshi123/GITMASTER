import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { fmtInr, positionsApi, type Book, type Leg, type Position, type PositionBook, type RoiRow } from "../api";
import { Card } from "../components/AnalysisSections";
import PositionCard from "../components/PositionCard";
import PositionForm, { type Prefill } from "../components/PositionForm";
import { posInfo } from "../info";

function draftPrefill(symbol: string | null, strategy: string | null): Prefill | null {
  if (!symbol) return null;
  try {
    const d = JSON.parse(sessionStorage.getItem(`od.draft.${symbol}`) || "{}") as { legs?: Leg[]; expiry?: string };
    return { symbol, strategy: strategy ?? undefined, expiry: d.expiry, legs: d.legs };
  } catch {
    return { symbol, strategy: strategy ?? undefined };
  }
}

export default function PositionsPage() {
  const { book: bookParam } = useParams();
  const book: Book = bookParam === "paper" ? "paper" : "real";
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<PositionBook | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Position | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const prefill = draftPrefill(params.get("from"), params.get("strategy"));

  const load = useCallback(() => {
    positionsApi.book(book).then((d) => { setData(d); setError(""); }).catch((e) => setError(String(e)));
  }, [book]);

  useEffect(() => {
    load();
    const t = window.setInterval(load, 60_000);
    return () => window.clearInterval(t);
  }, [load]);
  useEffect(() => { if (prefill) setFormOpen(true); }, [params]);   // eslint-disable-line react-hooks/exhaustive-deps

  const done = () => {
    setFormOpen(false);
    setEditing(null);
    if (params.get("from")) setParams({});
    load();
  };

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold text-slate-900">Positions</h1>
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-sm">
          {(["real", "paper"] as const).map((b) => (
            <button key={b} onClick={() => navigate(`/positions/${b}`)}
              className={`px-4 py-1.5 capitalize ${book === b ? (b === "real" ? "bg-emerald-600 text-white" : "bg-slate-700 text-white") : "bg-white text-slate-600"}`}>
              {b}
            </button>
          ))}
        </div>
        {data && (
          <span className="ml-auto text-xs text-slate-500">
            <span className={`px-1.5 py-0.5 rounded mr-2 ${data.freshness.tag === "LIVE" ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"}`}>
              {data.freshness.tag}
            </span>
            updated {data.freshness.updated} IST · NSE prices ~1–3 min delayed
          </span>
        )}
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <Card title={editing ? `Edit ${editing.symbol} ${editing.strategy}` : `Record a ${book} position`}
        right={!formOpen && !editing && (
          <button onClick={() => setFormOpen(true)} className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white">+ New position</button>
        )}>
        {data && (formOpen || editing) ? (
          <PositionForm
            key={editing?.id ?? prefill?.symbol ?? "new"}
            book={book} editing={editing} prefill={editing ? null : prefill}
            defaults={{ capital: data?.capital.default, risk_pct: data?.capital.risk_per_trade_pct }}
            onDone={done}
          />
        ) : (
          <p className="text-sm text-slate-500">
            Record a trade here, or build one on a stock's <Link to="/" className="text-blue-600 underline">analysis page</Link> and
            press <b>Record position</b> to carry the legs over.
          </p>
        )}
      </Card>

      {data && <RoiCard data={data} book={book} />}

      <Card title="Open positions" hint="live P&L · stop rule per trade: 1×/2×/3× credit or strike breach (0.5% buffer)">
        {!data ? <p className="text-sm text-slate-500">Loading…</p>
          : data.open.length === 0 ? <p className="text-sm text-slate-500 text-center py-6">No open positions. Record one above.</p>
            : (
              <div className="grid lg:grid-cols-2 gap-3">
                {data.open.map((p) => (
                  <PositionCard key={p.id} p={p} onChanged={load}
                    onEdit={() => { setEditing(p); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
                ))}
              </div>
            )}
      </Card>

      {data && <ClosedTable rows={data.closed} />}
    </div>
  );
}

function RoiCard({ data, book }: { data: PositionBook; book: Book }) {
  const { monthly, annual } = data.roi;
  return (
    <Card title={`ROI — ${book}`} hint="realised (closed) + unrealised (open, current month) · % of margin used" info={posInfo.roi(data)}>
      {monthly.length === 0 ? (
        <p className="text-sm text-slate-500 text-center py-4">
          No positions yet. Close a position with its realised P&L to start the monthly / annual ROI tables.
        </p>
      ) : (
        <div className="grid md:grid-cols-[2fr_1fr] gap-6">
          <RoiTable rows={monthly} label="Month" k="month" />
          <RoiTable rows={annual} label="Year" k="year" />
        </div>
      )}
    </Card>
  );
}

function RoiTable({ rows, label, k }: { rows: RoiRow[]; label: string; k: "month" | "year" }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <thead className="text-xs text-slate-500">
        <tr className="border-b border-slate-200 [&>th]:py-1 [&>th]:font-medium [&>th]:text-right [&>th:first-child]:text-left">
          <th>{label}</th><th>Margin</th><th>Realised</th><th>Unrealised</th><th>Total</th><th>ROI</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r[k]} className="border-b border-slate-100 [&>td]:py-1 [&>td]:text-right [&>td:first-child]:text-left">
            <td>{r[k]}</td>
            <td>{fmtInr(r.margin)}</td>
            <td className={tone(r.realized)}>{fmtInr(r.realized)}</td>
            <td className={tone(r.unrealized)}>{fmtInr(r.unrealized)}</td>
            <td className={`font-semibold ${tone(r.total)}`}>{fmtInr(r.total)}</td>
            <td className={`font-semibold ${tone(r.roi_pct ?? 0)}`}>{r.roi_pct != null ? `${r.roi_pct}%` : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ClosedTable({ rows }: { rows: Position[] }) {
  return (
    <Card title="Closed positions">
      {rows.length === 0 ? <p className="text-sm text-slate-400 text-center py-4">—</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead className="text-xs text-slate-500">
              <tr className="border-b border-slate-200 [&>th]:py-1 [&>th]:font-medium [&>th]:text-left">
                <th>Symbol</th><th>Strategy</th><th>Legs</th><th>Opened</th><th>Closed</th>
                <th className="!text-right">Credit</th><th className="!text-right">Margin</th>
                <th className="!text-right">Realised</th><th className="!text-right">ROI</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="border-b border-slate-100 [&>td]:py-1">
                  <td className="font-medium">{p.symbol}</td>
                  <td>{p.strategy}</td>
                  <td className="text-xs text-slate-500">
                    {p.legs.map((l) => `${l.side}${l.strike}${l.kind}`).join(" ")}
                  </td>
                  <td>{p.opened_at}</td>
                  <td>{p.closed_at}</td>
                  <td className="text-right">{fmtInr(p.credit_total || null)}</td>
                  <td className="text-right">{fmtInr(p.margin)}</td>
                  <td className={`text-right font-semibold ${tone(p.realized_pnl ?? 0)}`}>{fmtInr(p.realized_pnl)}</td>
                  <td className="text-right">{p.margin && p.realized_pnl != null ? `${(p.realized_pnl / p.margin * 100).toFixed(1)}%` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

const tone = (v: number) => (v > 0 ? "text-emerald-700" : v < 0 ? "text-red-600" : "");
