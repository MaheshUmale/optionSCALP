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
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from data.gathering.data_manager import DataManager
from data.gathering.live_feed import TradingViewLiveFeed
from core.strategies.trend_following import TrendFollowingStrategy
from core.strategies.delta_volume_strategy import DeltaVolumeStrategy
from trendlyne_client import TrendlyneClient
from tvDatafeed import Interval

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

dm = DataManager()
strategy = TrendFollowingStrategy()
delta_strategy = DeltaVolumeStrategy()
tl_client = TrendlyneClient()

class SessionState:
    def __init__(self):
        self.replay_idx = 0
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
        self.live_feed = None
        self.last_idx_candle = None
        self.last_ce_candle = None
        self.last_pe_candle = None
        self.idx_history = []
        self.ce_history = []
        self.pe_history = []
        self.last_total_volumes = {} # Track cumulative volumes to calculate deltas

@app.get("/", response_class=HTMLResponse)
async def get_live(request: Request):
    return templates.TemplateResponse("live.html", {"request": request})

@app.get("/replay", response_class=HTMLResponse)
async def get_replay(request: Request):
    return templates.TemplateResponse("replay.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket accepted")
    state = SessionState()

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
                    state.index_sym = data['index']
                    index_sym = state.index_sym
                    strategy.update_params(index_sym)
                    delta_strategy.update_params(index_sym)

                    idx_df = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000)
                    strike = dm.get_atm_strike(idx_df['close'].iloc[-1], step=100 if "BANK" in index_sym else 50)

                    state.ce_sym = dm.get_option_symbol(index_sym, strike, "C")
                    state.pe_sym = dm.get_option_symbol(index_sym, strike, "P")

                    ce_df = dm.get_data(state.ce_sym, interval=Interval.in_1_minute, n_bars=1000)
                    pe_df = dm.get_data(state.pe_sym, interval=Interval.in_1_minute, n_bars=1000)

                    # Seed history for live strategy calculation
                    idx_recs = format_records(idx_df)
                    ce_recs = format_records(ce_df)
                    pe_recs = format_records(pe_df)

                    state.idx_history = idx_recs[-100:]
                    state.ce_history = ce_recs[-100:]
                    state.pe_history = pe_recs[-100:]

                    state.ce_markers = []
                    state.pe_markers = []

                    state.last_idx_candle = idx_recs[-1]
                    state.last_ce_candle = ce_recs[-1]
                    state.last_pe_candle = pe_recs[-1]

                    # Pre-calculate historical signals for the chart
                    # Step every 5 bars to speed up initial load, or just check last 300 bars
                    start_bar = max(20, len(ce_df) - 300)
                    for i in range(start_bar, len(ce_df)):
                        last_time = ce_df.index[i]
                        # Use a sliding window for trend calculation to speed up indexing
                        sub_idx = idx_df.iloc[max(0, i-50):i+1]
                        if len(sub_idx) < 20: continue

                        trend = strategy.get_trend(sub_idx)
                        ce_setup = strategy.check_setup(ce_df.iloc[max(0, i-50):i+1], trend)
                        pe_setup = strategy.check_setup(pe_df.iloc[max(0, i-50):i+1], trend)

                        if ce_setup:
                            state.ce_markers.append({"time": ce_recs[i]['time'], "position": "belowBar", "color": "#2196F3", "shape": "arrowUp", "text": "CE BUY"})
                        if pe_setup:
                            state.pe_markers.append({"time": pe_recs[i]['time'], "position": "belowBar", "color": "#2196F3", "shape": "arrowUp", "text": "PE BUY"})

                    # Fetch Delta Volume signals from Trendlyne
                    delta_signals = await fetch_trendlyne_signals(index_sym, strike)

                    await websocket.send_json(clean_json({
                        "type": "live_data",
                        "index_data": format_records(idx_df),
                        "ce_data": ce_recs,
                        "pe_data": pe_recs,
                        "ce_markers": state.ce_markers,
                        "pe_markers": state.pe_markers,
                        "ce_symbol": state.ce_sym,
                        "pe_symbol": state.pe_sym,
                        "trend": strategy.get_trend(idx_df),
                        "delta_signals": delta_signals
                    }))

                    if state.live_feed: state.live_feed.stop()
                    loop = asyncio.get_running_loop()
                    state.live_feed = TradingViewLiveFeed(lambda u: asyncio.run_coroutine_threadsafe(handle_live_update(websocket, state, u), loop))

                    symbols = [f"NSE:{index_sym}", f"NSE:{state.ce_sym}", f"NSE:{state.pe_sym}"]
                    # Add some surrounding strikes for readiness
                    step = 100 if "BANK" in index_sym else 50
                    for offset in [-100, 100]:
                        for ot in ["C", "P"]:
                            symbols.append(f"NSE:{dm.get_option_symbol(index_sym, strike + offset, ot)}")

                    state.live_feed.start()
                    state.live_feed.add_symbols(list(set(symbols)))

                elif data['type'] == 'start_replay':
                    logger.info(f"Starting replay for {data['index']}")
                    index_sym = data['index']
                    strategy.update_params(index_sym)
                    state.replay_data_idx = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000)
                    strike = dm.get_atm_strike(state.replay_data_idx['close'].iloc[0], step=100 if "BANK" in index_sym else 50)

                    state.ce_sym = dm.get_option_symbol(index_sym, strike, "C")
                    state.pe_sym = dm.get_option_symbol(index_sym, strike, "P")
                    state.replay_data_ce = dm.get_data(state.ce_sym, interval=Interval.in_1_minute, n_bars=1000)
                    state.replay_data_pe = dm.get_data(state.pe_sym, interval=Interval.in_1_minute, n_bars=1000)

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
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Replay Loop Error: {e}")

    try:
        await asyncio.gather(listen_task(), replay_loop())
    finally:
        if state.live_feed:
            state.live_feed.stop()

def format_records(df):
    """Formats DataFrame for UI with Unix timestamps shifted to IST for presentation."""
    recs = df.copy().reset_index()
    # If the index is naive, it is IST as returned by tvDatafeed for NSE.
    # Localize to IST and convert to UTC for correct Unix timestamp.
    if recs['datetime'].dt.tz is None:
        recs['datetime'] = recs['datetime'].dt.tz_localize('Asia/Kolkata').dt.tz_convert('UTC')

    # Add Unix timestamp in seconds.
    # Shift by 5.5 hours (19800s) to force UI to show IST even if browser is in UTC.
    recs['time'] = recs['datetime'].apply(lambda x: int(x.timestamp()) + 19800)

    # Keep ISO string for reference if needed
    recs['datetime_str'] = recs['datetime'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Convert datetime objects to string to avoid JSON serializable error
    recs['datetime'] = recs['datetime_str']

    return recs.to_dict(orient='records')

async def send_replay_step(websocket, state):
    if websocket.client_state != WebSocketState.CONNECTED: return
    sub_ce = state.replay_data_ce.iloc[:state.replay_idx]
    sub_pe = state.replay_data_pe.iloc[:state.replay_idx]

    # Synchronize using UTC timestamps then shift for presentation
    last_time = sub_ce.index[-1]
    sub_idx = state.replay_data_idx[state.replay_data_idx.index <= last_time]
    if len(sub_idx) < 10: sub_idx = state.replay_data_idx.iloc[:10]

    trend = strategy.get_trend(sub_idx)
    ce_setup = strategy.check_setup(sub_ce, trend)
    pe_setup = strategy.check_setup(sub_pe, trend)

    ce_recs = format_records(sub_ce)
    pe_recs = format_records(sub_pe)

    if ce_setup:
        state.ce_markers.append({"time": ce_recs[-1]['time'], "position": "belowBar", "color": "#2196F3", "shape": "arrowUp", "text": "CE BUY"})
    if pe_setup:
        state.pe_markers.append({"time": pe_recs[-1]['time'], "position": "belowBar", "color": "#2196F3", "shape": "arrowUp", "text": "PE BUY"})

    msg = {
        "type": "replay_step",
        "index_data": format_records(sub_idx),
        "ce_data": ce_recs,
        "pe_data": pe_recs,
        "ce_markers": state.ce_markers,
        "pe_markers": state.pe_markers,
        "ce_symbol": state.ce_sym,
        "pe_symbol": state.pe_sym,
        "trend": trend,
        "max_idx": min(len(state.replay_data_ce), len(state.replay_data_pe))
    }

    cleaned = clean_json(msg)
    await websocket.send_json(cleaned)

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

async def handle_live_update(websocket, state, update):
    if websocket.client_state != WebSocketState.CONNECTED: return
    symbol = update['symbol']
    clean_symbol = symbol.replace("NSE:", "")
    is_index = clean_symbol == state.index_sym
    is_ce = clean_symbol == state.ce_sym
    is_pe = clean_symbol == state.pe_sym

    if not (is_index or is_ce or is_pe): return

    # Volume handling
    current_total_volume = update.get('volume')
    last_total_volume = state.last_total_volumes.get(symbol)

    volume_delta = 0
    if current_total_volume is not None:
        if last_total_volume is not None:
            volume_delta = max(0, current_total_volume - last_total_volume)
        else:
            # First live tick for this symbol: initialize total volume but don't add to candle
            volume_delta = 0
        state.last_total_volumes[symbol] = current_total_volume

    now = int(datetime.now().timestamp())
    interval_sec = 60
    # Apply 5.5h shift for IST presentation
    candle_time = ((now + 19800) // interval_sec) * interval_sec

    if is_index: target_candle = state.last_idx_candle
    elif is_ce: target_candle = state.last_ce_candle
    else: target_candle = state.last_pe_candle

    if target_candle is None or candle_time > target_candle['time']:
        # Save finished candle to history before starting new one
        if target_candle is not None:
            if is_index: state.idx_history.append(target_candle)
            elif is_ce: state.ce_history.append(target_candle)
            elif is_pe: state.pe_history.append(target_candle)

            # Keep only last 100 for strategy
            if len(state.idx_history) > 100: state.idx_history.pop(0)
            if len(state.ce_history) > 100: state.ce_history.pop(0)
            if len(state.pe_history) > 100: state.pe_history.pop(0)

            # Check for strategy setup on closed candle
            if is_ce or is_pe:
                if len(state.idx_history) > 20:
                    idx_df = pd.DataFrame(state.idx_history)
                    trend = strategy.get_trend(idx_df)
                    opt_df = pd.DataFrame(state.ce_history if is_ce else state.pe_history)
                    setup = strategy.check_setup(opt_df, trend)
                    if setup:
                        marker = {"time": target_candle['time'], "position": "belowBar", "color": "#2196F3", "shape": "arrowUp", "text": "BUY"}
                        if is_ce: state.ce_markers.append(marker)
                        else: state.pe_markers.append(marker)
                        await websocket.send_json(clean_json({
                            "type": "marker_update", "is_ce": is_ce, "is_pe": is_pe, "marker": marker, "signal": setup
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
        else: state.last_pe_candle = new_candle
        target_candle = new_candle

        # Every new candle, also refresh Trendlyne signals if in live mode
        if is_index:
            strike = dm.get_atm_strike(update['price'], step=100 if "BANK" in clean_symbol else 50)
            delta_signals = await fetch_trendlyne_signals(clean_symbol, strike)
            await websocket.send_json(clean_json({
                "type": "delta_signals",
                "delta_signals": delta_signals
            }))
    else:
        target_candle['close'] = update['price']
        if update['price'] > target_candle['high']: target_candle['high'] = update['price']
        if update['price'] < target_candle['low']: target_candle['low'] = update['price']
        target_candle['volume'] += volume_delta

    await websocket.send_json(clean_json({
        "type": "live_update", "symbol": update['symbol'], "candle": target_candle,
        "is_index": is_index, "is_ce": is_ce, "is_pe": is_pe
    }))


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
