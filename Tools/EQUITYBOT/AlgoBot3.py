from ib_insync import *
import pandas as pd
import numpy as np
import time
import datetime
import os


# -------------------------
# STATE MANAGEMENT
# -------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        df = pd.read_csv(STATE_FILE)
        return df.iloc[0].to_dict()
    return {'position': 0, 'entry_price': None}


def save_state(position, entry_price):
    df = pd.DataFrame([{
        'position': position,
        'entry_price': entry_price
    }])
    df.to_csv(STATE_FILE, index=False)


state = load_state()
position = state['position']
entry_price = state['entry_price']

print("Loaded State:", state)


# -------------------------
# LOGGING
# -------------------------
def log_trade(action, price, qty):
    row = {
        'time': datetime.datetime.now(),
        'action': action,
        'price': price,
        'quantity': qty
    }
    df = pd.DataFrame([row])

    if not os.path.exists(LOG_FILE):
        df.to_csv(LOG_FILE, index=False)
    else:
        df.to_csv(LOG_FILE, mode='a', header=False, index=False)


# -------------------------
# GET POSITION FROM IBKR
# -------------------------
def get_position():
    positions = ib.positions()
    for pos in positions:
        if pos.contract.symbol == SYMBOL:
            return pos.position
    return 0


# -------------------------
# GET DATA
# -------------------------
def get_data():
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr='2 D',
        barSizeSetting='1 min',
        whatToShow='TRADES',
        useRTH=True
    )
    return util.df(bars)


# -------------------------
# GET ACCOUNT CASH
# -------------------------
def get_cash():
    summary = ib.accountSummary()
    for item in summary:
        if item.tag == 'AvailableFunds':
            return float(item.value)
    return CAPITAL



# -------------------------
# CONFIG
# -------------------------
SYMBOL = 'D05'
CAPITAL = 10000
RISK_PER_TRADE = 0.2  # 20%
STATE_FILE = 'state.csv'
LOG_FILE = 'trades.csv'

# -------------------------
# CONNECT
# -------------------------
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)
ib.reqMarketDataType(3)

#contract = Stock(SYMBOL, 'SMART', 'USD')
contract = Stock(SYMBOL, 'SGX', 'SGD')
ib.qualifyContracts(contract)



# -------------------------
# MAIN LOOP
# -------------------------
while True:
    try:
        df = get_data()

        df['MA20'] = df['close'].rolling(20).mean()
        df['MA50'] = df['close'].rolling(50).mean()

        latest = df.iloc[-1]
        price = latest['close']

        # SIGNAL
        signal = 0
        if latest['MA20'] > latest['MA50']:
            signal = 1
        elif latest['MA20'] < latest['MA50']:
            signal = -1

        print(f"{datetime.datetime.now()} | Price: {price} | Signal: {signal} | Position: {position}")

        # -------------------------
        # STOP LOSS
        # -------------------------
        if position > 0 and entry_price is not None:
            if price < entry_price * 0.98:
                order = MarketOrder('SELL', abs(position))
                trade = ib.placeOrder(contract, order)

                while not trade.isDone():
                    ib.sleep(0.5)

                fill_price = trade.fills[-1].execution.price

                log_trade('STOP_LOSS_SELL', fill_price, position)

                position = get_position()
                entry_price = None
                save_state(position, entry_price)
                continue

        # -------------------------
        # ENTRY
        # -------------------------
        if signal == 1 and position <= 0:
            cash = get_cash()
            alloc_cash = cash * RISK_PER_TRADE
            qty = int(alloc_cash // price)

            if qty > 0:
                order = MarketOrder('BUY', qty)
                trade = ib.placeOrder(contract, order)

                while not trade.isDone():
                    ib.sleep(0.5)

                fill_price = trade.fills[-1].execution.price

                log_trade('BUY', fill_price, qty)

                position = get_position()
                entry_price = fill_price
                save_state(position, entry_price)

        # -------------------------
        # EXIT
        # -------------------------
        elif signal == -1 and position > 0:
            order = MarketOrder('SELL', abs(position))
            trade = ib.placeOrder(contract, order)

            while not trade.isDone():
                ib.sleep(0.5)

            fill_price = trade.fills[-1].execution.price

            log_trade('SELL', fill_price, position)

            position = get_position()
            entry_price = None
            save_state(position, entry_price)

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        time.sleep(60)