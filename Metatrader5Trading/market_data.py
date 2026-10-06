import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5
import matplotlib.pyplot as plt
import pandas as pd

from connection import connect_mt5, disconnect_mt5

SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_H1
MONTHS_BACK = 3
TARGET_TZ = "Asia/Singapore"

# MT5 bar times are the broker's server clock, not UTC. MetaQuotes-Demo runs on
# New York time + 7h (UTC+3 in summer, UTC+2 in winter), so shifting back 7h and
# localizing to New York gives correct UTC instants across DST changes.
SERVER_SHIFT_FROM_NY = pd.Timedelta(hours=7)


def get_history(symbol, timeframe, months_back):
    """Download OHLC bars for the last `months_back` months as a raw DataFrame."""
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Symbol {symbol} not available: {mt5.last_error()}")

    date_to = datetime.now(timezone.utc)
    date_from = date_to - pd.DateOffset(months=months_back)

    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No data returned for {symbol}: {mt5.last_error()}")

    return pd.DataFrame(rates)


def to_sgt_dataframe(df):
    """Convert MT5 server-time epochs to a readable SGT timestamp index."""
    server_time = pd.to_datetime(df["time"], unit="s")
    timestamp = ((server_time - SERVER_SHIFT_FROM_NY)
                 .dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
                 .dt.tz_convert(TARGET_TZ))

    df = df.drop(columns="time")
    df.insert(0, "timestamp", timestamp)
    return df.set_index("timestamp")


def plot_price(df, symbol):
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df.index, df["close"], linewidth=1, color="goldenrod")
    ax.set_title(f"{symbol} - H1 close price (last {MONTHS_BACK} months, SGT)")
    ax.set_xlabel("Time (SGT)")
    ax.set_ylabel("Price (USD)")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    try:
        connect_mt5()
        df = to_sgt_dataframe(get_history(SYMBOL, TIMEFRAME, MONTHS_BACK))
    except (ConnectionError, ValueError, RuntimeError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        disconnect_mt5()

    print(f"{len(df)} bars from {df.index[0]} to {df.index[-1]}")
    print(df.head())
    print(df.tail())

    # plot_price(df, SYMBOL)  # graph disabled - uncomment to show the chart
