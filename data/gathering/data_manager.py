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

    def get_next_expiry(self, index="BANKNIFTY"):
        # For LIVE mode, we should use the actual current date
        # But for development consistency as per memory, we might want to keep it.
        # However, "today_str" should probably be dynamic for true live mode.
        today_str = datetime.now().strftime("%y%m%d")
        if "BANKNIFTY" in index:
            expires = ["260127", "260224", "260326", "260330", "260331", "260630", "260929", "261229"]
        else:
            expires = ["260106", "260113", "260120", "260127", "260203", "260210", "260217", "260224", "260326", "260330", "260331"]
        for exp in expires:
            if exp >= today_str:
                return exp
        return expires[-1]

    def get_option_symbol(self, index, strike, opt_type, expiry=None):
        if expiry is None:
            expiry = self.get_next_expiry(index)

        # Try to match the exact format expected by TradingView for NSE options
        # Often it is SYMBOL + YY + MMM (short month) + DD + C/P + STRIKE
        # But based on your first prompt: BANKNIFTY260127C58400
        # Let's stick to SYMBOL + YY + MM + DD + C/P + STRIKE

        sym = f"{index}{expiry}{opt_type}{int(strike)}"
        return sym

    def get_data(self, symbol, interval=Interval.in_5_minute, n_bars=100):
        df = None
        # Clean symbol if needed (e.g. remove NSE: prefix for inner searches)
        clean_sym = symbol.replace("NSE:", "")

        try:
            # We try fetching with NSE exchange explicitly
            df = self.feed.get_historical_data(clean_sym, exchange="NSE", interval=interval, n_bars=n_bars)
        except Exception as e:
            print(f"TvFeed fetch error for {clean_sym}: {e}")

        if df is None or df.empty:
            print(f"Warning: Symbol {clean_sym} not found on TradingView. Falling back to simulated data for logic verification.")
            # High-fidelity mock data generator for trading logic testing
            is_option = "C" in clean_sym or "P" in clean_sym
            start_price = 300 if is_option else (59000 if "BANK" in clean_sym else 25000)

            freq = '1min' if interval == Interval.in_1_minute else '5min'
            # Use UTC for mock data as well to be consistent
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            dates = pd.date_range(end=now_utc, periods=n_bars, freq=freq)

            # Create a more realistic price movement
            volatility = 2.0 if is_option else 15.0
            changes = np.random.normal(0, volatility, n_bars)
            prices = np.cumsum(changes) + start_price

            data = {
                'open': prices,
                'high': prices + np.abs(np.random.normal(5, 2, n_bars)),
                'low': prices - np.abs(np.random.normal(5, 2, n_bars)),
                'close': prices + np.random.normal(0, 2, n_bars),
                'volume': np.random.randint(5000, 50000, n_bars)
            }
            df = pd.DataFrame(data, index=dates)
            df.index.name = 'datetime'
            # Add required columns if missing
            df['symbol'] = f"SIM:{clean_sym}"

        return df
