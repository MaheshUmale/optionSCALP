import pandas as pd
from datetime import datetime, timedelta

class SymbolMapper:
    @staticmethod
    def get_atm_strike(spot_price, index="BANKNIFTY"):
        step = 100 if "BANK" in index else 50
        return int(round(spot_price / step) * step)

    @staticmethod
    def get_next_expiry(index="BANKNIFTY"):
        # Based on user-provided 2026 dates
        today = datetime(2026, 1, 20)
        if "BANKNIFTY" in index:
            # BANKNIFTY 2026 Expiries (Monthly/Long)
            expiries = [datetime(2026, 1, 27), datetime(2026, 2, 24)]
        else:
            # NIFTY 2026 Weekly Expiries
            expiries = [datetime(2026, 1, 20), datetime(2026, 1, 27)]

        for exp in expiries:
            if exp >= today:
                return exp.strftime("%y%m%d")
        return expiries[-1].strftime("%y%m%d")

    @staticmethod
    def get_option_symbol(index, spot_price, trend):
        strike = SymbolMapper.get_atm_strike(spot_price, index)
        expiry = SymbolMapper.get_next_expiry(index)
        opt_type = "C" if trend == "BULLISH" else "P"
        return f"{index}{expiry}{opt_type}{strike}"
