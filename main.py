from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import json
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from tvDatafeed import Interval

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- MOCK DATA GENERATOR (High Fidelity) ---
def get_mock_df(symbol, n=300, interval='1min'):
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=n, freq=interval)
    base = 59000 if "BANK" in symbol else 300
    prices = base + np.cumsum(np.random.normal(0, 2, n))
    return pd.DataFrame({
        'open': prices, 'high': prices+5, 'low': prices-5, 'close': prices+1, 'volume': 5000
    }, index=dates)

def to_recs(df):
    r = df.reset_index()
    r['time'] = r['datetime'].apply(lambda x: int(x.timestamp()))
    return r[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')

@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("DEBUG: WS Connection Accepted")

    # Send dummy data immediately to test
    await websocket.send_json({"type": "hello"})

    # State
    state = {"playing": False, "idx": 150, "df_opt": None, "df_idx": None}

    async def run_replay():
        try:
            while True:
                if state["playing"] and state["df_opt"] is not None:
                    state["idx"] += 1
                    sub_opt = state["df_opt"].iloc[:state["idx"]]
                    sub_idx = state["df_idx"].iloc[:(state["idx"] // 5) + 50]

                    # Generate Footprint
                    last = sub_opt.iloc[-1]
                    fp = [{"price": float(p), "buy": 120, "sell": 90, "is_poc": p==int(last['close'])}
                          for p in range(int(last['low']), int(last['high'])+1)]

                    await websocket.send_json({
                        "type": "update",
                        "index": to_recs(sub_idx),
                        "option": to_recs(sub_opt),
                        "footprint": fp,
                        "option_symbol": "BANKNIFTY260120C59500"
                    })
                await asyncio.sleep(0.5)
        except Exception as e: print(f"DEBUG: Broadcast Error {e}")

    replay_task = asyncio.create_task(run_replay())

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            print(f"DEBUG: CMD Received: {msg['type']}")
            if msg['type'] == 'start':
                state["df_idx"] = get_mock_df("BN", 400, '5min')
                state["df_opt"] = get_mock_df("OPT", 400, '1min')
                state["idx"] = 150
                state["playing"] = True
            elif msg['type'] == 'pause':
                state["playing"] = False
    except WebSocketDisconnect:
        replay_task.cancel()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
