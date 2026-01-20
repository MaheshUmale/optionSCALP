import os
import pandas as pd
from data.gathering.tv_feed import TvFeed
from tvDatafeed import Interval

class DataManager:
    def __init__(self, data_dir="data_cache"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self.feed = TvFeed()

    def fetch_and_save(self, symbol, exchange="NSE", interval=Interval.in_5_minute, n_bars=1000):
        data = self.feed.get_historical_data(symbol, exchange, interval, n_bars)
        if data is not None:
            filename = f"{symbol}_{interval}.csv".replace(":", "_")
            filepath = os.path.join(self.data_dir, filename)
            data.to_csv(filepath)
            return data
        return None

    def load_data(self, symbol, interval=Interval.in_5_minute):
        filename = f"{symbol}_{interval}.csv".replace(":", "_")
        filepath = os.path.join(self.data_dir, filename)
        if os.path.exists(filepath):
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            return df
        return None

    def get_data(self, symbol, exchange="NSE", interval=Interval.in_5_minute, n_bars=1000, force_refresh=False):
        if not force_refresh:
            data = self.load_data(symbol, interval)
            if data is not None:
                return data

        return self.fetch_and_save(symbol, exchange, interval, n_bars)
