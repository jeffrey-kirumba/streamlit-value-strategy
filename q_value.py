import numpy as np 
import pandas as pd 
import time
import requests 
import xlsxwriter 
import math 
from scipy import stats 
import streamlit as st
from PIL import Image
from statistics import mean
import base64
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor


# stocks = pd.read_csv('sp_500_stocks.csv')
class YFWrap:
    def __init__(self) -> None:
        self.tickerInfo = {}
    
    def getAllData(self):
        stocks = pd.read_csv('sp_500_stocks.csv')
        allTickers = list(stocks['Ticker'])
        groups = len(allTickers) // 8
        args = self.chunks(list(allTickers), groups)
        try:
            allYfTicks = []
            for arg in args:
                ticks = yf.Tickers(arg)
                allYfTicks.append(ticks)
            
            with ThreadPoolExecutor() as executor:
                executor.map(self.getTickerInfo, allYfTicks)
        except Exception as e:
            print(f"yf error: {e}")

    def getTickerInfo(self, ticks: yf.Tickers):
        try:
            for symbol in ticks.symbols:
                self.tickerInfo[symbol] = ticks.tickers[symbol].info
        except Exception as e:
            print(f"yf error: {e}")

    def chunks(self, lst, n):
        """Yield successive n-sized chunks from lst."""
        final = []
        for i in range(0, len(lst), n):
            final.append(lst[i:i + n])
        return final
    
class ValueScreener:
    def __init__(self, tickerInfo) -> None:
        self.rv_columns = [
        'Ticker',
        'Price',
        'Number of Shares to Buy', 
        'Price-to-Earnings Ratio',
        'PE Percentile',
        'Price-to-Book Ratio',
        'PB Percentile',
        'Price-to-Sales Ratio',
        'PS Percentile',
        'EV/EBITDA',
        'EV/EBITDA Percentile',
        'EV/GP',
        'EV/GP Percentile',
        'RV Score'
        ]
        self.mainFrame = pd.DataFrame(columns = self.rv_columns)
        self.tickerInfo = tickerInfo
        
    def calcAllTickers(self):
        with ThreadPoolExecutor() as executor:
                executor.map(self.calcTicker, list(self.tickerInfo.keys()))
        metrics = {
                    'Price-to-Earnings Ratio': 'PE Percentile',
                    'Price-to-Book Ratio':'PB Percentile',
                    'Price-to-Sales Ratio': 'PS Percentile',
                    'EV/EBITDA':'EV/EBITDA Percentile',
                    'EV/GP':'EV/GP Percentile'
        }
        self.mainFrame = self.mainFrame.dropna()
        for metric in metrics.keys():
            self.mainFrame[metrics[metric]] = self.mainFrame[metric].rank(pct=True)

        self.mainFrame['RV Score'] = self.mainFrame[list(metrics.values())].mean(axis=1)
        self.mainFrame = self.mainFrame.sort_values(by = 'RV Score', ascending = False)


    
    def calcTicker(self, symbol):
        latestPrice = np.nan
        peRatio = np.nan
        priceToBook = np.nan
        priceToSales = np.nan
        enterprise_value = np.nan
        ebitda = np.nan
        gross_profit = np.nan
        ev_to_ebitda = np.nan
        ev_to_gross_profit = np.nan
        data = self.tickerInfo[symbol]
        if 'currentPrice' in data and type(data['currentPrice']) != str:
            latestPrice = data['currentPrice']
        elif 'regularMarketPreviousClose' in data and type(data['regularMarketPreviousClose']) != str:
            latestPrice = data['regularMarketPreviousClose']
        elif 'previousClose' in data and type(data['previousClose']) != str:
            latestPrice = data['previousClose']

        if 'trailingPE' in data and type(data['trailingPE']) != str:
            peRatio = data['trailingPE'] if data['trailingPE'] else np.nan

        if 'priceToBook' in data and type(data['priceToBook']) != str:
            priceToBook = data['priceToBook'] if data['priceToBook'] else np.nan

        if 'priceToSalesTrailing12Months' in data and type(data['priceToSalesTrailing12Months']) != str:
            priceToSales = data['priceToSalesTrailing12Months'] if data['priceToSalesTrailing12Months'] else np.nan

        if 'enterpriseValue' in data and type(data['enterpriseValue']) != str:
            enterprise_value = data['enterpriseValue'] if data['enterpriseValue'] else np.nan
        
        if 'ebitda' in data and type(data['ebitda']) != str:
            ebitda = data['ebitda'] if data['ebitda'] else np.nan
    
        if 'grossMargins' in data and 'totalRevenue' in data:
            grossMargins = data['grossMargins'] if data['grossMargins'] else np.nan
            totalRevenue = data['totalRevenue'] if data['totalRevenue'] else np.nan
            gross_profit = grossMargins * totalRevenue
    
        if 'enterpriseToEbitda' in data and type(data['enterpriseToEbitda']) != str:
            ev_to_ebitda = data['enterpriseToEbitda'] if data['enterpriseToEbitda'] else np.nan
        elif ebitda and enterprise_value:
            ev_to_ebitda = enterprise_value/ebitda
    
        if enterprise_value and gross_profit:
            ev_to_gross_profit = enterprise_value/gross_profit

        series = pd.Series([
                symbol,
                latestPrice,
                'N/A',
                peRatio,
                'N/A',
                priceToBook,
                'N/A',
                priceToSales,
                'N/A',
                ev_to_ebitda,
                'N/A',
                ev_to_gross_profit,
                'N/A',
                'N/A'
        ],
        index = self.rv_columns)
        self.mainFrame.loc[-1] = series
        self.mainFrame.index+=1
        self.mainFrame.sort_index()

    def applyPortfolioSize(self, portfolio_size):
        mainFrame = self.mainFrame.sort_values(by = 'RV Score', ascending = False)
        mainFrame = mainFrame[:50]
        position_size = float(portfolio_size) / len(mainFrame.index)
        mainFrame['Number of Shares to Buy'] = mainFrame['Price'].rfloordiv(position_size)
        mainFrame = mainFrame.replace(['N/A'], 0)
        return mainFrame

def filedownload(df: pd.DataFrame):
    if not df.empty:
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()  # strings <-> bytes conversions
        href = f'<a href="data:file/csv;base64,{b64}" download="SP500.csv">Download CSV File</a>'
        return href




@st.cache_resource
def getAllData() -> ValueScreener:
    yfRapper = YFWrap()
    yfRapper.getAllData() 
    vs = ValueScreener(tickerInfo=yfRapper.tickerInfo)
    vs.tickerInfo = yfRapper.tickerInfo
    vs.calcAllTickers()
    return vs

vs = getAllData()


displayFrame = None
st.title('Robust Value Strategy')
st.write("""
### This investment strategy ranks stocks in the S&P 500 by a score generated from common value metrics (EV/EBITDA, Price-to-book etc.) """)
image = Image.open('stockmarketphoto.jpg')
st.image(image, use_column_width=True)
st.write("""
### From there, it will recommend the number of shares to buy for an equal-weight portfolio of the top 50 stocks.
""")
capital = st.number_input('Enter the value of your portfolio')

if 'displayFrame' not in st.session_state:
    with st.spinner('Gathering data'):
        st.session_state.displayFrame = vs.mainFrame
        displayFrame = vs.mainFrame
elif capital > 0:
    vs.mainFrame = st.session_state.displayFrame
    # print("Applying portfolio size")
    displayFrame = vs.applyPortfolioSize(portfolio_size=capital)
#if count < all
    #display a warning saying ""
if capital == 0 and displayFrame['Ticker'].count() < 290:
    st.toast("Some tickers were left out, try again later", icon='🫡')

st.markdown(filedownload(displayFrame), unsafe_allow_html=True)
print(displayFrame.head(n=5))
st.table(displayFrame)