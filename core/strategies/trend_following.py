class TrendFollowingStrategy:
    def __init__(self, symbol_type="BANKNIFTY"):
        self.symbol_type = symbol_type
        self.target_range = (30, 40) if "BANKNIFTY" in symbol_type else (15, 20)

    def get_trend(self, index_df):
        if index_df is None or index_df.empty: return None
        # Trend on 15m/1h
        last_close = index_df['close'].iloc[-1]
        sma = index_df['close'].rolling(20).mean().iloc[-1]
        return "BULLISH" if last_close > sma else "BEARISH"

    def check_setup(self, option_df, trend):
        """
        On Option Chart:
        - Trend is BULLISH (Index) -> Look at CALL option
        - Wait for Small Bearish Candle (Pullback)
        - Body > 70%, Range 30-40
        """
        if option_df is None or option_df.empty: return None

        last_candle = option_df.iloc[-1]
        is_bearish = last_candle['close'] < last_candle['open']
        candle_range = last_candle['high'] - last_candle['low']
        body_size = abs(last_candle['close'] - last_candle['open'])

        if is_bearish and self.target_range[0] <= candle_range <= self.target_range[1] + 5:
            if body_size >= 0.7 * candle_range:
                return {
                    "type": "ENTRY",
                    "entry_price": last_candle['high'] + 1,
                    "sl": last_candle['low']
                }
        return None
