import feedparser
import time
FEED_URL = "https://trumpstruth.org/feed"

import feedparser
import time
from plyer import notification
from datetime import datetime
import os
import requests
from dotenv import load_dotenv
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("TOKEN or CHAT_ID is missing. Check your .env file.")

# URL of a Trump Truth Social RSS mirror
FEED_URL = "https://trumpstruth.org/feed"

def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()  # raises error if HTTP fails
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        return None



def monitor_truths():
    print("Monitoring Donald Trump's Truth Social posts...")
    # Get the ID of the most recent post to avoid alerting for old ones
    feed = feedparser.parse(FEED_URL)
    last_id = feed.entries[0].id if feed.entries else None

    while True:
        try:
            feed = feedparser.parse(FEED_URL)
            if feed.entries:
                latest_post = feed.entries[0]

                if latest_post.id != last_id:
                    print(f"\n🚨 NEW POST ALERT!")
                    print(f"Time: {latest_post.published}")
                    print(f"Content: {latest_post.summary}")
                    print(f"Link: {latest_post.link}")
                    print(datetime.now())

                    notification.notify(
                    title='Python Alert Test',
                    message='Trump posted a tweet. Check it out..!',
                    app_icon=None,  # You can add a path to an .ico file here later
                    timeout=20,  # The alert stays visible for 10 seconds
                    )

                    send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, f"{latest_post.published}:  {latest_post.summary} - {latest_post.link} 🚀")
                    last_id = latest_post.id

            # Check every 60 seconds
            time.sleep(60)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    monitor_truths()