from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketState
import pandas as pd
import uvicorn
import json
import asyncio
import numpy as np
import logging
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from data.gathering.data_manager import DataManager
from data.gathering.feed_manager import feed_manager
from data.gathering.upstoxAPIAccess import UpstoxClient
import config
from data.database import DatabaseManager
from core.strategies.trend_following import TrendFollowingStrategy
from core.strategies.master_strategies import STRATEGIES
from core.strategies.delta_volume_strategy import DeltaVolumeStrategy
from core.trade_manager import Trade, PnLTracker

IST_TZ = timezone(timedelta(hours=5, minutes=30))
delta_strategy = DeltaVolumeStrategy()
from trendlyne_client import TrendlyneClient
from trendlyneAdvClient import TrendlyneScalper
from tvDatafeed import Interval
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    use_upstox = hasattr(config, 'ACCESS_TOKEN') and config.ACCESS_TOKEN != "YOUR_ACCESS_TOKEN"
    if use_upstox:
        logger.info("Pre-starting Upstox feed at startup")
        feed_manager.get_upstox_feed(config.ACCESS_TOKEN)
        dm.set_upstox_client(UpstoxClient(config.ACCESS_TOKEN))
    else:
        logger.info("Pre-starting TradingView feed at startup")
        feed_manager.get_tv_feed()
    yield
    # Shutdown logic
    if feed_manager.upstox_feed:
        feed_manager.upstox_feed.stop()
    if feed_manager.tv_feed:
        feed_manager.tv_feed.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

dm = DataManager()
db = DatabaseManager()
tl_client = TrendlyneClient()
tl_adv = TrendlyneScalper()

class SessionState:
    def __init__(self):
        # Segregate strategy instances by symbol category to prevent variable collision
        self.strategies = {
            "CE": [s() for s in STRATEGIES],
            "PE": [s() for s in STRATEGIES],
            "INDEX": [s() for s in STRATEGIES]
        }
        self.tf_strategies = {
            "CE": TrendFollowingStrategy(),
            "PE": TrendFollowingStrategy()
        }
        self.tf_main = TrendFollowingStrategy() # For index trend calculation
        self.active_trades = []
        self.pnl_tracker = PnLTracker()
        self.last_trade_close_times = {} # (strategy_name, symbol) -> timestamp
        self.pcr_insights = {}
        self.buildup_history = []
        self.replay_idx = 0
        self.replay_speed = 0.5
        self.replay_data_idx = None
        self.replay_data_ce = None
        self.replay_data_pe = None
        self.ce_sym = ""
        self.pe_sym = ""
        self.index_sym = ""
        self.is_playing = False
        self.is_live = False
        self.ce_markers = []
        self.pe_markers = []
        self.last_idx_candle = None
        self.last_ce_candle = None
        self.last_pe_candle = None
        self.idx_history = []
        self.ce_history = []
        self.pe_history = []
        self.last_total_volumes = {} # Track cumulative volumes to calculate deltas
        self.pcr_insights = None
        self.upstox_client = None
        self.websocket = None
        self.subscribed_symbols = set()
        self.last_subscribed_candle = {} # symbol -> candle
        self.subscribed_history = {} # symbol -> list of candles

@app.get("/", response_class=HTMLResponse)
async def get_live(request: Request):
    return templates.TemplateResponse("live.html", {"request": request})

@app.get("/replay", response_class=HTMLResponse)
async def get_replay(request: Request):
    return templates.TemplateResponse("replay.html", {"request": request})

@app.get("/chart", response_class=HTMLResponse)
async def get_chart(request: Request):
    return templates.TemplateResponse("chart.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket accepted")
    state = SessionState()
    state.websocket = websocket
    loop = asyncio.get_running_loop()

    def live_callback(update):
        asyncio.run_coroutine_threadsafe(handle_live_update(state.websocket, state, update), loop)

    async def listen_task():
        logger.info("Listen task started")
        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                try:
                    msg = await websocket.receive_text()
                    logger.info(f"Received message: {msg}")
                    data = json.loads(msg)
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected")
                    break
                except Exception as e:
                    logger.error(f"Message error: {e}")
                    continue

                if data['type'] == 'fetch_live':
                    state.is_playing = False
                    state.is_live = True
                    # Reset state for live mode
                    state.active_trades = []
                    state.pnl_tracker = PnLTracker()
                    state.ce_markers = []
                    state.pe_markers = []
                    state.last_trade_close_times = {}
                    state.last_total_volumes = {}
                    await websocket.send_json({"type": "reset_ui"})

                    index_raw = data['index'].replace("NSE:", "")
                    state.index_sym = f"NSE:{index_raw}"
                    index_sym = index_raw # base symbol for DataManager
                    state.tf_main.update_params(index_sym)
                    for k in state.tf_strategies: state.tf_strategies[k].update_params(index_sym)

                    idx_df = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000)
                    if not idx_df.empty: idx_df = idx_df.between_time('03:45', '10:00')
                    if idx_df.empty:
                        await websocket.send_json({"type": "error", "message": "No index data found for market hours."})
                        return

                    strike = dm.get_atm_strike(idx_df['close'].iloc[-1], step=100 if "BANK" in index_sym else 50)

                    state.ce_sym = f"NSE:{dm.get_option_symbol(index_sym, strike, 'C')}"
                    state.pe_sym = f"NSE:{dm.get_option_symbol(index_sym, strike, 'P')}"

                    ce_df = dm.get_data(state.ce_sym, interval=Interval.in_1_minute, n_bars=300)
                    pe_df = dm.get_data(state.pe_sym, interval=Interval.in_1_minute, n_bars=300)
                    if not ce_df.empty: ce_df = ce_df.between_time('03:45', '10:00')
                    if not pe_df.empty: pe_df = pe_df.between_time('03:45', '10:00')

                    logger.info(f"Fetched history for {index_sym}: {len(idx_df)} bars. CE: {len(ce_df)} bars. PE: {len(pe_df)} bars.")

                    # Seed history for live strategy calculation
                    idx_recs = format_records(idx_df)
                    ce_recs = format_records(ce_df)
                    pe_recs = format_records(pe_df)

                    state.idx_history = idx_recs[-500:] if idx_recs else []
                    state.ce_history = ce_recs[-500:] if ce_recs else []
                    state.pe_history = pe_recs[-500:] if pe_recs else []

                    state.ce_markers = []
                    state.pe_markers = []

                    state.last_idx_candle = idx_recs[-1] if idx_recs else None
                    state.last_ce_candle = ce_recs[-1] if ce_recs else None
                    state.last_pe_candle = pe_recs[-1] if pe_recs else None

                    # Pre-calculate historical signals AND warm up strategy internal states
                    # Use last 300 bars for consistent state initialization
                    start_bar = max(20, len(ce_df) - 300)
                    for i in range(start_bar, len(ce_df)):
                        last_time = ce_df.index[i]
                        # Use at least 50 bars for indicator stability during warmup
                        sub_idx = idx_df.iloc[max(0, i-50):i+1]
                        sub_ce = ce_df.iloc[max(0, i-50):i+1]
                        sub_pe = pe_df.iloc[max(0, i-50):i+1]

                        # Use shifted timestamp for markers
                        c_time = ce_recs[i]['time']

                        # In warmup, we check for exits too to keep state clean
                        check_trade_exits(state, sub_idx, sub_ce, sub_pe)

                        # Run unified strategy processor (warmup mode)
                        # Warmup mode records trades in memory to track state/cooldown but avoids DB spam
                        h_signals = evaluate_all_strategies(state, sub_idx, sub_ce, sub_pe, last_time, c_time, record_trades=True, store_db=False)

                        for sig in h_signals:
                            color = "#2196F3" if sig['strat_name'] == "TREND_FOLLOWING" else "#FF9800"
                            marker = {"time": sig['time'], "position": "belowBar", "color": color, "shape": "arrowUp", "text": sig['strat_name']}
                            if sig.get('is_pe'):
                                state.pe_markers.append(marker)
                            else:
                                state.ce_markers.append(marker)

                    # Fetch Delta Volume signals and PCR Insights from Trendlyne
                    delta_signals = await fetch_trendlyne_signals(index_sym, strike)
                    pcr_res = await fetch_pcr_insights(index_sym)
                    state.pcr_insights = pcr_res.get('insights', {})
                    state.buildup_history = pcr_res.get('buildup_list', [])

                    # Convert trades to new_signals for the UI list
                    historical_signals = []
                    for t in state.pnl_tracker.trades:
                        historical_signals.append({
                            "strat_name": t.strategy_name,
                            "time": t.entry_time,
                            "entry_price": t.entry_price,
                            "sl": t.sl or 0,
                            "type": "LONG" if "PE" not in t.symbol else "SHORT" # Simplified side detection
                        })

                    await websocket.send_json(clean_json({
                        "type": "live_data",
                        "index_symbol": index_sym,
                        "index_data": format_records(idx_df),
                        "ce_data": ce_recs,
                        "pe_data": pe_recs,
                        "ce_markers": state.ce_markers,
                        "pe_markers": state.pe_markers,
                        "ce_symbol": state.ce_sym,
                        "pe_symbol": state.pe_sym,
                        "trend": state.tf_main.get_trend(idx_df, state.pcr_insights),
                        "delta_signals": delta_signals,
                        "pcr_insights": state.pcr_insights,
                        "pnl_stats": state.pnl_tracker.get_stats(),
                        "new_signals": historical_signals
                    }))

                    feed_manager.subscribe(live_callback)

                    # Check if Upstox is configured
                    use_upstox = hasattr(config, 'ACCESS_TOKEN') and config.ACCESS_TOKEN != "YOUR_ACCESS_TOKEN"
                    
                    if use_upstox:
                        logger.info("Using Upstox for Live Feed")
                        live_feed = feed_manager.get_upstox_feed(config.ACCESS_TOKEN)
                        state.upstox_client = dm.upstox_client
                        
                        # Use Upstox specific mapping
                        spot_prices = {index_sym: idx_df['close'].iloc[-1]}
                        upstox_mapping = dm.getNiftyAndBNFnOKeys([index_sym], spot_prices)
                        
                        if index_sym in upstox_mapping:
                            mapping = upstox_mapping[index_sym]
                            all_keys = mapping['all_keys']
                            # Add relevant Index Spot key
                            if index_sym == "NIFTY": all_keys.append("NSE_INDEX|Nifty 50")
                            elif index_sym == "BANKNIFTY": all_keys.append("NSE_INDEX|Nifty Bank")
                            
                            # Sync CE/PE symbols in state to match the real Upstox Trading Symbols for perfect live matching
                            for opt in mapping.get('options', []):
                                if opt['strike'] == strike:
                                    state.ce_sym = f"NSE:{opt['ce_trading_symbol']}"
                                    state.pe_sym = f"NSE:{opt['pe_trading_symbol']}"
                                    break

                            symbols_with_keys = []
                            for k in list(set(all_keys)):
                                # Priority 1: Fixed Spot Mapping
                                if k == "NSE_INDEX|Nifty 50": sym = "NSE:NIFTY"
                                elif k == "NSE_INDEX|Nifty Bank": sym = "NSE:BANKNIFTY"
                                # Priority 2: Future Mapping
                                elif k == mapping.get('future'):
                                    sym = f"NSE:{mapping.get('future_trading_symbol', k)}"
                                # Priority 3: Options Mapping
                                else:
                                    found_opt = False
                                    for opt in mapping.get('options', []):
                                        if k == opt['ce']:
                                            sym = f"NSE:{opt['ce_trading_symbol']}"
                                            found_opt = True
                                            break
                                        elif k == opt['pe']:
                                            sym = f"NSE:{opt['pe_trading_symbol']}"
                                            found_opt = True
                                            break
                                    if not found_opt:
                                        sym = k # Fallback
                                
                                symbols_with_keys.append({"symbol": sym, "key": k})
                            
                            live_feed.add_symbols(symbols_with_keys)
                        else:
                            logger.error("Failed to get Upstox instrument keys, falling back to TradingView")
                            use_upstox = False

                    if not use_upstox:
                        logger.info("Using TradingView for Live Feed")
                        live_feed = feed_manager.get_tv_feed()
                        # symbols in state already have NSE: prefix
                        symbols = [state.index_sym, state.ce_sym, state.pe_sym]
                        step = 100 if "BANK" in index_sym else 50
                        for offset in [-100, 100]:
                            for ot in ["C", "P"]:
                                symbols.append(f"NSE:{dm.get_option_symbol(index_sym, strike + offset, ot)}")
                        live_feed.add_symbols(list(set(symbols)))

                elif data['type'] == 'start_replay':
                    logger.info(f"Starting replay for {data['index']} at {data.get('date', 'now')}")
                    state.is_playing = False
                    state.is_live = False
                    # Reset state for new replay
                    state.active_trades = []
                    state.pnl_tracker = PnLTracker()
                    state.ce_markers = []
                    state.pe_markers = []
                    state.last_trade_close_times = {}
                    await websocket.send_json({"type": "reset_ui"})

                    index_sym = data['index']

                    ref_date = None
                    if data.get('date'):
                        try:
                            # Expected format YYYY-MM-DD
                            ref_date = datetime.strptime(data['date'], "%Y-%m-%d")
                            # Set to market close time for better data generation
                            ref_date = ref_date.replace(hour=15, minute=30)
                        except:
                            logger.error(f"Invalid date format: {data['date']}")

                    # Fetch PCR/Buildup for historical date
                    pcr_res = await fetch_pcr_insights(index_sym, ref_date=ref_date)
                    state.pcr_insights = pcr_res.get('insights', {})
                    state.buildup_history = pcr_res.get('buildup_list', [])

                    state.tf_main.update_params(index_sym)
                    for k in state.tf_strategies: state.tf_strategies[k].update_params(index_sym)
                    state.replay_data_idx = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
                    if not state.replay_data_idx.empty:
                        state.replay_data_idx = state.replay_data_idx.between_time('03:45', '10:00')

                    if state.replay_data_idx.empty:
                        await websocket.send_json({"type": "error", "message": f"No data found for {index_sym} in market hours."})
                        return

                    strike = dm.get_atm_strike(state.replay_data_idx['close'].iloc[0], step=100 if "BANK" in index_sym else 50)

                    state.ce_sym = dm.get_option_symbol(index_sym, strike, "C", reference_date=ref_date)
                    state.pe_sym = dm.get_option_symbol(index_sym, strike, "P", reference_date=ref_date)
                    state.replay_data_ce = dm.get_data(state.ce_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
                    state.replay_data_pe = dm.get_data(state.pe_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)

                    if not state.replay_data_ce.empty: state.replay_data_ce = state.replay_data_ce.between_time('03:45', '10:00')
                    if not state.replay_data_pe.empty: state.replay_data_pe = state.replay_data_pe.between_time('03:45', '10:00')

                    if state.replay_data_ce.empty or state.replay_data_pe.empty:
                        await websocket.send_json({"type": "error", "message": f"Option data not found for {state.ce_sym} or {state.pe_sym} in market hours."})
                        return

                    state.replay_idx = 50
                    state.ce_markers = []
                    state.pe_markers = []
                    state.is_playing = True

                    await websocket.send_json({
                        "type": "replay_info",
                        "max_idx": min(len(state.replay_data_ce), len(state.replay_data_pe)),
                        "current_idx": state.replay_idx
                    })
                    await send_replay_step(websocket, state)

                elif data['type'] == 'set_replay_index':
                    state.replay_idx = data['index']
                    await send_replay_step(websocket, state)

                elif data['type'] == 'pause_replay':
                    state.is_playing = False

                elif data['type'] == 'step_replay':
                    if state.replay_data_ce is not None and state.replay_idx < len(state.replay_data_ce):
                        state.replay_idx += 1
                        await send_replay_step(websocket, state)

                elif data['type'] == 'set_replay_speed':
                    state.replay_speed = float(data['speed'])

                elif data['type'] == 'subscribe_symbol':
                    sub_sym = f"NSE:{data['symbol'].replace('NSE:', '')}"
                    clean_sub_sym = sub_sym.replace("NSE:", "")
                    state.subscribed_symbols.add(sub_sym) # Use prefixed for consistency
                    logger.info(f"Subscription requested for {sub_sym}")
                    feed_manager.subscribe(live_callback)

                    use_upstox = hasattr(config, 'ACCESS_TOKEN') and config.ACCESS_TOKEN != "YOUR_ACCESS_TOKEN"
                    if use_upstox:
                        live_feed = feed_manager.get_upstox_feed(config.ACCESS_TOKEN)
                        inst_key = dm.get_upstox_key_for_tv_symbol(sub_sym)
                        if inst_key:
                             # Resolve the actual trading symbol from the master to ensure consistency
                             # If sub_sym is NSE:NIFTY, it maps to NSE_INDEX|Nifty 50.
                             # If we add_symbols with sub_sym as the display name, it will be used in updates.
                             live_feed.add_symbols([{"symbol": sub_sym, "key": inst_key}])
                        else:
                             # Fallback: use sub_sym as both if not found in master
                             live_feed.add_symbols([{"symbol": sub_sym, "key": sub_sym}])
                    else:
                        live_feed = feed_manager.get_tv_feed()
                        live_feed.add_symbols([sub_sym])

                    # Fetch and send history for popout
                    hist_df = dm.get_data(sub_sym, interval=Interval.in_1_minute, n_bars=300)
                    if not hist_df.empty:
                        hist_df = hist_df.between_time('03:45', '10:00')
                        recs = format_records(hist_df)

                        # Seed last candle for live updates
                        if recs:
                            state.last_subscribed_candle[clean_sub_sym] = recs[-1]
                            state.subscribed_history[clean_sub_sym] = recs[-100:]

                        await websocket.send_json(clean_json({
                            "type": "history_data",
                            "symbol": sub_sym,
                            "data": recs
                        }))

        except Exception as e:
            logger.exception("Listen Error")

    async def replay_loop():
        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                if state.is_playing and state.replay_data_ce is not None:
                    # print(f"Replay loop step: {state.replay_idx}")
                    if state.replay_idx < len(state.replay_data_ce):
                        state.replay_idx += 1
                        await send_replay_step(websocket, state)
                    else:
                        state.is_playing = False
                await asyncio.sleep(state.replay_speed)
        except Exception as e:
            logger.error(f"Replay Loop Error: {e}")

    try:
        await asyncio.gather(listen_task(), replay_loop())
    finally:
        feed_manager.unsubscribe(live_callback)

def is_within_trading_window(ts_utc):
    """
    Check if IST time is between 09:20 and 15:17.
    """
    if isinstance(ts_utc, (int, float)):
        dt = datetime.fromtimestamp(ts_utc, tz=timezone.utc)
    else:
        dt = ts_utc

    ist_dt = dt.astimezone(IST_TZ)
    h, m = ist_dt.hour, ist_dt.minute
    current_time = h * 60 + m

    # Standard Market Hours (IST)
    start_time = 9 * 60 + 15
    end_time = 15 * 60 + 30

    return start_time <= current_time <= end_time

def is_market_closing(ts_utc):
    """
    Check if IST time is 15:25 or later.
    """
    if isinstance(ts_utc, (int, float)):
        dt = datetime.fromtimestamp(ts_utc, tz=timezone.utc)
    else:
        dt = ts_utc

    ist_dt = dt.astimezone(IST_TZ)
    h, m = ist_dt.hour, ist_dt.minute
    current_time = h * 60 + m

    # Standard Square-off time (IST)
    close_time = 15 * 60 + 25
    return current_time >= close_time

def check_option_ema_filter(option_df):
    """
    EMA filter on option price:
    - price need to be above atleast one ema (9 or 14)
    - 9 ema rising OR 9 ema above 14 ema
    """
    if option_df is None or len(option_df) < 15:
        return False

    try:
        import pandas_ta as ta
        # Calculate EMA 9 and 14
        ema9 = ta.ema(option_df['close'], length=9)
        ema14 = ta.ema(option_df['close'], length=14)

        if ema9 is None or ema14 is None or pd.isna(ema9.iloc[-1]) or pd.isna(ema14.iloc[-1]):
            return False

        last_close = option_df['close'].iloc[-1]
        last_ema9 = ema9.iloc[-1]
        prev_ema9 = ema9.iloc[-2] if len(ema9) > 1 else last_ema9
        last_ema14 = ema14.iloc[-1]

        # price need to be above atleast one ema
        above_ema = (last_close > last_ema9) or (last_close > last_ema14)
        # 9 ema rising /or above 14 ema
        ema_condition = (last_ema9 > prev_ema9) or (last_ema9 > last_ema14)

        return above_ema and ema_condition
    except Exception as e:
        logger.error(f"EMA Filter error: {e}")
        return False

def format_records(df):
    """Formats DataFrame for UI with Unix timestamps shifted to IST for presentation."""
    if df.empty: return []
    recs = df.copy().reset_index()
    # Data is already localized to UTC in DataManager.get_data
    if 'datetime' not in recs.columns: return []
    if recs['datetime'] is None or recs['datetime'].dt.tz is None:
        recs['datetime'] = recs['datetime'].dt.tz_localize('Asia/Kolkata').dt.tz_convert('UTC')

    # Add Unix timestamp in seconds.
    # Shift by 5.5 hours (19800s) to force UI to show IST digits as UTC.
    recs['time'] = recs['datetime'].apply(lambda x: int(x.timestamp()) + 19800)

    # Keep ISO string for reference if needed
    recs['datetime_str'] = recs['datetime'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Convert datetime objects to string to avoid JSON serializable error
    recs['datetime'] = recs['datetime_str']

    return recs.to_dict(orient='records')

def normalize_buildup(status):
    if not status: return "NEUTRAL"
    s = str(status).upper()
    if "LONG BUILD" in s: return "LONG BUILD"
    if "SHORT COVER" in s: return "SHORT COVER"
    if "SHORT BUILD" in s: return "SHORT BUILD"
    if "LONG UNWIND" in s: return "LONG UNWIND"
    return "NEUTRAL"

def get_buildup_for_time(buildup_history, current_time):
    """
    Parses buildup_history to find the one matching current_time.
    Supports both list-of-lists and list-of-dicts formats from Trendlyne.
    """
    if not buildup_history: return "NEUTRAL"

    if isinstance(current_time, (int, float)):
        # Convert shifted IST timestamp back to naive datetime for matching
        # Note: shifted timestamp is IST as UTC, so utcfromtimestamp gives IST digits
        dt = datetime.utcfromtimestamp(current_time)
    else:
        dt = current_time

    curr_str = dt.strftime("%H:%M")

    for row in buildup_history:
        time_range = None
        status = None

        if isinstance(row, list) and len(row) > 1:
            time_range = row[0]
            status = row[1]
        elif isinstance(row, dict):
            time_range = row.get('interval') or row.get('time_range')
            status = row.get('buildup') or row.get('status') or row.get('buildup_type')

        if not time_range: continue

        try:
            if " TO " in time_range:
                start_str, end_str = time_range.split(" TO ")
                if start_str <= curr_str <= end_str:
                    return normalize_buildup(status)
        except:
            continue
    return None

async def send_replay_step(websocket, state):
    try:
        # 1. Basic Validation
        if websocket.client_state != WebSocketState.CONNECTED: return
        if state.replay_data_ce is None or state.replay_data_pe is None or state.replay_data_idx is None: return

        # 2. Slice Data
        sub_ce = state.replay_data_ce.iloc[max(0, state.replay_idx-50):state.replay_idx]
        sub_pe = state.replay_data_pe.iloc[max(0, state.replay_idx-50):state.replay_idx]
        if sub_ce.empty or sub_pe.empty: return

        last_time = sub_ce.index[-1]
        # Matching slice for index
        idx_full = state.replay_data_idx[state.replay_data_idx.index <= last_time]
        sub_idx = idx_full.iloc[-50:]
        if sub_idx.empty: return

        # 3. Initialize Context
        if not state.pcr_insights:
            state.pcr_insights = {'pcr': 1.0, 'pcr_change': 1.0, 'buildup_status': 'NEUTRAL'}

        # Update buildup status from history if available
        hist_buildup = get_buildup_for_time(state.buildup_history, last_time)
        if hist_buildup:
            state.pcr_insights['buildup_status'] = hist_buildup

        # 4. Check Active Trades
        old_trades_count = len(state.active_trades)
        check_trade_exits(state, sub_idx, sub_ce, sub_pe)
        if len(state.active_trades) != old_trades_count:
             # Re-calculate stats if a trade closed
             state.pnl_tracker.update_stats()

        # Update PnL stats even if no trade closed (to track open PnL if needed,
        # though currently update_stats only handles closed)
        state.pnl_tracker.update_stats()

        # EOD Square-off check
        if is_market_closing(last_time):
            for trade in state.active_trades[:]:
                df = sub_ce if trade.symbol == state.ce_sym else (sub_pe if trade.symbol == state.pe_sym else sub_idx)
                last_price = df['close'].iloc[-1]
                last_time_shifted = int(df.index[-1].timestamp()) + 19800
                trade.close(last_price, last_time_shifted, "EOD_SQUAREOFF")
                db.store_trade(trade)
                state.active_trades.remove(trade)

        # Store PCR Insights for analysis
        db.store_pcr_insight(state.index_sym.replace("NSE:", ""), int(last_time.timestamp()), state.pcr_insights, state.buildup_history)

        # 5. Format Records for Markers
        ce_recs = format_records(sub_ce)
        pe_recs = format_records(sub_pe)
        idx_recs = format_records(sub_idx)

        # 6. Process All Strategies (Unified & Synchronized)
        trend = state.tf_main.get_trend(sub_idx, state.pcr_insights)
        candle_time = ce_recs[-1]['time']
        new_signals = evaluate_all_strategies(state, sub_idx, sub_ce, sub_pe, last_time, candle_time)

        for sig in new_signals:
            color = "#2196F3" if sig['strat_name'] == "TREND_FOLLOWING" else "#FF9800"
            marker = {"time": sig['time'], "position": "belowBar", "color": color, "shape": "arrowUp", "text": sig['strat_name']}
            if sig.get('is_pe'):
                state.pe_markers.append(marker)
            else:
                state.ce_markers.append(marker)

        # 7. Construct Message
        msg = {
            "type": "replay_step",
            "index_data": idx_recs,
            "ce_data": ce_recs,
            "pe_data": pe_recs,
            "ce_markers": state.ce_markers,
            "pe_markers": state.pe_markers,
            "ce_symbol": state.ce_sym,
            "pe_symbol": state.pe_sym,
            "trend": trend,
            "max_idx": min(len(state.replay_data_ce), len(state.replay_data_pe)),
            "current_idx": state.replay_idx,
            "pnl_stats": state.pnl_tracker.get_stats(),
            "new_signals": new_signals
        }

        await websocket.send_json(clean_json(msg))
    except Exception as e:
        print(f"ERROR in send_replay_step: {e}")

def clean_json(obj):
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_json(i) for i in obj]
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, bool):
        return obj
    elif hasattr(obj, 'timestamp') and callable(obj.timestamp):
        return int(obj.timestamp())
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj

async def fetch_pcr_insights(index_sym, ref_date=None):
    """Fetches PCR and OI insights using TrendlyneAdvClient."""
    try:
        stock_id = await tl_adv.get_stock_id(index_sym)
        expiries = await tl_adv.get_expiry_data(stock_id)

        t_date = (ref_date or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        valid = []
        for e in expiries["expiresDts"]:
            try:
                dt = datetime.strptime(e, "%d-%b-%Y")
            except ValueError:
                try:
                    dt = datetime.strptime(e, "%Y-%m-%d")
                except:
                    continue
            if dt >= t_date:
                valid.append(dt)

        if not valid: return {"insights": {}, "buildup_list": []}
        target_dt = valid[0]
        api_expiry_str = target_dt.strftime("%Y-%m-%d")

        insights = {}
        # Only fetch live snapshot if it's for today
        if not ref_date or ref_date.date() == datetime.now().date():
            live_data = await tl_adv.get_live_oi_snapshot(stock_id, api_expiry_str)
            insights = tl_adv.extract_writer_insights(live_data) or {}
        else:
            insights = {'pcr': 1.0, 'pcr_change': 1.0, 'buildup_status': 'NEUTRAL'}

        # Fetch 5m buildup
        buildup_list = await tl_adv.get_buildup_5m(target_dt, index_sym)

        # Normalize buildup status text for latest insight
        if buildup_list and len(buildup_list) > 0:
            latest = buildup_list[0]
            status = "NEUTRAL"
            if isinstance(latest, list) and len(latest) > 1:
                status = latest[1]
            elif isinstance(latest, dict):
                status = latest.get('buildup') or latest.get('status') or latest.get('buildup_type') or "NEUTRAL"

            insights['buildup_status'] = normalize_buildup(status)

        return {"insights": insights, "buildup_list": buildup_list}
    except Exception as e:
        logger.error(f"Error fetching PCR insights: {e}")
    return {"insights": {}, "buildup_list": []}

async def fetch_trendlyne_signals(index_sym, atm_strike):
    """
    Fetches 5m buildup data for ATM and surrounding strikes and processes them.
    Uses async httpx to avoid blocking the event loop.
    """
    try:
        # Get expiry dynamically
        stock_id = await tl_client.get_stock_id_for_symbol(index_sym)
        expiry_list = await tl_client.get_expiry_dates(stock_id)
        if not expiry_list:
            expiry = "27-jan-2026-near" # Fallback if API fails
        else:
            # Map Trendlyne expiry format to URL format
            # e.g. "2026-01-27" -> "27-jan-2026-near"
            raw_expiry = expiry_list[0] # nearest
            dt = datetime.strptime(raw_expiry, "%Y-%m-%d")
            expiry = dt.strftime("%d-%b-%Y").lower() + "-near"

        call_data = {}
        put_data = {}

        step = 100 if "BANK" in index_sym else 50
        # ATM, 1 ITM, 1 OTM (The Battleground Cluster)
        strikes_to_check = [atm_strike - step, atm_strike, atm_strike + step]

        tasks = []
        for s in strikes_to_check:
            tasks.append(tl_client.get_buildup_5m_data(expiry, index_sym, s, "call"))
            tasks.append(tl_client.get_buildup_5m_data(expiry, index_sym, s, "put"))

        responses = await asyncio.gather(*tasks)

        for i, resp in enumerate(responses):
            strike = strikes_to_check[i // 2]
            opt_type = "call" if i % 2 == 0 else "put"
            if resp and 'body' in resp and 'data' in resp['body']:
                if opt_type == "call":
                    call_data[str(strike)] = resp['body']['data']
                else:
                    put_data[str(strike)] = resp['body']['data']

        signals = delta_strategy.get_buy_signal(atm_strike, call_data, put_data)
        return signals
    except Exception as e:
        logger.error(f"Error fetching Trendlyne signals: {e}")
        return None

def evaluate_all_strategies(state, idx_df, ce_df, pe_df, last_time, candle_time, record_trades=True, store_db=True):
    """
    Unified strategy processor for both Live and Replay.
    Returns a list of signals triggered.
    """
    new_signals = []
    sl_dist = 30 if "BANK" in state.index_sym else 20

    if not is_within_trading_window(last_time):
        return new_signals

    # A. Index-driven strategies
    if not idx_df.empty and len(idx_df) >= 20:
        for strat in state.strategies["INDEX"]:
            if strat.is_index_driven or any(x in strat.name for x in ["INDEX", "INSTITUTIONAL", "ROUND_LEVEL", "SAMPLE_TREND", "SCREENER", "GAP_FILL"]):
                setup = strat.check_setup(idx_df, state.pcr_insights)
                if setup:
                    s_type = setup.get('type', '').upper()
                    is_pe_trade = ("SHORT" in s_type) or ("PE" in s_type)
                    target_df = pe_df if is_pe_trade else ce_df
                    target_sym = state.pe_sym if is_pe_trade else state.ce_sym

                    if target_df.empty: continue
                    if not check_option_ema_filter(target_df): continue

                    setup['strat_name'] = strat.name
                    setup['time'] = candle_time
                    setup['entry_price'] = setup.get('entry_price') or target_df['close'].iloc[-1]
                    setup['sl'] = setup.get('sl') or (setup['entry_price'] - sl_dist)
                    setup['target'] = setup.get('target') or (setup['entry_price'] + sl_dist * 2)
                    setup['is_pe'] = is_pe_trade

                    if handle_new_trade(state, strat.name, target_sym, setup, candle_time, store=record_trades, store_db=store_db):
                        new_signals.append(setup)

    # B. Option-driven strategies
    for side, df, strat_list, sym in [
        ("CE", ce_df, state.strategies["CE"], state.ce_sym),
        ("PE", pe_df, state.strategies["PE"], state.pe_sym)
    ]:
        if df.empty or len(df) < 20: continue

        # Check standard option strats
        for strat in strat_list:
            if not strat.is_index_driven and not any(x in strat.name for x in ["INDEX", "INSTITUTIONAL", "ROUND_LEVEL", "SAMPLE_TREND", "SCREENER", "GAP_FILL"]):
                setup = strat.check_setup(df, state.pcr_insights)
                if setup:
                    if not check_option_ema_filter(df): continue

                    setup['strat_name'] = strat.name
                    setup['time'] = candle_time
                    setup['entry_price'] = setup.get('entry_price') or df['close'].iloc[-1]
                    setup['sl'] = setup.get('sl') or (setup['entry_price'] - sl_dist)
                    setup['target'] = setup.get('target') or (setup['entry_price'] + sl_dist * 2)
                    setup['is_pe'] = (side == "PE")

                    if handle_new_trade(state, strat.name, sym, setup, candle_time, store=record_trades, store_db=store_db):
                        new_signals.append(setup)

        # Check Trend Following
        tf_strat = state.tf_strategies[side]
        tf_setup = tf_strat.check_setup_unified(idx_df, df, state.pcr_insights, side)
        if tf_setup:
            if check_option_ema_filter(df):
                tf_setup['strat_name'] = tf_strat.name
                tf_setup['time'] = candle_time
                tf_setup['entry_price'] = tf_setup.get('entry_price') or df['close'].iloc[-1]
                tf_setup['sl'] = tf_setup.get('sl') or (tf_setup['entry_price'] - sl_dist)
                tf_setup['target'] = tf_setup.get('target') or (tf_setup['entry_price'] + sl_dist * 2)
                tf_setup['is_pe'] = (side == "PE")

                if handle_new_trade(state, tf_strat.name, sym, tf_setup, candle_time, store=record_trades, store_db=store_db):
                    new_signals.append(tf_setup)

    return new_signals

async def handle_live_update(websocket, state, update):
    if websocket.client_state != WebSocketState.CONNECTED: return

    # Normalize incoming symbol for matching
    raw_symbol = update['symbol']
    prefixed_symbol = f"NSE:{raw_symbol.replace('NSE:', '')}"
    clean_symbol = prefixed_symbol.replace("NSE:", "")

    is_index = prefixed_symbol == state.index_sym
    is_ce = prefixed_symbol == state.ce_sym
    is_pe = prefixed_symbol == state.pe_sym
    is_subscribed = prefixed_symbol in state.subscribed_symbols

    if not (is_index or is_ce or is_pe or is_subscribed): return

    # Volume handling
    current_total_volume = update.get('volume')
    last_total_volume = state.last_total_volumes.get(prefixed_symbol)

    volume_delta = 0
    if current_total_volume is not None:
        if last_total_volume is not None:
            volume_delta = max(0, current_total_volume - last_total_volume)
        else:
            # First live tick for this symbol: initialize total volume but don't add to candle
            volume_delta = 0
        state.last_total_volumes[prefixed_symbol] = current_total_volume

    # Use feed timestamp or fallback to current time
    now_ts = update.get('timestamp')
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    now = int(now_ts)
    interval_sec = 60
    # Apply 5.5h shift for IST presentation (Force IST digits as UTC)
    candle_time = ((now + 19800) // interval_sec) * interval_sec

    if is_index: target_candle = state.last_idx_candle
    elif is_ce: target_candle = state.last_ce_candle
    elif is_pe: target_candle = state.last_pe_candle
    elif is_subscribed: target_candle = state.last_subscribed_candle.get(clean_symbol)
    else: target_candle = None

    # Handle broker OHLC correction for COMPLETED candles (I1 is strictly the prior minute)
    if update.get('ohlc'):
        u_ohlc = update['ohlc']
        u_ts = (int(u_ohlc.get('ts', 0)) // 1000) + 19800

        # Update history with finalized broker data
        if is_index: history = state.idx_history
        elif is_ce: history = state.ce_history
        elif is_pe: history = state.pe_history
        elif is_subscribed: history = state.subscribed_history.get(clean_symbol, [])
        else: history = []

        for h_candle in reversed(history[-5:]): # Check last few candles
            if h_candle['time'] == u_ts:
                h_candle['open'] = u_ohlc.get('open', h_candle['open'])
                h_candle['high'] = u_ohlc.get('high', h_candle['high'])
                h_candle['low'] = u_ohlc.get('low', h_candle['low'])
                h_candle['close'] = u_ohlc.get('close', h_candle['close'])
                if u_ohlc.get('volume'): h_candle['volume'] = float(u_ohlc['volume'])
                db.store_ohlcv(clean_symbol, "Interval.in_1_minute", pd.DataFrame([h_candle]))
                # NOTE: We don't broadcast history_data on every tick to avoid UI lag.
                # Corrections will be synced on next candle close or via regular updates.
                break

    if target_candle is None or candle_time > target_candle['time']:
        # Save finished candle to history before starting new one
        if target_candle is not None:
            # Final broadcast of the closed candle for UI accuracy
            await websocket.send_json(clean_json({
                "type": "live_update", "symbol": prefixed_symbol, "candle": target_candle,
                "is_index": is_index, "is_ce": is_ce, "is_pe": is_pe
            }))

            # Store completed candle in DB
            db.store_ohlcv(clean_symbol, "Interval.in_1_minute", pd.DataFrame([target_candle]))

            if is_index:
                state.idx_history.append(target_candle)
                if len(state.idx_history) > 500: state.idx_history.pop(0)
            elif is_ce:
                state.ce_history.append(target_candle)
                if len(state.ce_history) > 500: state.ce_history.pop(0)
            elif is_pe:
                state.pe_history.append(target_candle)
                if len(state.pe_history) > 500: state.pe_history.pop(0)
            elif is_subscribed:
                if clean_symbol not in state.subscribed_history: state.subscribed_history[clean_symbol] = []
                state.subscribed_history[clean_symbol].append(target_candle)
                if len(state.subscribed_history[clean_symbol]) > 100: state.subscribed_history[clean_symbol].pop(0)

            # Strategy and Square-off check on closed candle
            if len(state.idx_history) > 20:
                logger.info(f"Processing strategies on closed candle: {target_candle['time']} for {clean_symbol}")
                current_utc = datetime.now(timezone.utc)

                # EOD Square-off check for live mode
                if is_market_closing(current_utc):
                    for trade in state.active_trades[:]:
                        # Use the correct price for the trade's symbol
                        exit_price = update['price'] if trade.symbol == prefixed_symbol else trade.entry_price
                        trade.close(exit_price, candle_time, "EOD_SQUAREOFF")
                        db.store_trade(trade)
                        state.active_trades.remove(trade)
                    return

                # Convert history to DataFrames with proper index for pandas_ta
                def to_df(hist):
                    if not hist: return pd.DataFrame()
                    df = pd.DataFrame(hist)
                    if 'time' in df.columns:
                        df.index = pd.to_datetime(df['time'] - 19800, unit='s')
                    return df

                idx_df = to_df(state.idx_history)
                ce_df = to_df(state.ce_history)
                pe_df = to_df(state.pe_history)

                # Run unified strategy processor
                # In Live, we check all strats on ANY candle close to match Replay sequential processing
                # but only if the relevant dataframes are not empty.
                # Use current_utc shifted for trading window check inside evaluate_all_strategies

                # Use sliding window for strategy calculation (matching warmup and replay)
                s_idx = idx_df.iloc[-50:]
                s_ce = ce_df.iloc[-50:]
                s_pe = pe_df.iloc[-50:]

                new_live_signals = evaluate_all_strategies(state, s_idx, s_ce, s_pe, current_utc, target_candle['time'])

                for sig in new_live_signals:
                     color = "#2196F3" if sig['strat_name'] == "TREND_FOLLOWING" else "#FF9800"
                     marker = {"time": sig['time'], "position": "belowBar", "color": color, "shape": "arrowUp", "text": sig['strat_name']}
                     is_pe_t = sig.get('is_pe', False)
                     if is_pe_t: state.pe_markers.append(marker)
                     else: state.ce_markers.append(marker)

                     await websocket.send_json(clean_json({
                        "type": "marker_update", "is_ce": not is_pe_t,
                        "is_pe": is_pe_t,
                        "symbol": state.pe_sym if is_pe_t else state.ce_sym,
                        "marker": marker, "signal": sig,
                        "pnl_stats": state.pnl_tracker.get_stats()
                     }))

        new_candle = {
            "time": candle_time,
            "open": update['price'],
            "high": update['price'],
            "low": update['price'],
            "close": update['price'],
            "volume": volume_delta
        }
        if is_index: state.last_idx_candle = new_candle
        elif is_ce: state.last_ce_candle = new_candle
        elif is_pe: state.last_pe_candle = new_candle
        elif is_subscribed: state.last_subscribed_candle[clean_symbol] = new_candle
        target_candle = new_candle

        # Every new candle, also refresh Trendlyne signals and PCR if in live mode
        if is_index:
            strike = dm.get_atm_strike(update['price'], step=100 if "BANK" in clean_symbol else 50)
            delta_signals = await fetch_trendlyne_signals(clean_symbol, strike)
            pcr_res = await fetch_pcr_insights(clean_symbol)
            state.pcr_insights = pcr_res.get('insights', {})
            state.buildup_history = pcr_res.get('buildup_list', [])

            # Option Chain handling if Upstox is enabled
            option_chain_data = None
            if state.upstox_client:
                try:
                    # Get next expiry for Upstox
                    spot_prices = {clean_symbol: update['price']}
                    upstox_mapping = dm.getNiftyAndBNFnOKeys([clean_symbol], spot_prices)
                    if clean_symbol in upstox_mapping:
                        expiry_date = upstox_mapping[clean_symbol]['expiry']
                        instrument_key = dm.get_upstox_key_for_tv_symbol(prefixed_symbol)
                        if instrument_key:
                            option_chain_res = state.upstox_client.get_put_call_option_chain(instrument_key, expiry_date)
                            if option_chain_res and option_chain_res.status == 'success':
                                option_chain_data = option_chain_res.data
                except Exception as e:
                    logger.error(f"Error fetching Upstox Option Chain: {e}")

            await websocket.send_json(clean_json({
                "type": "delta_signals",
                "delta_signals": delta_signals,
                "pcr_insights": state.pcr_insights,
                "option_chain": option_chain_data,
                "trend": state.tf_main.get_trend(pd.DataFrame(state.idx_history), state.pcr_insights) if state.idx_history else None
            }))
    else:
        # Update current candle from tick (ALWAYS USE LTP)
        target_candle['close'] = update['price']
        if update['price'] > target_candle['high']: target_candle['high'] = update['price']
        if update['price'] < target_candle['low']: target_candle['low'] = update['price']
        target_candle['volume'] += volume_delta

        # If the broker somehow sends CURRENT minute OHLC, we can still benefit from it
        # but keep LTP as the 'close'
        if update.get('ohlc'):
             u_ohlc = update['ohlc']
             u_ts = (int(u_ohlc.get('ts', 0)) // 1000) + 19800
             if u_ts == target_candle['time']:
                 target_candle['open'] = u_ohlc.get('open', target_candle['open'])
                 target_candle['high'] = max(target_candle['high'], u_ohlc.get('high', 0))
                 target_candle['low'] = min(target_candle['low'], u_ohlc.get('low', 999999))
                 # target_candle['close'] remains LTP

    # Check for exits on every tick for active trades of this symbol
    for trade in state.active_trades[:]:
        if trade.symbol == prefixed_symbol:
            last_price = update['price']
            # shifted IST unix timestamp
            last_time = candle_time

            closed = False
            exit_price = 0
            reason = ""

            if trade.trade_type == 'LONG':
                if trade.sl and last_price <= trade.sl:
                    closed, exit_price, reason = True, trade.sl, 'SL'
                elif trade.target and last_price >= trade.target:
                    closed, exit_price, reason = True, trade.target, 'TARGET'

            if closed:
                trade.close(exit_price, last_time, reason)
                db.store_trade(trade)
                state.last_trade_close_times[(trade.strategy_name, trade.symbol)] = last_time
                state.active_trades.remove(trade)
                logger.info(f"TRADE CLOSED: {trade.strategy_name} on {trade.symbol} at {exit_price} ({reason})")
                # Important: update_stats() is called inside get_stats()
                await websocket.send_json(clean_json({
                    "type": "pnl_stats",
                    "pnl_stats": state.pnl_tracker.get_stats()
                }))

    await websocket.send_json(clean_json({
        "type": "live_update", "symbol": prefixed_symbol, "candle": target_candle,
        "is_index": is_index, "is_ce": is_ce, "is_pe": is_pe,
        "pnl_stats": state.pnl_tracker.get_stats() if state.active_trades else None
    }))


def handle_new_trade(state, strategy_name, symbol, setup, time, store=True, store_db=True):
    # Check active trades
    for t in state.active_trades:
        if t.strategy_name == strategy_name and t.symbol == symbol:
            return False

    # Cooldown check: 5 minutes (300 seconds)
    last_close = state.last_trade_close_times.get((strategy_name, symbol), 0)
    if time - last_close < 300:
        return False

    if not store:
        # For warmup mode, we don't open real trades, but we still return True
        # to show markers and potentially update cooldown if desired.
        # Actually, let's keep it simple: warmup just shows markers and warms up strat.vars
        return True

    # Since we only BUY options (Call for market-long, Put for market-short),
    # all trades are "LONG" on the option premium.
    t_type = 'LONG'
    trade = Trade(symbol, setup['entry_price'], time, t_type, strategy_name, sl=setup.get('sl'), target=setup.get('target'))
    # Persist trade to DB if requested
    if store_db:
        db.store_trade(trade)
    state.active_trades.append(trade)
    state.pnl_tracker.add_trade(trade)
    return True

def check_trade_exits(state, sub_idx, sub_ce, sub_pe):
    for trade in state.active_trades[:]:
        df = sub_ce if trade.symbol == state.ce_sym else (sub_pe if trade.symbol == state.pe_sym else sub_idx)
        if df.empty: continue

        last_price = df['close'].iloc[-1]
        last_time = int(df.index[-1].timestamp()) + 19800

        closed = False
        exit_price = 0
        reason = ""

        if trade.trade_type == 'LONG':
            if trade.sl and last_price <= trade.sl:
                closed, exit_price, reason = True, trade.sl, 'SL'
            elif trade.target and last_price >= trade.target:
                closed, exit_price, reason = True, trade.target, 'TARGET'
        else: # SHORT
            if trade.sl and last_price >= trade.sl:
                closed, exit_price, reason = True, trade.sl, 'SL'
            elif trade.target and last_price <= trade.target:
                closed, exit_price, reason = True, trade.target, 'TARGET'

        if closed:
            trade.close(exit_price, last_time, reason)
            # Update trade in DB
            db.store_trade(trade)
            state.last_trade_close_times[(trade.strategy_name, trade.symbol)] = last_time
            state.active_trades.remove(trade)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
