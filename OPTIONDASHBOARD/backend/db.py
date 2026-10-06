"""SQLite storage. One file: data/optiondash.db (copy it to back up / migrate)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    date   TEXT NOT NULL,            -- YYYY-MM-DD (daily bars)
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS quotes (
    symbol TEXT PRIMARY KEY,
    ltp REAL, prev_close REAL, change_pct REAL,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS signals (
    symbol TEXT PRIMARY KEY,
    rsi_w REAL, rsi_d REAL, signal TEXT,
    computed_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    symbol TEXT NOT NULL,
    event_date TEXT NOT NULL,        -- YYYY-MM-DD
    kind TEXT NOT NULL,              -- R results | A agm/egm | D dividend | B bonus/split
    purpose TEXT,
    PRIMARY KEY (symbol, event_date, kind)
);
CREATE TABLE IF NOT EXISTS bookmarks (
    symbol TEXT PRIMARY KEY,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    note_date TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_notes_symbol ON notes(symbol);
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book TEXT NOT NULL,              -- real | paper
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,          -- Iron Condor | Bull Put | Bear Call | Custom
    expiry TEXT NOT NULL,
    lots INTEGER NOT NULL,
    lot_size INTEGER NOT NULL,
    capital REAL,
    risk_pct REAL,
    stop_rule TEXT NOT NULL,         -- 1x | 2x | 3x | breach
    note TEXT,
    entry_spot REAL,
    entry_pop REAL,
    margin REAL,
    status TEXT NOT NULL DEFAULT 'open',
    opened_at TEXT NOT NULL,         -- YYYY-MM-DD
    closed_at TEXT,
    realized_pnl REAL,
    created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,              -- CE | PE
    side TEXT NOT NULL,              -- S | B
    strike REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,                 -- set when the leg is closed on its own
    closed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_legs_position ON legs(position_id);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init() -> None:
    with connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)


# ---- meta -------------------------------------------------------------------

def get_meta(key: str, default: str | None = None) -> str | None:
    with connect() as con:
        row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))


# ---- candles ----------------------------------------------------------------

def last_candle_date(symbol: str) -> str | None:
    with connect() as con:
        row = con.execute("SELECT MAX(date) d FROM candles WHERE symbol=?", (symbol,)).fetchone()
    return row["d"]


def upsert_candles(symbol: str, df: pd.DataFrame) -> int:
    """df: index = date, columns open/high/low/close/volume."""
    if df is None or df.empty:
        return 0
    rows = [
        (symbol, pd.Timestamp(idx).strftime("%Y-%m-%d"),
         float(r.open), float(r.high), float(r.low), float(r.close),
         float(r.volume) if pd.notna(r.volume) else 0.0)
        for idx, r in df.iterrows()
        if pd.notna(r.close)
    ]
    with connect() as con:
        con.executemany(
            "INSERT OR REPLACE INTO candles(symbol, date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def load_candles(symbol: str) -> pd.DataFrame:
    with connect() as con:
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume FROM candles "
            "WHERE symbol=? ORDER BY date", con, params=(symbol,))
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")
