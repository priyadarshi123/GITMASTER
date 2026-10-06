"""Corporate events from NSE (board meetings + corporate actions) and expiry dates.

NSE's site blocks most datacenter IPs, so this works from a home connection but
may fail on a VPS; failures are logged and the dashboard simply shows no badges.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta

import requests

from . import db

log = logging.getLogger(__name__)

NSE = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept": "application/json,text/html",
    "Accept-Language": "en-US,en;q=0.9",
}


def monthly_expiry(year: int, month: int) -> date:
    """Last Tuesday of the month (NSE monthly F&O expiry since Sep 2025).
    Holiday shifts are not applied here; Angel's instrument master has exact
    expiries and replaces this once the option chain is wired up."""
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - calendar.TUESDAY) % 7)


def next_monthly_expiry(today: date | None = None) -> date:
    today = today or date.today()
    exp = monthly_expiry(today.year, today.month)
    if today > exp:
        y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        exp = monthly_expiry(y, m)
    return exp


def _kinds(text: str) -> set[str]:
    t = text.lower()
    kinds = set()
    if "result" in t:
        kinds.add("R")
    if "agm" in t or "egm" in t or "general meeting" in t:
        kinds.add("A")
    if "dividend" in t:
        kinds.add("D")
    if "bonus" in t or "split" in t or "sub-division" in t or "sub division" in t:
        kinds.add("B")
    return kinds


def _parse(d: str) -> date | None:
    try:
        return datetime.strptime(d, "%d-%b-%Y").date()
    except (TypeError, ValueError):
        return None


def refresh(symbols: set[str], horizon_days: int = 60) -> int:
    """Pull upcoming events for `symbols` and replace the future rows in the DB."""
    today = date.today()
    to = today + timedelta(days=horizon_days)
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(NSE, timeout=15)   # sets the cookies the API requires

    found: list[tuple[str, str, str, str]] = []

    r = s.get(f"{NSE}/api/event-calendar", timeout=20)
    r.raise_for_status()
    for row in r.json():
        d = _parse(row.get("date"))
        if row.get("symbol") in symbols and d and today <= d <= to:
            for k in _kinds(row.get("purpose", "") + " " + row.get("bm_desc", "")):
                found.append((row["symbol"], d.isoformat(), k, row.get("purpose", "")))

    r = s.get(f"{NSE}/api/corporates-corporateActions", timeout=20, params={
        "index": "equities", "from_date": f"{today:%d-%m-%Y}", "to_date": f"{to:%d-%m-%Y}"})
    r.raise_for_status()
    for row in r.json():
        d = _parse(row.get("exDate"))
        if row.get("symbol") in symbols and d:
            for k in _kinds(row.get("subject", "")):
                found.append((row["symbol"], d.isoformat(), k, row.get("subject", "")))

    with db.connect() as con:
        con.execute("DELETE FROM events WHERE event_date >= ?", (today.isoformat(),))
        con.executemany(
            "INSERT OR REPLACE INTO events(symbol, event_date, kind, purpose) VALUES (?, ?, ?, ?)", found)
    log.info("events: %d upcoming events stored", len(found))
    return len(found)


def upcoming(until: date) -> dict[str, list[dict]]:
    """symbol -> events between today and `until` (inclusive)."""
    with db.connect() as con:
        rows = con.execute(
            "SELECT symbol, event_date, kind, purpose FROM events "
            "WHERE event_date BETWEEN ? AND ? ORDER BY event_date",
            (date.today().isoformat(), until.isoformat())).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["symbol"], []).append(
            {"kind": r["kind"], "date": r["event_date"], "purpose": r["purpose"]})
    return out
