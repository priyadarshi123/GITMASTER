import { useEffect, useMemo, useRef, useState } from "react";
import {
  fmtInr, optionsApi, positionsApi, suggestApi,
  type Book, type ChainRow, type Leg, type Position, type PositionInput, type StopRule,
} from "../api";
import { useDashboard } from "../useDashboard";
import InfoTip, { fmtWhen } from "./InfoTip";
import PayoffAnalyser from "./PayoffAnalyser";

const STRATEGIES = ["Iron Condor", "Bull Put", "Bear Call", "Custom"] as const;
const CREDIT_STRATEGIES = new Set(["Iron Condor", "Bull Put", "Bear Call"]);
const STOPS: { value: StopRule; label: string }[] = [
  { value: "1x", label: "1:1 — 1× credit" },
  { value: "2x", label: "1:2 — 2× credit" },
  { value: "3x", label: "1:3 — 3× credit" },
  { value: "breach", label: "Strike breach (0.5% buffer)" },
];
// a premium above this share of the strike is almost certainly a strike typed into the price box
const PRICE_SANITY = 0.3;

interface FormLeg { kind: "CE" | "PE"; side: "S" | "B"; strike: string; price: string }

const template = (strategy: string): FormLeg[] => {
  const row = (kind: "CE" | "PE", side: "S" | "B"): FormLeg => ({ kind, side, strike: "", price: "" });
  if (strategy === "Bear Call") return [row("CE", "S"), row("CE", "B")];
  if (strategy === "Bull Put") return [row("PE", "S"), row("PE", "B")];
  if (strategy === "Iron Condor") return [row("CE", "S"), row("CE", "B"), row("PE", "S"), row("PE", "B")];
  return [row("CE", "S")];
};

const toForm = (legs: { kind: "CE" | "PE"; side: "S" | "B"; strike: number; price: number }[]): FormLeg[] =>
  legs.map((l) => ({ kind: l.kind, side: l.side, strike: String(l.strike), price: String(l.price) }));

export interface Prefill { symbol: string; strategy?: string; expiry?: string | null; legs?: Leg[] }

interface Props {
  book: Book;
  editing?: Position | null;
  prefill?: Prefill | null;
  defaults: { capital?: number; risk_pct?: number };
  onDone: () => void;
}

export default function PositionForm({ book, editing, prefill, defaults, onDone }: Props) {
  const { data: dash } = useDashboard();
  const [symbol, setSymbol] = useState(editing?.symbol ?? prefill?.symbol ?? "");
  const [strategy, setStrategy] = useState(editing?.strategy ?? prefill?.strategy ?? "Iron Condor");
  const [expiry, setExpiry] = useState(editing?.expiry ?? prefill?.expiry ?? "");
  const [lots, setLots] = useState(String(editing?.lots ?? 1));
  const [lotSize, setLotSize] = useState(String(editing?.lot_size ?? ""));
  const [capital, setCapital] = useState(String(editing?.capital ?? defaults.capital ?? ""));
  const [risk, setRisk] = useState(String(editing?.risk_pct ?? defaults.risk_pct ?? 1));
  const [stop, setStop] = useState<StopRule>(editing?.stop_rule ?? "3x");
  const [note, setNote] = useState(editing?.note ?? "");
  const [legs, setLegs] = useState<FormLeg[]>(() =>
    editing ? editing.legs.map((l) => ({ kind: l.kind, side: l.side, strike: String(l.strike), price: String(l.entry_price) }))
      : prefill?.legs?.length ? toForm(prefill.legs) : template(strategy));
  const [expiries, setExpiries] = useState<{ date: string; lot_size: number | null }[]>([]);
  const [chainRows, setChainRows] = useState<Map<number, ChainRow>>(new Map());
  const [spot, setSpot] = useState<number | null>(null);
  const [suggestion, setSuggestion] = useState<{ notes: string[]; at: string; nse: string } | null>(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  // legs came from a suggestion (not typed or carried over) → safe to refill on expiry change
  const autoFilled = useRef(false);
  const legsLocked = !!editing?.legs.some((l) => l.exit_price != null);

  // ---- data loading ---------------------------------------------------------------------

  const fillSuggested = async (sym: string, strat: string, exp: string) => {
    if (!CREDIT_STRATEGIES.has(strat)) return;
    setBusy("Finding recommended strikes…");
    try {
      const s = await suggestApi.get(sym, strat, exp || null);
      setLegs(toForm(s.legs));
      setSuggestion({ notes: s.notes, at: s.chain_fetched_at, nse: s.chain_timestamp });
      autoFilled.current = true;
      setMsg("");
    } catch (e) {
      setLegs(template(strat));
      setSuggestion(null);
      setMsg(`Couldn't fetch suggestions (${e}) — fill strikes manually`);
    } finally {
      setBusy("");
    }
  };

  const loadContract = async (sym = symbol, suggestAfter = !editing && !prefill?.legs?.length) => {
    if (!sym) return;
    try {
      const c = await positionsApi.contract(sym.toUpperCase());
      setExpiries(c.expiries);
      const pick = c.expiries.find((e) => e.date === expiry) ?? c.expiries[0];
      if (pick) {
        setExpiry(pick.date);
        if (!editing && pick.lot_size) setLotSize(String(pick.lot_size));
        if (suggestAfter) await fillSuggested(sym.toUpperCase(), strategy, pick.date);
      }
      setMsg("");
    } catch {
      setMsg("chain unavailable — fill expiry and lot size manually");
    }
  };
  useEffect(() => { if (symbol) loadContract(symbol); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  // chain for the chosen expiry: premiums / delta hints and price auto-fill
  useEffect(() => {
    if (!symbol || !expiry) return;
    let live = true;
    optionsApi.chain(symbol.toUpperCase(), expiry)
      .then((c) => {
        if (!live) return;
        setChainRows(new Map(c.rows.map((r) => [r.strike, r])));
        setSpot(c.underlying);
      })
      .catch(() => live && setChainRows(new Map()));
    return () => { live = false; };
  }, [symbol, expiry]);

  const quote = (l: FormLeg) => {
    const row = chainRows.get(parseFloat(l.strike));
    return row ? (l.kind === "CE" ? row.ce : row.pe) : null;
  };

  // ---- edits ------------------------------------------------------------------------------

  const changeStrategy = (next: string) => {
    setStrategy(next);
    if (legsLocked || editing) return;
    if (CREDIT_STRATEGIES.has(next) && symbol) fillSuggested(symbol.toUpperCase(), next, expiry);
    else if (!legs.some((l) => l.strike)) setLegs(template(next));
  };

  const changeExpiry = (next: string) => {
    setExpiry(next);
    const ls = expiries.find((x) => x.date === next)?.lot_size;
    if (ls) setLotSize(String(ls));
    if (autoFilled.current && symbol) fillSuggested(symbol.toUpperCase(), strategy, next);
  };

  const setLeg = (i: number, patch: Partial<FormLeg>) => {
    autoFilled.current = false;
    setLegs(legs.map((l, j) => {
      if (j !== i) return l;
      const next = { ...l, ...patch };
      // new strike or type → take the live premium for it
      if (("strike" in patch || "kind" in patch) && !("price" in patch)) {
        const q = quote(next);
        if (q?.ltp != null) next.price = String(q.ltp);
      }
      return next;
    }));
  };

  // ---- readout & checks ---------------------------------------------------------------------

  const readout = useMemo(() => {
    const credit = legs.reduce((s, l) => s + (l.side === "S" ? 1 : -1) * (parseFloat(l.price) || 0), 0);
    const lot = parseInt(lotSize) || 0, n = parseInt(lots) || 0;
    const mult = stop === "breach" ? null : parseInt(stop);
    const stopLot = mult && credit > 0 ? mult * credit * lot : null;
    const riskBudget = (parseFloat(capital) || 0) * (parseFloat(risk) || 0) / 100;
    const suspicious = legs.filter((l) => {
      const p = parseFloat(l.price), k = parseFloat(l.strike);
      return p > 0 && k > 0 && p > k * PRICE_SANITY;
    });
    return { credit, perLot: credit * lot, stopLot, stopTotal: stopLot != null ? stopLot * n : null, riskBudget, suspicious };
  }, [legs, lotSize, lots, stop, capital, risk]);

  const parsedLegs = () => legs.filter((l) => l.strike && l.price !== "")
    .map((l) => ({ kind: l.kind, side: l.side, strike: parseFloat(l.strike), price: parseFloat(l.price) }));

  const analyse = () => {
    if (!symbol || !expiry || !parseInt(lots) || !parseInt(lotSize) || !parsedLegs().length) {
      setMsg("Fill symbol, expiry, lots, lot size and at least one leg (strike + price) to analyse.");
      return;
    }
    setMsg("");
    setAnalysing(true);
  };

  const save = async () => {
    const parsed = parsedLegs();
    if (!symbol || !expiry || !parseInt(lots) || !parseInt(lotSize) || !parsed.length) {
      setMsg("Fill symbol, expiry, lots, lot size and at least one leg (strike + price).");
      return;
    }
    if (readout.suspicious.length) {
      setMsg("A price looks like a strike — enter the option premium (the LTP hint under the leg).");
      return;
    }
    if (CREDIT_STRATEGIES.has(strategy) && readout.credit <= 0) {
      setMsg(`${strategy} should receive a net credit — check which legs are Sell vs Buy and their premiums.`);
      return;
    }
    const body: PositionInput = {
      book, symbol: symbol.toUpperCase(), strategy, expiry, lots: parseInt(lots), lot_size: parseInt(lotSize),
      capital: parseFloat(capital) || null, risk_pct: parseFloat(risk) || null, stop_rule: stop,
      note: note || null, legs: parsed,
    };
    setSaving(true);
    try {
      if (editing) await positionsApi.update(editing.id, body);
      else await positionsApi.create(body);
      try { sessionStorage.removeItem(`od.draft.${body.symbol}`); } catch { /* storage unavailable */ }
      onDone();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setSaving(false);
    }
  };

  const input = "border border-slate-200 rounded-md px-2 py-1.5 text-sm w-full disabled:bg-slate-50";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Symbol">
          <input list="od-symbols" value={symbol} disabled={!!editing}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && loadContract(symbol, true)}
            className={`${input} w-36`} />
          <datalist id="od-symbols">{dash?.items.map((i) => <option key={i.symbol} value={i.symbol} />)}</datalist>
        </Field>
        {!editing && (
          <button onClick={() => loadContract(symbol, true)} className="px-3 py-1.5 text-sm border border-slate-200 rounded-md">
            Load expiries & suggest
          </button>
        )}
        {busy && <span className="text-xs text-slate-500">{busy}</span>}
        {msg && <span className="text-xs text-amber-700">⚠ {msg}</span>}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <Field label="Strategy">
          <select value={strategy} disabled={legsLocked} onChange={(e) => changeStrategy(e.target.value)} className={input}>
            {STRATEGIES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Expiry">
          {expiries.length ? (
            <select value={expiry} onChange={(e) => changeExpiry(e.target.value)} className={input}>
              {expiries.map((e) => <option key={e.date} value={e.date}>{e.date}</option>)}
            </select>
          ) : (
            <input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} className={input} />
          )}
        </Field>
        <Field label="Lots"><input type="number" min={1} value={lots} onChange={(e) => setLots(e.target.value)} className={input} /></Field>
        <Field label="Lot size"><input type="number" min={1} value={lotSize} onChange={(e) => setLotSize(e.target.value)} className={input} /></Field>
        <Field label="Capital (₹)"><input type="number" value={capital} onChange={(e) => setCapital(e.target.value)} className={input} /></Field>
        <Field label="Risk / trade %"><input type="number" step="0.1" value={risk} onChange={(e) => setRisk(e.target.value)} className={input} /></Field>
        <Field label="Stop loss">
          <select value={stop} onChange={(e) => setStop(e.target.value as StopRule)} className={input}>
            {STOPS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>
      </div>

      {suggestion && autoFilled.current && (
        <div className="text-xs bg-violet-50 border border-violet-200 text-violet-900 rounded-lg px-3 py-2">
          <b>Prefilled with suggested strikes</b> for {strategy}{" "}
          <InfoTip info={{
            title: "Suggested strikes",
            source: "NSE option chain + the portal's S/R levels (2-year window)",
            fetched: [{ label: "Chain from NSE", at: suggestion.at }, { label: "NSE data time", at: suggestion.nse }],
            calc: "Per side: the first strike ≥ 5% from CMP that lies beyond the nearest drawn S/R level inside the 5–12% zone with |delta| ≤ 0.30; hedge two strikes further out. Prices = last traded premium.",
          }} />
          <ul className="mt-1 list-disc pl-5">{suggestion.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          <span className="text-violet-700">Edit any strike or price — premiums refresh from the chain when you change a strike.</span>
        </div>
      )}

      <table className="w-full text-sm">
        <thead className="text-slate-500 text-xs">
          <tr className="[&>th]:text-left [&>th]:font-medium [&>th]:pb-1 border-b border-slate-200">
            <th className="w-28">Type</th><th className="w-36">Action</th><th>Strike</th><th>Premium / price (₹)</th><th className="w-8" />
          </tr>
        </thead>
        <tbody>
          {legs.map((l, i) => {
            const q = quote(l);
            const k = parseFloat(l.strike), p = parseFloat(l.price);
            const bad = p > 0 && k > 0 && p > k * PRICE_SANITY;
            return (
              <tr key={i} className="[&>td]:pt-1 [&>td]:pr-2 align-top">
                <td><select value={l.kind} disabled={legsLocked} onChange={(e) => setLeg(i, { kind: e.target.value as "CE" | "PE" })} className={input}>
                  <option>CE</option><option>PE</option></select></td>
                <td><select value={l.side} disabled={legsLocked} onChange={(e) => setLeg(i, { side: e.target.value as "S" | "B" })} className={input}>
                  <option value="S">Sell</option><option value="B">Buy (hedge)</option></select></td>
                <td>
                  <input type="number" list={`od-strikes-${l.kind}`} value={l.strike} disabled={legsLocked}
                    onChange={(e) => setLeg(i, { strike: e.target.value })} className={input} />
                  {q && spot && (
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      {((k / spot - 1) * 100).toFixed(1)}% from CMP · Δ {q.delta?.toFixed(2) ?? "—"} · IV {q.iv?.toFixed(1) ?? "—"} · OI {q.oi?.toLocaleString("en-IN") ?? "—"}
                    </div>
                  )}
                  {l.strike && chainRows.size > 0 && !q && <div className="text-[11px] text-amber-700 mt-0.5">not a listed strike for this expiry</div>}
                </td>
                <td>
                  <input type="number" step="0.05" value={l.price} disabled={legsLocked}
                    onChange={(e) => setLeg(i, { price: e.target.value })}
                    className={`${input} ${bad ? "border-red-400 bg-red-50" : ""}`} />
                  {q?.ltp != null && (
                    <div className="text-[11px] mt-0.5">
                      {bad
                        ? <span className="text-red-600">looks like a strike — premium is ₹{q.ltp.toFixed(2)} <button className="underline" onClick={() => setLeg(i, { price: String(q.ltp) })}>use it</button></span>
                        : <span className="text-slate-500">LTP ₹{q.ltp.toFixed(2)}{p && Math.abs(p - q.ltp) > 0.001 ? <> · <button className="underline" onClick={() => setLeg(i, { price: String(q.ltp) })}>use LTP</button></> : ""}</span>}
                    </div>
                  )}
                  {bad && q?.ltp == null && <div className="text-[11px] text-red-600 mt-0.5">looks like a strike — enter the option premium</div>}
                </td>
                <td className="pt-2">{!legsLocked && <button onClick={() => setLegs(legs.filter((_, j) => j !== i))} className="text-red-500">✕</button>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {(["CE", "PE"] as const).map((kind) => (
        <datalist key={kind} id={`od-strikes-${kind}`}>
          {[...chainRows.values()].filter((r) => (kind === "CE" ? r.ce : r.pe)?.ltp).map((r) => <option key={r.strike} value={r.strike} />)}
        </datalist>
      ))}
      {legsLocked ? (
        <p className="text-xs text-slate-500">Some legs are already closed, so legs can't be edited — header fields only.</p>
      ) : (
        <div className="flex gap-2">
          <button onClick={() => setLegs([...legs, { kind: "CE", side: "S", strike: "", price: "" }])}
            className="text-xs px-3 py-1 border border-slate-200 rounded-md">+ Add leg</button>
          {CREDIT_STRATEGIES.has(strategy) && symbol && !editing && (
            <button onClick={() => fillSuggested(symbol.toUpperCase(), strategy, expiry)}
              className="text-xs px-3 py-1 rounded-md bg-ink text-white">✨ Suggest strikes</button>
          )}
        </div>
      )}

      {readout.suspicious.length > 0 ? (
        <p className="text-sm text-red-600">
          Fix the highlighted price{readout.suspicious.length > 1 ? "s" : ""} — enter the option premium, not the strike. Credit and stop are recalculated once it's corrected.
        </p>
      ) : (
      <p className="text-sm">
        {readout.credit >= 0 ? <>Net credit: <b>₹{readout.credit.toFixed(2)}</b>/share ({fmtInr(readout.perLot)}/lot)</>
          : <span className="text-red-600">Net <b>debit</b> ₹{Math.abs(readout.credit).toFixed(2)}/share ({fmtInr(Math.abs(readout.perLot))}/lot)
            {CREDIT_STRATEGIES.has(strategy) && " — a " + strategy + " should receive a credit; check Sell/Buy and premiums"}</span>}
        {readout.stopLot != null && (
          <> · <b className="text-red-700">1:{stop[0]} stop</b> = loss of <b>{fmtInr(readout.stopLot)}/lot</b> ({stop[0]}× credit)</>
        )}
        {stop === "breach" && " · stop when spot comes within 0.5% of a short strike"}
        {readout.stopTotal != null && readout.riskBudget > 0 && (
          <span className={readout.stopTotal > readout.riskBudget ? "text-red-600" : "text-emerald-700"}>
            {" "}· total {fmtInr(readout.stopTotal)} vs risk budget {fmtInr(readout.riskBudget)}
            {readout.stopTotal > readout.riskBudget ? " — reduce lots or tighten the stop" : " ✓"}
          </span>
        )}
      </p>
      )}
      {suggestion && <p className="text-[11px] text-slate-400 -mt-2">Premiums as of {fmtWhen(suggestion.at)}</p>}

      <Field label="Note (optional)">
        <input value={note} onChange={(e) => setNote(e.target.value)} className={input} />
      </Field>

      <div className="flex gap-2">
        <button onClick={save} disabled={saving} className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-60">
          {editing ? "Save changes" : "Save position"}
        </button>
        <button onClick={analyse} className="px-4 py-2 rounded-lg border border-blue-600 text-blue-700 text-sm font-medium">
          Analyse
        </button>
        <button onClick={onDone} className="px-4 py-2 rounded-lg border border-slate-200 text-sm">Cancel</button>
      </div>
      {analysing && (
        <PayoffAnalyser onClose={() => setAnalysing(false)}
          load={() => positionsApi.analyseDraft(symbol.toUpperCase(), {
            expiry, lots: parseInt(lots), lot_size: parseInt(lotSize), strategy, legs: parsedLegs(),
          })} />
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs text-slate-500 mb-1">{label}</span>
      {children}
    </label>
  );
}
