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
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from data.gathering.tv_feed import TvFeed
from core.strategies.trend_following import TrendFollowingStrategy
from tvDatafeed import Interval

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class DataManager:
    def __init__(self):
        self.feed = TvFeed()

    def get_atm_strike(self, spot_price, step=100):
        return int(round(spot_price / step) * step)

    def get_next_expiry(self, index="BANKNIFTY"):
        today_str = datetime.now().strftime("%y%m%d")
        print(f"Calculating next expiry for {index} as of {today_str}")
        if "BANKNIFTY" in index:
            # Monthly/Long expiries for BANKNIFTY 2026
            expires = ["260127", "260224", "260326", "260330", "260331", "260630", "260929", "261229"]
        else:
            # Weekly expiries for NIFTY 2026
            expires = [  "260127", "260203", "260210", "260217", "260224", "260326", "260330", "260331"]
        for exp in expires:
            if exp >= today_str:
                return exp
        return expires[-1]

    def get_option_symbol(self, index, strike, opt_type, expiry=None):
        if expiry is None:
            expiry = self.get_next_expiry(index)
        return f"{index}{expiry}{opt_type}{int(strike)}"

    def get_data(self, symbol, interval=Interval.in_5_minute, n_bars=1000):
        df = None
        try:
            df = self.feed.get_historical_data(symbol, exchange="NSE", interval=interval, n_bars=n_bars)
        except Exception as e:
            print(f"TvFeed error: {e}")

        if df is None or df.empty:
            print(f"Warning: Generating mock data for {symbol}.")
            start_price = 59000 if "BANKNIFTY" in symbol else 25000
            if "C" in symbol or "P" in symbol: start_price = 300

            freq = '1min' if interval == Interval.in_1_minute else '5min'
            dates = pd.date_range(end=datetime.now().replace(second=0, microsecond=0), periods=n_bars, freq=freq)
            prices = np.cumsum(np.random.normal(0, 5, n_bars)) + start_price
            data = {
                'open': prices,
                'high': prices + np.random.uniform(2, 8, n_bars),
                'low': prices - np.random.uniform(2, 8, n_bars),
                'close': prices + np.random.normal(0, 3, n_bars),
                'volume': np.random.randint(1000, 10000, n_bars)
            }
            df = pd.DataFrame(data, index=dates)
            df.index.name = 'datetime'
        return df

dm = DataManager()
strategy = TrendFollowingStrategy()

class SessionState:
    def __init__(self):
        self.replay_idx = 0
        self.replay_data_idx = None
        self.replay_data_opt = None
        self.opt_sym = ""
        self.is_playing = False
        self.all_markers = []

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
            while True:
                try:
                    msg = await websocket.receive_text()
                    logger.info(f"Received message: {msg}")
                    data = json.loads(msg)
                except WebSocketDisconnect:
                    print("WebSocket disconnected")
                    break
                except Exception as e:
                    print(f"Message error: {e}")
                    continue

                if data['type'] == 'fetch_live':
                    # print(f"Fetching live data for {data['index']}")
                    state.is_playing = False
                    index_sym = data['index']
                    strategy.update_params(index_sym)
                    idx_df = dm.get_data(index_sym, interval=Interval.in_5_minute, n_bars=1000)
                    trend = strategy.get_trend(idx_df)
                    strike = dm.get_atm_strike(idx_df['close'].iloc[-1], step=100 if "BANK" in index_sym else 50)
                    opt_type = "C" if trend == "BULLISH" else "P"
                    opt_sym = dm.get_option_symbol(index_sym, strike, opt_type)
                    opt_df = dm.get_data(opt_sym, interval=Interval.in_1_minute, n_bars=1000)

                    state.opt_sym = opt_sym
                    state.all_markers = []

                    await websocket.send_json({
                        "type": "live_data",
                        "index_data": format_records(idx_df),
                        "option_data": format_records(opt_df),
                        "option_symbol": opt_sym,
                        "trend": trend
                    })

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
            while True:
                if state.is_playing and state.replay_data_opt is not None:
                    # print(f"Replay loop step: {state.replay_idx}")
                    if state.replay_idx < len(state.replay_data_opt):
                        state.replay_idx += 1
                        await send_replay_step(websocket, state)
                    else:
                        state.is_playing = False
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Replay Loop Error: {e}")

    await asyncio.gather(listen_task(), replay_loop())

def format_records(df):
    recs = df.reset_index()
    recs['datetime'] = recs['datetime'].dt.strftime('%Y-%m-%dT%H:%M:%S')
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

    # Ensure everything is JSON serializable
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
        return obj

    cleaned = clean_json(msg)
    await websocket.send_json(cleaned)

def generate_footprint_clusters(row):
    price_step = 1.0
    mid = (row['open'] + row['close']) / 2
    low = (row['low'] // price_step) * price_step
    high = (row['high'] // price_step) * price_step
    clusters = []
    curr = low
    while curr <= high:
        dist = max(0.1, 1.0 - abs(curr - mid) / (max(row['high'] - row['low'], 1)))
        vol = int(row['volume'] * dist / 20)
        dbias = (row['close'] - row['open']) / (max(row['high'] - row['low'], 1))
        buy_v = int(vol * (0.5 + 0.2 * dbias))
        sell_v = max(0, vol - buy_v)
        clusters.append({
            "price": round(curr, 1), "buy": buy_v, "sell": sell_v,
            "is_poc": abs(curr - mid) < price_step
        })
        curr += price_step
    return clusters

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
