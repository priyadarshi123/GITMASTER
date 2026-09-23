import threading
import time
import random
from queue import Queue
import datetime


market_queue = Queue()

symbols = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'FB', 'TSLA','NVDA']

def get_market_data(symbol):
    while True:
        price = round(random.uniform(100, 200), 2)

        tick = {
            'symbol': symbol,
            'price': price
        }

        market_queue.put(tick)
        print(f"{symbol}:  {price}")
        #time.sleep(random.uniform(0.5, 1.5))
        time.sleep(3)
        print(datetime.datetime.now())

def processor():
    while True:
        tick = market_queue.get()
        print(f"Processing: {tick}")
        market_queue.task_done()


for sym in symbols:
    t = threading.Thread(target=get_market_data,args=(sym,),daemon=True)
    t.start()


processor_thread = threading.Thread(target=processor,daemon=True)
processor_thread.start()

while True:
    time.sleep(5)
    print(
        f"Queue Size: {market_queue.qsize()}"
    )

