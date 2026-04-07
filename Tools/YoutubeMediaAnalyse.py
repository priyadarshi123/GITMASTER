import os
import requests
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from dotenv import load_dotenv

# ========================
# CONFIG
# ========================
load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("Missing YOUTUBE_API_KEY")

CHANNEL_IDS = {
    "CNBC": "UCvJJ_dzjViJCoLf5uKUTwoA"
}

KEYWORDS = ['recession', 'unemployment', 'crash', 'stimulus', 'crisis', 'inflation']

START_DATE = "2026-04-01T00:00:00Z"
END_DATE = "2026-04-05T23:59:59Z"

MAX_VIDEOS = 20
MAX_WORKERS = 5


# ========================
# FETCH VIDEOS
# ========================
def get_videos(channel_id):
    url = "https://www.googleapis.com/youtube/v3/search"

    params = {
        "key": API_KEY,
        "channelId": channel_id,
        "part": "snippet",
        "publishedAfter": START_DATE,
        "publishedBefore": END_DATE,
        "maxResults": MAX_VIDEOS,
        "type": "video"
    }

    res = requests.get(url, params=params).json()

    if "error" in res:
        print("API Error:", res["error"])
        return []

    return [item["id"]["videoId"] for item in res.get("items", [])]


# ========================
# FETCH COMMENTS
# ========================
def get_comments(video_id):
    url = "https://www.googleapis.com/youtube/v3/commentThreads"

    params = {
        "key": API_KEY,
        "videoId": video_id,
        "part": "snippet",
        "maxResults": 100
    }

    comments = []

    while True:
        res = requests.get(url, params=params).json()

        # Handle disabled comments or errors
        if "error" in res:
            return []

        comments.extend(res.get("items", []))

        if "nextPageToken" not in res:
            break

        params["pageToken"] = res["nextPageToken"]

    return comments


# ========================
# PARALLEL FETCH
# ========================
def fetch_all_comments(video_ids):
    all_comments = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(get_comments, vid): vid for vid in video_ids}

        for future in as_completed(futures):
            try:
                all_comments.extend(future.result())
            except Exception as e:
                print(f"Error fetching comments: {e}")

    return all_comments


# ========================
# KEYWORD COUNT
# ========================
def count_keywords(comments):
    keyword_counts = defaultdict(int)

    for c in comments:
        try:
            snippet = c['snippet']['topLevelComment']['snippet']
            date = snippet['publishedAt'][:10]
            text = snippet['textDisplay'].lower()

            if any(k in text for k in KEYWORDS):
                keyword_counts[date] += 1

        except KeyError:
            continue

    return keyword_counts


# ========================
# PIPELINE
# ========================
all_results = {}

for name, channel_id in CHANNEL_IDS.items():
    print(f"\nProcessing {name}...")

    video_ids = get_videos(channel_id)
    print(f"Fetched {len(video_ids)} videos")

    comments = fetch_all_comments(video_ids)
    print(f"Fetched {len(comments)} comments")

    counts = count_keywords(comments)
    all_results[name] = counts


# ========================
# DATAFRAME
# ========================
df = pd.DataFrame()

for channel, counts in all_results.items():
    temp = pd.Series(counts, name=channel)
    df = pd.concat([df, temp], axis=1)

df.fillna(0, inplace=True)
df.index = pd.to_datetime(df.index)
df.sort_index(inplace=True)

# Signal (rolling avg)
signal = df.sum(axis=1).rolling(3).mean()


# ========================
# MARKET DATA
# ========================
data = yf.download("^GSPC", start="2026-04-01", end="2026-04-05")

if data.empty:
    raise ValueError("No SPX data fetched")

if "Adj Close" in data.columns:
    spx = data["Adj Close"]
elif "Close" in data.columns:
    spx = data["Close"]
elif isinstance(data.columns, pd.MultiIndex):
    spx = data["Close"]["^GSPC"]
else:
    raise ValueError("Unexpected yfinance format")


# ========================
# PLOT
# ========================
fig, ax1 = plt.subplots(figsize=(14, 6))

ax1.bar(signal.index, signal.values, alpha=0.6, label="Sentiment Signal")
ax1.set_ylabel("Keyword Count")

ax2 = ax1.twinx()
ax2.plot(spx, linestyle="--", label="S&P 500")
ax2.set_ylabel("SPX")

ax1.legend(loc="upper left")
ax2.legend(loc="upper right")

plt.title("YouTube Sentiment vs Market")
plt.show()