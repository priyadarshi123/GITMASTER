import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

# -------------------------
# SETTINGS
# -------------------------
symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY"]
initial_cash = 10000
cash_per_asset = initial_cash / len(symbols)

start = "2020-01-01"
end = "2024-01-01"

# -------------------------
# BACKTEST FUNCTION
# -------------------------
def run_single_asset(symbol):
    data = yf.download(symbol, start=start, end=end)

    data['MA20'] = data['Close'].rolling(20).mean()
    data['MA50'] = data['Close'].rolling(50).mean()

    data['Signal'] = 0
    data.loc[data['MA20'] > data['MA50'], 'Signal'] = 1
    data.loc[data['MA20'] < data['MA50'], 'Signal'] = -1
    data['Signal'] = data['Signal'].astype(int)

    cash = cash_per_asset
    position = 0
    portfolio = []

    for i in range(len(data)):
        price = data['Close'].iloc[i].item()   # ✅ FIXED
        signal = int(data['Signal'].iloc[i])

        if signal == 1 and position == 0:
            shares = cash // price
            cash -= shares * price
            position = shares

        elif signal == -1 and position > 0:
            cash += position * price
            position = 0

        total = cash + position * price
        portfolio.append(total)

    data['Portfolio'] = portfolio
    return data[['Close', 'Portfolio']]

# -------------------------
# RUN STRATEGY
# -------------------------
portfolio_df = pd.DataFrame()
benchmark_df = pd.DataFrame()

for symbol in symbols:
    result = run_single_asset(symbol)

    portfolio_df[symbol] = result['Portfolio']

    # Buy & Hold benchmark
    benchmark_df[symbol] = cash_per_asset * (
        result['Close'] / result['Close'].iloc[0]
    )

# Align indices
portfolio_df = portfolio_df.dropna()
benchmark_df = benchmark_df.loc[portfolio_df.index]

# -------------------------
# COMBINED PORTFOLIO
# -------------------------
portfolio_df['Total'] = portfolio_df.sum(axis=1)
benchmark_df['Total'] = benchmark_df.sum(axis=1)

# -------------------------
# RETURNS
# -------------------------
strategy_returns = portfolio_df['Total'].pct_change().fillna(0)
market_returns = benchmark_df['Total'].pct_change().fillna(0)

# -------------------------
# METRICS (STRATEGY)
# -------------------------
strategy_sharpe = np.sqrt(252) * (
    strategy_returns.mean() / strategy_returns.std()
)

strategy_dd = (portfolio_df['Total'] / portfolio_df['Total'].cummax() - 1).min()

strategy_return = portfolio_df['Total'].iloc[-1] / initial_cash - 1

# -------------------------
# METRICS (MARKET)
# -------------------------
market_sharpe = np.sqrt(252) * (
    market_returns.mean() / market_returns.std()
)

market_dd = (benchmark_df['Total'] / benchmark_df['Total'].cummax() - 1).min()

market_return = benchmark_df['Total'].iloc[-1] / initial_cash - 1

# -------------------------
# PRINT RESULTS
# -------------------------
print("\n--- STRATEGY ---")
print(f"Return: {strategy_return:.2%}")
print(f"Sharpe: {strategy_sharpe:.2f}")
print(f"Max Drawdown: {strategy_dd:.2%}")

print("\n--- MARKET (BUY & HOLD) ---")
print(f"Return: {market_return:.2%}")
print(f"Sharpe: {market_sharpe:.2f}")
print(f"Max Drawdown: {market_dd:.2%}")

# -------------------------
# PLOT
# -------------------------
plt.figure(figsize=(12,6))
plt.plot(portfolio_df['Total'], label="Strategy")
plt.plot(benchmark_df['Total'], label="Market")
plt.legend()
plt.title("Portfolio Strategy vs Market")
plt.show()