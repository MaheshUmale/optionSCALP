import pandas as pd
import numpy as np

class TrendFollowingStrategy:
    def __init__(self, symbol_type="BANKNIFTY"):
        self.symbol_type = symbol_type
        self.pullback_range = (30, 40) if "BANKNIFTY" in symbol_type else (15, 20)

    def identify_trend(self, higher_tf_data):
        """
        Identify trend using 15m or 1h data.
        Returns 'BULLISH' or 'BEARISH'
        """
        if higher_tf_data is None or higher_tf_data.empty:
            return None

        # Simple trend identification: current price vs mean
        last_price = higher_tf_data['close'].iloc[-1]
        mean_price = higher_tf_data['close'].mean()

        if last_price > mean_price:
            return 'BULLISH'
        else:
            return 'BEARISH'

    def check_pullback_candle(self, candle):
        """
        Check if candle is a valid pullback candle:
        - Bearish for BULLISH trend (on Call option)
        - Small body, minimal wicks
        - Range within specific points
        """
        is_bearish = candle['close'] < candle['open']
        candle_range = candle['high'] - candle['low']
        body_size = abs(candle['close'] - candle['open'])
        wick_size = candle_range - body_size

        # Presenter nuance: Range 30-40, body > 70% of total range
        valid_range = self.pullback_range[0] <= candle_range <= self.pullback_range[1] + 10 # Adding some buffer
        solid_body = body_size >= (0.7 * candle_range)

        if is_bearish and valid_range and solid_body:
            return True
        return False

    def generate_signal(self, option_data, trend):
        """
        Scan for setup on 5m Options Chart
        """
        if option_data is None or len(option_data) < 1:
            return None

        last_candle = option_data.iloc[-1]

        if trend == 'BULLISH':
            if self.check_pullback_candle(last_candle):
                return {
                    'entry': last_candle['high'] + 1,
                    'sl': last_candle['low'],
                    'type': 'BUY_STOP'
                }
        # Similar logic for BEARISH trend on Put options (not fully implemented here for brevity)
        return None
