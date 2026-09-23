# main.py

import threading
import time

from feeds import get_market_data
from processor import market_queue, process_tick
from config import SYMBOLS


def feed_worker(symbol):

    stream = get_market_data(symbol)

    for tick in stream:

        print(f"[FEED] {tick}")

        market_queue.put(tick)


def processor_worker():

    while True:

        tick = market_queue.get()

        process_tick(tick)

        market_queue.task_done()


# Start feed threads
for sym in SYMBOLS:

    t = threading.Thread(
        target=feed_worker,
        args=(sym,),
        daemon=True
    )

    t.start()


# Start processor thread
processor_thread = threading.Thread(
    target=processor_worker,
    daemon=True
)

processor_thread.start()


# Keep app alive
while True:
    time.sleep(1)