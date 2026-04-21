import pandas as pd
from fredapi import Fred
import matplotlib.pyplot as plt
import seaborn as sns
sns.set()
import os
from dotenv import load_dotenv
load_dotenv()
FRED_API_KEY = os.getenv('FRED_API_KEY')
fred = Fred(api_key=FRED_API_KEY)
from datetime import datetime
from matplotlib.ticker import FuncFormatter

DATA_FILE = "treasury_yields.parquet"

# List of Treasury yield series IDs
series_ids = ['DGS1MO', 'DGS3MO', 'DGS6MO', 'DGS1', 'DGS2', 'DGS3', 'DGS5', 'DGS7', 'DGS10', 'DGS20', 'DGS30']

dateToday = datetime.today().strftime('%Y-%m-%d')


def fetch_data(start_date):
    data={}
    today = datetime.today().strftime('%Y-%m-%d')
    for s in series_ids:
        data[s] = fred.get_series(s, observation_start=start_date, observation_end=today)

    df = pd.DataFrame(data)
    df.index = pd.to_datetime(df.index)
    return df


if os.path.exists(DATA_FILE):
    existing = pd.read_parquet(DATA_FILE)
    last_date = existing.index.max().strftime('%Y-%m-%d')
    print(f"Updating from {last_date}...")
    new_data = fetch_data(last_date)

    df = pd.concat([existing, new_data])
else:
    print("Downloading full dataset...")
    df = fetch_data("1975-01-01")

# STEP 2: Save updated dataset
df.to_parquet(DATA_FILE)
print(df)

print("Data ready!")

# Rename columns for clarity
df.columns = ['1 Month', '3 Month', '6 Month', '1 Year', '2 Year', '3 Year', '5 Year', \
                  '7 Year', '10 Year', '20 Year', '30 Year']

df.index = pd.to_datetime(df.index)
# 🔥 FIX: remove duplicate dates
df = df[~df.index.duplicated(keep='last')]


latest_date = df.index.max().strftime('%Y-%m-%d')

def plot_yield_curve(date):
    maturities = ['1M', '3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '20Y', '30Y'] # Maturities
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(maturities, df.loc[date], marker='D', label='Yield Curve at ' + date)

    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.2f}%'))
    ax.set_xticks(range(len(maturities)))
    ax.set_xticklabels(maturities)

    # Add labels and title
    ax.set_xlabel('Maturity')
    ax.set_ylabel('Yield')
    ax.set_title('Treasury Yield Curve')

    fig.legend(loc=[0.69, 0.14])

    # Show the plot
    plt.grid(True)
    plt.show()

def plot_yield_curve1(date):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import numpy as np

    maturities = ['1M', '3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '20Y', '30Y']
    x = np.arange(len(maturities))

    row = df.loc[date]
    if isinstance(row, pd.DataFrame):  # safety
        row = row.iloc[-1]

    y = row.values

    # 🎨 Bloomberg-like styling
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))

    # Line + markers
    ax.plot(x, y, color='#FFD700', linewidth=2.5, marker='o', markersize=6)

    # Subtle grid
    ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.3)

    # Remove top/right borders
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Axis labels
    ax.set_xticks(x)
    ax.set_xticklabels(maturities, fontsize=10)
    ax.set_ylabel('Yield (%)', fontsize=11)

    # Title (left aligned like Bloomberg)
    ax.set_title(f'US Treasury Yield Curve — {date}', loc='left', fontsize=13, weight='bold')

    # Format Y axis as %
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.2f}%'))

    # Highlight latest point (optional nice touch)
    ax.scatter(x[-1], y[-1], color='white', s=60, zorder=5)

    plt.tight_layout()
    plt.show()

plot_yield_curve1(latest_date)















