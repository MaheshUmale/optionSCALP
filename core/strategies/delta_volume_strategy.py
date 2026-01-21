import pandas as pd
import numpy as np

class DeltaVolumeStrategy:
    def __init__(self, symbol_type="BANKNIFTY"):
        self.symbol_type = symbol_type
        self.step = 100 if "BANK" in symbol_type else 50

    def update_params(self, symbol_type):
        self.symbol_type = symbol_type
        self.step = 100 if "BANK" in symbol_type else 50

    def calculate_net_delta_volume(self, strike_buildup_data, option_type):
        """
        Calculates Net Delta Volume for a single strike.
        Call Delta Volume: Aggressive Call Buying (Price Up)
        Put Delta Volume: Aggressive Put Buying (Price Up for Put Option)
        """
        if not strike_buildup_data or len(strike_buildup_data) == 0:
            return 0

        latest = strike_buildup_data[-1]
        price_change = latest.get('close', 0) - latest.get('open', 0)
        volume = latest.get('volume', 0)

        # For option buyers, we want price of the OPTION to be rising
        # regardless of whether it's a Call or a Put.
        # Net Delta from perspective of bullish/bearish underlying:
        # Call buying (Price Up) = Positive Delta
        # Put buying (Price Up) = Negative Delta (for underlying)

        delta_volume = volume * np.sign(price_change)
        if option_type.lower() == "put":
            return -delta_volume
        return delta_volume

    def identify_seller_behavior(self, strike_buildup_data, option_type):
        """
        Analyzes relationship between Net Delta Volume, Price, and OI.
        Scenario B: Sellers are 'Exiting' (Short Covering)
        - Price: Moving rapidly UP (for the OPTION)
        - OI: Decreasing
        - Net Delta: Massive spike in volume
        """
        if len(strike_buildup_data) < 2:
            return "UNKNOWN"

        latest = strike_buildup_data[-1]
        prev = strike_buildup_data[-2]

        # Short covering means option sellers are panicking and buying back,
        # so option price RISES and OI DECREASES.
        option_price_rising = latest['close'] > prev['close']
        oi_decreasing = latest['oi'] < prev['oi']

        volumes = [d['volume'] for d in strike_buildup_data[-10:]]
        avg_vol = np.mean(volumes[:-1]) if len(volumes) > 1 else volumes[0]
        volume_spike = latest['volume'] > (avg_vol * 2.0) # Increased threshold for "massive spike"

        if option_price_rising and oi_decreasing and volume_spike:
            return "SHORT_COVERING"

        if not option_price_rising and latest['oi'] > prev['oi']:
            return "SHORT_BUILDUP"

        return "NEUTRAL"

    def get_buy_signal(self, spot_price, call_strikes_data, put_strikes_data):
        """
        Aggregates data across ATM/OTM strikes to find opportunities.
        """
        atm_strike = round(spot_price / self.step) * self.step

        # Check Calls (ATM and OTM/ITM cluster)
        call_signals = []
        total_call_delta = 0
        for strike, data in call_strikes_data.items():
            total_call_delta += self.calculate_net_delta_volume(data, "call")
            behavior = self.identify_seller_behavior(data, "call")
            if behavior == "SHORT_COVERING":
                call_signals.append(strike)

        # Check Puts (ATM and OTM/ITM cluster)
        put_signals = []
        total_put_delta = 0
        for strike, data in put_strikes_data.items():
            total_put_delta += self.calculate_net_delta_volume(data, "put")
            behavior = self.identify_seller_behavior(data, "put")
            if behavior == "SHORT_COVERING":
                put_signals.append(strike)

        # Net Delta for the "Battleground"
        net_delta = total_call_delta + total_put_delta

        if call_signals and net_delta > 0:
            return {"type": "BULLISH", "strikes": call_signals, "net_delta": net_delta}
        elif put_signals and net_delta < 0:
            return {"type": "BEARISH", "strikes": put_signals, "net_delta": net_delta}

        return None
