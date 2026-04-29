import pandas as pd
import os
from dotenv import load_dotenv
load_dotenv()
import streamlit as st
from sklearn.model_selection import train_test_split

db_url = os.getenv('DATABASE_URL')

from sqlalchemy import create_engine


def fetch_Stock_data_from_db():
    engine = create_engine(db_url)
    with engine.connect() as connection:
        query = "SELECT date, symbol, close FROM prices"
        df = pd.read_sql(query, connection)
    return df

def fetch_fed_data_from_db():
    engine = create_engine(db_url)
    with engine.connect() as connection:
        query = "SELECT date, indicator, value FROM macro"
        df = pd.read_sql(query, connection)
    return df

data = fetch_Stock_data_from_db()
data.sort_index(inplace=True)
data = data.pivot_table(index='date', columns=['symbol'], values='close')
data.reset_index(inplace=True)
data.ffill(inplace=True)
data.bfill(inplace=True)
######################################MACHINE LEARNING##########################

from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score

x= data[['SP500','BitCoin','Silver']]
#print(x)
y= data['Gold']
#print(y)

x_train,x_test,y_train,y_test= train_test_split(x,y,test_size=0.2,random_state=42)

#my_model= LinearRegression()
my_model = RandomForestRegressor(n_estimators=100, random_state=42)
my_model.fit(x_train,y_train)
y_train_pred= my_model.predict(x_train)
y_test_pred = my_model.predict(x_test)
print(y_test_pred)
print(y_test)

#sns.scatterplot(x=x_train.index,y=y_train_pred,color='blue')
#sns.scatterplot(x=x_test.index,y=y_test_pred,color='red')
plt.show()


r2_scrore = r2_score(y_test_pred,y_test)
print(r2_scrore)