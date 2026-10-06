from datetime import datetime, timezone

import MetaTrader5 as mt5

BUY = "BUY"
SELL = "SELL"

DEFAULT_DEVIATION = 20      # max slippage allowed, in points
DEFAULT_MAGIC = 50501       # tags orders placed by this bot so we can find them later

# symbol_info().filling_mode bit flags (not exported by the MetaTrader5 package)
SYMBOL_FILLING_FOK = 1
SYMBOL_FILLING_IOC = 2

# Plain-English explanations for the trade server return codes we're most likely to hit
RETCODE_HINTS = {
    10004: "Requote - price moved, try again",
    10006: "Request rejected by the broker",
    10013: "Invalid request",
    10014: "Invalid volume for this symbol",
    10015: "Invalid price",
    10016: "Invalid stop-loss / take-profit levels",
    10018: "Market is closed - wait for the trading session to open",
    10019: "Not enough free margin for this trade",
    10024: "Too many requests - slow down and retry",
    10027: "Algo Trading is switched off in the MT5 terminal - click the 'Algo Trading' "
           "button so it turns green",
    10030: "Filling mode not supported for this symbol",
    10031: "No connection to the trade server",
}


class OrderError(Exception):
    """An order could not be checked or placed. The message is safe to show the user."""


def _rejection_message(prefix, result):
    hint = RETCODE_HINTS.get(result.retcode, result.comment)
    return f"{prefix}: {hint} (retcode {result.retcode}, broker says '{result.comment}')"


def _filling_mode(info):
    """Pick a filling mode the broker supports for this symbol."""
    if info.filling_mode & SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    if info.filling_mode & SYMBOL_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def _normalize_volume(info, volume):
    """Snap volume to the symbol's lot step and clamp it to min/max."""
    step = info.volume_step
    volume = round(round(volume / step) * step, 8)
    return min(max(volume, info.volume_min), info.volume_max)


def _validate_stops(info, side, price, sl, tp):
    """Check SL/TP are on the correct side of price and outside the broker's stop level."""
    min_distance = info.trade_stops_level * info.point
    for name, level in (("SL", sl), ("TP", tp)):
        if level is None:
            continue
        below = (side == BUY) == (name == "SL")     # BUY: SL below, TP above; SELL: reverse
        distance = price - level if below else level - price
        if distance <= 0:
            raise ValueError(f"{name} {level} is on the wrong side of {side} price {price}")
        if distance < min_distance:
            raise ValueError(f"{name} {level} is closer than the broker's stop level "
                             f"({info.trade_stops_level} points) to price {price}")


def build_market_request(symbol, side, volume, sl=None, tp=None,
                         deviation=DEFAULT_DEVIATION, magic=DEFAULT_MAGIC, comment="python-bot"):
    """Build a validated market order request for the current bid/ask."""
    if side not in (BUY, SELL):
        raise ValueError(f"side must be {BUY} or {SELL}, got {side!r}")

    if not mt5.symbol_select(symbol, True):
        raise OrderError(f"Symbol {symbol} not found on this account - check the spelling "
                         f"(e.g. USDJPY, XAUUSD) or add it in MT5 Market Watch")
    info = mt5.symbol_info(symbol)
    if info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
        raise OrderError(f"Trading on {symbol} is restricted (trade_mode={info.trade_mode})")

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise OrderError(f"No price for {symbol}: {mt5.last_error()}")

    price = tick.ask if side == BUY else tick.bid
    sl = round(sl, info.digits) if sl is not None else None
    tp = round(tp, info.digits) if tp is not None else None
    _validate_stops(info, side, price, sl, tp)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": _normalize_volume(info, volume),
        "type": mt5.ORDER_TYPE_BUY if side == BUY else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _filling_mode(info),
    }
    if sl is not None:
        request["sl"] = sl
    if tp is not None:
        request["tp"] = tp
    return request


def place_market_order(symbol, side, volume, sl=None, tp=None, dry_run=True, **kwargs):
    """
    Place a market order. With dry_run=True the request is only checked by the
    broker (order_check) and nothing is executed.
    Returns the MT5 result object; raises OrderError if the order is rejected.
    """
    request = build_market_request(symbol, side, volume, sl, tp, **kwargs)

    if dry_run:
        result = mt5.order_check(request)
        if result is None:
            raise OrderError(f"Order check failed: {mt5.last_error()}")
        # order_check reports success with retcode 0
        if result.retcode != 0:
            raise OrderError(_rejection_message("Order check rejected", result))
        print(f"[DRY RUN] {side} {request['volume']} {symbol} @ {request['price']} "
              f"SL={request.get('sl')} TP={request.get('tp')} - check passed, "
              f"margin required {result.margin:.2f}")
        return result

    if not mt5.terminal_info().trade_allowed:
        raise OrderError(RETCODE_HINTS[10027])

    result = mt5.order_send(request)
    if result is None:
        raise OrderError(f"Order send failed: {mt5.last_error()}")
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise OrderError(_rejection_message("Order rejected", result))
    print(f"[FILLED] {side} {result.volume} {symbol} @ {result.price} "
          f"(order #{result.order}, deal #{result.deal})")
    return result


def print_order_details(result):
    """Print the fill result and the resulting open position for a sent order."""
    print("\n--- Order result ---")
    print(f"Retcode     : {result.retcode} ({result.comment})")
    print(f"Order ticket: {result.order}")
    print(f"Deal ticket : {result.deal}")
    print(f"Volume      : {result.volume}")
    print(f"Fill price  : {result.price}")
    print(f"Bid / Ask   : {result.bid} / {result.ask}")

    positions = mt5.positions_get(ticket=result.order) or ()
    if not positions:
        print("(no open position found for this ticket)")
        return
    p = positions[0]
    print("\n--- Open position ---")
    print(f"Ticket      : {p.ticket}")
    print(f"Symbol      : {p.symbol}")
    print(f"Type        : {'BUY' if p.type == mt5.POSITION_TYPE_BUY else 'SELL'}")
    print(f"Volume      : {p.volume}")
    print(f"Open price  : {p.price_open}")
    print(f"Current     : {p.price_current}")
    print(f"Stop loss   : {p.sl}")
    print(f"Take profit : {p.tp}")
    print(f"Profit      : {p.profit:.2f}")
    opened = datetime.fromtimestamp(p.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Opened at   : {opened} (server time)")
    print(f"Magic       : {p.magic}  Comment: {p.comment}")


def get_open_positions(symbol, magic=DEFAULT_MAGIC):
    """Open positions on `symbol` that were placed by this bot."""
    positions = mt5.positions_get(symbol=symbol) or ()
    return [p for p in positions if p.magic == magic]
