import argparse
import sys

import MetaTrader5 as mt5

from connection import connect_mt5, disconnect_mt5
from market_data import get_history, to_sgt_dataframe
from orders import (BUY, SELL, OrderError, get_open_positions, place_market_order,
                    print_order_details)
from strategy import HOLD, SmaCrossStrategy

SYMBOL = "USDJPY"       # default symbol; override with --symbol
TIMEFRAME = mt5.TIMEFRAME_H1
MONTHS_BACK = 1         # history the strategy gets to look at
VOLUME = 0.01           # lots per trade
MAX_POSITIONS = 1       # don't open a new trade while this many bot positions are open
# SL/TP for manual --side orders, as % of entry price so they suit any symbol
# (0.5% / 1.0% = ~0.79 / 1.58 yen on USDJPY, ~$21 / $41 on XAUUSD)
MANUAL_SL_PCT = 0.5
MANUAL_TP_PCT = 1.0


def run_once(symbol, strategy, dry_run=True):
    """Evaluate the strategy on the latest closed bar and place an order if it signals."""
    df = to_sgt_dataframe(get_history(symbol, TIMEFRAME, MONTHS_BACK))
    df = df.iloc[:-1]   # last bar is still forming - decide on closed bars only

    signal = strategy.generate_signal(df)
    print(f"[{strategy.name}] {symbol} last closed bar {df.index[-1]} "
          f"close={df['close'].iloc[-1]} -> {signal.action} ({signal.reason})")
    if signal.action == HOLD:
        return None

    open_positions = get_open_positions(symbol)
    if len(open_positions) >= MAX_POSITIONS:
        print(f"Skipping: {len(open_positions)} bot position(s) already open on {symbol}")
        return None

    return place_market_order(symbol, signal.action, VOLUME, sl=signal.sl, tp=signal.tp,
                              dry_run=dry_run, comment=strategy.name)


def place_manual(symbol, side, dry_run=True):
    """Skip the strategy and place one order at market with % based SL/TP."""
    if not mt5.symbol_select(symbol, True):
        raise OrderError(f"Symbol {symbol} not found on this account - check the spelling "
                         f"(e.g. USDJPY, XAUUSD) or add it in MT5 Market Watch")
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise OrderError(f"No price for {symbol}: {mt5.last_error()}")
    price = tick.ask if side == BUY else tick.bid
    direction = 1 if side == BUY else -1
    return place_market_order(symbol, side, VOLUME,
                              sl=price * (1 - direction * MANUAL_SL_PCT / 100),
                              tp=price * (1 + direction * MANUAL_TP_PCT / 100),
                              dry_run=dry_run, comment="manual")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the strategy (or a manual order) once")
    parser.add_argument("--symbol", default=SYMBOL, help=f"symbol to trade (default {SYMBOL})")
    parser.add_argument("--live", action="store_true",
                        help="actually send the order (default is a dry run via order_check)")
    parser.add_argument("--side", choices=[BUY, SELL],
                        help="skip the strategy and place a manual order on this side")
    args = parser.parse_args()

    exit_code = 0
    try:
        connect_mt5()
        if args.side:
            result = place_manual(args.symbol, args.side, dry_run=not args.live)
        else:
            result = run_once(args.symbol, SmaCrossStrategy(), dry_run=not args.live)
        if result is not None and args.live:
            print_order_details(result)
    # expected failures: bad credentials/connection, rejected orders, invalid SL/TP, no data.
    # Anything else is a bug and still shows a full traceback.
    except (ConnectionError, OrderError, ValueError, RuntimeError) as e:
        print(f"ERROR: {e}")
        exit_code = 1
    finally:
        disconnect_mt5()
    sys.exit(exit_code)
