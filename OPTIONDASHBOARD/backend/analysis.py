"""Per-symbol analysis for the Step 2 page: chart summary, reversal confluence,
squeeze, support/resistance levels, unfilled gaps and chart series."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import bollinger, keltner, pivots, resample, rsi, safe
from .signals import classify, zone

GAP_MIN_PCT = 1.5          # unfilled gaps at least this big
SR_LINE_MAX_PCT = 12.0     # draw S/R lines only within this distance of CMP
SR_LEGEND_MAX_PCT = 15.0   # list levels in the legend within this distance
SR_CLUSTER_TOL = 0.003     # pivots within 0.3% merge into one level
SR_SAME_TOUCH_DAYS = 10    # a daily + weekly pivot this close together = one touch
DIVERGENCE_ACTIVE_BARS = 20
PATTERN_LOOKBACK = 10
PIVOT_WINDOWS = {"D": (3, 3), "W": (2, 2), "M": (2, 2)}   # bars left/right of a swing


def pct_from(price: float, cmp: float) -> float:
    return round((price / cmp - 1) * 100, 1)


# ---- chart summary ---------------------------------------------------------------

def _bb_snapshot(df: pd.DataFrame, cmp: float) -> dict:
    bb = bollinger(df.close).iloc[-1]
    return {k: {"price": round(float(bb[f"bb_{k}"]), 2), "pct": pct_from(bb[f"bb_{k}"], cmp)}
            for k in ("upper", "mid", "lower")}


def _prev_month(monthly: pd.DataFrame, last_day: pd.Timestamp, cmp: float) -> dict:
    current = monthly.index[-1].month == last_day.month and monthly.index[-1].year == last_day.year
    bar = monthly.iloc[-2] if current and len(monthly) > 1 else monthly.iloc[-1]
    label = (monthly.index[-2] if current and len(monthly) > 1 else monthly.index[-1]).strftime("%Y-%m")
    return {"month": label,
            "high": {"price": round(float(bar.high), 2), "pct": pct_from(bar.high, cmp)},
            "low": {"price": round(float(bar.low), 2), "pct": pct_from(bar.low, cmp)}}


def chart_summary(daily, weekly, monthly, cfg: dict) -> dict:
    cmp = float(daily.close.iloc[-1])
    period = int(cfg.get("rsi_period", 14))
    bear, bull = float(cfg.get("bearish_below", 40)), float(cfg.get("bullish_above", 60))
    rows = {}
    for tf, df in (("weekly", weekly), ("daily", daily)):
        v = float(rsi(df.close, period).iloc[-1])
        z = zone(v, bear, bull)
        rule = {"bearish": f"RSI < {bear:g}", "bullish": f"RSI > {bull:g}",
                "neutral": f"{bear:g} ≤ RSI ≤ {bull:g}"}[z]
        rows[tf] = {"rsi": round(v, 1), "zone": z, "rule": rule}
    return {
        "cmp": cmp,
        "date": daily.index[-1].strftime("%Y-%m-%d"),
        "rsi": rows,
        "signal": classify(rows["weekly"]["rsi"], rows["daily"]["rsi"], bear, bull),
        "bb_weekly": _bb_snapshot(weekly, cmp),
        "bb_daily": _bb_snapshot(daily, cmp),
        "prev_month": _prev_month(monthly, daily.index[-1], cmp),
    }


# ---- reversal confluence -------------------------------------------------------------

def bb_exhaustion(daily: pd.DataFrame) -> dict:
    bb = bollinger(daily.close)
    tail, btail = daily.tail(3), bb.tail(3)
    last_close, mid = float(daily.close.iloc[-1]), float(bb.bb_mid.iloc[-1])
    half = "lower" if last_close < mid else "upper"
    # closes (not intraday wicks) outside the bands count as exhaustion
    if (tail.close <= btail.bb_lower).any():
        return {"pass": True, "direction": "bullish", "title": "Closed below lower band · Downside exhaustion",
                "detail": "Price closed at or below the lower Bollinger Band in the last 3 sessions — the down-move is stretched and prone to a bounce."}
    if (tail.close >= btail.bb_upper).any():
        return {"pass": True, "direction": "bearish", "title": "Closed above upper band · Upside exhaustion",
                "detail": "Price closed at or above the upper Bollinger Band in the last 3 sessions — the up-move is stretched and prone to a pullback."}
    trend = "down" if half == "lower" else "up"
    return {"pass": False, "direction": None, "title": f"Price in {half} half · No exhaustion",
            "detail": f"Price is in the {half} half of the bands — trend is {trend} but not yet at an extreme."}


def divergences(daily: pd.DataFrame, period: int = 14) -> list[dict]:
    """Regular RSI divergences between consecutive swing points (last ~2 years)."""
    df = daily.tail(520)
    r = rsi(daily.close, period).reindex(df.index)
    highs, lows = pivots(df, 5, 3)
    n = len(df)
    out = []
    for mask, kind in ((lows, "bullish"), (highs, "bearish")):
        idx = np.flatnonzero(mask.values)
        for a, b in zip(idx, idx[1:]):
            if not 5 <= b - a <= 60 or np.isnan(r.iloc[a]) or np.isnan(r.iloc[b]):
                continue
            if kind == "bullish":
                hit = df.low.iloc[b] < df.low.iloc[a] and r.iloc[b] > r.iloc[a]
                p1, p2 = df.low.iloc[a], df.low.iloc[b]
            else:
                hit = df.high.iloc[b] > df.high.iloc[a] and r.iloc[b] < r.iloc[a]
                p1, p2 = df.high.iloc[a], df.high.iloc[b]
            if hit:
                out.append({"kind": kind,
                            "from": df.index[a].strftime("%Y-%m-%d"), "to": df.index[b].strftime("%Y-%m-%d"),
                            "price_from": round(float(p1), 2), "price_to": round(float(p2), 2),
                            "rsi_from": round(float(r.iloc[a]), 1), "rsi_to": round(float(r.iloc[b]), 1),
                            "bars_ago": int(n - 1 - b)})
    return sorted(out, key=lambda d: d["to"])


def divergence_check(daily: pd.DataFrame, period: int) -> dict:
    divs = divergences(daily, period)
    active = [d for d in divs if d["bars_ago"] <= DIVERGENCE_ACTIVE_BARS]
    if active:
        d = active[-1]
        return {"pass": True, "direction": d["kind"], "items": divs,
                "title": f"{d['kind'].title()} divergence {d['bars_ago']} bars ago",
                "detail": (f"Price made a {'lower low' if d['kind'] == 'bullish' else 'higher high'} "
                           f"({d['price_from']} → {d['price_to']}) but RSI did not "
                           f"({d['rsi_from']} → {d['rsi_to']}) — momentum is fading.")}
    old = len(divs)
    return {"pass": False, "direction": None, "items": divs,
            "title": f"{old} historical divergence(s) — none active in last {DIVERGENCE_ACTIVE_BARS} bars",
            "detail": (f"Past divergences exist but they are too old to act on. Only divergences within the last "
                       f"{DIVERGENCE_ACTIVE_BARS} days count.") if old else "No RSI divergence found in the last 2 years."}


def candle_patterns(daily: pd.DataFrame) -> list[dict]:
    df = daily.tail(PATTERN_LOOKBACK + 10)
    bb = bollinger(daily.close).reindex(df.index)
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
    body = np.abs(c - o)
    rng = h - l
    up_wick = h - np.maximum(o, c)
    lo_wick = np.minimum(o, c) - l
    avg_body = pd.Series(body).rolling(10, min_periods=3).mean().values
    found = []
    for i in range(max(2, len(df) - PATTERN_LOOKBACK), len(df)):
        if rng[i] <= 0:
            continue
        pats = []
        if lo_wick[i] >= 2 * body[i] and up_wick[i] <= max(body[i], 0.1 * rng[i]):
            pats.append(("Hammer", "bullish"))
        if up_wick[i] >= 2 * body[i] and lo_wick[i] <= max(body[i], 0.1 * rng[i]):
            pats.append(("Shooting star", "bearish"))
        if c[i - 1] < o[i - 1] and c[i] > o[i] and c[i] >= o[i - 1] and o[i] <= c[i - 1] and body[i] > body[i - 1]:
            pats.append(("Bullish engulfing", "bullish"))
        if c[i - 1] > o[i - 1] and c[i] < o[i] and c[i] <= o[i - 1] and o[i] >= c[i - 1] and body[i] > body[i - 1]:
            pats.append(("Bearish engulfing", "bearish"))
        big2 = body[i - 2] >= (avg_body[i - 2] if not np.isnan(avg_body[i - 2]) else 0)
        if big2 and body[i - 1] <= 0.5 * body[i - 2]:
            mid2 = (o[i - 2] + c[i - 2]) / 2
            if c[i - 2] < o[i - 2] and c[i] > o[i] and c[i] > mid2:
                pats.append(("Morning star", "bullish"))
            if c[i - 2] > o[i - 2] and c[i] < o[i] and c[i] < mid2:
                pats.append(("Evening star", "bearish"))
        mid1 = (o[i - 1] + c[i - 1]) / 2
        if c[i - 1] < o[i - 1] and o[i] < c[i - 1] and mid1 < c[i] < o[i - 1]:
            pats.append(("Piercing line", "bullish"))
        if c[i - 1] > o[i - 1] and o[i] > c[i - 1] and o[i - 1] < c[i] < mid1:
            pats.append(("Dark cloud cover", "bearish"))
        for name, direction in pats:
            # quality: comes after a move in the opposite direction, near the outer band
            if direction == "bullish":
                prior = i >= 5 and c[i - 1] < c[i - 5]
                near = l[i] <= bb.bb_lower.iloc[i] * 1.02 if not np.isnan(bb.bb_lower.iloc[i]) else False
            else:
                prior = i >= 5 and c[i - 1] > c[i - 5]
                near = h[i] >= bb.bb_upper.iloc[i] * 0.98 if not np.isnan(bb.bb_upper.iloc[i]) else False
            found.append({"date": df.index[i].strftime("%Y-%m-%d"), "name": name,
                          "direction": direction, "quality": bool(prior and near)})
    return found


def pattern_check(daily: pd.DataFrame) -> dict:
    pats = candle_patterns(daily)
    good = [p for p in pats if p["quality"]]
    if good:
        p = good[-1]
        return {"pass": True, "direction": p["direction"], "items": pats,
                "title": f"{p['name']} on {p['date']}",
                "detail": f"A {p['direction']} reversal candle formed after a move into the "
                          f"{'lower' if p['direction'] == 'bullish' else 'upper'} band — candle-level confirmation."}
    return {"pass": False, "direction": None, "items": pats,
            "title": f"No high-quality pattern in last {PATTERN_LOOKBACK} days",
            "detail": "No strong reversal candle has appeared recently. Without a pattern, the other signals have no candle-level confirmation."}


def squeeze(df: pd.DataFrame) -> dict:
    """TTM-style squeeze: Bollinger Bands inside Keltner Channels = compression;
    bands moving back outside = squeeze 'fired'."""
    bb, kc = bollinger(df.close), keltner(df)
    valid = bb.bb_upper.notna() & kc.kc_upper.notna()
    on = (bb.bb_upper < kc.kc_upper) & (bb.bb_lower > kc.kc_lower) & valid
    if len(on) < 3:
        return {"state": "off"}
    direction = "up" if df.close.iloc[-1] > bb.bb_mid.iloc[-1] else "down"
    if not on.iloc[-1] and on.iloc[-3:-1].any():
        return {"state": "fired", "direction": direction}
    if on.iloc[-1]:
        bars = int((on[::-1].cumprod()).sum())
        return {"state": "on", "bars": bars}
    return {"state": "off"}


def confluence(daily: pd.DataFrame, weekly: pd.DataFrame, period: int) -> dict:
    checks = {"bollinger": bb_exhaustion(daily),
              "divergence": divergence_check(daily, period),
              "candlestick": pattern_check(daily)}
    votes = {"bullish": 0, "bearish": 0}
    for c in checks.values():
        if c["pass"]:
            votes[c["direction"]] += 1
    direction = max(votes, key=votes.get)
    score = votes[direction]
    verdict = {0: "No significant reversal signal", 1: f"Weak {direction} reversal hint",
               2: f"Probable {direction} reversal", 3: f"Strong {direction} reversal"}[score]
    sq = {"weekly": squeeze(weekly), "daily": squeeze(daily)}
    return {"score": score, "direction": direction if score else None, "verdict": verdict,
            "checks": checks, "squeeze": sq, "meaning": _meaning(checks, score, direction, sq)}


def _meaning(checks: dict, score: int, direction: str, sq: dict) -> str:
    parts = []
    if score == 0:
        if checks["bollinger"]["title"].startswith("Price in"):
            parts.append("The stock is trading normally inside its Bollinger Bands with no momentum "
                         "warning signs and no reversal patterns. Nothing here indicates the current trend is about to change.")
        else:
            parts.append("No reversal evidence is lining up right now.")
    else:
        against = "rally" if direction == "bullish" else "decline"
        parts.append(f"{score} of 3 reversal checks point {direction} — the market may be setting up a "
                     f"{against} against the current move. Be cautious selling options on the side it would run into.")
    for tf, s in sq.items():
        if s["state"] == "fired":
            parts.append(f"The {tf} volatility squeeze has fired {s['direction']}wards, so expect range "
                         "expansion — keep short strikes further away than usual.")
        elif s["state"] == "on":
            parts.append(f"The {tf} chart is in a squeeze ({s['bars']} bars) — volatility is compressed "
                         "and a sharp move often follows.")
    return " ".join(parts)


# ---- support / resistance -----------------------------------------------------------

def sr_levels(daily: pd.DataFrame, years: int, cmp: float) -> list[dict]:
    start = daily.index[-1] - pd.DateOffset(years=years)
    d = daily[daily.index >= start]
    frames = {"D": d, "W": resample(d, "W-FRI"), "M": resample(d, "MS")}
    pts = []
    for tf, df in frames.items():
        left, right = PIVOT_WINDOWS[tf]
        highs, lows = pivots(df, left, right)
        pts += [(float(df.high[t]), t, tf) for t in df.index[highs]]
        pts += [(float(df.low[t]), t, tf) for t in df.index[lows]]
    pts.sort(key=lambda p: p[0])

    clusters: list[list[tuple]] = []
    for p in pts:
        if clusters and abs(p[0] / np.mean([q[0] for q in clusters[-1]]) - 1) <= SR_CLUSTER_TOL:
            clusters[-1].append(p)
        else:
            clusters.append([p])

    levels = []
    for cl in clusters:
        price = float(np.mean([p[0] for p in cl]))
        dist = pct_from(price, cmp)
        if abs(dist) > SR_LEGEND_MAX_PCT:
            continue
        # merge the same turning point seen on several timeframes into one touch
        touches: list[dict] = []
        for p in sorted(cl, key=lambda p: p[1]):
            if touches and (p[1] - touches[-1]["_t"]).days <= SR_SAME_TOUCH_DAYS:
                touches[-1]["tfs"].add(p[2])
            else:
                touches.append({"_t": p[1], "date": p[1].strftime("%Y-%m-%d"), "price": round(p[0], 2), "tfs": {p[2]}})
        tfs = sorted({p[2] for p in cl}, key="DWM".index)
        levels.append({
            "price": round(price, 2),
            "kind": "R" if price > cmp else "S",
            "pct": dist,
            "tfs": "+".join(tfs),
            "touches": len(touches),
            "multi_tf": len(tfs) > 1,
            "drawn": len(touches) >= 2 and abs(dist) <= SR_LINE_MAX_PCT,
            "points": [{"date": t["date"], "price": t["price"], "tfs": "+".join(sorted(t["tfs"], key="DWM".index))}
                       for t in touches],
        })
    return sorted(levels, key=lambda lv: -lv["price"])


def unfilled_gaps(daily: pd.DataFrame, years: int) -> list[dict]:
    start = daily.index[-1] - pd.DateOffset(years=years)
    d = daily[daily.index >= start]
    h, l = d.high.values, d.low.values
    later_low = np.minimum.accumulate(l[::-1])[::-1]     # min low from i onwards
    later_high = np.maximum.accumulate(h[::-1])[::-1]
    out = []
    for i in range(1, len(d)):
        after_low = later_low[i + 1] if i + 1 < len(d) else np.inf
        after_high = later_high[i + 1] if i + 1 < len(d) else -np.inf
        if l[i] >= h[i - 1] * (1 + GAP_MIN_PCT / 100) and after_low > h[i - 1]:
            out.append({"date": d.index[i].strftime("%Y-%m-%d"), "kind": "up",
                        "bottom": round(float(h[i - 1]), 2), "top": round(float(min(l[i], after_low)), 2)})
        elif h[i] <= l[i - 1] * (1 - GAP_MIN_PCT / 100) and after_high < l[i - 1]:
            out.append({"date": d.index[i].strftime("%Y-%m-%d"), "kind": "down",
                        "bottom": round(float(max(h[i], after_high)), 2), "top": round(float(l[i - 1]), 2)})
    return out


# ---- chart series -------------------------------------------------------------------------

def ohlc_series(df: pd.DataFrame, since: pd.Timestamp) -> list[dict]:
    bb = bollinger(df.close)
    out = []
    for t, r in df[df.index >= since].iterrows():
        b = bb.loc[t]
        out.append({"time": t.strftime("%Y-%m-%d"), "open": r.open, "high": r.high, "low": r.low,
                    "close": r.close, "bb_upper": safe(b.bb_upper), "bb_mid": safe(b.bb_mid),
                    "bb_lower": safe(b.bb_lower)})
    return out


def rsi_series(df: pd.DataFrame, since: pd.Timestamp, period: int) -> list[dict]:
    r = rsi(df.close, period)
    r = r[r.index >= since].dropna()
    return [{"time": t.strftime("%Y-%m-%d"), "value": round(float(v), 2)} for t, v in r.items()]


def analyse(daily: pd.DataFrame, cfg: dict, years: int = 2, tf: str = "W") -> dict:
    period = int(cfg.get("rsi_period", 14))
    weekly, monthly = resample(daily, "W-FRI"), resample(daily, "MS")
    summary = chart_summary(daily, weekly, monthly, cfg)
    cmp = summary["cmp"]
    conf = confluence(daily, weekly, period)
    summary["confluence"] = {"score": conf["score"], "verdict": conf["verdict"]}
    last = daily.index[-1]
    price_df = {"D": daily, "W": weekly, "M": monthly}[tf]
    return {
        "summary": summary,
        "confluence": conf,
        "rsi_charts": {"weekly": rsi_series(weekly, last - pd.DateOffset(years=3), period),
                       "daily": rsi_series(daily, last - pd.DateOffset(years=2), period)},
        "sr": {"tf": tf, "years": years,
               "candles": ohlc_series(price_df, last - pd.DateOffset(years=years)),
               "levels": sr_levels(daily, years, cmp),
               "gaps": unfilled_gaps(daily, years),
               "zone_pct": [5, 12]},
    }
