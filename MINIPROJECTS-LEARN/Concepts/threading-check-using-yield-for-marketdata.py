import threading
from queue import Queue
import random
import time

queue = Queue()

STOCK = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'FB', 'TSLA','NVDA']

message_queue = Queue()

def get_messages(stk):
    while True:
        num = round(random.uniform(1, 10,),2)
        tick = { "stock": stk , "price" : num, "date": time.time() }
        yield tick
        time.sleep(random.uniform(0.5, 1.5))


def work_thread(stk):   #To get the stream of messages and put it in the queue
    stream = get_messages(stk)
    for tick in stream:
        print(f"Generated  message: {tick}")
        message_queue.put(tick)

def processor():  #To get the message from the queue and process it
    while True:
        message = message_queue.get()
        print(f"Processing message: {message}")
        message_queue.task_done()


for stk in STOCK:
    t = threading.Thread(target=work_thread,args=(stk,),daemon=True)
    t.start()

processor_thread = threading.Thread(target=processor,daemon=True)
processor_thread.start()


while True:
    time.sleep(1)
    print(f"Queue Size: {message_queue.qsize()}")


