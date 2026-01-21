from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketState
import uvicorn
import json
import asyncio
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from data.gathering.data_manager import DataManager
from data.gathering.live_feed import TradingViewLiveFeed
from core.strategies.trend_following import TrendFollowingStrategy
from tvDatafeed import Interval

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

dm = DataManager()
strategy = TrendFollowingStrategy()

class SessionState:
    def __init__(self):
        self.replay_idx = 0
        self.replay_data_idx = None
        self.replay_data_opt = None
        self.opt_sym = ""
        self.index_sym = ""
        self.is_playing = False
        self.is_live = False
        self.all_markers = []
        self.live_feed = None
        self.last_idx_candle = None
        self.last_opt_candle = None

@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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

                    # Fetch current day's data (n_bars=1000 should cover it)
                    idx_df = dm.get_data(index_sym, interval=Interval.in_5_minute, n_bars=1000)
                    trend = strategy.get_trend(idx_df)
                    strike = dm.get_atm_strike(idx_df['close'].iloc[-1], step=100 if "BANK" in index_sym else 50)
                    opt_type = "C" if trend == "BULLISH" else "P"
                    state.opt_sym = dm.get_option_symbol(index_sym, strike, opt_type)
                    opt_sym = state.opt_sym
                    opt_df = dm.get_data(opt_sym, interval=Interval.in_1_minute, n_bars=1000)

                    state.all_markers = []
                    state.last_idx_candle = idx_df.iloc[-1].to_dict()
                    state.last_idx_candle['time'] = int(idx_df.index[-1].timestamp())
                    state.last_opt_candle = opt_df.iloc[-1].to_dict()
                    state.last_opt_candle['time'] = int(opt_df.index[-1].timestamp())

                    await websocket.send_json(clean_json({
                        "type": "live_data",
                        "index_data": format_records(idx_df),
                        "option_data": format_records(opt_df),
                        "option_symbol": opt_sym,
                        "trend": trend,
                        "footprint": generate_footprint_clusters(opt_df.iloc[-1])
                    }))

                    # Setup Live Feed
                    if state.live_feed:
                        state.live_feed.stop()

                    loop = asyncio.get_running_loop()
                    def live_callback(update):
                        asyncio.run_coroutine_threadsafe(
                            handle_live_update(websocket, state, update),
                            loop
                        )

                    state.live_feed = TradingViewLiveFeed(live_callback)
                    # Symbols in TV are like NSE:NIFTY
                    tv_index = f"NSE:{index_sym}"
                    tv_option = f"NSE:{opt_sym}"
                    state.live_feed.start()
                    state.live_feed.add_symbols([tv_index, tv_option])

                elif data['type'] == 'start_replay':
                    logger.info(f"Starting replay for {data['index']}")
                    index_sym = data['index']
                    strategy.update_params(index_sym)
                    # Use a larger window for index to have history
                    state.replay_data_idx = dm.get_data(index_sym, interval=Interval.in_5_minute, n_bars=1000)

                    # Initial trend detection to pick CE/PE
                    initial_idx_slice = state.replay_data_idx.iloc[:50//5 + 10]
                    trend = strategy.get_trend(initial_idx_slice)
                    strike = dm.get_atm_strike(state.replay_data_idx['close'].iloc[0], step=100 if "BANK" in index_sym else 50)
                    opt_type = "C" if trend == "BULLISH" else "P"

                    state.opt_sym = dm.get_option_symbol(index_sym, strike, opt_type)
                    state.replay_data_opt = dm.get_data(state.opt_sym, interval=Interval.in_1_minute, n_bars=1000)
                    state.replay_idx = 50
                    state.all_markers = []
                    state.is_playing = True

                    await websocket.send_json({
                        "type": "replay_info",
                        "max_idx": len(state.replay_data_opt),
                        "current_idx": state.replay_idx,
                        "option_symbol": state.opt_sym
                    })
                    await send_replay_step(websocket, state)

                elif data['type'] == 'set_replay_index':
                    state.replay_idx = data['index']
                    await send_replay_step(websocket, state)

                elif data['type'] == 'pause_replay':
                    state.is_playing = False

                elif data['type'] == 'step_replay':
                    if state.replay_data_opt is not None and state.replay_idx < len(state.replay_data_opt):
                        state.replay_idx += 1
                        await send_replay_step(websocket, state)
        except Exception as e:
            logger.exception("Listen Error")

    async def replay_loop():
        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                if state.is_playing and state.replay_data_opt is not None:
                    # print(f"Replay loop step: {state.replay_idx}")
                    if state.replay_idx < len(state.replay_data_opt):
                        state.replay_idx += 1
                        await send_replay_step(websocket, state)
                    else:
                        state.is_playing = False
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Replay Loop Error: {e}")

    try:
        await asyncio.gather(listen_task(), replay_loop())
    finally:
        if state.live_feed:
            state.live_feed.stop()

def format_records(df):
    """Formats DataFrame for UI with Unix timestamps (UTC)."""
    recs = df.copy().reset_index()
    # If the index is naive, assume it is UTC as tvDatafeed typically returns UTC for historical data
    if recs['datetime'].dt.tz is None:
        recs['datetime'] = recs['datetime'].dt.tz_localize('UTC')

    # Add Unix timestamp in seconds for lightweight-charts
    recs['time'] = recs['datetime'].apply(lambda x: int(x.timestamp()))

    # Keep ISO string for reference if needed
    recs['datetime_str'] = recs['datetime'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Convert datetime objects to string to avoid JSON serializable error
    recs['datetime'] = recs['datetime_str']

    return recs.to_dict(orient='records')

async def send_replay_step(websocket, state):
    if websocket.client_state != WebSocketState.CONNECTED: return
    logger.info(f"Sending replay step {state.replay_idx}")
    sub_opt = state.replay_data_opt.iloc[:state.replay_idx]

    # Synchronize index data based on timestamp of the last option candle
    last_opt_time = sub_opt.index[-1]
    sub_idx = state.replay_data_idx[state.replay_data_idx.index <= last_opt_time]

    # Ensure at least some index data is shown
    if len(sub_idx) < 10:
        sub_idx = state.replay_data_idx.iloc[:10]

    trend = strategy.get_trend(sub_idx)
    setup = strategy.check_setup(sub_opt, trend)
    clusters = generate_footprint_clusters(sub_opt.iloc[-1])

    opt_recs = format_records(sub_opt)
    if setup:
        state.all_markers.append({
            "time": opt_recs[-1]['datetime'],
            "position": "belowBar", "color": "#2196F3", "shape": "arrowUp", "text": "BUY"
        })

    # setup is either None or a dict. If it's a dict, we can send it.
    msg = {
        "type": "replay_step",
        "index_data": format_records(sub_idx),
        "option_data": opt_recs,
        "footprint": clusters,
        "signal": setup if setup else None,
        "markers": state.all_markers,
        "option_symbol": state.opt_sym
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

async def handle_live_update(websocket, state, update):
    if websocket.client_state != WebSocketState.CONNECTED: return

    # update: {"symbol": "...", "price": ..., "volume": ..., "timestamp": ...}
    is_index = state.index_sym in update['symbol']

    # In a real app, we'd aggregate ticks into candles.
    # For now, let's just update the last candle or create a new one if time has passed.
    now = int(datetime.now().timestamp())
    interval_sec = 300 if is_index else 60
    candle_time = (now // interval_sec) * interval_sec

    target_candle = state.last_idx_candle if is_index else state.last_opt_candle

    if target_candle is None or candle_time > target_candle['time']:
        # New candle
        new_candle = {
            "time": candle_time,
            "open": update['price'],
            "high": update['price'],
            "low": update['price'],
            "close": update['price'],
            "volume": update['volume'] if update['volume'] else 0
        }
        if is_index: state.last_idx_candle = new_candle
        else: state.last_opt_candle = new_candle
        target_candle = new_candle
    else:
        # Update existing candle
        target_candle['close'] = update['price']
        if update['price'] > target_candle['high']: target_candle['high'] = update['price']
        if update['price'] < target_candle['low']: target_candle['low'] = update['price']
        if update['volume']: target_candle['volume'] = update['volume']

    msg = {
        "type": "live_update",
        "symbol": update['symbol'],
        "candle": target_candle,
        "is_index": is_index
    }

    # If it's an option update, we might also want to send footprint
    if not is_index:
        msg["footprint"] = generate_footprint_clusters(target_candle)

    await websocket.send_json(clean_json(msg))

def generate_footprint_clusters(row):
    """Generates footprint clusters from a candle row (Series or dict)."""
    try:
        price_step = 1.0
        # Handle both pandas Series and dict
        open_p = row.get('open') if isinstance(row, dict) else row['open']
        close_p = row.get('close') if isinstance(row, dict) else row['close']
        high_p = row.get('high') if isinstance(row, dict) else row['high']
        low_p = row.get('low') if isinstance(row, dict) else row['low']
        volume = row.get('volume') if isinstance(row, dict) else row['volume']

        mid = (open_p + close_p) / 2
        low_bound = (low_p // price_step) * price_step
        high_bound = (high_p // price_step) * price_step

        clusters = []
        curr = low_bound
        range_val = max(high_p - low_p, 1.0)

        while curr <= high_bound:
            dist = max(0.1, 1.0 - abs(curr - mid) / range_val)
            vol = int(volume * dist / 20)
            dbias = (close_p - open_p) / range_val
            buy_v = int(vol * (0.5 + 0.2 * dbias))
            sell_v = max(0, vol - buy_v)
            clusters.append({
                "price": round(float(curr), 1),
                "buy": int(buy_v),
                "sell": int(sell_v),
                "is_poc": abs(curr - mid) < price_step
            })
            curr += price_step
        return clusters
    except Exception as e:
        logger.error(f"Error generating footprint: {e}")
        return []

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
