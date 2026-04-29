from ib_insync import *
from newsapi import NewsApiClient
import pandas as pd
import os
from datetime import datetime

class DataHandler:
    def __init__(self, config):
        self.ib = IB()
        self.ib.connect(
            config['broker']['host'],
            config['broker']['port'],
            clientId=config['broker']['client_id']
        )

        self.contract = Future('CL', '202606', 'NYMEX')

        self.news_enabled = config['news']['enabled']
        if self.news_enabled:
            self.newsapi = NewsApiClient(api_key=config['news']['api_key'])

    # Get latest price
    def get_price(self):
        ticker = self.ib.reqMktData(self.contract)
        self.ib.sleep(2)
        return ticker.last

    # Get market depth
    def get_order_book(self):
        depth = self.ib.reqMktDepth(self.contract, numRows=5)
        self.ib.sleep(1)
        return depth

    # Compute imbalance
    def get_imbalance(self, depth):
        bids = [row.size for row in depth.domBids]
        asks = [row.size for row in depth.domAsks]

        bid_vol = sum(bids)
        ask_vol = sum(asks)

        if bid_vol + ask_vol == 0:
            return 0

        return (bid_vol - ask_vol) / (bid_vol + ask_vol)


    # Fetch news sentiment
    def get_news_signal(self):
        if not self.news_enabled:
            return "NEUTRAL"

        articles = self.newsapi.get_everything(
            q='crude oil OR OPEC',
            page_size=3
        )

        score = 0
        for a in articles['articles']:
            text = a['title'].lower()
            if 'cut' in text or 'war' in text:
                score += 1
            if 'increase' in text or 'surplus' in text:
                score -= 1

        if score > 0:
            return "BULLISH"
        elif score < 0:
            return "BEARISH"
        return "NEUTRAL"


class TickRecorder:
    def __init__(self, filename="tick_data.parquet"):
        self.filename = filename
        self.buffer = []

    def record_tick(self, price, volume, imbalance):
        self.buffer.append({
            "time": datetime.utcnow(),
            "price": price,
            "volume": volume,
            "imbalance": imbalance
        })

        # Flush every 100 ticks
        if len(self.buffer) >= 100:
            self.flush()

    def flush(self):
        """Flush buffered ticks to parquet file. Safe to call even if buffer is empty."""
        if not self.buffer:
            print(f"[TickRecorder] Buffer is empty, skipping flush to {self.filename}")
            return
        
        try:
            df = pd.DataFrame(self.buffer)

            if os.path.exists(self.filename):
                old = pd.read_parquet(self.filename)
                df = pd.concat([old, df], ignore_index=True)
                print(f"[TickRecorder] Appending {len(self.buffer)} ticks to existing file")
            else:
                print(f"[TickRecorder] Creating new parquet file: {self.filename}")

            df.to_parquet(self.filename, index=False)
            print(f"[TickRecorder] Successfully wrote {len(df)} total records to {self.filename}")
            self.buffer = []
        except Exception as e:
            print(f"[TickRecorder] ERROR writing to {self.filename}: {e}")
            raise
    
    def close(self):
        """Ensure all buffered data is written before program exit."""
        print(f"[TickRecorder] Closing: flushing {len(self.buffer)} remaining ticks")
        self.flush()

