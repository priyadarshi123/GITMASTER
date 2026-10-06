import os
from pathlib import Path

import MetaTrader5 as mt5
from dotenv import load_dotenv

# Load credentials from the .env file next to this script
load_dotenv(Path(__file__).parent / ".env")


def load_credentials():
    """Read MT5 credentials from environment variables."""
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    path = os.getenv("MT5_PATH") or None

    missing = [name for name, value in
               [("MT5_LOGIN", login), ("MT5_PASSWORD", password), ("MT5_SERVER", server)]
               if not value]
    if missing:
        raise ValueError(f"Missing credentials in .env: {', '.join(missing)}")

    return int(login), password, server, path


def connect_mt5():
    """Initialize the MT5 terminal and log in to the trading account."""
    login, password, server, path = load_credentials()

    # timeout (ms) stops initialize() from hanging silently if the terminal can't log in
    init_kwargs = {"login": login, "password": password, "server": server, "timeout": 30000}
    if path:
        init_kwargs["path"] = path

    print(f"Connecting to account {login} on {server} ...", flush=True)
    if not mt5.initialize(**init_kwargs):
        error = mt5.last_error()
        mt5.shutdown()
        raise ConnectionError(f"MT5 initialize/login failed: {error}")

    account = mt5.account_info()
    if account is None:
        error = mt5.last_error()
        mt5.shutdown()
        raise ConnectionError(f"Connected, but could not read account info: {error}")

    return account


def disconnect_mt5():
    mt5.shutdown()


if __name__ == "__main__":
    try:
        account = connect_mt5()
        terminal = mt5.terminal_info()
        print(f"Connected to MetaTrader 5 (build {mt5.version()[1]})")
        print(f"Terminal : {terminal.name}")
        print(f"Account  : {account.login} ({account.name})")
        print(f"Server   : {account.server}")
        print(f"Balance  : {account.balance:.2f} {account.currency}")
        print(f"Equity   : {account.equity:.2f} {account.currency}")
        print(f"Leverage : 1:{account.leverage}")
    except (ValueError, ConnectionError) as e:
        print(e)
    finally:
        disconnect_mt5()
