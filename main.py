from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import json
import asyncio
import pandas as pd
from data.gathering.data_manager import DataManager
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
        self.is_playing = False

state = SessionState()

@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)

            if data['type'] == 'fetch_live':
                index_sym = data['index']
                idx_df = dm.get_data(index_sym, interval=Interval.in_5_minute, n_bars=100)
                if idx_df is not None:
                    trend = strategy.get_trend(idx_df)
                    last_spot = idx_df['close'].iloc[-1]
                    strike = dm.get_atm_strike(last_spot)
                    opt_type = "C" if trend == "BULLISH" else "P"
                    opt_sym = dm.get_option_symbol(index_sym, strike, opt_type)
                    opt_df = dm.get_data(opt_sym, interval=Interval.in_5_minute, n_bars=50)

                    await websocket.send_json({
                        "type": "live_data",
                        "index_data": idx_df.reset_index().to_dict(orient='records'),
                        "option_data": opt_df.reset_index().to_dict(orient='records') if opt_df is not None else [],
                        "trend": trend,
                        "option_symbol": opt_sym
                    })

            elif data['type'] == 'start_replay':
                index_sym = data['index']
                state.replay_data_idx = dm.get_data(index_sym, interval=Interval.in_5_minute, n_bars=300)
                last_spot = state.replay_data_idx['close'].iloc[0]
                strike = dm.get_atm_strike(last_spot)
                opt_sym = dm.get_option_symbol(index_sym, strike, "C")
                state.replay_data_opt = dm.get_data(opt_sym, interval=Interval.in_1_minute, n_bars=300)
                state.replay_idx = 50
                state.is_playing = True

            elif data['type'] == 'pause_replay':
                state.is_playing = False

            elif data['type'] == 'step_replay':
                if state.replay_data_opt is not None and state.replay_idx < len(state.replay_data_opt):
                    state.replay_idx += 1
                    await send_replay_step(websocket)

            if state.is_playing and state.replay_data_opt is not None:
                if state.replay_idx < len(state.replay_data_opt):
                    state.replay_idx += 1
                    await send_replay_step(websocket)
                    await asyncio.sleep(1) # Replay speed

    except Exception as e:
        print(f"WS Error: {e}")

async def send_replay_step(websocket):
    sub_opt = state.replay_data_opt.iloc[:state.replay_idx]
    sub_idx = state.replay_data_idx.iloc[:state.replay_idx // 5 + 10]

    # Strategy check
    trend = strategy.get_trend(sub_idx)
    setup = strategy.check_setup(sub_opt, trend)

    # Footprint data for last candle
    last_candle = sub_opt.iloc[-1].to_dict()
    # Mock footprint clusters
    clusters = generate_footprint_clusters(sub_opt.iloc[-1])

    await websocket.send_json({
        "type": "replay_step",
        "index_data": sub_idx.reset_index().to_dict(orient='records'),
        "option_data": sub_opt.reset_index().to_dict(orient='records'),
        "footprint": clusters,
        "signal": setup,
        "idx": state.replay_idx
    })

def generate_footprint_clusters(row):
    # Professional Footprint Data Generation
    price_step = 1.0
    low = (row['low'] // price_step) * price_step
    high = (row['high'] // price_step) * price_step
    clusters = []
    curr = low
    mid = (row['open'] + row['close']) / 2
    while curr <= high:
        dist = 1.0 - abs(curr - mid) / (max(row['high'] - row['low'], 1))
        vol = max(1, int(row['volume'] * dist / 10))
        delta_bias = (row['close'] - row['open']) / (max(row['high'] - row['low'], 1))
        buy_v = int(vol * (0.5 + 0.2 * delta_bias))
        sell_v = vol - buy_v
        clusters.append({"price": curr, "buy": buy_v, "sell": sell_v})
        curr += price_step
    return clusters

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
