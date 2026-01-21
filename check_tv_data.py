from data.gathering.tv_feed import TvFeed
from tvDatafeed import Interval
import pandas as pd

feed = TvFeed()
df = feed.get_historical_data("BANKNIFTY", exchange="NSE", interval=Interval.in_1_minute, n_bars=5)
if df is not None:
    print("DataFrame Head:")
    print(df)
    print("\nIndex Info:")
    print(df.index)
    print("\nFirst Index Item Type:", type(df.index[0]))
    print("Is naive?", df.index[0].tz is None)
else:
    print("Failed to fetch data")
