import pandas as pd
import numpy as np
from data.gathering.tv_feed import TvFeed
from data.database import DatabaseManager
from tvDatafeed import Interval
import math
from datetime import datetime, timezone, timedelta
import requests
import gzip
import io
import os
import json
import re
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST_TZ = timezone(timedelta(hours=5, minutes=30))

class DataManager:
    def __init__(self):
        self.feed = TvFeed()
        self.db = DatabaseManager()
        self._instrument_df = None
        self.upstox_client = None
        self.key_cache = {} # Cache for instrument mapping

    def set_upstox_client(self, client):
        self.upstox_client = client

    def get_atm_strike(self, spot_price, step=100):
        return int(round(spot_price / step) * step)

    def get_next_expiry(self, index="BANKNIFTY", reference_date=None):
        """Returns the next valid expiry date in YYMMDD format."""
        if reference_date is None:
            reference_date = datetime.now(IST_TZ)

        # Ensure we use the date as per IST
        today_str = reference_date.astimezone(IST_TZ).strftime("%y%m%d")

        # Based on NSE 2026 Expiry Metadata
        if "BANKNIFTY" in index:
            expires = [
                "260127", "260224", "260326", "260330", "260331",
                "260630", "260929", "261229"
            ]
        else:
            expires = [
                "260106", "260113", "260120", "260127", "260203",
                "260210", "260217", "260224", "260326", "260330",
                "260331", "260625", "260630", "260929", "261229", "261231"
            ]

        for exp in expires:
            if exp >= today_str:
                return exp
        return expires[-1]

    def get_option_symbol(self, index, strike, opt_type, expiry=None, reference_date=None):
        # Clean index symbol from any prefix
        clean_index = index.replace("NSE:", "").replace("INDEX:", "")

        if expiry is None:
            expiry = self.get_next_expiry(clean_index, reference_date=reference_date)

        # Correct TradingView NSE Option Symbol format: (INDEX)(YYMMDD)(C/P)(STRIKE)
        # opt_type should be "C" or "P"
        type_code = opt_type[0].upper() # Handle "CE"->"C", "PE"->"P"

        sym = f"{clean_index}{expiry}{type_code}{int(strike)}"
        print(f"Generated option symbol for TV: {sym}")
        return sym

    def get_upstox_instruments_df(self):
        if self._instrument_df is not None:
            return self._instrument_df
        
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
        try:
            response = requests.get(url, timeout=30)
            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
                self._instrument_df = pd.read_json(f)
            return self._instrument_df
        except Exception as e:
            print(f"Error downloading Upstox instruments: {e}")
            return pd.DataFrame()

    def getNiftyAndBNFnOKeys(self, symbols=["NIFTY", "BANKNIFTY"], spot_prices={"NIFTY": 0, "BANKNIFTY": 0}):
        """
        Implementation as per getNiftyAndBNFnOKeys API requirement.
        Fetches instrument keys for Spot, Future, and Options.
        """
        df = self.get_upstox_instruments_df()
        if df.empty: return {}

        # Hardcoded Future keys as specified by user
        KNOWN_FUTURES = {
            "NIFTY": "NSE_FO|49229",
            "BANKNIFTY": "NSE_FO|49224"
        }

        full_mapping = {}
        for symbol in symbols:
            spot = spot_prices.get(symbol)
            if not spot: continue
            
            # --- 1. Current Month Future ---
            current_fut_key = KNOWN_FUTURES.get(symbol)
            if not current_fut_key:
                fut_df = df[(df['name'] == symbol) & (df['instrument_type'] == 'FUT')].sort_values(by='expiry')
                if not fut_df.empty:
                    current_fut_key = fut_df.iloc[0]['instrument_key']

            current_fut_tsym = ""
            if current_fut_key:
                res_f = df[df['instrument_key'] == current_fut_key]
                if not res_f.empty:
                    current_fut_tsym = res_f.iloc[0]['trading_symbol']
                else:
                    current_fut_tsym = symbol + " FUT"

            # --- 2. Nearest Expiry Options ---
            opt_df = df[(df['name'] == symbol) & (df['instrument_type'].isin(['CE', 'PE']))].copy()
            if opt_df.empty: continue
            
            # Robust date parsing: handle both numeric and string
            # Upstox master often uses milliseconds (e.g. 1.7e12)
            try:
                num_exp = pd.to_numeric(opt_df['expiry'], errors='coerce')
                if not num_exp.isna().all() and num_exp.dropna().mean() > 1e11:
                    opt_df['expiry_dt'] = pd.to_datetime(num_exp, origin='unix', unit='ms', errors='coerce')
                else:
                    opt_df['expiry_dt'] = pd.to_datetime(opt_df['expiry'], errors='coerce')
            except:
                opt_df['expiry_dt'] = pd.to_datetime(opt_df['expiry'], errors='coerce')

            nearest_expiry = opt_df['expiry_dt'].min()
            near_opt_df = opt_df[opt_df['expiry_dt'] == nearest_expiry]

            # --- 3. Identify Strikes (ATM +/- 5) ---
            unique_strikes = sorted(near_opt_df['strike_price'].unique())
            atm_strike = min(unique_strikes, key=lambda x: abs(x - spot))
            atm_index = unique_strikes.index(atm_strike)
            
            start_idx = max(0, atm_index - 5)
            end_idx = min(len(unique_strikes), atm_index + 6)
            selected_strikes = unique_strikes[start_idx : end_idx]

            # --- 4. Build Result ---
            option_keys = []
            for strike in selected_strikes:
                ce_row = near_opt_df[(near_opt_df['strike_price'] == strike) & (near_opt_df['instrument_type'] == 'CE')]
                pe_row = near_opt_df[(near_opt_df['strike_price'] == strike) & (near_opt_df['instrument_type'] == 'PE')]
                
                if ce_row.empty or pe_row.empty: continue

                option_keys.append({
                    "strike": strike,
                    "ce": ce_row.iloc[0]['instrument_key'],
                    "ce_trading_symbol": ce_row.iloc[0]['trading_symbol'],
                    "pe": pe_row.iloc[0]['instrument_key'],
                    "pe_trading_symbol": pe_row.iloc[0]['trading_symbol']
                })

            full_mapping[symbol] = {
                "future": current_fut_key,
                "future_trading_symbol": current_fut_tsym,
                "expiry": nearest_expiry.strftime('%Y-%m-%d') if pd.notnull(nearest_expiry) else None,
                "options": option_keys,
                "all_keys": [current_fut_key] + [opt['ce'] for opt in option_keys] + [opt['pe'] for opt in option_keys]
            }

            # Populate Cache for consistent resolution
            if symbol == "NIFTY": self.key_cache["NSE:NIFTY"] = "NSE_INDEX|Nifty 50"
            elif symbol == "BANKNIFTY": self.key_cache["NSE:BANKNIFTY"] = "NSE_INDEX|Nifty Bank"

            if current_fut_key:
                self.key_cache[f"NSE:{current_fut_tsym}"] = current_fut_key

            for opt in option_keys:
                expiry_dt = pd.to_datetime(nearest_expiry)
                expiry_short = expiry_dt.strftime('%y%m%d')
                strike_int = int(opt['strike'])
                self.key_cache[f"NSE:{symbol}{expiry_short}C{strike_int}"] = opt['ce']
                self.key_cache[f"NSE:{symbol}{expiry_short}P{strike_int}"] = opt['pe']
                self.key_cache[f"NSE:{opt['ce_trading_symbol']}"] = opt['ce']
                self.key_cache[f"NSE:{opt['pe_trading_symbol']}"] = opt['pe']

        return full_mapping

    def get_upstox_key_for_tv_symbol(self, tv_symbol):
        """
        Maps a TradingView symbol or Upstox Trading Symbol to Upstox instrument key.
        """
        if tv_symbol in self.key_cache:
            return self.key_cache[tv_symbol]

        df = self.get_upstox_instruments_df()
        if df.empty: return None

        # Fixed Spot Keys as per user instruction
        if tv_symbol in ["NSE:NIFTY", "NIFTY"]: return "NSE_INDEX|Nifty 50"
        if tv_symbol in ["NSE:BANKNIFTY", "BANKNIFTY"]: return "NSE_INDEX|Nifty Bank"

        clean_sym = tv_symbol.replace("NSE:", "")

        # 1. Try matching against 'trading_symbol' directly (for Futures and Options)
        res = df[df['trading_symbol'] == clean_sym]
        if not res.empty:
            return res.iloc[0]['instrument_key']

        # 2. Try TV Option Symbol format parsing: (INDEX)(YYMMDD)(C/P)(STRIKE)
        match = re.match(r"([A-Z]+)(\d{6})([CP])(\d+)", clean_sym)
        if match:
            name, expiry_short, opt_type, strike = match.groups()
            strike = float(strike)
            upstox_type = 'CE' if opt_type == 'C' else 'PE'
            
            opt_df = df[(df['name'] == name) & 
                        (df['instrument_type'] == upstox_type) & 
                        (df['strike_price'] == strike)].copy()
            
            if not opt_df.empty:
                # Robust date parsing
                try:
                    num_exp = pd.to_numeric(opt_df['expiry'], errors='coerce')
                    if not num_exp.isna().all() and num_exp.dropna().mean() > 1e11:
                        opt_df['expiry_dt'] = pd.to_datetime(num_exp, origin='unix', unit='ms', errors='coerce')
                    else:
                        opt_df['expiry_dt'] = pd.to_datetime(opt_df['expiry'], errors='coerce')
                except:
                    opt_df['expiry_dt'] = pd.to_datetime(opt_df['expiry'], errors='coerce')
                
                # Convert to YYMMDD for matching
                opt_df['expiry_short'] = opt_df['expiry_dt'].dt.strftime('%y%m%d')
                res = opt_df[opt_df['expiry_short'] == expiry_short]
                
                if not res.empty:
                    return res.iloc[0]['instrument_key']

        return None

    def get_data(self, symbol, interval=Interval.in_5_minute, n_bars=100, reference_date=None):
        logger.info(f"DataManager.get_data called for {symbol} (n_bars={n_bars}, reference_date={reference_date})")
        # Clean symbol if needed (e.g. remove NSE: prefix for inner searches)
        # Handle multiple prefixes if they exist
        clean_sym = symbol
        while clean_sym.startswith("NSE:"):
            clean_sym = clean_sym[4:]

        int_str = str(interval)

        # 1. Try DB first
        df_db = self.db.get_ohlcv(clean_sym, int_str)
        if not df_db.empty and len(df_db) >= n_bars:
            logger.info(f"Returning {len(df_db)} bars from cache for {clean_sym}")
            df = df_db.tail(n_bars)
        else:
            df = None

            # 2. Try Upstox if enabled
            if self.upstox_client:
                try:
                    inst_key = self.get_upstox_key_for_tv_symbol(symbol)
                    if inst_key:
                        # Map TV interval to Upstox interval string
                        u_interval = "1m" if "1" in int_str else "5m"
                        logger.info(f"Attempting Upstox fetch for {clean_sym} ({inst_key})")
                        res = self.upstox_client.get_intra_day_candle_data(inst_key, u_interval)
                        if res and res.status == 'success' and res.data and res.data.candles:
                            # Upstox candles: [timestamp, open, high, low, close, volume, oi]
                            candles = res.data.candles
                            df_u = pd.DataFrame(candles, columns=['datetime', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                            df_u['datetime'] = pd.to_datetime(df_u['datetime'])
                            df_u.set_index('datetime', inplace=True)
                            df_u = df_u.sort_index()
                            df = df_u
                            print(f"Successfully fetched {len(df)} bars from Upstox")
                except Exception as e:
                    print(f"Upstox fetch error for {clean_sym}: {e}")

            # 3. Fallback to TvFeed
            if df is None or df.empty:
                print(f"Falling back to TvFeed for {clean_sym}")
                df = self.feed.get_historical_data(
                    symbol=clean_sym,
                    exchange="NSE",
                    interval=interval,
                    n_bars=n_bars
                )
            
            if df is not None and not df.empty:
                print(f"Successfully fetched {len(df)} bars for {clean_sym} from TvFeed")
                # Standardize index to UTC
                if df.index.tz is None:
                    df.index = df.index.tz_localize('Asia/Kolkata').tz_convert('UTC')
                else:
                    df.index = df.index.tz_convert('UTC')

                # Store in DB
                self.db.store_ohlcv(clean_sym, int_str, df)
        
        # CRITICAL FIX: Filter by reference_date if provided
        # For replay purposes, we want data UP TO the reference_date (not after it)
        if df is not None and not df.empty and reference_date is not None:
            # Convert reference_date to UTC for comparison
            if hasattr(reference_date, 'tzinfo') and reference_date.tzinfo is not None:
                ref_date_utc = reference_date.astimezone(timezone.utc)
            else:
                # Assume IST if naive
                ref_date_utc = reference_date.replace(tzinfo=IST_TZ).astimezone(timezone.utc)
            
            # Filter to only include data UP TO reference_date (inclusive of that day)
            # Add end of day to include all of reference_date's data
            end_of_ref_day = ref_date_utc.replace(hour=23, minute=59, second=59)
            df_filtered = df[df.index <= end_of_ref_day]
            
            if not df_filtered.empty:
                # Return the last n_bars from the filtered dataset
                df = df_filtered.tail(n_bars)
                logger.info(f"Filtered to {len(df)} bars up to {reference_date.date()}")
            else:
                logger.warning(f"No data found for {symbol} on or before {reference_date.date()}")
        
        if df is None or df.empty:
            print(f"Error: No data available for {symbol}")
            return pd.DataFrame()
        
        return df

        print(f"Error: Symbol {clean_sym} not found on TradingView. No data available.")
        return pd.DataFrame()