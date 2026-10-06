"""Telegram alerts: 09:20 / 15:35 position summaries and stop alerts at 95% / 100%.

Bot token and chat id live in .env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID); times,
levels and books in settings.yaml `alerts:`. Every message sent (or failed) is kept
in a short log for the Alerts page. Dedup state lives in the `meta` table, so a
restart doesn't resend today's summary or a stop alert already delivered.
"""
from __future__ import annotations

import html
import json
import logging
import os
from datetime import datetime, time, timedelta

import requests

from . import config, db, positions, service

log = logging.getLogger(__name__)

LOG_KEY = "alerts_log"
LOG_KEEP = 50
SUMMARY_WINDOW = timedelta(minutes=30)     # a summary missed by more than this (app was off) is skipped
REARM_GAP = 10                              # stop alert re-arms once usage falls this many points below the level


def _cfg() -> dict:
    return config.settings().get("alerts", {})


def creds() -> tuple[str, str]:
    config._load_dotenv()
    return os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")


def configured() -> bool:
    return all(creds())


# ---- sending -----------------------------------------------------------------------------

def send(text: str, kind: str) -> dict:
    """Send an HTML-formatted message; returns {"ok", "error"} and logs the attempt."""
    token, chat = creds()
    if not (token and chat):
        result = {"ok": False, "error": "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set in .env"}
    else:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=15, json={
                "chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            result = {"ok": bool(body.get("ok")), "error": None if body.get("ok") else body.get("description") or f"HTTP {r.status_code}"}
        except requests.RequestException as e:
            result = {"ok": False, "error": str(e).replace(token, "***")}
    if not result["ok"]:
        log.warning("telegram %s failed: %s", kind, result["error"])
    _append_log({"at": db.now_iso(), "kind": kind, "ok": result["ok"], "error": result["error"], "text": text})
    return result


def _append_log(entry: dict) -> None:
    rows = history()
    rows.insert(0, entry)
    db.set_meta(LOG_KEY, json.dumps(rows[:LOG_KEEP]))


def history() -> list[dict]:
    raw = db.get_meta(LOG_KEY)
    return json.loads(raw) if raw else []


# ---- message builders ------------------------------------------------------------------------

def _inr(v: float | None) -> str:
    if v is None:
        return "—"
    s = f"₹{abs(round(v)):,}"
    return f"−{s}" if v < 0 else f"+{s}" if v > 0 else s


def _books() -> list[str]:
    return [b for b in _cfg().get("books", ["real", "paper"]) if b in ("real", "paper")]


def summary_text(label: str) -> str:
    e = html.escape
    lines = [f"<b>📊 Option Dashboard — {e(label)}</b>", datetime.now().strftime("%a %d %b %Y, %H:%M IST"), ""]
    for b in _books():
        bk = positions.book(b)
        open_ = bk["open"]
        total = sum(p.get("pnl") or 0 for p in open_)
        lines.append(f"<b>{b.upper()}</b> · {len(open_)} open · P&amp;L {_inr(total)}")
        for p in open_:
            legs = " ".join(f"{l['side']}{l['strike']:g}{l['kind']}" for l in p["legs"] if l["exit_price"] is None)
            stop = p.get("stop_used_pct")
            flag = "🔴" if (stop or 0) >= 100 else "🟠" if (stop or 0) >= 80 else "🟢"
            bits = [f"{flag} <b>{e(p['symbol'])}</b> {e(p['strategy'])} ({e(legs)}) exp {p['expiry']}",
                    f"   P&amp;L {_inr(p.get('pnl'))}"
                    + (f" · stop {stop:.0f}%" if stop is not None else "")
                    + (f" · spot {p['spot']:,.1f}" if p.get("spot") else "")
                    + (f" ({p['spot_move_pct']:+.2f}%)" if p.get("spot_move_pct") is not None else "")
                    + (f" · POP {p['pop_now']}%" if p.get("pop_now") is not None else "")]
            if p.get("expired"):
                bits.append("   ⚠ expired — close it")
            if p.get("error"):
                bits.append(f"   ⚠ {e(p['error'])}")
            lines.extend(bits)
        month = next((r for r in bk["roi"]["monthly"] if r["month"] == datetime.now().strftime("%Y-%m")), None)
        if month:
            lines.append(f"   Month: realised {_inr(month['realized'])} · total {_inr(month['total'])}"
                         + (f" · ROI {month['roi_pct']}%" if month["roi_pct"] is not None else ""))
        lines.append("")

    if _cfg().get("include_signals", True):
        try:
            items = service.dashboard()["items"]
            counts: dict[str, list[str]] = {}
            for i in items:
                if i["signal"]:
                    counts.setdefault(i["signal"], []).append(i["symbol"])
            if counts:
                lines.append("<b>Signals</b>")
                for sig in ("Bear Call", "Bull Put", "Iron Condor"):
                    if sig in counts:
                        syms = counts[sig]
                        shown = ", ".join(syms[:8]) + (f" +{len(syms) - 8}" if len(syms) > 8 else "")
                        lines.append(f"{e(sig)} ({len(syms)}): {e(shown)}")
        except Exception as ex:      # signals are a nice-to-have; never block the summary
            log.warning("summary signals: %s", ex)
    return "\n".join(lines).strip()


def stop_text(p: dict, level: int) -> str:
    e = html.escape
    head = "🛑 STOP HIT" if level >= 100 else f"⚠️ {level}% of stop used"
    rule = "strike breach" if p["stop_rule"] == "breach" else f"{p['stop_rule']} credit (₹{abs(round(p['stop_loss'] or 0)):,} loss)"
    legs = " ".join(f"{l['side']}{l['strike']:g}{l['kind']}" for l in p["legs"] if l["exit_price"] is None)
    return "\n".join([
        f"<b>{head} — {e(p['symbol'])} {e(p['strategy'])}</b> [{p['book'].upper()}]",
        f"{e(legs)} · exp {p['expiry']}",
        f"Stop used {p['stop_used_pct']:.0f}% · rule {e(rule)}",
        f"P&amp;L {_inr(p.get('pnl'))}" + (f" · spot {p['spot']:,.1f}" if p.get("spot") else "")
        + (f" · nearest short {p['nearest_short_pct']}% away" if p.get("nearest_short_pct") is not None else ""),
    ])


# ---- scheduled work ----------------------------------------------------------------------------

def send_summary(label: str = "Summary") -> dict:
    return send(summary_text(label), "summary")


def check_stops() -> list[dict]:
    """Alert once per level crossed; re-arm when usage drops REARM_GAP below the level."""
    levels = sorted(int(v) for v in _cfg().get("stop_levels", [95, 100]))
    sent = []
    for b in _books():
        for p in positions.book(b)["open"]:
            used = p.get("stop_used_pct")
            if used is None:
                continue
            for level in levels:
                key = f"alert_stop:{p['id']}:{level}"
                armed = db.get_meta(key) is None
                if used >= level and armed:
                    res = send(stop_text(p, level), "stop")
                    if res["ok"]:
                        db.set_meta(key, db.now_iso())
                    sent.append({"id": p["id"], "level": level, **res})
                elif used < level - REARM_GAP and not armed:
                    with db.connect() as con:
                        con.execute("DELETE FROM meta WHERE key=?", (key,))
    return sent


def tick(now: datetime) -> None:
    """Called by the scheduler every 30 s."""
    cfg = _cfg()
    if not cfg.get("enabled", False) or not configured() or now.weekday() >= 5:
        return
    for hhmm, label in _summary_times(cfg):
        at = datetime.combine(now.date(), time.fromisoformat(hhmm))
        key = f"alert_summary:{now.date().isoformat()}:{hhmm}"
        if at <= now < at + SUMMARY_WINDOW and db.get_meta(key) is None:
            db.set_meta(key, db.now_iso())          # mark first: a slow NSE call must not double-send
            send_summary(label)
    every = int(cfg.get("stop_check_min", 5))
    last = db.get_meta("alert_stop_checked")
    if service.market_open_now() and (last is None or (now - datetime.fromisoformat(last)).total_seconds() >= every * 60):
        db.set_meta("alert_stop_checked", now.isoformat(timespec="seconds"))
        check_stops()


def _summary_times(cfg: dict) -> list[tuple[str, str]]:
    times = cfg.get("summary_times", ["09:20", "15:35"])
    return [(t, "Morning" if t < "12:00" else "Close") for t in times]


def status() -> dict:
    token, chat = creds()
    cfg = _cfg()
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "configured": bool(token and chat),
        "token_set": bool(token),
        "chat_id": chat or None,
        "summary_times": cfg.get("summary_times", ["09:20", "15:35"]),
        "stop_levels": cfg.get("stop_levels", [95, 100]),
        "stop_check_min": int(cfg.get("stop_check_min", 5)),
        "books": _books(),
        "log": history(),
    }
