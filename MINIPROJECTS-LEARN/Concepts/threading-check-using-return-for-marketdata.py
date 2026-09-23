import threading
from queue import Queue
import random
import time

queue = Queue()

STOCK = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'FB', 'TSLA','NVDA']

message_queue = Queue()

def get_messages(stk):
    num = round(random.uniform(1, 10,),2)
    tick = { "stock": stk , "price" : num, "date": time.time() }
    time.sleep(1)
    return tick



def work_thread(stk):
    while True:
        tick = get_messages(stk)
        print(f"Generated  message: {tick}")
        message_queue.put(tick)

def processor():
    while True:
        received_tick = message_queue.get()
        print(f"Processing message: {received_tick}")
        message_queue.task_done()


for stk in STOCK:
    t = threading.Thread(target=work_thread,args=(stk,),daemon=True)
    t.start()

processor_thread = threading.Thread(target=processor,daemon=True)
processor_thread.start()


while True:
    time.sleep(1)
    print(f"Queue Size: {message_queue.qsize()}")


