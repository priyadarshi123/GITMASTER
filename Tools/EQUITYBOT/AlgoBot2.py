import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

symbols = ["AAPL", "MSFT", "NVDA", "TSLA"]
benchmark_symbol = "SPY"

initial_cash = 10000
cash_per_asset = initial_cash / len(symbols)

start = "2025-01-01"
end = "2026-04-01"

fee = 0.001
risk_per_trade = 0.2

# -------------------------
# MARKET FILTER (SPY)
# -------------------------
spy = yf.download(benchmark_symbol, start=start, end=end)
spy['MA200'] = spy['Close'].rolling(200).mean()
spy['Bull'] = spy['Close'] > spy['MA200']

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

    data = data.join(spy['Bull'], how='left')

    cash = cash_per_asset
    position = 0
    entry_price = 0

    portfolio = []
    trades = []

    for i in range(len(data)):
        price = data['Close'].iloc[i].item()
        signal = int(data['Signal'].iloc[i])
        bull = bool(data['Bull'].iloc[i])

        # ENTRY
        if signal == 1 and position == 0 and bull:
            alloc_cash = cash * risk_per_trade
            shares = alloc_cash // price

            if shares > 0:
                cost = shares * price * (1 + fee)
                cash -= cost
                position = shares
                entry_price = price

        # EXIT
        elif signal == -1 and position > 0:
            proceeds = position * price * (1 - fee)
            cash += proceeds

            trade_return = (price - entry_price) / entry_price
            trades.append(trade_return)

            position = 0

        total = cash + position * price
        portfolio.append(total)

    data['Portfolio'] = portfolio
    return data[['Close', 'Portfolio']], trades

# -------------------------
# RUN
# -------------------------
portfolio_df = pd.DataFrame()
all_trades = []

for symbol in symbols:
    result, trades = run_single_asset(symbol)
    portfolio_df[symbol] = result['Portfolio']
    all_trades.extend(trades)

portfolio_df = portfolio_df.dropna()
portfolio_df['Total'] = portfolio_df.sum(axis=1)

# -------------------------
# BENCHMARK
# -------------------------
benchmark = yf.download(benchmark_symbol, start=start, end=end)
benchmark = benchmark.loc[portfolio_df.index]

benchmark['Portfolio'] = initial_cash * (
    benchmark['Close'] / benchmark['Close'].iloc[0]
)

# -------------------------
# RETURNS
# -------------------------
returns = portfolio_df['Total'].pct_change().fillna(0)
bench_returns = benchmark['Portfolio'].pct_change().fillna(0)

# -------------------------
# METRICS
# -------------------------
sharpe = np.sqrt(252) * returns.mean() / returns.std()
max_dd = (portfolio_df['Total'] / portfolio_df['Total'].cummax() - 1).min()
total_return = portfolio_df['Total'].iloc[-1] / initial_cash - 1

bench_sharpe = np.sqrt(252) * bench_returns.mean() / bench_returns.std()
bench_dd = (benchmark['Portfolio'] / benchmark['Portfolio'].cummax() - 1).min()
bench_return = benchmark['Portfolio'].iloc[-1] / initial_cash - 1

# Trade stats
win_rate = np.mean([t > 0 for t in all_trades]) if all_trades else 0
num_trades = len(all_trades)

# -------------------------
# OUTPUT
# -------------------------
print("\n--- STRATEGY ---")
print(f"Return: {total_return:.2%}")
print(f"Sharpe: {sharpe:.2f}")
print(f"Max Drawdown: {max_dd:.2%}")
print(f"Win Rate: {win_rate:.2%}")
print(f"Trades: {num_trades}")

print("\n--- MARKET ---")
print(f"Return: {bench_return:.2%}")
print(f"Sharpe: {bench_sharpe:.2f}")
print(f"Max Drawdown: {bench_dd:.2%}")

# -------------------------
# PLOT
# -------------------------
plt.figure(figsize=(12,6))
plt.plot(portfolio_df['Total'], label="Strategy")
plt.plot(benchmark['Portfolio'], label="Market")
plt.legend()
plt.title("Strategy vs Market")
plt.show()