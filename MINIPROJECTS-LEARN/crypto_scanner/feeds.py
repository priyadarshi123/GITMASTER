import random
import time


def get_market_data(symbol):
    base_price = {
        "BTCUSDT": 60000,
        "ETHUSDT": 3000,
        "SOLUSDT": 150,
        "BNBUSDT": 600
    }

    current_price = base_price[symbol]

    while True:
        movement = random.uniform(-1, 1)

        current_price += movement

        tick = {
            "symbol": symbol,
            "price": round(current_price,2),
            "timestamp": time.time()
        }

        yield tick

        time.sleep(random.uniform(0.5, 1.5))
