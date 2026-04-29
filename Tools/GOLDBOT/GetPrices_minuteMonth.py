from ib_insync import *
import pandas as pd
import time
from datetime import datetime, timedelta

# -----------------------------
# CONFIG
# -----------------------------
HOST = '127.0.0.1'
PORT =  4002   #7497 for production
CLIENT_ID = 5

SYMBOL = 'GC'  # Gold futures
EXCHANGE = 'COMEX'
CURRENCY = 'USD'
EXPIRY = '202606'  # June 2026

BAR_SIZE = '1 min'
CHUNK_DURATION = '6 D'
TOTAL_DAYS = 30

RETRIES = 3
SLEEP_BETWEEN_CALLS = 2


# -----------------------------
# CONNECT
# -----------------------------
ib = IB()
ib.connect(HOST, PORT, clientId=CLIENT_ID)


# -----------------------------
# CONTRACT
# -----------------------------
contract = Future(
    symbol=SYMBOL,
    lastTradeDateOrContractMonth=EXPIRY,
    exchange=EXCHANGE,
    currency=CURRENCY
)

ib.qualifyContracts(contract)


# -----------------------------
# FETCH FUNCTION (with retry)
# -----------------------------
def fetch_chunk(end_datetime):
    for attempt in range(RETRIES):
        try:
            bars = ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr=CHUNK_DURATION,
                barSizeSetting=BAR_SIZE,
                whatToShow='TRADES',
                useRTH=False,
                formatDate=1
            )
            return bars

        except Exception as e:
            print(f"⚠️ Error: {e}, retry {attempt+1}/{RETRIES}")
            time.sleep(2)

    return []


# -----------------------------
# MAIN PAGINATION LOOP
# -----------------------------
end_time = datetime.now()
all_dfs = []

days_fetched = 0

while days_fetched < TOTAL_DAYS:
    print(f"📥 Fetching chunk ending at {end_time}")

    bars = fetch_chunk(end_time)

    if not bars:
        print("❌ No data returned, stopping...")
        break

    df = util.df(bars)

    if df.empty:
        print("❌ Empty dataframe, stopping...")
        break

    all_dfs.append(df)

    # Move backward
    earliest_time = df['date'].min()
    end_time = earliest_time - timedelta(seconds=1)

    days_fetched += 7

    time.sleep(SLEEP_BETWEEN_CALLS)


# -----------------------------
# MERGE + CLEAN
# -----------------------------
full_df = pd.concat(all_dfs)

# Clean
full_df = full_df.drop_duplicates(subset='date')
full_df = full_df.sort_values('date').reset_index(drop=True)

# Rename (optional, consistent with your earlier code)
full_df.rename(columns={'date': 'timestamp'}, inplace=True)

print("✅ Data fetch complete")
print(full_df.tail())


# -----------------------------
# SAVE
# -----------------------------
file_name = f"GC_{EXPIRY}_1min_last{TOTAL_DAYS}d.csv"
full_df.to_csv(file_name, index=False)

print(f"💾 Saved to {file_name}")


# -----------------------------
# DISCONNECT
# -----------------------------
ib.disconnect()