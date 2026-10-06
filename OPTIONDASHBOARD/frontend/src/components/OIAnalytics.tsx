import { fmtPrice, type Chain } from "../api";
import { oiInfo } from "../info";
import InfoTip, { type Info } from "./InfoTip";

/** OI summary strip shown above the option chain (the per-strike bars live in the chain table). */
export default function OISummary({ chain }: { chain: Chain }) {
  const an = chain.analytics;
  const spot = chain.underlying;
  const pct = (k: number | null) => (k == null ? "" : `${k > spot ? "+" : ""}${((k / spot - 1) * 100).toFixed(1)}% from CMP`);
  const pcrTone = an.pcr_oi == null ? "" : an.pcr_oi < 0.7 ? "text-red-600" : an.pcr_oi > 1.3 ? "text-emerald-700" : "text-slate-900";

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2 text-sm">
      <Tile info={oiInfo.pcr(chain)} label="PCR (OI)" value={an.pcr_oi?.toFixed(2) ?? "—"} cls={pcrTone}
        sub={an.pcr_oi == null ? "" : an.pcr_oi < 0.7 ? "call-heavy · bearish tilt" : an.pcr_oi > 1.3 ? "put-heavy · bullish tilt" : "balanced"} />
      <Tile info={oiInfo.pcrVol(chain)} label="PCR (volume)" value={an.pcr_volume?.toFixed(2) ?? "—"} />
      <Tile info={oiInfo.maxPain(chain)} label="Max pain ◆" value={an.max_pain ? fmtPrice(an.max_pain) : "—"} sub={pct(an.max_pain)} />
      <Tile info={oiInfo.atmIv(chain)} label="ATM IV" value={an.atm_iv ? `${an.atm_iv}%` : "—"} sub={`ATM ${an.atm}`} />
      <Tile info={oiInfo.walls(chain)} label="Call wall (resistance)" value={an.top_ce_oi.map((t) => t.strike).join(" · ")} cls="text-red-700" sub="highest call OI" />
      <Tile info={oiInfo.walls(chain)} label="Put wall (support)" value={an.top_pe_oi.map((t) => t.strike).join(" · ")} cls="text-emerald-700" sub="highest put OI" />
      <Tile info={oiInfo.dte(chain)} label="Days to expiry" value={String(an.days_to_expiry)} />
    </div>
  );
}

function Tile({ label, value, sub, cls = "text-slate-900", info }: { label: string; value: string; sub?: string; cls?: string; info?: Info }) {
  return (
    <div className="bg-slate-50 rounded-lg px-3 py-2">
      <div className="text-[11px] text-slate-500">{label} {info && <InfoTip info={info} />}</div>
      <div className={`font-semibold ${cls}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-400">{sub}</div>}
    </div>
  );
}
