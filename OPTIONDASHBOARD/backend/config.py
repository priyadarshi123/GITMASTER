"""Loads settings.yaml, watchlist.yaml and .env.

Config files are re-read on every call to `settings()` / `watchlist()` (they are
tiny), so edits take effect on the next refresh without restarting the app.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "optiondash.db"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    sector: str
    kind: str                 # "index" | "stock"
    rank: int
    expiries: int = 1
    yahoo: str = ""
    nse_index: str | None = None
    angel_token: str | None = None


@dataclass
class AngelCreds:
    api_key: str = ""
    client_code: str = ""
    mpin: str = ""
    totp_secret: str = ""

    @property
    def complete(self) -> bool:
        return all([self.api_key, self.client_code, self.mpin, self.totp_secret])


def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def settings() -> dict:
    return _load_yaml("settings.yaml")


def watchlist() -> list[Instrument]:
    """Enabled instruments in display order (indices first)."""
    raw = _load_yaml("watchlist.yaml")
    out: list[Instrument] = []
    rank = 0
    for kind, key in (("index", "indices"), ("stock", "stocks")):
        for row in raw.get(key) or []:
            if not row.get("enabled", True):
                continue
            rank += 1
            sym = str(row["symbol"]).upper()
            out.append(Instrument(
                symbol=sym,
                name=row.get("name", sym),
                sector=row.get("sector", "Index" if kind == "index" else "Other"),
                kind=kind,
                rank=rank,
                expiries=int(row.get("expiries", 1)),
                yahoo=row.get("yahoo") or f"{sym}.NS",
                nse_index=row.get("nse_index"),
                angel_token=str(row["angel_token"]) if row.get("angel_token") else None,
            ))
    return out


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def angel_creds() -> AngelCreds:
    _load_dotenv()
    return AngelCreds(
        api_key=os.environ.get("ANGEL_API_KEY", ""),
        client_code=os.environ.get("ANGEL_CLIENT_CODE", ""),
        mpin=os.environ.get("ANGEL_MPIN", ""),
        totp_secret=os.environ.get("ANGEL_TOTP_SECRET", ""),
    )
