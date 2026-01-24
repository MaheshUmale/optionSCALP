from pymongo import MongoClient
from datetime import datetime
import pandas as pd

class MongoDataManager:
    def __init__(self, host='localhost', port=27017, db_name='upstox_strategy_db'):
        self.client = MongoClient(host, port)
        self.db = self.client[db_name]
        self.collection = self.db['tick_data']

    def get_tick_data(self, instrument_key, start_time, end_time):
        query = {
            "instrumentKey": instrument_key,
            "_insertion_time": {
                "$gte": start_time,
                "$lte": end_time
            }
        }
        cursor = self.collection.find(query).sort("_insertion_time", 1)
        data = list(cursor)
        for item in data:
            if '_id' in item:
                del item['_id']
        return data

    def get_all_ticks_for_session(self, instrument_keys, date_str):
        # date_str in YYYY-MM-DD
        start_time = datetime.strptime(f"{date_str} 09:15:00", "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(f"{date_str} 15:30:00", "%Y-%m-%d %H:%M:%S")

        query = {
            "instrumentKey": {"$in": instrument_keys},
            "_insertion_time": {
                "$gte": start_time,
                "$lte": end_time
            }
        }
        cursor = self.collection.find(query).sort("_insertion_time", 1)
        # This could be large, maybe use a generator
        return cursor

    def get_oi_data_for_strikes(self, strikes_keys, current_time):
        # current_time is the _insertion_time to look around
        # Find latest OI for each strike before current_time
        pass
