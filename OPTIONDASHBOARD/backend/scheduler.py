"""Background auto-refresh: every `auto_interval_min` during market hours, plus one
run after the close so the day's final candles are stored. Also drives Telegram alerts."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, time

from . import alerts, config, service

log = logging.getLogger(__name__)
TICK_SEC = 30


def _due(now: datetime) -> bool:
    cfg = config.settings().get("refresh", {})
    last = service.last_refresh()
    if last is None:
        return True
    interval = int(cfg.get("auto_interval_min", 15))
    if interval > 0 and service.market_open_now(cfg):
        return (now - last).total_seconds() >= interval * 60
    close = datetime.combine(now.date(), time.fromisoformat(cfg.get("market_close", "15:30")))
    return (cfg.get("post_close_refresh", True) and now.weekday() < 5
            and now > close and last < close)


def _loop(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            if _due(datetime.now()):
                log.info("scheduler: auto refresh")
                service.refresh(force=True)
        except Exception:
            log.exception("scheduler tick failed")
        try:
            alerts.tick(datetime.now())
        except Exception:
            log.exception("alerts tick failed")
        stop.wait(TICK_SEC)


def start() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=_loop, args=(stop,), daemon=True, name="scheduler").start()
    return stop
