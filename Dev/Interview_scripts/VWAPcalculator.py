'''Given a list of trades: [(price, volume), ...]
Calculate the Volume Weighted Average Price (VWAP):
VWAP = sum(price * volume) / sum(volume)

Extension: Calculate rolling VWAP over last N trades.'''


from collections import deque


def VWAP(trades):
    sum_price_volume = 0
    sum_volume = 0
    for price, volume in trades:
        sum_price_volume += price*volume
        sum_volume += volume
        vwap = sum_price_volume / sum_volume
    return vwap

trades=[(100,5),(200,6),(102,3) ,(103,1)]
print(VWAP(trades))


def rolling_VWAP(trades,N):
    window=deque(maxlen=N)

    rolling_vwaps=[]

    for price, volume in trades:
        window.append((price,volume))

        sum_price_volume = 0
        sum_volume = 0

        for p,v in window:
            sum_price_volume += p * v
            sum_volume += v


        vwap = sum_price_volume/sum_volume

        rolling_vwaps.append(vwap)

    return rolling_vwaps

trades=[(100,5),(200,6),(102,3) ,(103,1)]
print(rolling_VWAP(trades,3))