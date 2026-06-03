'''Implement a rate limiter that allows at most N events
per T seconds using a sliding window.
Given a list of (timestamp, event_id), return
which events are allowed and which are throttled.'''


from collections import deque

def rate_limiter(events,N,T):
    window = deque()
    allowed= []
    throttled=[]

    for timestamp,event_id in events:

        while window and timestamp - window[0] > T:
            print("Hi")
            window.popleft()
            print(window)

    print(window)


events = [
    (1, "A"),
    (2, "B"),
    (3, "C"),
    (5, "D"),
    (12, "E"),
    (13, "F")
]

rate_limiter(events, N=3, T=10)