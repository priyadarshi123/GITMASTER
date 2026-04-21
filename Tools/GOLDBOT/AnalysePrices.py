import matplotlib.pyplot as plt
import pandas as pd


df = pd.read_csv('GC_202606_1min_last15d.csv')


TIMEFRAME_MINUTES = 1  # Configurable timeframe in minutes
shift_period = TIMEFRAME_MINUTES  # Assuming data is in 1-minute intervals

df[f'price_{TIMEFRAME_MINUTES}min_ago'] = df['price'].shift(shift_period)
df[f'return_{TIMEFRAME_MINUTES}min'] = (df['price'] / df[f'price_{TIMEFRAME_MINUTES}min_ago']) - 1


df1 = df[f'price_{TIMEFRAME_MINUTES}min_ago'] <

plt.plot(df['close'], label='Closing Price')
plt.title('Gold Price Over Time')
plt.ylabel('Closing Price')
plt.xlabel('Date')
plt.show()