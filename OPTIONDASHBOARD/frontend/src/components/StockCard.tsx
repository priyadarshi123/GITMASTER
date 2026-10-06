import { fmtPrice, type Item } from "../api";
import { dash } from "../info";
import InfoTip, { type Info } from "./InfoTip";
import { EventBadges, SectorChip, SignalChip } from "./chips";

interface Props {
  item: Item;
  eventsInfo: Info;
  selected: boolean;
  onSelect: () => void;
  onBookmark: () => void;
}

export default function StockCard({ item, eventsInfo, selected, onSelect, onBookmark }: Props) {
  const up = (item.change_pct ?? 0) >= 0;
  return (
    <div
      role="checkbox"
      aria-checked={selected}
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => (e.key === " " || e.key === "Enter") && (e.preventDefault(), onSelect())}
      className={`relative bg-white rounded-xl border p-4 pr-9 cursor-pointer transition select-none
        hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand
        ${selected ? "border-blue-500 ring-1 ring-blue-500 shadow-md" : "border-slate-200"}`}
    >
      <button
        onClick={(e) => (e.stopPropagation(), onBookmark())}
        title={item.bookmarked ? "Remove from watchlist" : "Add to watchlist"}
        className={`absolute top-2 right-2 text-lg leading-none ${item.bookmarked ? "text-brand" : "text-slate-300 hover:text-slate-500"}`}
      >
        {item.bookmarked ? "★" : "☆"}
      </button>
      <span
        className={`absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-2 grid place-items-center
          ${selected ? "border-blue-500 bg-blue-500" : "border-slate-300"}`}
      >
        {selected && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
      </span>

      <div className="flex gap-3">
        <div className="text-slate-400 text-sm w-5 shrink-0 pt-6 text-right">{item.rank}</div>
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-baseline justify-between gap-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="font-semibold text-slate-900 truncate">{item.symbol}</span>
              <EventBadges events={item.events} />
              {item.events.length > 0 && <InfoTip info={eventsInfo} />}
              {item.notes > 0 && (
                <span title={`${item.notes} note(s)`} className="text-[10px] px-1 rounded bg-slate-100 text-slate-500">
                  ✎{item.notes}
                </span>
              )}
            </div>
            <div className="text-sm whitespace-nowrap flex items-center gap-1">
              <span className="font-medium text-slate-900">{fmtPrice(item.ltp)}</span>{" "}
              {item.change_pct != null && (
                <span className={`text-xs ${up ? "text-emerald-600" : "text-red-600"}`}>
                  {up ? "+" : ""}{item.change_pct.toFixed(2)}%
                </span>
              )}
              <InfoTip info={dash.price(item)} />
            </div>
          </div>
          <div className="text-xs text-slate-500 truncate">{item.name}</div>
          <div><SectorChip sector={item.sector} /></div>
          <div className="flex items-center gap-2 flex-wrap">
            <SignalChip signal={item.signal} />
            <span className="text-xs text-slate-500 tabular-nums">
              W:{item.rsi_w?.toFixed(0) ?? "–"} D:{item.rsi_d?.toFixed(0) ?? "–"}
            </span>
            <InfoTip info={dash.rsi(item)} />
          </div>
        </div>
      </div>
    </div>
  );
}
