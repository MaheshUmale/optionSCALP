import sqlite3
import pandas as pd
import threading
from datetime import datetime
import json

class DatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path="optionscalp.db"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance.db_path = db_path
                cls._instance._init_db()
        return cls._instance

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL;')
            cursor = conn.cursor()

            # OHLCV Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ohlcv (
                    symbol TEXT,
                    interval TEXT,
                    timestamp INTEGER,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    PRIMARY KEY (symbol, interval, timestamp)
                )
            ''')

            # Trades Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    strategy_name TEXT,
                    trade_type TEXT,
                    entry_price REAL,
                    entry_time INTEGER,
                    exit_price REAL,
                    exit_time INTEGER,
                    sl REAL,
                    target REAL,
                    pnl REAL,
                    status TEXT,
                    exit_reason TEXT
                )
            ''')

            # PCR Insights Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pcr_insights (
                    symbol TEXT,
                    timestamp INTEGER,
                    pcr REAL,
                    pcr_change REAL,
                    buildup_status TEXT,
                    raw_data TEXT,
                    PRIMARY KEY (symbol, timestamp)
                )
            ''')

            # Historical PCR Data Table (5-min intervals)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pcr_data (
                    symbol TEXT,
                    timestamp INTEGER,
                    pcr REAL,
                    total_call_oi REAL,
                    total_put_oi REAL,
                    PRIMARY KEY (symbol, timestamp)
                )
            ''')

            conn.commit()

    def store_ohlcv(self, symbol, interval, df):
        if df is None or df.empty:
            return

        data = df.copy()
        if 'timestamp' not in data.columns:
            # Handle both index as datetime or a 'time' column
            if isinstance(data.index, pd.DatetimeIndex):
                data['timestamp'] = (data.index.view('int64') // 10**9).astype(int)
            elif 'time' in data.columns:
                data['timestamp'] = data['time']
            else:
                return

        with self._get_connection() as conn:
            for _, row in data.iterrows():
                conn.execute('''
                    INSERT OR REPLACE INTO ohlcv (symbol, interval, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, interval, int(row['timestamp']), row['open'], row['high'], row['low'], row['close'], row['volume']))
            conn.commit()

    def get_ohlcv(self, symbol, interval, start_ts=None, end_ts=None):
        query = "SELECT timestamp, open, high, low, close, volume FROM ohlcv WHERE symbol = ? AND interval = ?"
        params = [symbol, interval]

        if start_ts:
            query += " AND timestamp >= ?"
            params.append(start_ts)
        if end_ts:
            query += " AND timestamp <= ?"
            params.append(end_ts)

        query += " ORDER BY timestamp ASC"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                df.set_index('datetime', inplace=True)
            return df

    def store_trade(self, trade):
        with self._get_connection() as conn:
            if hasattr(trade, 'db_id') and trade.db_id:
                conn.execute('''
                    UPDATE trades SET
                        exit_price = ?, exit_time = ?, pnl = ?, status = ?, exit_reason = ?
                    WHERE id = ?
                ''', (trade.exit_price, trade.exit_time, trade.pnl, trade.status, trade.exit_reason, trade.db_id))
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trades (symbol, strategy_name, trade_type, entry_price, entry_time, sl, target, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade.symbol, trade.strategy_name, trade.trade_type, trade.entry_price, trade.entry_time, trade.sl, trade.target, trade.status))
                trade.db_id = cursor.lastrowid
            conn.commit()

    def store_pcr_insight(self, symbol, timestamp, insight, raw_list=None):
        if not insight: return
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO pcr_insights (symbol, timestamp, pcr, pcr_change, buildup_status, raw_data)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                timestamp,
                insight.get('pcr'),
                insight.get('pcr_change'),
                insight.get('buildup_status'),
                json.dumps(raw_list) if raw_list else None
            ))
            conn.commit()

    def get_trades(self, strategy_name=None):
        query = "SELECT * FROM trades"
        params = []
        if strategy_name:
            query += " WHERE strategy_name = ?"
            params.append(strategy_name)

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def store_pcr_history(self, symbol, timestamp, pcr, total_call_oi, total_put_oi):
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO pcr_data (symbol, timestamp, pcr, total_call_oi, total_put_oi)
                VALUES (?, ?, ?, ?, ?)
            ''', (symbol, timestamp, pcr, total_call_oi, total_put_oi))
            conn.commit()

    def get_pcr_history(self, symbol, start_ts=None, end_ts=None):
        query = "SELECT timestamp, pcr, total_call_oi, total_put_oi FROM pcr_data WHERE symbol = ?"
        params = [symbol]

        if start_ts:
            query += " AND timestamp >= ?"
            params.append(start_ts)
        if end_ts:
            query += " AND timestamp <= ?"
            params.append(end_ts)

        query += " ORDER BY timestamp ASC"

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)
