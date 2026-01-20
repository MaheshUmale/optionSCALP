import numpy as np
import pandas as pd
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
        # Based on user-provided NSE meta data for Jan 2026
        # Tuesday: 06, 13, 20, 27
        today_str = "260120"
        expires = ["260106", "260113", "260120", "260127", "260203"]
        for exp in expires:
            if exp >= today_str:
                return exp
        return expires[-1]

    def get_option_symbol(self, index="BANKNIFTY", strike=58400, type="C", expiry=None):
        if expiry is None:
            expiry = self.get_next_expiry(index)
        # Fix: Ensure correct symbol format for TV
        return f"{index}{expiry}{type}{int(strike)}"

    def get_data(self, symbol, interval=Interval.in_5_minute, n_bars=100):
        # Fallback to dummy data if TV feed fails for the simulation
        df = self.feed.get_historical_data(symbol, exchange="NSE", interval=interval, n_bars=n_bars)
        if df is None or df.empty:
            print(f"Warning: No live data for {symbol}, generating dummy data.")
            # Generate dummy OHLCV
            dates = pd.date_range(end=datetime.now(), periods=n_bars, freq='5min')
            data = {
                'open': np.random.uniform(300, 350, n_bars),
                'high': np.random.uniform(350, 400, n_bars),
                'low': np.random.uniform(250, 300, n_bars),
                'close': np.random.uniform(300, 350, n_bars),
                'volume': np.random.randint(1000, 5000, n_bars)
            }
            df = pd.DataFrame(data, index=dates)
            df.index.name = 'datetime'
        return df
