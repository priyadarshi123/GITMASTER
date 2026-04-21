import pandas as pd

from ib_insync import *
import pandas as pd

ib = IB()
ib.connect('127.0.0.1',7497,clientId=2)

# Define Micro Gold Futures (MGC)
contract = Future(symbol='MGC', lastTradeDateOrContractMonth='202606', exchange='COMEX', currency='USD')
ib.qualifyContracts(contract)

all_data = []

end_time = ''

for i in range(1):  # 5 hours of data
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=end_time,
        durationStr='1800 S',
        barSizeSetting='1 secs',
        whatToShow='TRADES',
        useRTH=False,
        formatDate=1
    )
    ib.sleep(1)
    df = util.df(bars)

    if df.empty:
        break

    all_data.append(df)

    # Move backward in time
    end_time = df['date'].iloc[0]

# Combine
final_df = pd.concat(all_data).drop_duplicates().sort_values('date')

final_df.to_csv("gold_1sec_full.csv", index=False)

print(df.head())
ib.disconnect()