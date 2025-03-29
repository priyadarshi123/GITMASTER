import requests
from bs4 import BeautifulSoup

url= "https://www.screener.in/company/RELIANCE/consolidated/#profit-loss"
headers = {"User-Agent": "Chrome/134.0.6998.89"}

response = requests.get(url,headers=headers)

print(response.content)

soup = BeautifulSoup(response.content,"html.parser")

print(soup)


