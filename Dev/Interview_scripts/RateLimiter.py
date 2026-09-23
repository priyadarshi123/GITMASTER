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
        # Remove events outside the time window
        while window and timestamp - window[0] > T:
            print("Hi - removing old event")
            window.popleft()
            print(f"Window after removal: {list(window)}")
        
        # Check if we can allow this event
        print(window)
        if len(window) < N:
            window.append(timestamp)
            allowed.append((timestamp, event_id))
            print(f"ALLOWED: {event_id} at {timestamp}")
        else:
            throttled.append((timestamp, event_id))
            print(f"THROTTLED: {event_id} at {timestamp}")

    print(f"\nFinal window: {list(window)}")
    print(f"Allowed: {allowed}")
    print(f"Throttled: {throttled}")


events = [
    (1, "A"),
    (2, "B"),
    (3, "C"),
    (5, "D"),
    (12, "E"),
    (13, "F")
]

rate_limiter(events, N=3, T=10)