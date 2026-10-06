"""Angel One SmartAPI provider (REST, no SDK dependency).

Login uses client code + MPIN + TOTP generated from the secret in .env, so it can
run unattended every morning. The session token is valid for the trading day.

Docs: https://smartapi.angelbroking.com/docs
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import struct
import threading
import time
from datetime import date, timedelta

import pandas as pd
import requests

from ..config import DATA_DIR, AngelCreds, Instrument
from .base import Quote

log = logging.getLogger(__name__)

BASE = "https://apiconnect.angelone.in"
SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
SCRIP_MASTER_FILE = DATA_DIR / "angel_scripmaster.json"

CANDLE_MAX_DAYS = 2000        # API limit per request for ONE_DAY
CANDLE_MIN_GAP = 0.35         # seconds between candle calls (limit ~3/s)
QUOTE_BATCH = 50              # tokens per quote call


def totp(secret: str, interval: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret.replace(" ", "").upper() + "=" * (-len(secret) % 8))
    counter = struct.pack(">Q", int(time.time()) // interval)
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10 ** digits
    return str(code).zfill(digits)


class AngelError(RuntimeError):
    pass


class AngelProvider:
    name = "angel"
    live = True

    def __init__(self, creds: AngelCreds):
        self.creds = creds
        self._jwt: str | None = None
        self._login_day: date | None = None
        self._lock = threading.Lock()
        self._last_candle_call = 0.0
        self._tokens: dict[str, str] | None = None

    # ---- session ------------------------------------------------------------

    def _headers(self, auth: bool = True) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.creds.api_key,
        }
        if auth:
            h["Authorization"] = f"Bearer {self.login()}"
        return h

    def login(self, force: bool = False) -> str:
        with self._lock:
            if self._jwt and self._login_day == date.today() and not force:
                return self._jwt
            body = {
                "clientcode": self.creds.client_code,
                "password": self.creds.mpin,
                "totp": totp(self.creds.totp_secret),
            }
            r = requests.post(f"{BASE}/rest/auth/angelbroking/user/v1/loginByPassword",
                              headers=self._headers(auth=False), json=body, timeout=20)
            data = r.json() if r.content else {}
            if not data.get("status"):
                raise AngelError(f"login failed: {data.get('message') or r.status_code} "
                                 f"({data.get('errorcode', '')})")
            self._jwt = data["data"]["jwtToken"]
            self._login_day = date.today()
            log.info("angel: logged in as %s", self.creds.client_code)
            return self._jwt

    def _post(self, path: str, body: dict) -> dict:
        for attempt in range(2):
            r = requests.post(f"{BASE}{path}", headers=self._headers(), json=body, timeout=30)
            data = r.json() if r.content else {}
            if data.get("status"):
                return data
            if data.get("errorcode") in ("AG8001", "AG8002", "AG8003") and attempt == 0:
                self.login(force=True)   # token invalid / expired
                continue
            raise AngelError(f"{path}: {data.get('message') or r.status_code} ({data.get('errorcode', '')})")
        raise AngelError(f"{path}: failed")

    # ---- instrument master ------------------------------------------------------

    def scrip_master(self) -> list[dict]:
        """Angel's full instrument list (~40 MB), cached once per day."""
        fresh = (SCRIP_MASTER_FILE.exists()
                 and date.fromtimestamp(SCRIP_MASTER_FILE.stat().st_mtime) == date.today())
        if not fresh:
            log.info("angel: downloading instrument master")
            r = requests.get(SCRIP_MASTER_URL, timeout=120)
            r.raise_for_status()
            SCRIP_MASTER_FILE.write_bytes(r.content)
            self._tokens = None
        with open(SCRIP_MASTER_FILE, encoding="utf-8") as f:
            return json.load(f)

    def token_for(self, inst: Instrument) -> str | None:
        if inst.angel_token:
            return inst.angel_token
        if self._tokens is None:
            self._tokens = {
                row["symbol"][:-3]: row["token"]
                for row in self.scrip_master()
                if row.get("exch_seg") == "NSE" and str(row.get("symbol", "")).endswith("-EQ")
            }
        return self._tokens.get(inst.symbol)

    # ---- market data --------------------------------------------------------------

    def _candles(self, token: str, start: date, end: date) -> list[list]:
        rows: list[list] = []
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(chunk_start + timedelta(days=CANDLE_MAX_DAYS - 1), end)
            wait = CANDLE_MIN_GAP - (time.monotonic() - self._last_candle_call)
            if wait > 0:
                time.sleep(wait)
            self._last_candle_call = time.monotonic()
            data = self._post("/rest/secure/angelbroking/historical/v1/getCandleData", {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "ONE_DAY",
                "fromdate": f"{chunk_start:%Y-%m-%d} 09:15",
                "todate": f"{chunk_end:%Y-%m-%d} 15:30",
            })
            rows.extend(data.get("data") or [])
            chunk_start = chunk_end + timedelta(days=1)
        return rows

    def daily_candles(self, instruments: list[Instrument], start: date) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for inst in instruments:
            token = self.token_for(inst)
            if not token:
                log.warning("angel: no token for %s", inst.symbol)
                continue
            try:
                rows = self._candles(token, start, date.today())
            except AngelError as e:
                log.warning("angel: candles %s: %s", inst.symbol, e)
                continue
            if not rows:
                continue
            df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
            df.index = pd.to_datetime(df.pop("ts").str[:10])
            out[inst.symbol] = df
        return out

    def quotes(self, instruments: list[Instrument]) -> dict[str, Quote]:
        by_token = {}
        for inst in instruments:
            token = self.token_for(inst)
            if token:
                by_token[token] = inst.symbol
        tokens = list(by_token)
        out: dict[str, Quote] = {}
        for i in range(0, len(tokens), QUOTE_BATCH):
            data = self._post("/rest/secure/angelbroking/market/v1/quote/", {
                "mode": "OHLC",
                "exchangeTokens": {"NSE": tokens[i:i + QUOTE_BATCH]},
            })
            for q in (data.get("data") or {}).get("fetched") or []:
                symbol = by_token.get(str(q.get("symbolToken")))
                if symbol and q.get("ltp") is not None:
                    out[symbol] = Quote(ltp=float(q["ltp"]), prev_close=float(q.get("close") or 0))
        return out
