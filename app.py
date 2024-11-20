import json
import time
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
import requests
import os
from ta.trend import SMAIndicator, EMAIndicator

# Constants
REFRESH_INTERVAL_DEFAULT = 5  # Default refresh interval in seconds
PORTFOLIO_FILE = "portfolio_data.json"
REFRESH_INTERVAL = 5

# Ensure the portfolio file exists
if not os.path.exists(PORTFOLIO_FILE):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump({}, f)

# Define the list of Nifty 50 stocks
nifty_50_stocks = [
    "INDUSINDBK", "TATAMOTORS", "ASIANPAINT", "ONGC", "HEROMOTOCO", "TRENT", 
    "ADANIENT", "BAJAJ-AUTO", "COALINDIA", "TATACONSUM", "TATASTEEL", "RELIANCE", 
    "SBILIFE", "HINDUNILVR", "SHRIRAMFIN", "NESTLEIND", "TITAN", "ADANIPORTS", 
    "BPCL", "MARUTI", "BRITANNIA", "BAJAJFINSV", "HINDALCO", "BAJFINANCE", 
    "AXISBANK", "GRASIM", "BHARTIARTL", "NTPC", "BEL", "KOTAKBANK", "POWERGRID", 
    "ULTRACEMCO", "ITC", "DRREDDY", "M&M", "CIPLA", "TCS", "SUNPHARMA", "JSWSTEEL", 
    "LT", "HDFCLIFE", "SBIN", "ICICIBANK", "INFY", "EICHERMOT", "APOLLOHOSP", 
    "TECHM", "WIPRO", "HDFCBANK", "HCLTECH"
]

bank_nifty_stocks = [
    "AUBANK", "CANBK", "AXISBANK", "HDFCBANK", "ICICIBANK", "KOTAKBANK", "SBIN", "INDUSINDBK", 
    "BANKBARODA", "PNB", "FEDERALBNK", "IDFCFIRSTB"
]

fin_nifty_stocks = [
    "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN", "RELIANCE", 
    "BAJAJFINSV", "BAJFINANCE", "MUTHOOTFIN", "HDFCLIFE", "TATAMOTORS", "TCS", 
    "HDFC", "ICICIGI", "L&T", "ADANIGREEN", "ICICIPRULI", "M&M", "CHOLAFIN", "HDFCAMC", 
    "LICHSGFIN" , "MCX", "PFC", "RECLTD", "SBICARD", "SBILIFE", "SHRIRAMFIN"
]

midcap_nifty_stocks = [
    "ASHOKLEY", "AUBANK", "AUROPHARMA", "BHARATFORG", "COFORGE", "COLPAL", "CONCOR", "COMMINSIND",
    "DIXON", "FEDERALBNK", "GODREJPROP", "HDFCAMC", "HINDPETRO", "IDEA", "IDFCFIRSTB", "INDHOTEL",
    "INDUSTOWER", "LUPIN", "MPHASIS", "MRF", "PERSISTENT", "PIIND","POLYCAB", "SRF", "VOLTAS"
]

sensex_stocks = [
    "ADANIPORTS", "ASIANPAINT", "AXISBANK", "BAJAJFINSV", "BAJFINANCE", "BHARTIARTL", "HCLTECH",
    "HDFCBANK", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY", "ITC", "JSWSTEEL", "KOTAKBANK",
    "LT", "M&M", "MARUTI", "NESTLEIND", "NTPC", "POWERGRID", "RELIANCE", "SBIN", "SUNPHARMA",
    "TATAMOTORS", "TATASTEEL", "TCS", "TECHM", "TITAN", "ULTRACEMCO"
]

# Load or initialize portfolio
def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, "r") as file:
            return json.load(file)
    except Exception as e:
        st.error(f"Error loading portfolio: {e}")
        return {}

def save_portfolio(portfolio_data):
    try:
        with open(PORTFOLIO_FILE, "w") as file:
            json.dump(portfolio_data, file)
    except Exception as e:
        st.error(f"Error saving portfolio: {e}")

# Helper function to get stock data with a delay for refresh
def get_stock_data1(symbol):
    stock = yf.Ticker(symbol + ".NS")
    hist = stock.history(period="1d")
    return hist["Close"].iloc[-1] if not hist.empty else None

def fetch_news(stock_symbol):
    try:
        NEWS_API_KEY = 'your_news_api_key'  # Replace with your actual News API key
        url = f"https://newsapi.org/v2/everything?q={stock_symbol}&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
        response = requests.get(url)
        if response.status_code != 200:
            st.warning(f"Failed to fetch news. Status code: {response.status_code}")
            return []
        articles = response.json().get("articles", [])
        return articles[:5]  # Limit to the top 5 articles
    except Exception as e:
        st.error(f"Error fetching news for {stock_symbol}: {e}")
        return []

# Caching stock data for performance
@st.cache_data(ttl=3600)  # Cache for 1 hour to avoid refetching often
def get_stock_data(symbol):
    stock = yf.Ticker(symbol)
    today = date.today()
    last_year = today - timedelta(days=365)
    try:
        hist = stock.history(start=last_year, end=today)
        # Fetch 1-day intraday data (interval of 5 minutes)
        intraday = stock.history(period="1d", interval="5m")
        current_price = stock.info.get('currentPrice', hist['Close'][-1])  # Fallback to latest Close price
        high_52 = hist['High'].max()
        low_52 = hist['Low'].min()
        pe_ratio = stock.info.get('trailingPE', 'N/A')
        recent_low = hist['Low'].rolling(window=20).min().iloc[-1]  # 20-day low as support
        recent_high = hist['High'].rolling(window=20).max().iloc[-1]  # 20-day high as resistance
        
        analyst_rec = stock.recommendations
        major_holders = stock.major_holders
        all_stats = stock.info
    except (IndexError, KeyError):
        return {"Error": f"Data for {symbol} is unavailable."}
    
    gain_from_low = (current_price - low_52) / low_52 * 100 if low_52 else 'N/A'
    drop_from_high = (high_52 - current_price) / high_52 * 100 if high_52 else 'N/A'
    
    # Add Technical Indicators
    rsi = RSIIndicator(hist['Close']).rsi()[-1]  # Get the latest RSI
    macd = MACD(hist['Close'])
    macd_signal = macd.macd_signal()[-1]  # Get the latest MACD signal
    bb = BollingerBands(hist['Close'])
    bb_upper = bb.bollinger_hband()[-1]  # Upper band
    bb_lower = bb.bollinger_lband()[-1]  # Lower band
    
    return {
        "Current Price": current_price,
        "52-Week High": high_52,
        "52-Week Low": low_52,
        "Support Level": recent_low,
        "Resistance Level": recent_high,
        "Analyst Recommendations": analyst_rec,
        "Major Holders": major_holders,
        "All Statistics": all_stats,
        "Gain from Low (%)": gain_from_low,
        "Drop from High (%)": drop_from_high,
        "PE Ratio": pe_ratio,
        "RSI": rsi,
        "MACD Signal": macd_signal,
        "Bollinger Bands": {"Upper": bb_upper, "Lower": bb_lower},
         "1-Year Trend": hist,
        "1-Day Trend": intraday,  # 1-day intraday trend data
        "Historical Data": hist,
    }

# Utility function to save/load JSON
def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f)

def load_json(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return default_value

# Initialize session state
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = load_json(PORTFOLIO_FILE, {})
if "refresh_interval" not in st.session_state:
    st.session_state["refresh_interval"] = REFRESH_INTERVAL_DEFAULT

# Refresh button 
# Add this if you need refresh button i Disabled this cuz its looks awful in UI

#if st.button("Refresh Data"):
#    st.cache_data.clear()  # Clears all cached data
#    st.success("Data cache cleared! Fetching fresh data...")

# Tabs
tab1, tab2, tab3,tab4 = st.tabs(["📈 Stock Tracker", "💼 Watchlist","📰 News", "⚙️ Settings"])

st.sidebar.header("Settings")
refresh_enabled = st.sidebar.checkbox("Enable Auto-Refresh", value=True)
refresh_interval = st.sidebar.slider("Refresh Interval (seconds):", min_value=5, max_value=60, value=REFRESH_INTERVAL)

# Tab 1: Stock Tracker
with tab1:
    # Streamlit UI
    st.title("📈 Nifty Stock Tracker")

    st.subheader("Filters")
    index_filter = st.selectbox(
    "Filter Stocks by Index:",
    options=["All Stocks", "Nifty 50", "Bank Nifty", "Fin Nifty", "Midcap Nifty", "Sensex"],
    index=0,
    )
    # Filter stocks based on selected index
    if index_filter == "All Stocks":
        stock_list = nifty_50_stocks + bank_nifty_stocks + fin_nifty_stocks + midcap_nifty_stocks + sensex_stocks
    elif index_filter == "Nifty 50":
        stock_list = nifty_50_stocks
    elif index_filter == "Bank Nifty":
        stock_list = bank_nifty_stocks
    elif index_filter == "Fin Nifty":
        stock_list = fin_nifty_stocks
    elif index_filter == "Midcap Nifty":
        stock_list = midcap_nifty_stocks
    elif index_filter == "Sensex":
        stock_list = sensex_stocks

    # Stock selection
    selected_stocks = st.multiselect(
        "Select Stock(s):",
        options=sorted(set(stock_list)),
        default=[stock_list[0]] if stock_list else []  # Ensure the default exists in options
    )
    # Display information for each selected stock
    if selected_stocks:
        for symbol in selected_stocks:
            data = get_stock_data(symbol + ".NS")  # Adding ".NS" for NSE stocks
            
            # Check if data retrieval was successful
            if "Error" in data:
                st.write(data["Error"])
            else:
                # Display stock information in a visually appealing format
                st.subheader(f"{symbol} Statistics")
                col1, col2, col3 = st.columns(3)
                
                # Display Current Price, 52-Week High, 52-Week Low in columns
                col1.metric("Current Price", f"₹{data['Current Price']}")
                col2.metric("52-Week High", f"₹{data['52-Week High']}")
                col3.metric("52-Week Low", f"₹{data['52-Week Low']}")
                
                # Show gain/drop in colored format
                gain_delta_color = "normal" if data['Gain from Low (%)'] >= 0 else "inverse"
                drop_delta_color = "inverse" if data['Drop from High (%)'] >= 0 else "normal"
                
                col1.metric("Gain from 52-Week Low", f"{data['Gain from Low (%)']:.2f}%", delta_color=gain_delta_color)
                col2.metric("Drop from 52-Week High", f"{data['Drop from High (%)']:.2f}%", delta_color=drop_delta_color)
                col3.metric("PE Ratio", data["PE Ratio"])

                # refresh button for stock data
                if st.button("Refresh Stock Data"):
                    stock, hist = get_stock_data(selected_stocks)
                    if stock and hist is not None:
                        st.success(f"Data refreshed for {selected_stocks}")

                st.write(f"**Support Level:** ₹{data['Support Level']:.2f}")
                st.write(f"**Resistance Level:** ₹{data['Resistance Level']:.2f}")
                
                # Display technical indicators (RSI, MACD, Bollinger Bands)
                st.write(f"**RSI:** {data['RSI']:.2f}")
                st.write(f"**MACD Signal:** {data['MACD Signal']:.2f}")
                st.write(f"**Bollinger Bands (Upper):** ₹{data['Bollinger Bands']['Upper']:.2f}")
                st.write(f"**Bollinger Bands (Lower):** ₹{data['Bollinger Bands']['Lower']:.2f}")

                # Initialize visibility states for each section independently
    if f"{symbol}_1d_chart_visible" not in st.session_state:
        st.session_state[f"{symbol}_1d_chart_visible"] = False

    if f"{symbol}_1y_chart_visible" not in st.session_state:
        st.session_state[f"{symbol}_1y_chart_visible"] = False

    if f"{symbol}_sma_ema" not in st.session_state:
        st.session_state[f"{symbol}_sma_ema"] = False

    if f"{symbol}_analytics_visible" not in st.session_state:
        st.session_state[f"{symbol}_analytics_visible"] = False
                
    # 1D Chart Toggle
    if st.button(f"1D Chart for {symbol}"):
        st.session_state[f"{symbol}_1d_chart_visible"] = not st.session_state[f"{symbol}_1d_chart_visible"]

    # Display sections based on visibility state
    if st.session_state[f"{symbol}_1d_chart_visible"]:
        # Price chart
        fig_1d_price = go.Figure()
        fig_1d_price.add_trace(go.Scatter(x=data["1-Day Trend"].index, y=data["1-Day Trend"]['Close'], mode='lines', name='Price'))
        fig_1d_price.update_layout(
        title="1-Day Price",
        yaxis=dict(title="Price"),
        xaxis=dict(title="Time")
        )
        st.plotly_chart(fig_1d_price)

        # Volume chart
        fig_1d_volume = go.Figure()
        fig_1d_volume.add_trace(go.Bar(x=data["1-Day Trend"].index, y=data["1-Day Trend"]['Volume'], name='Volume', marker_color='orange'))
        fig_1d_volume.update_layout(
        title="1-Day Volume",
        yaxis=dict(title="Volume"),
        xaxis=dict(title="Time")
        )
        st.plotly_chart(fig_1d_volume)

    # 1Y Chart Toggle
    if st.button(f"1Y Chart for {symbol}"):
        st.session_state[f"{symbol}_1y_chart_visible"] = not st.session_state[f"{symbol}_1y_chart_visible"]

    if st.session_state[f"{symbol}_1y_chart_visible"]:
        # Price chart
        fig_1y_price = go.Figure()
        fig_1y_price.add_trace(go.Scatter(x=data["1-Year Trend"].index, y=data["1-Year Trend"]['Close'], mode='lines', name='Price'))
        fig_1y_price.update_layout(
        title="1-Year Price",
        yaxis=dict(title="Price"),
        xaxis=dict(title="Date")
        )
        st.plotly_chart(fig_1y_price)

        # Volume chart
        fig_1y_volume = go.Figure()
        fig_1y_volume.add_trace(go.Bar(x=data["1-Year Trend"].index, y=data["1-Year Trend"]['Volume'], name='Volume', marker_color='orange'))
        fig_1y_volume.update_layout(
        title="1-Year Volume",
        yaxis=dict(title="Volume"),
        xaxis=dict(title="Date")
        )
        st.plotly_chart(fig_1y_volume)

    # 1Y Chart Toggle
    if st.button(f"**SMA & EMA for {symbol}**"):
        st.session_state[f"{symbol}_sma_ema"] = not st.session_state[f"{symbol}_sma_ema"]

    if st.session_state[f"{symbol}_sma_ema"]:

        # Historical data analysis
        for symbol in selected_stocks:
            data = get_stock_data(symbol + ".NS")

            if "Error" not in data:
                # SMA and EMA Calculation
                hist_data = data["Historical Data"]
                sma = SMAIndicator(hist_data['Close'], window=20).sma_indicator()
                ema = EMAIndicator(hist_data['Close'], window=20).ema_indicator()

                st.write(f"**SMA & EMA for {symbol}**")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist_data.index, y=hist_data['Close'], mode='lines', name='Price'))
                fig.add_trace(go.Scatter(x=hist_data.index, y=sma, mode='lines', name='SMA (20)'))
                fig.add_trace(go.Scatter(x=hist_data.index, y=ema, mode='lines', name='EMA (20)'))
                fig.update_layout(title=f"{symbol} Price with SMA/EMA", xaxis=dict(title="Date"), yaxis=dict(title="Price"))
                st.plotly_chart(fig)

        # Real-time Notifications for Stock Price Changes
        notification_threshold = st.number_input(
            "Set Notification Threshold (%) for Price Change:", min_value=1, max_value=50, value=5, step=1
        )
        for symbol in selected_stocks:
            data = get_stock_data(symbol + ".NS")
            if "Error" not in data:
                current_price = data["Current Price"]
                gain = data["Gain from Low (%)"]
                drop = data["Drop from High (%)"]
                if gain > notification_threshold or abs(drop) > notification_threshold:
                    st.warning(f"{symbol} has significant price movement!")

        # Sector-based performance comparison
        sector_performance_data = [
            {"Stock": stock, "Current Price": get_stock_data1(stock + ".NS")}
            for stock in selected_stocks
        ]
        sector_df = pd.DataFrame(sector_performance_data)
        st.subheader("Sector-Based Performance Comparison")
        st.bar_chart(sector_df.set_index("Stock"))

    # Analytics and Statistics Toggle
    if st.button(f"Analytics and Statistics for {symbol}"):
        st.session_state[f"{symbol}_analytics_visible"] = not st.session_state[f"{symbol}_analytics_visible"]
        
    if st.session_state[f"{symbol}_analytics_visible"]:
        # Analytics and Statistics Code
        st.write("### Analyst Recommendations")
        st.write(data["Analyst Recommendations"])
        
        st.write("### Major Holders")
        st.write(data["Major Holders"])
                    
        st.write("### All Statistics")
        st.write(data["All Statistics"])

# Tab 2: Portfolio
with tab2:
    st.subheader("💼 Watchlist")
    # Ensure portfolio is loaded into session state on startup
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = load_portfolio()

     # Add stock to portfolio
    st.subheader("Add to Watchlist")
    symbol_input = st.selectbox("Select Stock to Add:", options=nifty_50_stocks + bank_nifty_stocks + fin_nifty_stocks + midcap_nifty_stocks + sensex_stocks)
    current_price = get_stock_data1(symbol_input)  # Ensure current price is float
    purchase_price_input = st.number_input(
    "Enter Purchase Price (₹):", min_value=0.01, value=current_price, step=0.01, format="%.2f"
    )

    if st.button("Add to Watchlist"):
        if purchase_price_input > 0:  # Validate price is reasonable
            st.session_state.portfolio[symbol_input] = {
                "purchase_price": purchase_price_input,
                "purchase_date": str(date.today()),
                "current_price": current_price,
            }
            save_portfolio(st.session_state.portfolio)
            st.success(f"{symbol_input} added to Watchlist.")
        else:
            st.error("Purchase price must be greater than 0.")

    # Display portfolio
    st.subheader("Your Watchlist")
    portfolio_data = []
    for symbol, data in st.session_state.portfolio.items():
        current_price = get_stock_data1(symbol)
        price_difference = current_price - data["purchase_price"]
        percentage_change = (price_difference / data["purchase_price"]) * 100
        portfolio_data.append([
            symbol, data["purchase_price"], current_price, f"{price_difference:.2f}", f"{percentage_change:.2f}%"
        ])

    portfolio_df = pd.DataFrame(portfolio_data, columns=["Stock", "Added Price", "Current Price", "Difference", "Change (%)"])
    st.write(portfolio_df)

    # Option to delete individual stocks
    stock_to_remove = st.selectbox("Select a stock to remove from watchlist:", options=list(st.session_state.portfolio.keys()))
    if st.button("Remove from Watchlist"):
        if stock_to_remove in st.session_state.portfolio:
            del st.session_state.portfolio[stock_to_remove]
            save_portfolio(st.session_state.portfolio)
            st.success(f"{stock_to_remove} removed from watchlist.")

    # Option to clear entire portfolio
    if st.button("Clear Watchlist"):
        st.session_state.portfolio = {}
        save_portfolio({})
        st.success("Watchlist cleared.")

with tab3:
    # News Section
    st.subheader("Stock News")

    news_stock_symbol = st.selectbox("Choose a stock symbol to view latest news:", options=nifty_50_stocks + bank_nifty_stocks + fin_nifty_stocks + midcap_nifty_stocks + sensex_stocks)

    if st.button("Fetch News"):
        news_articles = fetch_news(news_stock_symbol)
        if news_articles:
            for article in news_articles:
                st.write(f"**{article['title']}**")
                st.write(f"Published at: {article['publishedAt']}")
                st.write(article['description'])
                st.write(f"[Read more]({article['url']})")
        else:
            st.write("No news articles found.")

# Tab 4: Settings
with tab4:
    st.subheader("⚙️ Settings")
    st.session_state["refresh_interval"] = st.slider(
        "Set Refresh Interval (seconds):", 1, 60, st.session_state["refresh_interval"]
    )
    if st.button("Apply Settings"):
        st.rerun()

if refresh_enabled:
    time.sleep(refresh_interval)
    st.rerun()