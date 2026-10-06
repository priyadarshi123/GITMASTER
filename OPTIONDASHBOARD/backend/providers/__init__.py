"""Picks the data provider: Angel One when credentials exist and login works,
otherwise Yahoo Finance. `get()` caches the choice; `reset()` re-evaluates it
(e.g. after .env is filled in)."""
from __future__ import annotations

import logging

from .. import config
from .angel import AngelError, AngelProvider
from .base import Provider, Quote
from .yahoo import YahooProvider

log = logging.getLogger(__name__)

_provider: Provider | None = None
_note = ""


def get() -> Provider:
    global _provider, _note
    if _provider is not None:
        return _provider
    choice = config.settings().get("data", {}).get("provider", "auto")
    creds = config.angel_creds()
    if choice in ("auto", "angel") and creds.complete:
        angel = AngelProvider(creds)
        try:
            angel.login()
            _provider, _note = angel, "Angel One SmartAPI · live"
            return _provider
        except (AngelError, OSError, ValueError) as e:
            log.error("angel login failed, falling back to Yahoo: %s", e)
            _note = f"Angel One login failed ({e}) — using free Yahoo + NSE data"
    else:
        _note = "Free data: Yahoo Finance prices (~15 min delay) + NSE option chains and indices"
    _provider = YahooProvider()
    return _provider


def note() -> str:
    return _note


def reset() -> None:
    global _provider
    _provider = None


__all__ = ["get", "note", "reset", "Provider", "Quote"]
