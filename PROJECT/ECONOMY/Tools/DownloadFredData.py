from fredapi import Fred
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
##print(str(Path(__file__).resolve()))
#print(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[1]))

base_dir = Path(__file__).resolve().parents[1]
data_dir = base_dir / "datasource"
data_dir.mkdir(exist_ok=True)
file_path = data_dir / "fred_yields.csv"


from my_functions import *
load_dotenv()
fred = Fred(api_key=os.getenv('FRED_API_KEY'))
yields = get_yield_data(observation_start='01-01-1975',observation_end = '2025-12-31')
yields.to_csv(file_path)
print(yields)