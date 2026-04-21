import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

# Step 1: Download data
symbol = "AAPL"

data = yf.download(symbol, start="2024-01-01", end="2026-05-01")

# Step 2: Calculate moving averages
data['MA20'] = data['Close'].rolling(window=20).mean()
data['MA50'] = data['Close'].rolling(window=50).mean()

# Step 3: Generate signals
data['Signal'] = 0
data.iloc[20:, data.columns.get_loc('Signal')] = np.where(data['MA20'][20:] > data['MA50'][20:], 1, -1)

# Step 4: Calculate returns
data['Returns'] = data['Close'].pct_change()
data['Strategy_Returns'] = data['Returns'] * data['Signal'].shift(1)

# Step 5: Cumulative performance
data['Cumulative_Market'] = (1 + data['Returns']).cumprod()
data['Cumulative_Strategy'] = (1 + data['Strategy_Returns']).cumprod()

# Step 6: Plot
plt.figure(figsize=(12,6))
plt.plot(data['Cumulative_Market'], label="Market")
plt.plot(data['Cumulative_Strategy'], label="Strategy")
plt.legend()
plt.title(f"{symbol} Strategy Backtest")
plt.show()

# Step 7: Print performance
print("Final Market Return:", data['Cumulative_Market'].iloc[-1])
print("Final Strategy Return:", data['Cumulative_Strategy'].iloc[-1])