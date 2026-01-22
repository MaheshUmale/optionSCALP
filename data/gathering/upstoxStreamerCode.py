import upstox_client
import time


def main():
    configuration = upstox_client.Configuration()
    access_token = <ACCESS_TOKEN>
    configuration.access_token = access_token

    streamer = upstox_client.MarketDataStreamerV3(
        upstox_client.ApiClient(configuration))

    def on_open():
        streamer.subscribe(
            ["NSE_EQ|INE020B01018"], "full")

    # Handle incoming market data messages\
    def on_message(message):
        print(message)

    streamer.on("open", on_open)
    streamer.on("message", on_message)
    
    # Modify auto-reconnect parameters: enable it, set interval to 10 seconds, and retry count to 3
    streamer.auto_reconnect(True, 10, 3)

    streamer.connect()

    time.sleep(5)
    streamer.subscribe(
        ["NSE_EQ|INE467B01029"], "full")


if __name__ == "__main__":
    main()

