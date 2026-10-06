"""Real/paper position book: record, value live against the NSE chain, stop
tracking, partial (leg) closes, and monthly/annual ROI."""
from __future__ import annotations

import logging
from datetime import date, datetime, time

from . import chains, config, db, options
from .providers import nse

log = logging.getLogger(__name__)

STOP_MULTIPLE = {"1x": 1.0, "2x": 2.0, "3x": 3.0}
BREACH_BUFFER = 0.005      # strike-breach stop fires within 0.5% of the short strike


# ---- persistence ------------------------------------------------------------------------

def _legs(con, position_id: int) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT * FROM legs WHERE position_id=? ORDER BY kind, strike", (position_id,))]


def get(position_id: int) -> dict | None:
    with db.connect() as con:
        row = con.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
        if not row:
            return None
        p = dict(row)
        p["legs"] = _legs(con, position_id)
    return p


def create(data: dict) -> int:
    stamp = db.now_iso()
    with db.connect() as con:
        cur = con.execute(
            "INSERT INTO positions(book, symbol, strategy, expiry, lots, lot_size, capital, risk_pct, "
            "stop_rule, note, entry_spot, entry_pop, margin, status, opened_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)",
            (data["book"], data["symbol"], data["strategy"], data["expiry"], data["lots"], data["lot_size"],
             data.get("capital"), data.get("risk_pct"), data["stop_rule"], data.get("note"),
             data.get("entry_spot"), data.get("entry_pop"), data.get("margin"),
             data.get("opened_at") or date.today().isoformat(), stamp, stamp))
        pid = cur.lastrowid
        con.executemany(
            "INSERT INTO legs(position_id, kind, side, strike, entry_price) VALUES (?, ?, ?, ?, ?)",
            [(pid, l["kind"], l["side"], l["strike"], l["price"]) for l in data["legs"]])
    _fill_entry_stats(pid)
    return pid


def update(position_id: int, data: dict) -> bool:
    """Edit entry details. Legs are replaced only while none has been closed."""
    p = get(position_id)
    if not p:
        return False
    with db.connect() as con:
        con.execute(
            "UPDATE positions SET strategy=?, expiry=?, lots=?, lot_size=?, capital=?, risk_pct=?, stop_rule=?, "
            "note=?, margin=COALESCE(?, margin), opened_at=COALESCE(?, opened_at), updated_at=? WHERE id=?",
            (data["strategy"], data["expiry"], data["lots"], data["lot_size"], data.get("capital"),
             data.get("risk_pct"), data["stop_rule"], data.get("note"), data.get("margin"),
             data.get("opened_at"), db.now_iso(), position_id))
        if data.get("legs") and not any(l["exit_price"] is not None for l in p["legs"]):
            con.execute("DELETE FROM legs WHERE position_id=?", (position_id,))
            con.executemany(
                "INSERT INTO legs(position_id, kind, side, strike, entry_price) VALUES (?, ?, ?, ?, ?)",
                [(position_id, l["kind"], l["side"], l["strike"], l["price"]) for l in data["legs"]])
    return True


def delete(position_id: int) -> bool:
    with db.connect() as con:
        con.execute("DELETE FROM legs WHERE position_id=?", (position_id,))
        return con.execute("DELETE FROM positions WHERE id=?", (position_id,)).rowcount > 0


def close(position_id: int, realized_pnl: float, closed_at: str | None = None) -> bool:
    with db.connect() as con:
        return con.execute(
            "UPDATE positions SET status='closed', realized_pnl=?, closed_at=?, updated_at=? WHERE id=? AND status='open'",
            (realized_pnl, closed_at or date.today().isoformat(), db.now_iso(), position_id)).rowcount > 0


def close_legs(position_id: int, exits: dict[int, float]) -> bool:
    """Close chosen legs at the given prices; the rest stay open and the credit,
    max loss and stop are recomputed from what remains."""
    today = date.today().isoformat()
    with db.connect() as con:
        for leg_id, price in exits.items():
            con.execute("UPDATE legs SET exit_price=?, closed_at=? WHERE id=? AND position_id=? AND exit_price IS NULL",
                        (price, today, leg_id, position_id))
    p = get(position_id)
    if p and all(l["exit_price"] is not None for l in p["legs"]):
        close(position_id, round(_realized_from_legs(p), 2))
    return True


def _fill_entry_stats(pid: int) -> None:
    """Spot, POP and margin at entry (best effort — NSE may be unreachable)."""
    p = get(pid)
    try:
        legs = [{"kind": l["kind"], "side": l["side"], "strike": l["strike"], "price": l["entry_price"],
                 "lots": p["lots"]} for l in p["legs"]]
        ev = chains.evaluate(p["symbol"], date.fromisoformat(p["expiry"]), legs, p["lot_size"])
    except (nse.NSEError, ValueError) as e:
        log.warning("entry stats for position %s: %s", pid, e)
        return
    with db.connect() as con:
        con.execute(
            "UPDATE positions SET entry_spot=COALESCE(entry_spot, ?), entry_pop=COALESCE(entry_pop, ?), "
            "margin=COALESCE(margin, ?) WHERE id=?",
            (ev.get("spot"), ev.get("pop"), (ev.get("margin") or {}).get("amount"), pid))


# ---- valuation ----------------------------------------------------------------------------

def _qty(p: dict) -> int:
    return int(p["lots"]) * int(p["lot_size"])


def _leg_pnl(leg: dict, price: float, qty: int) -> float:
    sign = 1 if leg["side"] == "S" else -1
    return sign * (leg["entry_price"] - price) * qty


def _realized_from_legs(p: dict) -> float:
    return sum(_leg_pnl(l, l["exit_price"], _qty(p)) for l in p["legs"] if l["exit_price"] is not None)


def _structure(p: dict, open_legs: list[dict]) -> dict:
    """Credit, max loss and stop for the legs still open."""
    lot = int(p["lot_size"])
    credit = sum((1 if l["side"] == "S" else -1) * l["entry_price"] for l in open_legs)
    parsed = [options.Leg(l["kind"], l["side"], l["strike"], l["entry_price"], 1) for l in open_legs]
    spot = p.get("entry_spot") or (max(l["strike"] for l in open_legs) if open_legs else 0)
    ev = options.evaluate(parsed, spot, None, 0.05, 0.0, lot, {}, False) if parsed else {}
    rule = p["stop_rule"]
    stop_loss = STOP_MULTIPLE[rule] * credit * _qty(p) if rule in STOP_MULTIPLE and credit > 0 else None
    return {
        "credit_share": round(credit, 2),
        "credit_lot": round(credit * lot, 2),
        "credit_total": round(credit * _qty(p), 2),
        "max_loss_total": None if not ev or ev.get("max_loss") is None else round(ev["max_loss"] * p["lots"], 2),
        "breakevens": ev.get("breakevens", []),
        "stop_loss": round(stop_loss, 2) if stop_loss is not None else None,
    }


def freshness() -> dict:
    now = datetime.now()
    if now.weekday() >= 5:
        tag = "AS OF CLOSE"
    elif now.time() < time(9, 15):
        tag = "AT PREV CLOSE"
    elif now.time() > time(15, 30):
        tag = "AS OF CLOSE"
    else:
        tag = "LIVE"
    return {"tag": tag, "updated": now.strftime("%H:%M")}


def value(p: dict, chain_cache: dict) -> dict:
    """Live P&L, stop usage, POP now vs entry, spot move since entry."""
    open_legs = [l for l in p["legs"] if l["exit_price"] is None]
    out = {**p, **_structure(p, open_legs), "realized_legs": round(_realized_from_legs(p), 2)}
    if p["status"] != "open":
        return out
    expiry = date.fromisoformat(p["expiry"])
    out["expired"] = expiry < date.today()
    key = (p["symbol"], p["expiry"])
    try:
        if key not in chain_cache:
            chain_cache[key] = chains.chain(p["symbol"], expiry) if not out["expired"] else None
        ch = chain_cache[key]
    except nse.NSEError as e:
        out["error"] = f"chain unavailable: {e}"
        return out

    spot = ch["analytics"]["spot"] if ch else None
    if ch:
        out["chain_fetched_at"], out["chain_timestamp"] = ch["fetched_at"], ch["timestamp"]
    by_strike = {r["strike"]: r for r in ch["rows"]} if ch else {}
    qty = _qty(p)
    unreal = 0.0
    for l in open_legs:
        quote = ((by_strike.get(l["strike"]) or {}).get(l["kind"].lower()) or {})
        price = quote.get("ltp")
        if price is None and spot is not None:
            price = max(0.0, spot - l["strike"]) if l["kind"] == "CE" else max(0.0, l["strike"] - spot)
        l["ltp"] = price
        if price is not None:
            l["pnl"] = round(_leg_pnl(l, price, qty), 2)
            unreal += l["pnl"]
    out["spot"] = spot
    out["unrealized"] = round(unreal, 2)
    out["pnl"] = round(unreal + out["realized_legs"], 2)
    if spot and p.get("entry_spot"):
        out["spot_move_pct"] = round((spot / p["entry_spot"] - 1) * 100, 2)

    # stop usage
    if p["stop_rule"] in STOP_MULTIPLE and out["stop_loss"]:
        out["stop_used_pct"] = round(max(0.0, -unreal) / out["stop_loss"] * 100, 1)
    elif p["stop_rule"] == "breach" and spot:
        used = []
        for l in open_legs:
            if l["side"] != "S":
                continue
            trigger = l["strike"] * (1 - BREACH_BUFFER) if l["kind"] == "CE" else l["strike"] * (1 + BREACH_BUFFER)
            start = p.get("entry_spot") or spot
            span = trigger - start
            used.append(max(0.0, (spot - start) / span * 100) if span else 100.0)
        out["stop_used_pct"] = round(max(used), 1) if used else None
    # secondary info: how close the nearest short strike is
    shorts = [l for l in open_legs if l["side"] == "S"]
    if spot and shorts:
        out["nearest_short_pct"] = round(min(abs(l["strike"] / spot - 1) * 100 for l in shorts), 2)

    # POP now for the remaining legs at their entry prices
    if ch and open_legs:
        try:
            ev = chains.evaluate(p["symbol"], expiry,
                                 [{"kind": l["kind"], "side": l["side"], "strike": l["strike"],
                                   "price": l["entry_price"], "lots": 1} for l in open_legs], p["lot_size"])
            out["pop_now"] = ev.get("pop")
        except nse.NSEError:
            pass
    return out


def analyse(position_id: int) -> dict | None:
    """Payoff-analyser inputs for a recorded position (its open legs only)."""
    p = get(position_id)
    if not p:
        return None
    open_legs = [l for l in p["legs"] if l["exit_price"] is None]
    if not open_legs:
        raise ValueError("no open legs to analyse")
    out = analyse_legs(p["symbol"], date.fromisoformat(p["expiry"]), open_legs, p["lots"], p["lot_size"])
    out.update(id=p["id"], book=p["book"], strategy=p["strategy"],
               realized_legs=round(_realized_from_legs(p), 2))
    return out


def analyse_legs(symbol: str, expiry: date, legs: list[dict], lots: int, lot_size: int) -> dict:
    """Inputs for the payoff analyser: legs (id, kind, side, strike, entry_price) with
    their live IV, spot and time to expiry. Payoff curves, metrics and Greeks are
    computed client-side so the target sliders and leg toggles respond instantly.
    Also used for unsaved legs in the position form."""
    if expiry < date.today():
        raise ValueError("expiry has passed")
    ch = chains.chain(symbol, expiry)
    if ch["expiry"] != expiry.isoformat():
        raise ValueError(f"{expiry.isoformat()} is not a listed expiry for {symbol}")
    spot = ch["analytics"]["spot"]
    atm_iv = ch["analytics"]["atm_iv"]
    by_strike = {r["strike"]: r for r in ch["rows"]}
    out_legs = []
    for l in legs:
        quote = (by_strike.get(l["strike"]) or {}).get(l["kind"].lower()) or {}
        out_legs.append({"id": l["id"], "kind": l["kind"], "side": l["side"], "strike": l["strike"],
                         "entry_price": l["entry_price"], "ltp": quote.get("ltp"),
                         "iv": quote.get("iv") or atm_iv})
    return {
        "id": None, "book": None, "symbol": symbol, "strategy": None,
        "expiry": expiry.isoformat(), "expiry_at": datetime.combine(expiry, options.EXPIRY_TIME).isoformat(),
        "lots": lots, "lot_size": lot_size, "qty": int(lots) * int(lot_size),
        "spot": spot, "atm_iv": atm_iv, "r": float(config.settings().get("options", {}).get("risk_free_rate", 0.065)),
        "realized_legs": 0.0,
        "legs": out_legs,
        "chain_timestamp": ch["timestamp"], "chain_fetched_at": ch["fetched_at"],
    }


def book(book_name: str) -> dict:
    with db.connect() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM positions WHERE book=? ORDER BY status, opened_at DESC, id DESC", (book_name,))]
        for p in rows:
            p["legs"] = _legs(con, p["id"])
    cache: dict = {}
    valued = [value(p, cache) for p in rows]
    open_ = [p for p in valued if p["status"] == "open"]
    closed = [p for p in valued if p["status"] == "closed"]
    return {"open": open_, "closed": closed, "roi": roi(open_, closed), "freshness": freshness(),
            "valued_at": db.now_iso(),
            "capital": config.settings().get("capital", {})}


def roi(open_: list[dict], closed: list[dict]) -> dict:
    """Per month: margin used by positions active that month, realised (closed that
    month) and unrealised (open now, counted in the current month); ROI on margin."""
    months: dict[str, dict] = {}

    def bucket(m: str) -> dict:
        return months.setdefault(m, {"month": m, "margin": 0.0, "realized": 0.0, "unrealized": 0.0, "trades": 0})

    for p in closed:
        b = bucket(p["closed_at"][:7])
        b["realized"] += p["realized_pnl"] or 0.0
        b["margin"] += p["margin"] or 0.0
        b["trades"] += 1
    if open_:
        b = bucket(date.today().strftime("%Y-%m"))
        for p in open_:
            b["unrealized"] += p.get("pnl") or 0.0
            b["margin"] += p["margin"] or 0.0

    def finish(rows: list[dict]) -> list[dict]:
        for r in rows:
            r["total"] = round(r["realized"] + r["unrealized"], 2)
            r["roi_pct"] = round(r["total"] / r["margin"] * 100, 2) if r["margin"] else None
            for k in ("margin", "realized", "unrealized"):
                r[k] = round(r[k], 2)
        return rows

    monthly = finish(sorted(months.values(), key=lambda r: r["month"], reverse=True))
    years: dict[str, dict] = {}
    for m in monthly:
        y = years.setdefault(m["month"][:4], {"year": m["month"][:4], "margin": 0.0, "realized": 0.0,
                                               "unrealized": 0.0, "trades": 0})
        for k in ("margin", "realized", "unrealized", "trades"):
            y[k] += m[k]
    annual = finish(sorted(years.values(), key=lambda r: r["year"], reverse=True))
    return {"monthly": monthly, "annual": annual}
