import pandas as pd
import numpy as np

class TrendFollowingStrategy:
    def __init__(self, symbol_type="BANKNIFTY"):
        self.symbol_type = symbol_type
        self.update_params(symbol_type)

    def update_params(self, symbol_type):
        self.symbol_type = symbol_type
        self.target_range = (30, 40) if "BANKNIFTY" in symbol_type else (15, 20)

    def get_trend(self, index_df, pcr_insights=None):
        if index_df is None or len(index_df) < 20: return "NEUTRAL"

        # Primary Trend: Price vs 20 SMA
        last_close = index_df['close'].iloc[-1]
        sma = index_df['close'].rolling(20).mean().iloc[-1]

        if pd.isna(sma): return "NEUTRAL"

        price_trend = "BULLISH" if last_close > (sma + 2) else ("BEARISH" if last_close < (sma - 2) else "NEUTRAL")

        # Secondary Trend: PCR, PCR Change, and Buildup Status
        if pcr_insights and price_trend != "NEUTRAL":
            pcr = pcr_insights.get('pcr', 1.0)
            pcr_chg = pcr_insights.get('pcr_change', 1.0)
            buildup = pcr_insights.get('buildup_status', '').upper()

            is_bullish_buildup = 'LONG BUILD' in buildup or 'SHORT COVER' in buildup
            is_bearish_buildup = 'SHORT BUILD' in buildup or 'LONG UNWIND' in buildup

            if price_trend == "BULLISH":
                # Confirm Bullish: Need at least one sentiment indicator to be bullish or neutral
                if pcr >= 0.85 or pcr_chg >= 1.0 or is_bullish_buildup: return "BULLISH"
                else: return "NEUTRAL"
            else:
                # Confirm Bearish: Need at least one sentiment indicator to be bearish or neutral
                if pcr <= 1.15 or pcr_chg <= 1.0 or is_bearish_buildup: return "BEARISH"
                else: return "NEUTRAL"

        return price_trend

    def check_setup(self, option_df, trend, option_type):
        """
        On Option Chart:
        - Trend is BULLISH (Index) -> Look at CALL option (CE)
        - Trend is BEARISH (Index) -> Look at PUT option (PE)
        - Wait for Small Bearish Candle (Pullback)
        """
        if option_df is None or option_df.empty: return None
        if not trend or trend == "NEUTRAL": return None

        # Balanced Approach: Only trade CE on Bullish Trend and PE on Bearish Trend
        # Support both "C"/"P" and "CE"/"PE" formats
        is_ce = option_type in ["CE", "C"]
        is_pe = option_type in ["PE", "P"]

        if trend == "BULLISH" and not is_ce: return None
        if trend == "BEARISH" and not is_pe: return None

        last_candle = option_df.iloc[-1]
        # Entry candle must be bearish (pullback)
        is_bearish = last_candle['close'] < last_candle['open']
        candle_range = last_candle['high'] - last_candle['low']
        body_size = abs(last_candle['close'] - last_candle['open'])

        # Slightly more relaxed range to prevent bias if one side has higher volatility
        min_range = self.target_range[0] - 5
        max_range = self.target_range[1] + 10

        if is_bearish and min_range <= candle_range <= max_range:
            if body_size >= 0.6 * candle_range: # Relaxed body size from 70% to 60%
                return {
                    "type": f"{option_type}_ENTRY",
                    "entry_price": last_candle['high'] + 1,
                    "sl": last_candle['low']
                }
        return None
