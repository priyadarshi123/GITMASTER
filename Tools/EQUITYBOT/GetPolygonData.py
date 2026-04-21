import requests
import pandas as pd

API_KEY = "YOUR_API_KEY"


def get_polygon_data(symbol="AAPL", multiplier=1, timespan="minute", limit=5000):
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/2024-01-01/2024-01-10"

    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": limit,
        "apiKey": API_KEY
    }

    response = requests.get(url, params=params)
    data = response.json()

    if "results" not in data:
        print("No data returned:", data)
        return pd.DataFrame()

    df = pd.DataFrame(data["results"])

    # Rename columns to match your IBKR style
    df.rename(columns={
        "t": "date",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume"
    }, inplace=True)

    # Convert timestamp
    df["date"] = pd.to_datetime(df["date"], unit="ms")
    df.set_index("date", inplace=True)

    return df


df = get_polygon_data()
print(df.head())