import os

# TradingView / TVDatafeed configuration
# For the rongardF fork of tvDatafeed
# No credentials needed for public data, but can be provided if you have a Pro account
TV_USERNAME = None
TV_PASSWORD = None

# NSE / Upstox Configuration
# Replace with your actual Upstox API credentials if using Upstox for live feed
API_KEY = "YOUR_API_KEY"
SECRET_KEY = "YOUR_SECRET_KEY"
# ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI3NkFGMzUiLCJqdGkiOiI2OTcxYTc1OTY3NWI3ZTQ1YzhiZmI2MTMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2OTA1NjA4OSwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY5MTE5MjAwfQ.zaELj1DnYOlSSXhe263H2grl70smKGTCFup2XV5Nc5M"
ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI3NkFGMzUiLCJqdGkiOiI2OTcyZTczMmJkNDA4NDUyZWJkZDU4NjMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2OTEzNzk3MCwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY5MjA1NjAwfQ.yP3z3h1zRnN-XjOygFBrDIu7ApAB3xyYND5SpsmOntE' 

REDIRECT_URI = "http://localhost:8000/callback"

# Database Configuration
DB_PATH = "optionscalp.db"

# Trading Settings
DEFAULT_QUANTITY = 1
MAX_TRADES_PER_DAY = 10
RISK_PER_TRADE = 20  # points
TARGET_PER_TRADE = 40 # points

# Market Hours (IST)
MARKET_START_TIME = "09:15"
MARKET_END_TIME = "15:30"
SQUARE_OFF_TIME = "15:20"
