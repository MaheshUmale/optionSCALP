import upstox_client
from upstox_client.rest import ApiException

class UpstoxClient:
    def __init__(self, access_token=None):
          
        if access_token:
            self.configuration = upstox_client.Configuration()
            self.configuration.access_token = access_token
            self.api_client = upstox_client.ApiClient(self.configuration)
        else:
            print("[UpstoxClient] Not initialized due to missing 'upstox_access_token' in config.json.")
     
    def get_historical_candle_data(self, instrument_key, interval, to_date, from_date):
        if not self.api_client: return None
        history_api = upstox_client.HistoryV3Api(self.api_client)

        # More robust interval mapping
        # If interval is already '1minute', '5minute' etc (from DataManager mapping)
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
            print(f"[UpstoxClient] API Error in get_historical_candle_data: {e}")
            return None

    def get_intra_day_candle_data(self, instrument_key, interval):
        if not self.api_client: return None
        import upstox_client as upstox_sdk
        history_api = upstox_sdk.HistoryV3Api(self.api_client)

        if 'minute' in interval:
            unit = 'minutes'
            value = interval.replace('minute', '')
        elif 'm' in interval:
            unit = 'minutes'
            value = interval.replace('m', '')
        else: # Default to 1 minute for intraday
            unit = 'minutes'
            value = '1'

        try:
            return history_api.get_intra_day_candle_data(
                instrument_key=instrument_key,
                unit=unit,
                interval=value
            )
        except Exception as e:
            print(f"[UpstoxClient] API Error in get_intra_day_candle_data: {e}")
            return None

    def get_market_data_feed_authorize(self):
        if not self.api_client: return None
        websocket_api = upstox_client.WebsocketApi(self.api_client)
        return websocket_api.get_market_data_feed_authorize(api_version='2.0')

    def get_put_call_option_chain(self, instrument_key, expiry_date):
        if not self.api_client: return None
        options_api = upstox_client.OptionsApi(self.api_client)
        return options_api.get_put_call_option_chain(
            instrument_key=instrument_key,
            expiry_date=expiry_date
        )

    def get_ltp(self, instrument_keys):
        """
        Fetches the last traded price for one or more instrument keys.
        instrument_keys can be a single string or a comma-separated string of keys.
        """
        if not self.api_client: return None
        import upstox_client as upstox_sdk
        try:
            api_instance = upstox_sdk.MarketQuoteV3Api(self.api_client)
            return api_instance.get_ltp(instrument_key=instrument_keys)
        except Exception as e:
            print(f"[UpstoxClient] API Error in get_ltp: {e}")
            return None
 
    """
    Fetches Upstox instrument keys for given symbols (e.g. NIFTY, BANKNIFTY)
    and generates option instrument keys for ATM +/- 5 strikes.
    """
    if not UPSTOX_AVAILABLE:
        print("Upstox client library not available.")
        return {}

    configuration = upstox_client.Configuration()
    configuration.access_token = config.ACCESS_TOKEN
    apiInstance = upstox_client.InstrumentsV3Api(upstox_client.ApiClient(configuration))

    full_mapping = {}

    for symbol in symbols:
        try:
            response = apiInstance.get_instruments(instrument_type="FUTURE", exchange="NSE_FO", symbol=symbol)
        except ApiException as e:
            print(f"Exception when calling InstrumentsV3Api->get_instruments for {symbol}: {e}")
            continue

        # Find nearest expiry future
        futures = response.data
        if not futures:
            print(f"No futures found for symbol: {symbol}")
            continue

        nearest_expiry = min(futures, key=lambda x: x.expiry_date).expiry_date
        current_fut = next((fut for fut in futures if fut.expiry_date == nearest_expiry), None)
        if not current_fut:
            print(f"No future found for nearest expiry of {symbol}")
            continue

        current_fut_key = current_fut.instrument_key

        # Fetch options for the same expiry
        try:
            opt_response = apiInstance.get_instruments(instrument_type="OPTION", exchange="NSE_FO", symbol=symbol)
        except ApiException as e:
            print(f"Exception when calling InstrumentsV3Api->get_instruments for options of {symbol}: {e}")
            continue

        options = [opt for opt in opt_response.data if opt.expiry_date == nearest_expiry]
        if not options:
            print(f"No options found for nearest expiry of {symbol}")
            continue

        # Determine ATM strike
        spot_price = current_spots.get(symbol, 0)
        if spot_price == 0:
            print(f"Spot price not available for {symbol}")
            continue

        atm_strike = int(round(spot_price / 100) * 100)

        # Select strikes: ATM +/- 5 strikes (100 point intervals)
        selected_strikes = [atm_strike + i * 100 for i in range(-5, 6)]