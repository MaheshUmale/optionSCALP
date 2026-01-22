from data.gathering.data_manager import DataManager
from tvDatafeed import Interval
from datetime import datetime
import pandas as pd

dm = DataManager()
idx_df = dm.get_data("BANKNIFTY", interval=Interval.in_1_minute, n_bars=5)
print("Index Tail:")
print(idx_df.tail())
print("Index info:")
print(idx_df.index)

def format_records_debug(df):
    recs = df.copy().reset_index()
    if recs['datetime'].dt.tz is None:
        print("Localizing naive IST")
        recs['datetime_localized'] = recs['datetime'].dt.tz_localize('Asia/Kolkata')
        recs['datetime_utc'] = recs['datetime_localized'].dt.tz_convert('UTC')
    else:
        print("Already localized")
        recs['datetime_utc'] = recs['datetime'].dt.tz_convert('UTC')

    recs['ts'] = recs['datetime_utc'].apply(lambda x: int(x.timestamp()))
    recs['ts_shifted'] = recs['ts'] + 19800

    for i, row in recs.iterrows():
        print(f"Orig: {row['datetime']} | UTC: {row['datetime_utc']} | TS: {row['ts']} | Shifted TS: {row['ts_shifted']} | Shifted as UTC: {datetime.utcfromtimestamp(row['ts_shifted'])}")

format_records_debug(idx_df)
