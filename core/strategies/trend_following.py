class TrendFollowingStrategy:
    def __init__(self, symbol_type="BANKNIFTY"):
        self.symbol_type = symbol_type
        self.update_params(symbol_type)

    def update_params(self, symbol_type):
        self.symbol_type = symbol_type
        self.target_range = (30, 40) if "BANKNIFTY" in symbol_type else (15, 20)

    def get_trend(self, index_df, pcr_insights=None):
        if index_df is None or index_df.empty: return None
        # Primary Trend: Price vs 20 SMA
        last_close = index_df['close'].iloc[-1]
        sma = index_df['close'].rolling(20).mean().iloc[-1]
        price_trend = "BULLISH" if last_close > sma else "BEARISH"

        # Secondary Trend: PCR, PCR Change, and Buildup Status
        # PCR > 1 is Bullish (Put writers active), PCR < 1 is Bearish (Call writers active)
        # PCR Change > 1 is Bullish, PCR Change < 1 is Bearish
        if pcr_insights:
            pcr = pcr_insights.get('pcr', 1.0)
            pcr_chg = pcr_insights.get('pcr_change', 1.0)
            buildup = pcr_insights.get('buildup_status', '').upper()

            is_bullish_buildup = 'LONG BUILD' in buildup or 'SHORT COVER' in buildup
            is_bearish_buildup = 'SHORT BUILD' in buildup or 'LONG UNWIND' in buildup

            # Weighted sentiment: PCR Change and Buildup are often more leading than static PCR
            if price_trend == "BULLISH":
                # Confirm Bullish: Need at least one sentiment indicator to be bullish
                if pcr > 0.9 or pcr_chg > 1.0 or is_bullish_buildup: return "BULLISH"
                else: return "NEUTRAL" # Conflicting data
            else:
                # Confirm Bearish: Need at least one sentiment indicator to be bearish
                if pcr < 1.1 or pcr_chg < 1.0 or is_bearish_buildup: return "BEARISH"
                else: return "NEUTRAL"

        return price_trend

    def check_setup(self, option_df, trend, option_type):
        """
        On Option Chart:
        - Trend is BULLISH (Index) -> Look at CALL option
        - Trend is BEARISH (Index) -> Look at PUT option
        - Wait for Small Bearish Candle (Pullback)
        - Body > 70%, Range 30-40
        """
        if option_df is None or option_df.empty: return None
        if trend == "NEUTRAL": return None

        # Balanced Approach: Only trade CE on Bullish Trend and PE on Bearish Trend
        if trend == "BULLISH" and option_type != "CE": return None
        if trend == "BEARISH" and option_type != "PE": return None

        last_candle = option_df.iloc[-1]
        is_bearish = last_candle['close'] < last_candle['open']
        candle_range = last_candle['high'] - last_candle['low']
        body_size = abs(last_candle['close'] - last_candle['open'])

        if is_bearish and self.target_range[0] <= candle_range <= self.target_range[1] + 5:
            if body_size >= 0.7 * candle_range:
                return {
                    "type": f"{option_type}_ENTRY",
                    "entry_price": last_candle['high'] + 1,
                    "sl": last_candle['low']
                }
        return None
