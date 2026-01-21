import pandas as pd
import numpy as np

class OptionScalpStrategy:
    def __init__(self):
        self.sl_points = {"BANKNIFTY": 30, "NIFTY": 20}
        self.target_points = {"BANKNIFTY": 60, "NIFTY": 40}

    def get_trend(self, index_df):
        """Simple trend detection using EMAs or Price Action."""
        if index_df is None or len(index_df) < 20:
            return "NEUTRAL"

        ema20 = index_df['close'].ewm(span=20).mean().iloc[-1]
        current_price = index_df['close'].iloc[-1]

        if current_price > ema20:
            return "BULLISH"
        elif current_price < ema20:
            return "BEARISH"
        return "NEUTRAL"

    def check_setup(self, opt_df, trend, index_name="BANKNIFTY"):
        """
        Strategy 1: Price Action Pullback (User Specification)
        - Setup candle: Range 30-40 points (for Bank Nifty)
        - Solid body: Close near high (for CE) or near low (for PE)
        - SL: 30 pts (BN) / 20 pts (Nifty)
        """
        if opt_df is None or len(opt_df) < 1 or trend == "NEUTRAL":
            return None

        candle = opt_df.iloc[-1]
        c_range = candle['high'] - candle['low']
        body = abs(candle['close'] - candle['open'])

        # Range Filter (Adjusted for Index)
        target_range = 35 if "BANK" in index_name else 20
        range_match = (target_range - 10) <= c_range <= (target_range + 10)

        # Body Filter (Solid Body > 70% of range)
        solid_body = body > (c_range * 0.7)

        if range_match and solid_body:
            sl_val = self.sl_points.get(index_name, 30)
            return {
                "type": "BUY",
                "entry_price": candle['close'],
                "sl": candle['close'] - sl_val,
                "tp": candle['close'] + (sl_val * 2)
            }
        return None
