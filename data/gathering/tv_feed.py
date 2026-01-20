from tvDatafeed import TvDatafeed, Interval
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TvFeed:
    def __init__(self, username=None, password=None):
        try:
            if username and password:
                self.tv = TvDatafeed(username, password)
            else:
                self.tv = TvDatafeed()
            logger.info("TvDatafeed initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TvDatafeed: {e}")
            self.tv = None

    def get_historical_data(self, symbol, exchange="NSE", interval=Interval.in_5_minute, n_bars=5000, fut_contract=None):
        if not self.tv:
            logger.error("TvDatafeed not initialized")
            return None

        try:
            data = self.tv.get_hist(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                n_bars=n_bars,
                fut_contract=fut_contract
            )
            if data is not None and not data.empty:
                return pd.DataFrame(data)
            else:
                logger.warning(f"No data found for {symbol}")
                return None
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def get_nifty_data(self, interval=Interval.in_5_minute, n_bars=500):
        return self.get_historical_data("NIFTY", interval=interval, n_bars=n_bars)

    def get_banknifty_data(self, interval=Interval.in_5_minute, n_bars=500):
        return self.get_historical_data("BANKNIFTY", interval=interval, n_bars=n_bars)

    def get_option_data(self, symbol, interval=Interval.in_5_minute, n_bars=500):
        return self.get_historical_data(symbol, exchange="NSE", interval=interval, n_bars=n_bars)
