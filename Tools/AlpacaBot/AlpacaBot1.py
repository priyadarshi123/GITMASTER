import requests

BASE_URL = "https://paper-api.alpaca.markets/v2"
API_KEY = "PKXVZ4IZPHHEWNLSXIXK7ENLYN"
API_SECRET = "CfpX4rBE5CW7YW7F26ufng2nQcJ4CLV9jMZtTHxS9pQW"

headers = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
    "Content-Type": "application/json"
}

order = {
    "symbol": "AAPL",
    "qty": 1,
    "side": "buy",
    "type": "market",
    "time_in_force": "day"
}

response = requests.post(f"{BASE_URL}/orders", json=order, headers=headers)
print(response.status_code)
print(response.json())