from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import alerts, chains, config, db, positions, scheduler, service
from .providers import nse
from .indicators import resample, rsi

DIST = config.ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    stop = scheduler.start()
    yield
    stop.set()


app = FastAPI(title="Option Dashboard", lifespan=lifespan)


@app.get("/api/dashboard")
def dashboard():
    return service.dashboard()


@app.post("/api/refresh")
def refresh(force: bool = False):
    """Starts a refresh in the background; poll /api/status for progress."""
    if reason := service.skip_reason(force):
        return {"started": False, "reason": reason}
    service.refresh_async(force=True)
    return {"started": True}


@app.get("/api/status")
def status():
    last = service.last_refresh()
    return {"refresh": service.state(), "asof": last.isoformat() if last else None}


@app.post("/api/bookmarks/{symbol}")
def bookmark(symbol: str):
    return {"symbol": symbol, "bookmarked": service.toggle_bookmark(symbol.upper())}


@app.get("/api/analysis/{symbol}")
def analysis(symbol: str, years: int = 2, tf: str = "W"):
    if years not in (2, 5) or tf.upper() not in ("D", "W", "M"):
        raise HTTPException(400, "years must be 2 or 5, tf D/W/M")
    out = service.analyse(symbol.upper(), years, tf.upper())
    if out is None:
        raise HTTPException(404, f"not enough history for {symbol} — run a refresh")
    return out


@app.get("/api/chain/{symbol}")
def option_chain(symbol: str, expiry: str | None = None):
    try:
        return chains.chain(symbol.upper(), date.fromisoformat(expiry) if expiry else None)
    except nse.NSEError as e:
        raise HTTPException(502, f"NSE option chain unavailable: {e}")


@app.get("/api/suggest/{symbol}")
def suggest(symbol: str, strategy: str, expiry: str | None = None):
    try:
        return chains.suggest(symbol.upper(), strategy, date.fromisoformat(expiry) if expiry else None)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except nse.NSEError as e:
        raise HTTPException(502, f"NSE option chain unavailable: {e}")


class LegIn(BaseModel):
    kind: Literal["CE", "PE"]
    side: Literal["S", "B"]
    strike: float
    price: float
    lots: int = 1


class StrategyIn(BaseModel):
    expiry: str
    legs: list[LegIn]
    lot_size: int | None = None


@app.post("/api/strategy/{symbol}")
def strategy(symbol: str, body: StrategyIn):
    if not body.legs:
        return {}
    try:
        return chains.evaluate(symbol.upper(), date.fromisoformat(body.expiry),
                               [l.model_dump() for l in body.legs], body.lot_size)
    except nse.NSEError as e:
        raise HTTPException(502, f"NSE option chain unavailable: {e}")


@app.get("/api/contract/{symbol}")
def contract(symbol: str):
    """Expiries + lot size per expiry, for the position form."""
    symbol = symbol.upper()
    try:
        exps = chains.expiries(symbol)
        return {"symbol": symbol, "expiries": [{"date": e.isoformat(), "lot_size": chains.lot_size(symbol, e)}
                                               for e in exps]}
    except nse.NSEError as e:
        raise HTTPException(502, f"NSE unavailable: {e}")


# ---- positions -------------------------------------------------------------------------

class PosLegIn(BaseModel):
    kind: Literal["CE", "PE"]
    side: Literal["S", "B"]
    strike: float
    price: float


class PositionIn(BaseModel):
    book: Literal["real", "paper"] = "real"
    symbol: str
    strategy: str
    expiry: str
    lots: int
    lot_size: int
    capital: float | None = None
    risk_pct: float | None = None
    stop_rule: Literal["1x", "2x", "3x", "breach"] = "3x"
    note: str | None = None
    margin: float | None = None
    opened_at: str | None = None
    legs: list[PosLegIn]


@app.get("/api/positions")
def list_positions(book: Literal["real", "paper"] = "real"):
    return positions.book(book)


@app.post("/api/positions")
def create_position(body: PositionIn):
    if not body.legs:
        raise HTTPException(400, "a position needs at least one leg")
    data = body.model_dump()
    data["symbol"] = data["symbol"].upper()
    return {"id": positions.create(data)}


@app.put("/api/positions/{pid}")
def edit_position(pid: int, body: PositionIn):
    if not positions.update(pid, body.model_dump()):
        raise HTTPException(404, "position not found")
    return {"ok": True}


class CloseIn(BaseModel):
    realized_pnl: float
    closed_at: str | None = None


@app.post("/api/positions/{pid}/close")
def close_position(pid: int, body: CloseIn):
    if not positions.close(pid, body.realized_pnl, body.closed_at):
        raise HTTPException(404, "open position not found")
    return {"ok": True}


class CloseLegsIn(BaseModel):
    exits: dict[int, float]      # leg id -> exit price


@app.post("/api/positions/{pid}/close-legs")
def close_legs(pid: int, body: CloseLegsIn):
    if not positions.get(pid):
        raise HTTPException(404, "position not found")
    positions.close_legs(pid, body.exits)
    return {"ok": True}


@app.get("/api/positions/{pid}/analyse")
def analyse_position(pid: int):
    try:
        out = positions.analyse(pid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except nse.NSEError as e:
        raise HTTPException(502, f"NSE unavailable: {e}")
    if out is None:
        raise HTTPException(404, "position not found")
    return out


class AnalyseIn(BaseModel):
    expiry: str
    lots: int
    lot_size: int
    strategy: str | None = None
    legs: list[PosLegIn]


@app.post("/api/analyse/{symbol}")
def analyse_draft(symbol: str, body: AnalyseIn):
    """Payoff analyser for legs not yet recorded (the position form)."""
    if not body.legs:
        raise HTTPException(400, "add at least one leg")
    legs = [{"id": i, "kind": l.kind, "side": l.side, "strike": l.strike, "entry_price": l.price}
            for i, l in enumerate(body.legs)]
    try:
        out = positions.analyse_legs(symbol.upper(), date.fromisoformat(body.expiry), legs, body.lots, body.lot_size)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except nse.NSEError as e:
        raise HTTPException(502, f"NSE unavailable: {e}")
    out["strategy"] = body.strategy
    return out


@app.delete("/api/positions/{pid}")
def delete_position(pid: int):
    if not positions.delete(pid):
        raise HTTPException(404, "position not found")
    return {"ok": True}


# ---- alerts (Telegram) --------------------------------------------------------------------

@app.get("/api/alerts")
def alerts_status():
    return alerts.status()


@app.post("/api/alerts/test")
def alerts_test():
    return alerts.send("✅ Option Dashboard is connected to this chat.", "test")


@app.post("/api/alerts/summary")
def alerts_summary():
    return alerts.send_summary("Summary (manual)")


@app.post("/api/alerts/check-stops")
def alerts_check_stops():
    return {"sent": alerts.check_stops()}


class NoteIn(BaseModel):
    text: str
    note_date: str | None = None


@app.get("/api/notes/{symbol}")
def list_notes(symbol: str):
    return service.notes(symbol.upper())


@app.post("/api/notes/{symbol}")
def add_note(symbol: str, note: NoteIn):
    if not note.text.strip():
        raise HTTPException(400, "empty note")
    return {"id": service.add_note(symbol.upper(), note.text.strip(), note.note_date)}


@app.put("/api/notes/id/{note_id}")
def edit_note(note_id: int, note: NoteIn):
    if not service.update_note(note_id, note.text.strip(), note.note_date):
        raise HTTPException(404, "note not found")
    return {"ok": True}


@app.delete("/api/notes/id/{note_id}")
def delete_note(note_id: int):
    if not service.delete_note(note_id):
        raise HTTPException(404, "note not found")
    return {"ok": True}


@app.get("/api/candles/{symbol}")
def candles(symbol: str, tf: str = "D"):
    rule = {"D": None, "W": "W-FRI", "M": "MS"}.get(tf.upper(), "")
    if rule == "":
        raise HTTPException(400, "tf must be D, W or M")
    df = db.load_candles(symbol.upper())
    if df.empty:
        raise HTTPException(404, f"no candles for {symbol}")
    if rule:
        df = resample(df, rule)
    period = int(config.settings().get("signals", {}).get("rsi_period", 14))
    df = df.assign(rsi=rsi(df.close, period).round(2))
    df.index = df.index.strftime("%Y-%m-%d")
    df = df.reset_index(names="date").astype(object)
    df = df.where(df.notna(), None)          # NaN (RSI warm-up) -> null
    return {"symbol": symbol.upper(), "tf": tf.upper(), "candles": df.to_dict(orient="records")}


# ---- frontend (built React app) ---------------------------------------------------

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = DIST / path
        return FileResponse(file if path and file.is_file() else DIST / "index.html")
