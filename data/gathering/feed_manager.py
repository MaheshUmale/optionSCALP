import logging
import asyncio
from data.gathering.live_feed import TradingViewLiveFeed
from data.gathering.upstox_feed import UpstoxLiveFeed
import config

logger = logging.getLogger(__name__)

class FeedManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FeedManager, cls).__new__(cls)
            cls._instance.upstox_feed = None
            cls._instance.tv_feed = None
            cls._instance.subscribers = [] # list of (callback, state_filter)
        return cls._instance

    def get_upstox_feed(self, access_token):
        if self.upstox_feed is None:
            logger.info("Initializing Global Upstox Live Feed")
            self.upstox_feed = UpstoxLiveFeed(access_token, self._broadcast)
            self.upstox_feed.start()
        return self.upstox_feed

    def get_tv_feed(self):
        if self.tv_feed is None:
            logger.info("Initializing Global TradingView Live Feed")
            self.tv_feed = TradingViewLiveFeed(self._broadcast)
            self.tv_feed.start()
        return self.tv_feed

    def subscribe(self, callback):
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            logger.info(f"New subscriber added. Total: {len(self.subscribers)}")

    def unsubscribe(self, callback):
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"Subscriber removed. Total: {len(self.subscribers)}")

    def _broadcast(self, update):
        # We need to be careful with async here.
        # The feeds might be calling this from a background thread.
        for cb in self.subscribers:
            try:
                cb(update)
            except Exception as e:
                logger.error(f"Error in broadcast to subscriber: {e}")

feed_manager = FeedManager()
