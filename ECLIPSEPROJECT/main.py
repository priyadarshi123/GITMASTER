import pandas as pd
import warnings
import pymysql


exchange = pd.read_csv("ExchangeTradeList.csv")
#print(exchange)

connection = pymysql.connect(
    host="localhost",
    user="root",
    password="Eva@2017",
    database="PDTEST"
)

warnings.filterwarnings("ignore", category=UserWarning)

query = "select * from trades"
try:
    internal = pd.read_sql(query, connection)
except Exception as e:
    print("Some error while connecting to MySQL", e)
    connection.close()
    exit()

connection.close()


#print(internal)




exchange["ExchangeTradeID"] = exchange["ExchangeTradeID"].astype(str)
internal["exchangetradeid"] = internal["exchangetradeid"].astype(str)

exchange_ids = set(exchange["ExchangeTradeID"])
internal_ids = set(internal["exchangetradeid"])

missing_internal = exchange_ids - internal_ids
missing_exchange = internal_ids - exchange_ids


print("Total Exchange Trades :", len(exchange))
print("Total Internal Trades :", len(internal))

print("Trade ID's present in Exchange but missing in the internal database:")
for trade in missing_internal:
    print(trade)


print("Trades Id's  present in Internal but missing in the Exchange database:")
for trade in missing_exchange:
    print(trade)

