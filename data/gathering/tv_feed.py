import pandas as pd
from tvDatafeed import TvDatafeed, Interval
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TvFeed:
    def __init__(self):
        try:
            self.tv = TvDatafeed()
            logger.info("TvDatafeed initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TvDatafeed: {e}")
            self.tv = None

    def get_historical_data(self, symbol, exchange="NSE", interval=Interval.in_5_minute, n_bars=100):
        if not self.tv:
            return None
        try:
            data = self.tv.get_hist(symbol=symbol, exchange=exchange, interval=interval, n_bars=n_bars)
            if data is not None:
                df = pd.DataFrame(data)
                return df
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
        return None
