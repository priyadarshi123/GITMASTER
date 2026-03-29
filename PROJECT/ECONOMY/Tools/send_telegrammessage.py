import requests
import os
from dotenv import load_dotenv
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("TOKEN or CHAT_ID is missing. Check your .env file.")

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

result = send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, "Trade alert triggered 🚀")
print(result)