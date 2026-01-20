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

    def get_option_symbol(self, index="BANKNIFTY", strike=58400, type="C", expiry="260127"):
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
