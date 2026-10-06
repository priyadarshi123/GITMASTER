import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  LineSeries,
  LineStyle,
  type IChartApi,
  type IPrimitivePaneRenderer,
  type IPrimitivePaneView,
  type ISeriesApi,
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type SeriesType,
  type Time,
} from "lightweight-charts";

export interface OHLC {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  bb_upper?: number | null;
  bb_mid?: number | null;
  bb_lower?: number | null;
}

/** Horizontal price band, optionally starting at a date (e.g. an unfilled gap). */
export interface Band {
  from: number;
  to: number;
  color: string;
  startTime?: string;
}

export interface HLine {
  price: number;
  color: string;
  width?: 1 | 2 | 3 | 4;
  style?: LineStyle;
  title?: string;
}

const UP = "#16a34a";
const DOWN = "#dc2626";
const BB = "#60a5fa";
const MID = "#f59e0b";

function baseChart(el: HTMLElement): IChartApi {
  return createChart(el, {
    autoSize: true,
    layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#475569", fontSize: 11 },
    grid: { vertLines: { color: "#f1f5f9" }, horzLines: { color: "#f1f5f9" } },
    rightPriceScale: { borderColor: "#e2e8f0" },
    timeScale: { borderColor: "#e2e8f0" },
    crosshair: { mode: 0 },
  });
}

// ---- band primitive: shaded price ranges drawn behind the series ---------------------

class BandsRenderer implements IPrimitivePaneRenderer {
  constructor(private owner: BandsPrimitive) {}
  draw() {}
  drawBackground(target: Parameters<IPrimitivePaneRenderer["draw"]>[0]) {
    const p = this.owner.params;
    if (!p) return;
    target.useBitmapCoordinateSpace(({ context: ctx, bitmapSize, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
      for (const b of this.owner.bands) {
        const y1 = p.series.priceToCoordinate(b.from);
        const y2 = p.series.priceToCoordinate(b.to);
        if (y1 == null || y2 == null) continue;
        let x = 0;
        if (b.startTime) {
          const t = p.chart.timeScale().timeToCoordinate(b.startTime as Time);
          if (t == null) continue;
          x = Math.max(0, t * hr);
        }
        ctx.fillStyle = b.color;
        ctx.fillRect(x, Math.min(y1, y2) * vr, bitmapSize.width - x, Math.abs(y2 - y1) * vr);
      }
    });
  }
}

class BandsPrimitive implements ISeriesPrimitive<Time> {
  bands: Band[] = [];
  params: SeriesAttachedParameter<Time, SeriesType> | null = null;
  private view: IPrimitivePaneView = { renderer: () => new BandsRenderer(this), zOrder: () => "bottom" };
  attached(p: SeriesAttachedParameter<Time, SeriesType>) { this.params = p; }
  detached() { this.params = null; }
  paneViews() { return [this.view]; }
  updateAllViews() {}
  set(bands: Band[]) {
    this.bands = bands;
    this.params?.requestUpdate();
  }
}

// ---- RSI chart -------------------------------------------------------------------------

export function RsiChart({ data, color, bear = 40, bull = 60 }: {
  data: { time: string; value: number }[]; color: string; bear?: number; bull?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = baseChart(ref.current);
    const s = chart.addSeries(LineSeries, { color, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    s.setData(data.map((d) => ({ time: d.time as Time, value: d.value })));
    s.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
    const bands = new BandsPrimitive();
    s.attachPrimitive(bands);
    bands.set([
      { from: bull, to: 100, color: "rgba(22,163,74,0.07)" },
      { from: 0, to: bear, color: "rgba(220,38,38,0.07)" },
    ]);
    s.createPriceLine({ price: bull, color: UP, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "" });
    s.createPriceLine({ price: bear, color: DOWN, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "" });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data, color, bear, bull]);
  return <div ref={ref} className="h-64 w-full" />;
}

// ---- price chart (candles or line) with Bollinger Bands, lines and bands ----------------------

export function PriceChart({ candles, mode, showBB = true, lines = [], bands = [], height = 420 }: {
  candles: OHLC[];
  mode: "candle" | "line";
  showBB?: boolean;
  lines?: HLine[];
  bands?: Band[];
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const main = useRef<ISeriesApi<SeriesType> | null>(null);
  const prim = useRef<BandsPrimitive | null>(null);
  const priceLines = useRef<ReturnType<ISeriesApi<SeriesType>["createPriceLine"]>[]>([]);

  // series (rebuilt when data or mode changes)
  useEffect(() => {
    if (!ref.current) return;
    const chart = baseChart(ref.current);
    const t = (c: OHLC) => c.time as Time;
    let s: ISeriesApi<SeriesType>;
    if (mode === "candle") {
      s = chart.addSeries(CandlestickSeries, {
        upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN,
        priceLineVisible: false,
      });
      s.setData(candles.map((c) => ({ time: t(c), open: c.open, high: c.high, low: c.low, close: c.close })));
    } else {
      s = chart.addSeries(LineSeries, { color: "#334155", lineWidth: 2, priceLineVisible: false });
      s.setData(candles.map((c) => ({ time: t(c), value: c.close })));
    }
    if (showBB) {
      const band = (key: "bb_upper" | "bb_mid" | "bb_lower", color: string, style: LineStyle) => {
        const l = chart.addSeries(LineSeries, {
          color, lineWidth: 1, lineStyle: style, priceLineVisible: false, lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        l.setData(candles.filter((c) => c[key] != null).map((c) => ({ time: t(c), value: c[key] as number })));
      };
      band("bb_upper", BB, LineStyle.Dashed);
      band("bb_mid", MID, LineStyle.Solid);
      band("bb_lower", BB, LineStyle.Dashed);
    }
    const p = new BandsPrimitive();
    s.attachPrimitive(p);
    main.current = s;
    prim.current = p;
    priceLines.current = [];
    chart.timeScale().fitContent();
    return () => {
      chart.remove();
      main.current = null;
      prim.current = null;
    };
  }, [candles, mode, showBB]);

  // overlays (cheap to update without rebuilding the chart)
  useEffect(() => {
    const s = main.current;
    if (!s) return;
    priceLines.current.forEach((pl) => s.removePriceLine(pl));
    priceLines.current = lines.map((l) =>
      s.createPriceLine({
        price: l.price, color: l.color, lineWidth: l.width ?? 1, lineStyle: l.style ?? LineStyle.Solid,
        axisLabelVisible: !!l.title, title: l.title ?? "",
      }));
    prim.current?.set(bands);
  }, [lines, bands, candles, mode, showBB]);

  return <div ref={ref} style={{ height }} className="w-full" />;
}

export { LineStyle };
