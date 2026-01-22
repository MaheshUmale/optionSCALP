import json
import logging
import threading
import time
from datetime import datetime
import upstox_client

logger = logging.getLogger(__name__)

class UpstoxLiveFeed:
    def __init__(self, access_token, callback):
        self.access_token = access_token
        self.callback = callback
        self.streamer = None
        self.instrument_keys = []
        self.key_to_symbol = {} # Mapping instrument_key -> display_symbol
        self.is_running = False

    def on_open(self):
        logger.info("[UpstoxLiveFeed] Connection opened.")
        if self.instrument_keys:
            self.streamer.subscribe(self.instrument_keys, "full")

    def on_error(self, error):
        logger.error(f"[UpstoxLiveFeed] Error: {error}")

    def on_close(self, close_status_code, close_msg):
        logger.info(f"[UpstoxLiveFeed] Connection closed: {close_status_code} - {close_msg}")

    def on_message(self, message):
        """
        Handles incoming market data messages.
        The message format from MarketDataStreamerV3 (full feed) is mapped here.
        """
        try:
            # message is already decoded by the SDK if using MarketDataStreamerV3
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            if data.get("type") == "live_feed":
                feeds = data.get("feeds", {})
                for key, feed in feeds.items():
                    full_feed = feed.get("fullFeed", {})
                    market_ff = full_feed.get("marketFF", {})

                    ltpc = market_ff.get("ltpc", {})
                    ltp = ltpc.get("ltp")
                    ltt = ltpc.get("ltt")

                    market_ohlc = market_ff.get("marketOHLC", {})
                    ohlc_list = market_ohlc.get("ohlc", [])

                    # Find 1-minute candle (interval 'I1')
                    i1_candle = next((c for c in ohlc_list if c.get("interval") == "I1"), None)

                    # volume from marketFF (vtt is volume traded today)
                    total_volume = market_ff.get("vtt")
                    if total_volume is not None:
                        total_volume = float(total_volume)

                    # Use feed timestamp for current tick time (more accurate for bucket alignment)
                    ts_ms = market_ff.get("ts") or ltt
                    if ts_ms:
                        ts = float(ts_ms) / 1000
                    else:
                        ts = datetime.now(timezone.utc).timestamp()

                    display_symbol = self.key_to_symbol.get(key, key)

                    update = {
                        "symbol": display_symbol,
                        "instrument_key": key,
                        "price": ltp,
                        "volume": total_volume,
                        "timestamp": ts,
                        "oi": market_ff.get("oi"),
                        "iv": market_ff.get("iv"),
                        "ohlc": i1_candle
                    }

                    if ltp is not None:
                        self.callback(update)

        except Exception as e:
            logger.error(f"[UpstoxLiveFeed] Error parsing message: {e}")

    def start(self):
        if self.is_running:
            return

        logger.info("[UpstoxLiveFeed] Starting streamer...")
        configuration = upstox_client.Configuration()
        configuration.access_token = self.access_token

        try:
            self.streamer = upstox_client.MarketDataStreamerV3(
                upstox_client.ApiClient(configuration)
            )

            self.streamer.on("open", self.on_open)
            self.streamer.on("message", self.on_message)
            self.streamer.on("error", self.on_error)
            self.streamer.on("close", self.on_close)

            self.streamer.auto_reconnect(True, 10, 5)
            self.streamer.connect()
            self.is_running = True
        except Exception as e:
            logger.error(f"[UpstoxLiveFeed] Failed to start streamer: {e}")

    def stop(self):
        self.is_running = False
        if self.streamer:
            try:
                self.streamer.disconnect()
            except:
                pass
            self.streamer = None

    def add_symbols(self, symbols_with_keys):
        """
        symbols_with_keys: list of dicts like {"symbol": "NSE:NIFTY", "key": "NSE_INDEX|Nifty 50"}
        """
        new_keys = []
        for item in symbols_with_keys:
            key = item["key"]
            sym = item["symbol"]
            self.key_to_symbol[key] = sym
            if key not in self.instrument_keys:
                self.instrument_keys.append(key)
                new_keys.append(key)

        if self.is_running and self.streamer and new_keys:
            try:
                self.streamer.subscribe(new_keys, "full")
            except Exception as e:
                logger.error(f"[UpstoxLiveFeed] Subscription error: {e}")
