import numpy as np 
import pandas as pd 
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
class ValueScreener:
    def __init__(self) -> None:
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
        self.tickerInfo = {}
        
    def getTickerInfo(self, ticker):
            try:
                symbObj = yf.Ticker(ticker)
                self.tickerInfo[ticker] = symbObj.info
            except Exception as e:
                print(e)
                print(f'Error getting tick info for {ticker}')

    def getAllTickerInfo(self):
        stocks = pd.read_csv('sp_500_stocks.csv')
        allTickers = list(stocks['Ticker'])
        with ThreadPoolExecutor() as executor:
            executor.map(self.getTickerInfo, allTickers)

    def getData(self):
        self.getAllTickerInfo()
        for symbol in self.tickerInfo:
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
 
        for column in ['Price-to-Earnings Ratio', 'Price-to-Book Ratio','Price-to-Sales Ratio', 'EV/EBITDA','EV/GP']:
            self.mainFrame[column].fillna(self.mainFrame[column].mean(), inplace = True)
        

        metrics = {
                    'Price-to-Earnings Ratio': 'PE Percentile',
                    'Price-to-Book Ratio':'PB Percentile',
                    'Price-to-Sales Ratio': 'PS Percentile',
                    'EV/EBITDA':'EV/EBITDA Percentile',
                    'EV/GP':'EV/GP Percentile'
        }

        for row in self.mainFrame.index:
            for metric in metrics.keys():
                self.mainFrame.loc[row, metrics[metric]] = stats.percentileofscore(self.mainFrame[metric], self.mainFrame.loc[row, metric])/100

        # Print each percentile score to make sure it was calculated properly
        for metric in metrics.values():
            print(self.mainFrame[metric]) 

        for row in self.mainFrame.index:
            value_percentiles = []
            for metric in metrics.keys():
                value_percentiles.append(self.mainFrame.loc[row, metrics[metric]])
            self.mainFrame.loc[row, 'RV Score'] = np.mean(value_percentiles)
            print('value percentiles', value_percentiles)
            print('RV Score', self.mainFrame.loc[row, 'RV Score'])

    def applyPortfolioSize(self, portfolio_size):
        mainFrame = self.mainFrame.sort_values(by = 'RV Score', ascending = False)
        mainFrame = mainFrame[:50]
        mainFrame.reset_index(drop = True, inplace = True)
        position_size = float(portfolio_size) / len(mainFrame.index)
        for i in range(0, len(mainFrame['Ticker'])-1):
            try:
                mainFrame.loc[i, 'Number of Shares to Buy'] = math.floor(position_size / mainFrame['Price'][i])
            except Exception:
                print('portfolio size', position_size)
                print('price', mainFrame['Price'][i])
        
        mainFrame = mainFrame.replace(['N/A'], 0)
        return mainFrame

def filedownload(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # strings <-> bytes conversions
    href = f'<a href="data:file/csv;base64,{b64}" download="SP500.csv">Download CSV File</a>'
    return href


vs = ValueScreener()
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
        vs.getData()
        st.session_state.displayFrame = vs.mainFrame
        displayFrame = vs.mainFrame
elif capital > 0:
    vs.mainFrame = st.session_state.displayFrame
    displayFrame = vs.applyPortfolioSize(portfolio_size=capital)
st.markdown(filedownload(displayFrame), unsafe_allow_html=True)
st.table(displayFrame)