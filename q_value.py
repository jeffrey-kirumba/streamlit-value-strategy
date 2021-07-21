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

#I know it's good practice to put keys in a secrets.py but this is a public api key
IEX_CLOUD_API_TOKEN = 'Tpk_059b97af715d417d9f49f50b51b1c448'

stocks = pd.read_csv('sp_500_stocks.csv')

def build_df(portfolio_size):
    stocks = pd.read_csv('sp_500_stocks.csv')
    def chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]   
            
    symbol_groups = list(chunks(stocks['Ticker'], 100))
    symbol_strings = []
    for i in range(0, len(symbol_groups)):
        symbol_strings.append(','.join(symbol_groups[i]))


    rv_columns = [
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

    rv_dataframe = pd.DataFrame(columns = rv_columns)

    for symbol_string in symbol_strings:
        batch_api_call_url = f'https://sandbox.iexapis.com/stable/stock/market/batch?symbols={symbol_string}&types=quote,advanced-stats&token={IEX_CLOUD_API_TOKEN}'
        data = requests.get(batch_api_call_url).json()
        for symbol in symbol_string.split(','):
            enterprise_value = data[symbol]['advanced-stats']['enterpriseValue']
            ebitda = data[symbol]['advanced-stats']['EBITDA']
            gross_profit = data[symbol]['advanced-stats']['grossProfit']
            
            try:
                ev_to_ebitda = enterprise_value/ebitda
            except TypeError:
                ev_to_ebitda = np.NaN
            
            try:
                ev_to_gross_profit = enterprise_value/gross_profit
            except TypeError:
                ev_to_gross_profit = np.NaN
                
            rv_dataframe = rv_dataframe.append(
                pd.Series([
                    symbol,
                    data[symbol]['quote']['latestPrice'],
                    'N/A',
                    data[symbol]['quote']['peRatio'],
                    'N/A',
                    data[symbol]['advanced-stats']['priceToBook'],
                    'N/A',
                    data[symbol]['advanced-stats']['priceToSales'],
                    'N/A',
                    ev_to_ebitda,
                    'N/A',
                    ev_to_gross_profit,
                    'N/A',
                    'N/A'
            ],
            index = rv_columns),
                ignore_index = True
            )

    for column in ['Price-to-Earnings Ratio', 'Price-to-Book Ratio','Price-to-Sales Ratio',  'EV/EBITDA','EV/GP']:
        rv_dataframe[column].fillna(rv_dataframe[column].mean(), inplace = True)

    metrics = {
                'Price-to-Earnings Ratio': 'PE Percentile',
                'Price-to-Book Ratio':'PB Percentile',
                'Price-to-Sales Ratio': 'PS Percentile',
                'EV/EBITDA':'EV/EBITDA Percentile',
                'EV/GP':'EV/GP Percentile'
    }

    for row in rv_dataframe.index:
        for metric in metrics.keys():
            rv_dataframe.loc[row, metrics[metric]] = stats.percentileofscore(rv_dataframe[metric], rv_dataframe.loc[row, metric])/100

    # Print each percentile score to make sure it was calculated properly
    for metric in metrics.values():
        print(rv_dataframe[metric]) 

    for row in rv_dataframe.index:
        value_percentiles = []
        for metric in metrics.keys():
            value_percentiles.append(rv_dataframe.loc[row, metrics[metric]])
        rv_dataframe.loc[row, 'RV Score'] = mean(value_percentiles)

    rv_dataframe.sort_values(by = 'RV Score', inplace = True)
    rv_dataframe = rv_dataframe[:50]
    rv_dataframe.reset_index(drop = True, inplace = True)

    position_size = float(portfolio_size) / len(rv_dataframe.index)
    for i in range(0, len(rv_dataframe['Ticker'])-1):
        rv_dataframe.loc[i, 'Number of Shares to Buy'] = math.floor(position_size / rv_dataframe['Price'][i])

    return rv_dataframe

def filedownload(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # strings <-> bytes conversions
    href = f'<a href="data:file/csv;base64,{b64}" download="SP500.csv">Download CSV File</a>'
    return href

st.title('Robust Value Strategy')

st.write("""
### This investment strategy selects 50 of the cheapest stocks in the S&P 500 relative to their value (earnings and assets) """)

image = Image.open('stockmarketphoto.jpg')
st.image(image, use_column_width=True)

st.write("""
### From there, it will calculate recommended the number of shares to buy for an equal-weight portfolio of these 50 stocks.
""")

capital = st.number_input('Enter the value of your portfolio')
final_df = build_df(capital)
st.table(final_df)

st.markdown(filedownload(final_df), unsafe_allow_html=True)

