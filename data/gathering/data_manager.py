import pandas as pd
import numpy as np
from data.gathering.tv_feed import TvFeed
from tvDatafeed import Interval
import math
from datetime import datetime

class DataManager:
    def __init__(self):
        self.feed = TvFeed()

    def get_atm_strike(self, spot_price, step=100):
        return round(spot_price / step) * step

    def get_next_expiry(self, index="BANKNIFTY"):
        # Fixed simulation date
        today_str = "260120"

        if "BANKNIFTY" in index:
            # User response for BANKNIFTY 2026
            expires = ["260127", "260224", "260326", "260330", "260331", "260630", "260929", "261229"]
        else:
            # User response for NIFTY 2026
            expires = ["260106", "260113", "260120", "260127", "260203", "260210", "260217", "260224", "260326", "260330", "260331"]

        for exp in expires:
            if exp >= today_str:
                return exp
        return expires[-1]

    def get_option_symbol(self, index="BANKNIFTY", strike=58400, type="C", expiry=None):
        if expiry is None:
            expiry = self.get_next_expiry(index)
        # Ensure strike is an integer for TradingView symbol
        return f"{index}{expiry}{type}{int(strike)}"

    def get_data(self, symbol, interval=Interval.in_5_minute, n_bars=100):
        df = None
        try:
            df = self.feed.get_historical_data(symbol, exchange="NSE", interval=interval, n_bars=n_bars)
        except Exception as e:
            print(f"TvFeed error for {symbol}: {e}")

        if df is None or df.empty:
            print(f"Warning: No live data for {symbol}, generating high-quality mock data.")
            # Realistic mock data for UI and Replay demonstration
            start_price = 50000 if "NIFTY" in symbol else 300
            if "BANKNIFTY" in symbol and "P" not in symbol and "C" not in symbol:
                start_price = 59000

            dates = pd.date_range(end=datetime.now(), periods=n_bars, freq='5min')
            # Use random walk for price
            prices = np.cumsum(np.random.normal(0, 15, n_bars)) + start_price
            data = {
                'open': prices - np.random.uniform(0, 5, n_bars),
                'high': prices + np.random.uniform(5, 15, n_bars),
                'low': prices - np.random.uniform(5, 15, n_bars),
                'close': prices + np.random.uniform(0, 5, n_bars),
                'volume': np.random.randint(10000, 50000, n_bars)
            }
            df = pd.DataFrame(data, index=dates)
            df.index.name = 'datetime'
        return df
