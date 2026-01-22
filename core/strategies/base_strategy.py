import pandas as pd
import pandas_ta as ta

class BaseStrategy:
    def __init__(self, name, symbol_type="BANKNIFTY", is_index_driven=False):
        self.name = name
        self.symbol_type = symbol_type
        self.is_index_driven = is_index_driven
        self.vars = {} # Dictionary to store strategy-specific persistent variables

    def update_params(self, symbol_type):
        self.symbol_type = symbol_type

    def get_indicators(self, df):
        """Calculate necessary indicators for the strategy."""
        return df

    def check_setup(self, df, pcr_insights=None):
        """
        Check for entry setup.
        Returns: dict with entry info if setup is met, else None.
        """
        return None

    def reset_vars(self):
        self.vars = {}
