import pandas as pd
from data.gathering.tv_feed import TvFeed
from tvDatafeed import Interval
import math

class DataManager:
    def __init__(self):
        self.feed = TvFeed()

    def get_index_data(self, symbol="BANKNIFTY", interval=Interval.in_5_minute, n_bars=100):
        return self.feed.get_historical_data(symbol, exchange="NSE", interval=interval, n_bars=n_bars)

    def get_atm_strike(self, spot_price, step=100):
        return round(spot_price / step) * step

    def get_next_expiry(self, index="BANKNIFTY"):
        from datetime import datetime, timedelta
        # Current date in simulation is Jan 20, 2026
        today = datetime(2026, 1, 20)

        # Bank Nifty: Wednesday (weekday 2)
        # Nifty: Thursday (weekday 3)
        target_weekday = 2 if "BANKNIFTY" in index else 3

        days_ahead = target_weekday - today.weekday()
        if days_ahead < 0: # Target already passed this week
            days_ahead += 7

        expiry_date = today + timedelta(days_ahead)
        return expiry_date.strftime("%y%m%d")

    def get_option_symbol(self, index="BANKNIFTY", strike=58400, type="C", expiry=None):
        if expiry is None:
            expiry = self.get_next_expiry(index)
        # Format: BANKNIFTY260127C58400
        return f"{index}{expiry}{type}{strike}"

    def get_data(self, symbol, interval=Interval.in_5_minute, n_bars=100):
        df = self.feed.get_historical_data(symbol, exchange="NSE", interval=interval, n_bars=n_bars)
        if df is not None:
            # Fix gaps in time - reindex to remove empty spaces between market hours if needed
            # For plotting we often just use range index to avoid time gaps
            df = df.reset_index()
            if 'datetime' not in df.columns and 'index' in df.columns:
                df = df.rename(columns={'index': 'datetime'})
        return df
