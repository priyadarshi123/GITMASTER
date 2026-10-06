"""Option Dashboard entry point.

    python master.py            # start API + scheduler + UI at http://127.0.0.1:8050
    python master.py --refresh  # one refresh from the command line, then exit
"""
import argparse
import logging

import uvicorn

from backend import config, db, service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Option Dashboard")
    parser.add_argument("--refresh", action="store_true", help="refresh data once and exit")
    args = parser.parse_args()

    if args.refresh:
        db.init()
        print(service.refresh(force=True))
        return

    srv = config.settings().get("server", {})
    uvicorn.run("backend.api:app", host=srv.get("host", "127.0.0.1"), port=int(srv.get("port", 8050)))


if __name__ == "__main__":
    main()
