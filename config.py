import os

# TradingView / TVDatafeed configuration
# For the rongardF fork of tvDatafeed
# No credentials needed for public data, but can be provided if you have a Pro account
TV_USERNAME = None
TV_PASSWORD = None

# NSE / Upstox Configuration
# Replace with your actual Upstox API credentials if using Upstox for live feed
API_KEY = 'YOUR_API_KEY'
SECRET_KEY = 'YOUR_SECRET_KEY'

ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI3NkFGMzUiLCJqdGkiOiI2OTc0ODZjZmI4YTNiNDI1ZWMyMTM1NTYiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2OTI0NDM2NywiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY5MjkyMDAwfQ.L8_lAp-yaVpRFGZHvxUj1kc0sR90LBU0tbOBNRHOdj0'

REDIRECT_URI = 'http://localhost:8000/callback'

# Database Configuration
DB_PATH = 'trading_data.db'

# Trading Settings
DEFAULT_QUANTITY = 1
MAX_TRADES_PER_DAY = 10
RISK_PER_TRADE = 20  # points
TARGET_PER_TRADE = 40 # points

# Market Hours (IST)
MARKET_START_TIME = '09:15'
MARKET_END_TIME = '15:30'
SQUARE_OFF_TIME = '15:20'
