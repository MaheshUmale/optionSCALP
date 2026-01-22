from pymongo import MongoClient
import pandas as pd
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

class MongoDataManager:
    def __init__(self, uri='mongodb://localhost:27017/', db_name='upstox_strategy_db', collection_name='tick_data'):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def get_tick_data(self, instrument_key, date_str):
        """
        Fetches tick data for a specific instrument and date.
        date_str format: YYYY-MM-DD
        """
        start_date = datetime.strptime(date_str, "%Y-%m-%d")
        end_date = start_date + timedelta(days=1)

        query = {
            "instrumentKey": instrument_key,
            "_insertion_time": {
                "$gte": start_date,
                "$lt": end_date
            }
        }

        logger.info(f"Fetching ticks for {instrument_key} on {date_str}")
        cursor = self.collection.find(query).sort("_insertion_time", 1)

        ticks = []
        for doc in cursor:
            ff = doc.get('fullFeed', {})
            tick = None
            if 'marketFF' in ff:
                ltpc = ff['marketFF'].get('ltpc', {})
                tick = {
                    'time': int(ltpc.get('ltt', 0)) // 1000,
                    'price': float(ltpc.get('ltp', 0)),
                    'volume': float(ltpc.get('ltq', 0)),
                    'type': 'market'
                }
            elif 'indexFF' in ff:
                ltpc = ff['indexFF'].get('ltpc', {})
                tick = {
                    'time': int(ltpc.get('ltt', 0)) // 1000,
                    'price': float(ltpc.get('ltp', 0)),
                    'type': 'index'
                }

            if tick:
                ticks.append(tick)

        return pd.DataFrame(ticks)

    def get_available_keys(self, date_str):
        start_date = datetime.strptime(date_str, "%Y-%m-%d")
        end_date = start_date + timedelta(days=1)

        return self.collection.distinct("instrumentKey", {"_insertion_time": {"$gte": start_date, "$lt": end_date}})

    @staticmethod
    def ticks_to_candles(df):
        """Converts tick DataFrame to 1-minute OHLCV candles."""
        if df.empty: return pd.DataFrame()

        # Ensure we have a datetime index
        if 'datetime' not in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('datetime', inplace=True)

        resampled = df['price'].resample('1min').ohlc()
        if 'volume' in df.columns:
            resampled['volume'] = df['volume'].resample('1min').sum()
        else:
            resampled['volume'] = 0.0

        return resampled.dropna()

    @staticmethod
    def align_dataframes(dfs, frequency='1min'):
        """Aligns multiple DataFrames to a common time index."""
        if not dfs: return []

        # Filter out empty DFs
        valid_dfs = [df for df in dfs if not df.empty]
        if not valid_dfs: return dfs

        # Find common time range
        start = min(df.index.min() for df in valid_dfs)
        end = max(df.index.max() for df in valid_dfs)

        full_index = pd.date_range(start=start, end=end, freq=frequency)

        aligned_dfs = []
        for df in dfs:
            if df.empty:
                # Create empty DF with same columns and common index
                empty_df = pd.DataFrame(index=full_index, columns=df.columns if not df.empty else ['open', 'high', 'low', 'close', 'volume'])
                aligned_dfs.append(empty_df.fillna(method='ffill')) # Though empty won't have anything to ffill
            else:
                # Reindex and forward fill missing values
                aligned = df.reindex(full_index).ffill()
                aligned_dfs.append(aligned)

        return aligned_dfs
