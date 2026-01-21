import json
import random
import re
import string
import threading
import asyncio
from datetime import datetime
from websocket import create_connection
import logging

logger = logging.getLogger(__name__)

class TradingViewLiveFeed:
    def __init__(self, callback):
        self.callback = callback
        self.ws = None
        self.session = self.generate_session()
        self.symbols = []
        self.is_running = False
        self.thread = None

    def generate_session(self):
        string_length = 12
        letters = string.ascii_lowercase
        random_string = "".join(random.choice(letters) for _ in range(string_length))
        return "qs_" + random_string

    def prepend_header(self, content):
        return f"~m~{len(content)}~m~{content}"

    def construct_message(self, func, param_list):
        return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

    def create_message(self, func, param_list):
        return self.prepend_header(self.construct_message(func, param_list))

    def send_message(self, func, args):
        if self.ws:
            self.ws.send(self.create_message(func, args))

    def send_ping_packet(self, result):
        ping_str = re.findall(".......(.*)", result)
        if ping_str:
            ping_str = ping_str[0]
            self.ws.send(f"~m~{len(ping_str)}~m~{ping_str}")

    def connect(self):
        trading_view_socket = "wss://data.tradingview.com/socket.io/websocket"
        headers = json.dumps({"Origin": "https://data.tradingview.com"})
        self.ws = create_connection(trading_view_socket, headers=headers)

        self.send_message("quote_create_session", [self.session])
        self.send_message(
            "quote_set_fields",
            [
                self.session,
                "lp",
                "volume",
                "ch",
                "chp",
            ],
        )

    def add_symbols(self, symbols):
        for sym in symbols:
            if sym not in self.symbols:
                self.symbols.append(sym)
                self.send_message("quote_add_symbols", [self.session, sym])

    def start(self):
        self.is_running = True
        self.connect()
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.ws:
            self.ws.close()

    def _run(self):
        while self.is_running:
            try:
                result = self.ws.recv()
                if "quote_completed" in result or "session_id" in result:
                    continue

                # Split messages if multiple are received in one packet
                messages = re.split(r'~m~\d+~m~', result)
                for msg in messages:
                    if not msg: continue

                    try:
                        json_res = json.loads(msg)
                        if json_res["m"] == "qsd":
                            prefix = json_res["p"][1]
                            symbol = prefix["n"]
                            v = prefix.get("v", {})

                            update = {
                                "symbol": symbol,
                                "price": v.get("lp"),
                                "volume": v.get("volume"),
                                "change": v.get("ch"),
                                "change_percentage": v.get("chp"),
                                "timestamp": datetime.now().timestamp()
                            }
                            # Only call callback if price is present (not all updates have all fields)
                            if update["price"] is not None:
                                self.callback(update)
                    except json.JSONDecodeError:
                        # Might be a ping or other message
                        if "~m~" not in msg:
                            self.send_ping_packet(result)
            except Exception as e:
                if self.is_running:
                    logger.error(f"LiveFeed Error: {e}")
                    # Attempt reconnect
                    try:
                        self.connect()
                        for sym in self.symbols:
                            self.send_message("quote_add_symbols", [self.session, sym])
                    except:
                        pass
                else:
                    break
