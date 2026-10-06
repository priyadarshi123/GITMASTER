"""NSE website data (free, no account): option chains, lot sizes, index quotes and
index history (sector indices, FINNIFTY, MIDCPNIFTY).

These are the JSON endpoints behind nseindia.com pages. They need the cookies the
site sets on a normal page visit, are updated every ~1-3 min, and are usually
blocked from cloud/datacenter IPs — fine from a home PC, test before relying on a VPS.
"""
from __future__ import annotations

import io
import logging
import threading
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

log = logging.getLogger(__name__)

NSE = "https://www.nseindia.com"
LOTS_URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{NSE}/option-chain",
}
MIN_GAP = 0.35            # seconds between requests
COOKIE_TTL = 240          # re-visit the home page this often
HISTORY_CHUNK_DAYS = 90   # the history API returns at most ~70 rows per call

INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}


class NSEError(RuntimeError):
    pass


class NSEClient:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self._cookies_at = 0.0
        self._last = 0.0
        self._lock = threading.Lock()

    def _warm(self, force: bool = False) -> None:
        if force or time.monotonic() - self._cookies_at > COOKIE_TTL:
            self.s.get(f"{NSE}/option-chain", timeout=15)
            self._cookies_at = time.monotonic()

    def get(self, url: str, params: dict | None = None, as_json: bool = True):
        with self._lock:
            for attempt in range(3):
                self._warm(force=attempt > 0)
                wait = MIN_GAP - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.monotonic()
                try:
                    r = self.s.get(url, params=params, timeout=25)
                    if r.status_code == 200 and r.content:
                        return r.json() if as_json else r.text
                    log.debug("nse %s -> %s", url, r.status_code)
                except (requests.RequestException, ValueError) as e:
                    log.debug("nse %s failed: %s", url, e)
                time.sleep(1 + attempt)
        raise NSEError(f"NSE request failed: {url}")


_client: NSEClient | None = None


def client() -> NSEClient:
    global _client
    if _client is None:
        _client = NSEClient()
    return _client


# ---- option chain -----------------------------------------------------------------

def expiries(symbol: str) -> list[date]:
    data = client().get(f"{NSE}/api/option-chain-contract-info", {"symbol": symbol})
    return sorted(datetime.strptime(d, "%d-%b-%Y").date() for d in data.get("expiryDates", []))


def option_chain(symbol: str, expiry: date) -> dict:
    """Normalised chain: {underlying, timestamp, expiry, rows: [{strike, ce:{...}, pe:{...}}]}."""
    kind = "Indices" if symbol in INDEX_SYMBOLS else "Equity"
    data = client().get(f"{NSE}/api/option-chain-v3",
                        {"type": kind, "symbol": symbol, "expiry": f"{expiry:%d-%b-%Y}"})
    rec = data.get("records") or {}

    def leg(d: dict | None) -> dict | None:
        if not d:
            return None
        return {
            "ltp": d.get("lastPrice"),
            "change": d.get("change"),
            "bid": d.get("buyPrice1"),
            "ask": d.get("sellPrice1"),
            "iv": d.get("impliedVolatility") or None,
            "oi": d.get("openInterest"),
            "oi_change": d.get("changeinOpenInterest"),
            "volume": d.get("totalTradedVolume"),
        }

    rows = [{"strike": float(r["strikePrice"]), "ce": leg(r.get("CE")), "pe": leg(r.get("PE"))}
            for r in rec.get("data") or []]
    return {
        "symbol": symbol,
        "expiry": expiry.isoformat(),
        "underlying": rec.get("underlyingValue"),
        "timestamp": rec.get("timestamp"),
        "rows": sorted(rows, key=lambda r: r["strike"]),
    }


def lot_sizes() -> dict[str, dict[str, int]]:
    """symbol -> {"OCT-26": 500, ...} from NSE's F&O market lots file."""
    text = client().get(LOTS_URL, as_json=False)
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip() for c in df.columns]
    out: dict[str, dict[str, int]] = {}
    for _, r in df.iterrows():
        sym = str(r["SYMBOL"]).strip()
        if not sym or sym == "Symbol":
            continue
        out[sym] = {c: int(str(r[c]).strip()) for c in df.columns[2:]
                    if str(r[c]).strip().isdigit()}
    return out


# ---- indices ------------------------------------------------------------------------

def index_quotes() -> dict[str, dict]:
    """NSE index name -> today's {open, high, low, last, prev_close} for every NSE index."""
    data = client().get(f"{NSE}/api/allIndices")
    return {d["index"]: {"open": d.get("open"), "high": d.get("high"), "low": d.get("low"),
                         "last": d.get("last"), "prev_close": d.get("previousClose")}
            for d in data.get("data", [])}


def index_history(name: str, start: date, end: date | None = None) -> pd.DataFrame:
    """Daily OHLC for an NSE index name as listed by allIndices (e.g. 'NIFTY OIL & GAS')."""
    end = end or date.today()
    frames = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=HISTORY_CHUNK_DAYS - 1), end)
        data = client().get(f"{NSE}/api/historicalOR/indicesHistory", {
            "indexType": name, "from": f"{chunk_start:%d-%m-%Y}", "to": f"{chunk_end:%d-%m-%Y}"})
        rows = data.get("data") or []
        if rows:
            frames.append(pd.DataFrame({
                "date": pd.to_datetime([r["EOD_TIMESTAMP"] for r in rows], format="%d-%b-%Y"),
                "open": [r["EOD_OPEN_INDEX_VAL"] for r in rows],
                "high": [r["EOD_HIGH_INDEX_VAL"] for r in rows],
                "low": [r["EOD_LOW_INDEX_VAL"] for r in rows],
                "close": [r["EOD_CLOSE_INDEX_VAL"] for r in rows],
                "volume": [r.get("HIT_TRADED_QTY") or 0 for r in rows],
            }))
        chunk_start = chunk_end + timedelta(days=1)
    if not frames:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.concat(frames).drop_duplicates("date").set_index("date").sort_index()
    df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["close"])
    # some older index rows carry only a close ("-" for open/high/low)
    for col in ("open", "high", "low"):
        df[col] = df[col].fillna(df.close)
    return df.fillna(0.0)
