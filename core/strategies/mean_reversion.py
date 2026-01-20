import pandas as pd
import numpy as np

class MeanReversionStrategy:
    def __init__(self):
        pass

    def calculate_vwap(self, df):
        v = df['volume']
        p = (df['high'] + df['low'] + df['close']) / 3
        return (p * v).cumsum() / v.cumsum()

    def detect_delta_divergence(self, df):
        """
        Since we might not have real tick delta, we approximate:
        Delta proxy = (Close - Low) - (High - Close) weighted by volume
        """
        if df is None or df.empty:
            return None

        # Approximate Delta
        df['delta_proxy'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low']).replace(0, 1) * df['volume']

        last_candle = df.iloc[-1]

        # Trap: Red candle with positive delta
        is_red = last_candle['close'] < last_candle['open']
        is_positive_delta = last_candle['delta_proxy'] > 0

        if is_red and is_positive_delta:
            return 'BULLISH_REVERSAL_TRAP'

        return None

    def generate_signal(self, df):
        df = df.copy()
        df['vwap'] = self.calculate_vwap(df)

        trap = self.detect_delta_divergence(df)
        if trap == 'BULLISH_REVERSAL_TRAP':
            last_candle = df.iloc[-1]
            if last_candle['close'] < last_candle['vwap']: # Price below VWAP
                return {
                    'entry': last_candle['high'] + 1,
                    'target': last_candle['vwap'],
                    'sl': last_candle['low']
                }
        return None
