import pandas as pd
import numpy as np
from data.gathering.tv_feed import TvFeed
from tvDatafeed import Interval
import math
from datetime import datetime, timezone, timedelta

class DataManager:
    def __init__(self):
        self.feed = TvFeed()

    def get_atm_strike(self, spot_price, step=100):
        return int(round(spot_price / step) * step)

    def get_next_expiry(self, index="BANKNIFTY", reference_date=None):
        """Returns the next valid expiry date in YYMMDD format."""
        if reference_date is None:
            reference_date = datetime.now()

        today_str = reference_date.strftime("%y%m%d")

        # Based on NSE 2026 Expiry Metadata
        if "BANKNIFTY" in index:
            expires = [
                "260127", "260224", "260326", "260330", "260331",
                "260630", "260929", "261229"
            ]
        else:
            expires = [
                "260106", "260113", "260120", "260127", "260203",
                "260210", "260217", "260224", "260326", "260330",
                "260331", "260625", "260630", "260929", "261229", "261231"
            ]

        for exp in expires:
            if exp >= today_str:
                return exp
        return expires[-1]

    def get_option_symbol(self, index, strike, opt_type, expiry=None, reference_date=None):
        if expiry is None:
            expiry = self.get_next_expiry(index, reference_date=reference_date)

        # Correct TradingView NSE Option Symbol format: (INDEX)(YYMMDD)(C/P)(STRIKE)
        # opt_type should be "C" or "P"
        type_code = opt_type[0].upper() # Handle "CE"->"C", "PE"->"P"

        sym = f"{index}{expiry}{type_code}{int(strike)}"
        print(f"Generated option symbol for TV: {sym}")
        return sym

    def get_data(self, symbol, interval=Interval.in_5_minute, n_bars=100, reference_date=None):
        df = None
        # Clean symbol if needed (e.g. remove NSE: prefix for inner searches)
        clean_sym = symbol.replace("NSE:", "")

        try:
            # We try fetching with NSE exchange explicitly
            df = self.feed.get_historical_data(clean_sym, exchange="NSE", interval=interval, n_bars=n_bars)
        except Exception as e:
            print(f"TvFeed fetch error for {clean_sym}: {e}")

        if df is None or df.empty:
            print(f"Error: Symbol {clean_sym} not found on TradingView. No data available.")
            return pd.DataFrame()

        return df
