import pandas as pd

df = pd.read_csv("GC_202606_1min_last15d.csv")
df = df[df['volume'] > 0]
# Rename for consistency
df.rename(columns={'date': 'timestamp', 'close': 'price'}, inplace=True)

df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

print(df.tail())


TIMEFRAME_MINUTES = 1  # Configurable timeframe in minutes
shift_period = TIMEFRAME_MINUTES  # Assuming data is in 1-minute intervals

df[f'price_{TIMEFRAME_MINUTES}min_ago'] = df['price'].shift(shift_period)
df[f'return_{TIMEFRAME_MINUTES}min'] = (df['price'] / df[f'price_{TIMEFRAME_MINUTES}min_ago']) - 1
df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('UTC')
df['time_diff'] = df['timestamp'].diff().dt.total_seconds()


ENTRY_THRESHOLD = -0.007   # -0.3%
TAKE_PROFIT = 0.01      # +0.15%
STOP_LOSS = 0.01         # +0.3%
MAX_HOLD = 240             # seconds
COMMISSION = 1.0  # per trade


position = 0
entry_price = 0
entry_time = None
lowest_price = None

trades = []

print(f"Min return {TIMEFRAME_MINUTES}min:", df[f'return_{TIMEFRAME_MINUTES}min'].min())
print(f"Max return {TIMEFRAME_MINUTES}min:", df[f'return_{TIMEFRAME_MINUTES}min'].max())
print(df.index)
for i in range(len(df)):
    row = df.iloc[i]

    # Skip if time difference > 65 seconds (not regular trading hours)
    if not pd.isna(df.loc[i, 'time_diff']) and df.loc[i, 'time_diff'] > 65:
        continue

    price = row['price']
    time = row['timestamp']

    # ENTRY

    if position == 0:
        if df.loc[i, f'return_{TIMEFRAME_MINUTES}min'] < ENTRY_THRESHOLD:
            position = -1
            entry_price = price
            entry_time = time
            lowest_price = price

    # EXIT

    elif position == -1:
        lowest_price = min(lowest_price, price)
        exit_reason = None

        if price > lowest_price * (1+TAKE_PROFIT):
            exit_reason = 'Take Profit'

        #stoploss

        elif price >=entry_price * (1 + STOP_LOSS):
            exit_reason = 'Stop Loss'

        elif (time - entry_time).seconds >= MAX_HOLD:
            exit_reason = "TIME"


        if exit_reason:
            SLIPPAGE = 0.0002  # 0.02%

            # when calculating pnl
            effective_price = price * (1 + SLIPPAGE)

            pnl = entry_price - effective_price
            pnl = pnl - COMMISSION

            trades.append({
                "entry_time": entry_time,
                "exit_time": time,
                "entry_price": entry_price,
                "exit_price": price,
                "pnl": pnl,
                "reason": exit_reason
            })

            position = 0


trades_df = pd.DataFrame(trades)
if trades_df.empty:
    print("No trades generated. Check strategy parameters.")
else:
    print("Total Trades:", len(trades_df))
    print("Total PnL:", trades_df['pnl'].sum())
    print("Win Rate:", (trades_df['pnl'] > 0).mean())

    print("\nExit Breakdown:")
    print(trades_df['reason'].value_counts())

    trades_df['cum_pnl'] = trades_df['pnl'].cumsum()

    import matplotlib.pyplot as plt
    plt.plot(trades_df['cum_pnl'])
    plt.title("Equity Curve")
    plt.show()
