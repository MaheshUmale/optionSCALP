import upstox_client
from upstox_client.rest import ApiException
import logging

logger = logging.getLogger(__name__)

class UpstoxClient:
    def __init__(self, access_token=None):
        self.api_client = None
        if access_token:
            self.configuration = upstox_client.Configuration()
            self.configuration.access_token = access_token
            self.api_client = upstox_client.ApiClient(self.configuration)
        else:
            logger.warning("[UpstoxClient] Not initialized due to missing access_token.")
     
    def get_historical_candle_data(self, instrument_key, interval, to_date, from_date):
        if not self.api_client: return None
        history_api = upstox_client.HistoryV3Api(self.api_client)

        if 'minute' in interval:
            unit = 'minutes'
            value = interval.replace('minute', '')
        elif 'm' in interval:
            unit = 'minutes'
            value = interval.replace('m', '')
        elif 'day' in interval:
            unit = 'day'
            value = '1'
        elif 'd' in interval:
            unit = 'day'
            value = interval.replace('d', '')
        else:
            unit = 'minutes'
            value = '1'

        try:
            return history_api.get_historical_candle_data1(
                instrument_key=instrument_key,
                unit=unit,
                interval=value,
                to_date=to_date,
                from_date=from_date
            )
        except Exception as e:
            logger.error(f"[UpstoxClient] API Error in get_historical_candle_data: {e}")
            return None

    def get_intra_day_candle_data(self, instrument_key, interval):
        if not self.api_client: return None
        history_api = upstox_client.HistoryV3Api(self.api_client)

        if 'minute' in interval:
            unit = 'minutes'
            value = interval.replace('minute', '')
        elif 'm' in interval:
            unit = 'minutes'
            value = interval.replace('m', '')
        else:
            unit = 'minutes'
            value = '1'

        try:
            return history_api.get_intra_day_candle_data(
                instrument_key=instrument_key,
                unit=unit,
                interval=value
            )
        except Exception as e:
            logger.error(f"[UpstoxClient] API Error in get_intra_day_candle_data: {e}")
            return None

    def get_market_data_feed_authorize(self):
        if not self.api_client: return None
        websocket_api = upstox_client.WebsocketApi(self.api_client)
        return websocket_api.get_market_data_feed_authorize(api_version='2.0')

    def get_put_call_option_chain(self, instrument_key, expiry_date):
        if not self.api_client: return None
        options_api = upstox_client.OptionsApi(self.api_client)
        try:
            return options_api.get_put_call_option_chain(
                instrument_key=instrument_key,
                expiry_date=expiry_date
            )
        except Exception as e:
            logger.error(f"[UpstoxClient] API Error in get_put_call_option_chain: {e}")
            return None

    def get_ltp(self, instrument_keys):
        if not self.api_client: return None
        try:
            api_instance = upstox_client.MarketQuoteV3Api(self.api_client)
            return api_instance.get_ltp(instrument_key=instrument_keys)
        except Exception as e:
            logger.error(f"[UpstoxClient] API Error in get_ltp: {e}")
            return None
