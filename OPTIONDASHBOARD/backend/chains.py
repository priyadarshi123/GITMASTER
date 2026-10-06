"""Option chain read model: NSE chain + Greeks + analytics, expiries, lot sizes,
and strategy evaluation for the position builder."""
from __future__ import annotations

import copy
import json
import threading
import time
from datetime import date

from . import config, db, options
from .providers import nse

_cache: dict[tuple[str, str], tuple[float, dict]] = {}
_lock = threading.Lock()


def _cfg() -> dict:
    return config.settings().get("options", {})


def is_index(symbol: str) -> bool:
    inst = next((i for i in config.watchlist() if i.symbol == symbol), None)
    return (inst.kind == "index") if inst else symbol in nse.INDEX_SYMBOLS


def expiries(symbol: str) -> list[date]:
    key = f"expiries:{symbol}"
    raw = db.get_meta(key)
    if raw:
        cached = json.loads(raw)
        if cached.get("day") == date.today().isoformat():
            return [date.fromisoformat(d) for d in cached["dates"]]
    dates = [d for d in nse.expiries(symbol) if d >= date.today()]
    db.set_meta(key, json.dumps({"day": date.today().isoformat(), "dates": [d.isoformat() for d in dates]}))
    return dates


def lot_size(symbol: str, expiry: date) -> int | None:
    raw = db.get_meta("lot_sizes")
    cached = json.loads(raw) if raw else {}
    if cached.get("day") != date.today().isoformat():
        cached = {"day": date.today().isoformat(), "lots": nse.lot_sizes()}
        db.set_meta("lot_sizes", json.dumps(cached))
    by_month = cached["lots"].get(symbol) or {}
    return by_month.get(expiry.strftime("%b-%y").upper()) or next(iter(by_month.values()), None)


def chain(symbol: str, expiry: date | None = None) -> dict:
    exps = expiries(symbol)
    if not exps:
        raise nse.NSEError(f"no F&O expiries for {symbol}")
    expiry = expiry if expiry in exps else exps[0]
    key = (symbol, expiry.isoformat())
    ttl = float(_cfg().get("chain_cache_sec", 60))
    with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < ttl:
            return copy.deepcopy(hit[1])
    data = options.enrich_chain(nse.option_chain(symbol, expiry), float(_cfg().get("risk_free_rate", 0.065)))
    data["expiries"] = [d.isoformat() for d in exps]
    data["lot_size"] = lot_size(symbol, expiry)
    data["is_index"] = is_index(symbol)
    data["fetched_at"] = db.now_iso()
    with _lock:
        _cache[key] = (time.monotonic(), data)
    return copy.deepcopy(data)


def evaluate(symbol: str, expiry: date, legs: list[dict], lot_size_: int | None = None,
             spot: float | None = None, iv: float | None = None) -> dict:
    """Payoff metrics for user-built legs. Spot/IV default to the live chain."""
    ch = chain(symbol, expiry)
    spot = spot or ch["analytics"]["spot"]
    lot = lot_size_ or ch["lot_size"] or 1
    parsed = [options.Leg(kind=l["kind"], side=l["side"], strike=float(l["strike"]),
                          price=float(l["price"]), lots=int(l.get("lots", 1))) for l in legs]
    # POP uses the average IV of the short strikes (fallback: ATM IV)
    if iv is None:
        by_strike = {r["strike"]: r for r in ch["rows"]}
        ivs = [((by_strike.get(l.strike) or {}).get(l.kind.lower()) or {}).get("iv")
               for l in parsed if l.side == "S"]
        ivs = [v for v in ivs if v]
        iv = sum(ivs) / len(ivs) if ivs else ch["analytics"]["atm_iv"]
    cfg = config.settings()
    out = options.evaluate(parsed, spot, iv, options.years_to_expiry(expiry),
                           float(_cfg().get("risk_free_rate", 0.065)), lot,
                           _cfg().get("margin", {}), ch["is_index"])
    capital = float(cfg.get("capital", {}).get("default", 100000))
    cap_pct = float(cfg.get("capital", {}).get("margin_cap_pct", 20))
    out.update(computed_at=db.now_iso(), chain_fetched_at=ch["fetched_at"], chain_timestamp=ch["timestamp"],
               spot=spot, iv_used=round(iv, 2) if iv else None, lot_size=lot,
               capital=capital, margin_cap=round(capital * cap_pct / 100, 0), margin_cap_pct=cap_pct)
    out["within_cap"] = bool(out.get("margin")) and out["margin"]["amount"] <= out["margin_cap"]
    return out


# ---- strike suggestions -------------------------------------------------------------

ZONE = (5.0, 12.0)            # % from CMP
MAX_SHORT_DELTA = 0.30
HEDGE_STEPS = 2               # hedge this many strikes beyond the short one
STRUCTURE_SIDES = {"Bear Call": ("CE",), "Bull Put": ("PE",), "Iron Condor": ("CE", "PE")}


def suggest(symbol: str, strategy: str, expiry: date | None = None) -> dict:
    """Recommended legs for a structure: sell the first strike just beyond the nearest
    drawn S/R level inside the 5–12% zone with |delta| ≤ 0.30; hedge two strikes out."""
    from . import analysis   # local import: analysis pulls in pandas-heavy helpers

    sides = STRUCTURE_SIDES.get(strategy)
    if not sides:
        raise ValueError(f"no suggestion for strategy {strategy!r}")
    ch = chain(symbol, expiry)
    spot = ch["analytics"]["spot"]
    daily = db.load_candles(symbol)
    levels = [l for l in analysis.sr_levels(daily, 2, spot) if l["drawn"]] if len(daily) > 60 else []

    legs, notes = [], []
    for kind in sides:
        key = kind.lower()
        otm = [r for r in ch["rows"] if (r.get(key) or {}).get("ltp")
               and (r["strike"] >= spot * (1 + ZONE[0] / 100) if kind == "CE" else r["strike"] <= spot * (1 - ZONE[0] / 100))]
        ordered = otm if kind == "CE" else otm[::-1]          # nearest to CMP first
        if not ordered:
            notes.append(f"No traded {kind} strikes ≥ {ZONE[0]:g}% from CMP")
            continue
        in_zone = [l["price"] for l in levels
                   if l["kind"] == ("R" if kind == "CE" else "S") and ZONE[0] <= abs(l["pct"]) <= ZONE[1]]
        guard = (min(in_zone) if kind == "CE" else max(in_zone)) if in_zone else None
        beyond = (lambda k: guard is None or (k > guard if kind == "CE" else k < guard))
        def delta_ok(r) -> bool:
            d = r[key].get("delta")
            return d is not None and abs(d) <= MAX_SHORT_DELTA
        # preference: beyond the S/R guard with low delta → beyond the guard → nearest in zone
        short = (next((r for r in ordered if beyond(r["strike"]) and delta_ok(r)), None)
                 or next((r for r in ordered if beyond(r["strike"])), None)
                 or ordered[0])
        i = ordered.index(short)
        hedge = ordered[i + HEDGE_STEPS] if i + HEDGE_STEPS < len(ordered) else (ordered[i + 1] if i + 1 < len(ordered) else None)
        for side, row in (("S", short), ("B", hedge)):
            if row:
                q = row[key]
                legs.append({"kind": kind, "side": side, "strike": row["strike"], "price": q["ltp"],
                             "delta": q.get("delta"), "iv": q.get("iv"), "oi": q.get("oi"),
                             "pct": round((row["strike"] / spot - 1) * 100, 2)})
        why = f"beyond {'resistance' if kind == 'CE' else 'support'} {guard:.1f}" if guard else "no S/R level in the 5–12% zone"
        notes.append(f"{kind}: sell {short['strike']:g} ({why}, Δ {short[key].get('delta')}), "
                     f"hedge {hedge['strike']:g}" if hedge else f"{kind}: sell {short['strike']:g}, no hedge strike available")
    return {"symbol": symbol, "strategy": strategy, "expiry": ch["expiry"], "spot": spot,
            "lot_size": ch["lot_size"], "legs": legs, "notes": notes,
            "chain_fetched_at": ch["fetched_at"], "chain_timestamp": ch["timestamp"]}
