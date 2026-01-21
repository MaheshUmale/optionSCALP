import streamlit as st
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
import plotly.graph_objects as go
from datetime import datetime
import time
import sqlite3

# --- INITIALIZE TVDATAFEED ---
tv = TvDatafeed()

# --- CONFIGURATION ---
DB_NAME = "trading_data.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS pcr_history 
                       (timestamp DATETIME, pcr REAL, pcr_change REAL)''')

def get_tv_data(symbol, exchange='NSE', interval=Interval.in_1_minute, n_bars=100):
    try:
        # TradingView usually expects 'NIFTY' or 'BANKNIFTY' directly for Indices
        # For Options, it follows 'INDEX' + 'YYMMDD' + 'STRIKE' + 'TYPE'
        df = tv.get_hist(symbol=symbol, exchange=exchange, interval=interval, n_bars=n_bars)
        return df
    except:
        return None

# --- UI SETUP ---
st.set_page_config(layout="wide", page_title="2026 Option Tracker")
init_db()

st.title("📈 Live Index & Option Charts (YYMMDD)")

# Sidebar for Market Selection
st.sidebar.header("Configuration")
index_ref = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY"])

# --- EXPIRY HANDLING (Using your 260127 format) ---
# List of 2026 Expiries provided in your earlier logic
all_expiries = ["260127", "260224", "260326", "260330", "260331"]
t_date = datetime.now()

# Applying your filter rule: datetime.strptime(e, "%y%m%d") >= t_date
valid_expiries = [e for e in all_expiries if datetime.strptime(e, "%y%m%d") >= t_date]

selected_expiry = st.sidebar.selectbox("Expiry (YYMMDD)", valid_expiries)

strike = st.sidebar.number_input("Strike Price", value=24500 if index_ref == "NIFTY" else 52000, step=50 if index_ref == "NIFTY" else 100)
opt_type = st.sidebar.radio("Option Type", ["C", "P"])

# SYMBOL CONSTRUCTION: e.g., NIFTY260127C24500 FOR  TRADINGVIEW ( NSE:(INDEX)(YYMMDD)(C/P)(STRIKE) = index + expiry + type + strike )
option_symbol = f"{index_ref}{selected_expiry}{opt_type}{int(strike)}"

# --- DASHBOARD LAYOUT ---
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"Index: {index_ref}")
    idx_chart = st.empty()

with col2:
    st.subheader(f"Option: {option_symbol}")
    opt_chart = st.empty()

# --- LIVE REFRESH LOOP ---
while True:
    # 1. Fetch & Plot Index
    idx_df = get_tv_data(index_ref)
    if idx_df is not None:
        fig_idx = go.Figure(data=[go.Candlestick(
            x=idx_df.index, open=idx_df['open'], high=idx_df['high'], 
            low=idx_df['low'], close=idx_df['close'], name=index_ref
        )])
        fig_idx.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False,
                             margin=dict(l=10, r=10, t=30, b=10))
        idx_chart.plotly_chart(fig_idx, use_container_width=True)

    # 2. Fetch & Plot Option
    opt_df = get_tv_data(option_symbol)
    if opt_df is not None:
        fig_opt = go.Figure(data=[go.Candlestick(
            x=opt_df.index, open=opt_df['open'], high=opt_df['high'], 
            low=opt_df['low'], close=opt_df['close'], name=option_symbol
        )])
        fig_opt.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False,
                             margin=dict(l=10, r=10, t=30, b=10))
        opt_chart.plotly_chart(fig_opt, use_container_width=True)
    else:
        opt_chart.error(f"Symbol {option_symbol} not found on NSE. Check if Strike/Expiry is active.")

    time.sleep(15)
    st.rerun()