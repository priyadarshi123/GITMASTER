"""Refresh pipeline (candles -> quotes -> signals -> events) and read models for the API."""
from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, time, timedelta

import pandas as pd

from . import analysis, config, db, events, providers, signals
from .indicators import resample
from .providers import nse

log = logging.getLogger(__name__)

_refresh_lock = threading.Lock()
_state = {"running": False, "step": "", "error": ""}


def state() -> dict:
    return dict(_state)


def last_refresh() -> datetime | None:
    v = db.get_meta("last_refresh")
    return datetime.fromisoformat(v) if v else None


def market_open_now(cfg: dict | None = None) -> bool:
    cfg = cfg or config.settings().get("refresh", {})
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    start = time.fromisoformat(cfg.get("market_open", "09:15"))
    end = time.fromisoformat(cfg.get("market_close", "15:30"))
    return start <= now.time() <= end


def skip_reason(force: bool = False) -> str | None:
    """Why a refresh request should be skipped, or None if it should run."""
    if _state["running"]:
        return "refresh already running"
    gap = int(config.settings().get("refresh", {}).get("min_gap_sec", 120))
    last = last_refresh()
    if not force and last and (datetime.now() - last).total_seconds() < gap:
        return f"data is under {gap}s old"
    return None


def refresh(force: bool = False) -> dict:
    """Run a full refresh unless one ran within `min_gap_sec` (or one is running)."""
    if reason := skip_reason(force):
        return {"skipped": True, "reason": reason}
    cfg = config.settings()
    if not _refresh_lock.acquire(blocking=False):
        return {"skipped": True, "reason": "refresh already running"}
    try:
        _state.update(running=True, error="")
        _run(cfg)
        db.set_meta("last_refresh", db.now_iso())
        return {"skipped": False}
    except Exception as e:  # keep the app up; surface the error in the UI
        log.exception("refresh failed")
        _state["error"] = str(e)
        return {"skipped": False, "error": str(e)}
    finally:
        _state.update(running=False, step="")
        _refresh_lock.release()


def refresh_async(force: bool = False) -> None:
    threading.Thread(target=refresh, kwargs={"force": force}, daemon=True).start()


def _run(cfg: dict) -> None:
    instruments = config.watchlist()
    provider = providers.get()
    years = int(cfg.get("data", {}).get("history_years", 5))

    # 1. candles: full history for new symbols, otherwise the last few days
    #    (re-fetching a short overlap also replaces today's still-forming bar)
    _state["step"] = "candles"
    full_start = date.today() - timedelta(days=365 * years + 10)
    from_nse = [i for i in instruments if i.nse_index]
    from_provider = [i for i in instruments if not i.nse_index]
    new, existing = [], []
    for inst in from_provider:
        (existing if db.last_candle_date(inst.symbol) else new).append(inst)
    batches = [(new, full_start), (existing, date.today() - timedelta(days=10))]
    for batch, start in batches:
        if batch:
            for symbol, df in provider.daily_candles(batch, start).items():
                db.upsert_candles(symbol, df)
    for inst in from_nse:
        try:
            update_nse_index(inst.nse_index, inst.symbol, years)
        except nse.NSEError as e:
            log.warning("nse history %s: %s", inst.symbol, e)

    # 2. live quotes
    _state["step"] = "quotes"
    quotes = provider.quotes(from_provider)
    if from_nse:
        try:
            quotes.update(_nse_index_quotes(from_nse))
        except nse.NSEError as e:
            log.warning("nse index quotes: %s", e)
    stamp = db.now_iso()
    with db.connect() as con:
        con.executemany(
            "INSERT OR REPLACE INTO quotes(symbol, ltp, prev_close, change_pct, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [(s, q.ltp, q.prev_close, round(q.change_pct, 2), stamp) for s, q in quotes.items()])

    # 3. signals
    _state["step"] = "signals"
    sig_cfg = cfg.get("signals", {})
    rows = []
    for inst in instruments:
        res = signals.compute(db.load_candles(inst.symbol), sig_cfg)
        if res:
            rows.append((inst.symbol, res["rsi_w"], res["rsi_d"], res["signal"], stamp))
    with db.connect() as con:
        con.executemany(
            "INSERT OR REPLACE INTO signals(symbol, rsi_w, rsi_d, signal, computed_at) "
            "VALUES (?, ?, ?, ?, ?)", rows)

    # 4. expiry calendar from NSE, once a day
    today = date.today().isoformat()
    if db.get_meta("expiries_day") != today:
        _state["step"] = "expiries"
        try:
            stock = next((i.symbol for i in instruments if i.kind == "stock"), "RELIANCE")
            db.set_meta("stock_expiries", json.dumps([d.isoformat() for d in nse.expiries(stock)]))
            db.set_meta("expiries_day", today)
            db.set_meta("expiries_at", db.now_iso())
        except nse.NSEError as e:
            log.warning("expiries: %s", e)

    # 5. corporate events, once a day
    if cfg.get("events", {}).get("enabled", True) and db.get_meta("events_day") != today:
        _state["step"] = "events"
        try:
            events.refresh({i.symbol for i in instruments if i.kind == "stock"})
            db.set_meta("events_day", date.today().isoformat())
            db.set_meta("events_at", db.now_iso())
        except Exception as e:
            log.warning("events refresh failed: %s", e)


# ---- NSE indices -------------------------------------------------------------------

def update_nse_index(name: str, key: str, years: int = 5) -> None:
    """Full history on first use, then only the last couple of weeks."""
    last = db.last_candle_date(key)
    start = (date.fromisoformat(last) - timedelta(days=14) if last
             else date.today() - timedelta(days=365 * years + 10))
    db.upsert_candles(key, nse.index_history(name, start))
    db.set_meta(f"nse_index_at:{key}", db.now_iso())


def _nse_index_quotes(instruments) -> dict[str, providers.Quote]:
    """Quotes from NSE's index board; on a trading day also writes today's
    forming bar so daily RSI includes it (the history API only has closed days)."""
    board = nse.index_quotes()
    today = pd.Timestamp(date.today())
    out = {}
    for inst in instruments:
        q = board.get(inst.nse_index)
        if not q or not q.get("last"):
            continue
        out[inst.symbol] = providers.Quote(ltp=float(q["last"]), prev_close=float(q["prev_close"] or 0))
        if today.weekday() < 5 and (db.last_candle_date(inst.symbol) or "") < today.strftime("%Y-%m-%d"):
            bar = {k: float(q[k] or q["last"]) for k in ("open", "high", "low")}
            bar.update(close=float(q["last"]), volume=0.0)
            db.upsert_candles(inst.symbol, pd.DataFrame([bar], index=[today]))
    return out


def sector_candles(name: str) -> pd.DataFrame:
    """Daily candles for an NSE sector index, fetched lazily and refreshed at most every 6 h."""
    key = f"IDX:{name}"
    stamp = db.get_meta(f"nse_index_at:{key}")
    if not stamp or (datetime.now() - datetime.fromisoformat(stamp)).total_seconds() > 6 * 3600:
        try:
            update_nse_index(name, key)
        except nse.NSEError as e:
            log.warning("sector index %s: %s", name, e)
    return db.load_candles(key)


def next_expiry() -> date:
    today = date.today()
    for d in json.loads(db.get_meta("stock_expiries") or "[]"):
        if date.fromisoformat(d) >= today:
            return date.fromisoformat(d)
    return events.next_monthly_expiry(today)


# ---- read models ---------------------------------------------------------------

PROVIDER_LABEL = {"yahoo": "Yahoo Finance (≈15 min delayed)", "angel": "Angel One SmartAPI (live)"}


def price_source(inst, provider) -> str:
    if inst.nse_index:
        return f"NSE index data ({inst.nse_index})"
    return PROVIDER_LABEL.get(provider.name, provider.name)


def dashboard() -> dict:
    instruments = config.watchlist()
    expiry = next_expiry()
    upcoming = events.upcoming(expiry)
    with db.connect() as con:
        quotes = {r["symbol"]: dict(r) for r in con.execute("SELECT * FROM quotes")}
        sigs = {r["symbol"]: dict(r) for r in con.execute("SELECT * FROM signals")}
        marks = {r["symbol"] for r in con.execute("SELECT symbol FROM bookmarks")}
        notes = {r["symbol"]: r["n"] for r in con.execute(
            "SELECT symbol, COUNT(*) n FROM notes GROUP BY symbol")}
        last_bars = {r["symbol"]: r["d"] for r in con.execute(
            "SELECT symbol, MAX(date) d FROM candles GROUP BY symbol")}

    provider = providers.get()
    items = []
    for inst in instruments:
        q, s = quotes.get(inst.symbol, {}), sigs.get(inst.symbol, {})
        items.append({
            "rank": inst.rank,
            "symbol": inst.symbol,
            "name": inst.name,
            "sector": inst.sector,
            "kind": inst.kind,
            "ltp": q.get("ltp"),
            "change_pct": q.get("change_pct"),
            "rsi_w": s.get("rsi_w"),
            "rsi_d": s.get("rsi_d"),
            "signal": s.get("signal"),
            "events": upcoming.get(inst.symbol, []),
            "bookmarked": inst.symbol in marks,
            "notes": notes.get(inst.symbol, 0),
            "source": price_source(inst, provider),
            "quote_at": q.get("updated_at"),
            "last_bar": last_bars.get(inst.symbol),
            "signal_at": s.get("computed_at"),
        })

    last = last_refresh()
    return {
        "items": items,
        "expiry": expiry.isoformat(),
        "asof": last.isoformat() if last else None,
        "provider": {"name": provider.name, "live": provider.live, "note": providers.note()},
        "refresh": state(),
        "market_open": market_open_now(),
        "fetched": {"events": db.get_meta("events_at") or db.get_meta("events_day"),
                    "expiries": db.get_meta("expiries_at") or db.get_meta("expiries_day")},
    }


def toggle_bookmark(symbol: str) -> bool:
    with db.connect() as con:
        if con.execute("SELECT 1 FROM bookmarks WHERE symbol=?", (symbol,)).fetchone():
            con.execute("DELETE FROM bookmarks WHERE symbol=?", (symbol,))
            return False
        con.execute("INSERT INTO bookmarks(symbol, created_at) VALUES (?, ?)", (symbol, db.now_iso()))
        return True


def analyse(symbol: str, years: int, tf: str) -> dict | None:
    inst = next((i for i in config.watchlist() if i.symbol == symbol), None)
    daily = db.load_candles(symbol)
    if len(daily) < 60:
        return None
    cfg = config.settings()
    out = analysis.analyse(daily, cfg.get("signals", {}), years, tf)
    out["instrument"] = {"symbol": symbol, "name": inst.name if inst else symbol,
                         "sector": inst.sector if inst else "", "kind": inst.kind if inst else "stock"}
    with db.connect() as con:
        q = con.execute("SELECT ltp, change_pct, updated_at FROM quotes WHERE symbol=?", (symbol,)).fetchone()
    out["quote"] = dict(q) if q else None
    last = last_refresh()
    out["meta"] = {
        "source": price_source(inst, providers.get()) if inst else "local database",
        "last_bar": daily.index[-1].strftime("%Y-%m-%d"),
        "first_bar": daily.index[0].strftime("%Y-%m-%d"),
        "bars": len(daily),
        "refreshed_at": last.isoformat() if last else None,
        "computed_at": db.now_iso(),
    }

    sector_name = (cfg.get("sector_indices") or {}).get(inst.sector if inst else "")
    out["sector"] = None
    if sector_name:
        idx = sector_candles(sector_name)
        if not idx.empty:
            monthly = resample(idx, "MS")
            out["sector"] = {"sector": inst.sector, "index": sector_name,
                             "fetched_at": db.get_meta(f"nse_index_at:IDX:{sector_name}"),
                             "last_bar": idx.index[-1].strftime("%Y-%m-%d"),
                             "candles": analysis.ohlc_series(monthly, monthly.index[-1] - pd.DateOffset(years=5))}
    return out


# ---- notes ---------------------------------------------------------------------------

def notes(symbol: str) -> list[dict]:
    with db.connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, symbol, note_date, text, created_at, updated_at FROM notes "
            "WHERE symbol=? ORDER BY note_date DESC, id DESC", (symbol,))]


def add_note(symbol: str, text: str, note_date: str | None = None) -> int:
    stamp = db.now_iso()
    with db.connect() as con:
        cur = con.execute(
            "INSERT INTO notes(symbol, note_date, text, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (symbol, note_date or date.today().isoformat(), text, stamp, stamp))
        return cur.lastrowid


def update_note(note_id: int, text: str, note_date: str | None = None) -> bool:
    with db.connect() as con:
        cur = con.execute(
            "UPDATE notes SET text=?, note_date=COALESCE(?, note_date), updated_at=? WHERE id=?",
            (text, note_date, db.now_iso(), note_id))
        return cur.rowcount > 0


def delete_note(note_id: int) -> bool:
    with db.connect() as con:
        return con.execute("DELETE FROM notes WHERE id=?", (note_id,)).rowcount > 0
