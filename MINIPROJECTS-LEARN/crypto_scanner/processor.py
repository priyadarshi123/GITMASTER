from queue import Queue
from collections import deque
price_history = {}
WINDOW = 5

market_queue = Queue()

def process_tick(tick):

    symbol = tick["symbol"]
    price = tick["price"]

    if symbol not in price_history:

        price_history[symbol] = deque(maxlen=WINDOW)

    price_history[symbol].append(price)

    history = price_history[symbol]

    print(f"\n[PROCESSOR] {symbol} -> {price}")

    print(f"History: {list(history)}")

    if len(history) >= WINDOW:

        sma = calculate_sma(history)

        print(f"SMA-{WINDOW}: {sma}")


def calculate_sma(prices):
    return round(sum(prices)/len(prices),2 )