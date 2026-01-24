from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import uvicorn
import json
import asyncio
import numpy as np
import logging
import uuid
import httpx
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from data.gathering.data_manager import DataManager
from data.gathering.feed_manager import feed_manager
from data.gathering.mongo_manager import MongoDataManager
import config
from data.database import DatabaseManager
from core.trade_manager import PnLTracker, Trade
from core.utils import calculate_buildup, black_scholes_greeks, find_iv
from core.state_manager import MarketState, clean_json

IST_TZ = timezone(timedelta(hours=5, minutes=30))
ENGINE_URL = "http://localhost:8002/evaluate"

app = FastAPI(title="OptionScalp: Data Acquisition Hub (Cockpit v3.0 Spec)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

dm = DataManager()
db = DatabaseManager(db_path=config.DB_PATH)
mongo = MongoDataManager()

class GlobalState:
    def __init__(self):
        self.market_state = MarketState()
        self.active_trades = []
        self.pnl_tracker = PnLTracker()
        self.websocket = None
        self.is_playing = False
        self.is_live = False
        self.index_sym, self.ce_sym, self.pe_sym = "", "", ""
        self.strike_map = {} # strike -> {"ce_key": ..., "pe_key": ...}

state = GlobalState()

@app.post("/api/signal")
async def receive_signal(signal: dict):
    """Signals from Strategy Engine or Exit logic"""
    logger.info(f"Signal: {signal['strat_name']} on {signal['symbol']} Type: {signal.get('type')}")

    if signal.get('type') == 'BUY':
        new_trade = Trade(
            symbol=signal['symbol'],
            entry_price=signal['entry_price'],
            entry_time=signal.get('time', datetime.now().timestamp()),
            trade_type='LONG',
            strategy_name=signal['strat_name'],
            sl=signal.get('sl'),
            target=signal.get('target')
        )
        state.active_trades.append(new_trade)

    new_signal = {
        "id": str(uuid.uuid4()),
        "type": signal.get('type', 'BUY'),
        "price": signal['entry_price'],
        "time": signal.get('iso_time') or (datetime.fromtimestamp(signal['time'] - 19800, tz=timezone.utc).isoformat() if 'time' in signal else datetime.now(timezone.utc).isoformat()),
        "label": signal['strat_name']
    }

    if signal['symbol'] == state.index_sym:
        state.market_state.underlying['signals'].append(new_signal)
    elif signal['symbol'] == state.ce_sym:
        state.market_state.ceOption['signals'].append(new_signal)
    elif signal['symbol'] == state.pe_sym:
        state.market_state.peOption['signals'].append(new_signal)

    return {"status": "accepted"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.websocket = websocket
    logger.info("UI Connected")
    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            if data['type'] == 'fetch_live': await handle_fetch_live(data)
            elif data['type'] == 'start_replay': await handle_start_replay(data)
            elif data['type'] == 'ping': await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        state.websocket = None
        logger.info("UI Disconnected")

async def handle_start_replay(data):
    state.is_playing, state.is_live = False, False
    state.market_state = MarketState()

    idx_raw = data['index'].replace("NSE:", "")
    state.index_sym = f"NSE:{idx_raw}"
    date_str = data.get('date', datetime.now().strftime("%Y-%m-%d"))

    ref_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0)
    idx_df = dm.get_data(state.index_sym, n_bars=1, reference_date=ref_date)
    if idx_df.empty: return await state.websocket.send_json({"type": "error", "message": "No index data"})

    mapping = dm.getNiftyAndBNFnOKeys([idx_raw], {idx_raw: idx_df['close'].iloc[0]})
    if idx_raw not in mapping: return await state.websocket.send_json({"type": "error", "message": "Failed to map instruments"})

    setup_market_mapping(idx_raw, mapping[idx_raw], idx_df['close'].iloc[0])

    all_keys = list(state.market_state.rev_instrument_keys.keys())
    ticks_cursor = mongo.get_all_ticks_for_session(all_keys, date_str)

    state.is_playing = True
    asyncio.create_task(replay_engine(ticks_cursor))

def setup_market_mapping(idx_raw, mapping, spot):
    state.market_state.instrument_keys[state.index_sym] = "NSE_INDEX|Nifty Bank" if "BANK" in idx_raw else "NSE_INDEX|Nifty 50"
    state.market_state.rev_instrument_keys[state.market_state.instrument_keys[state.index_sym]] = state.index_sym

    strike = dm.get_atm_strike(spot, step=100 if "BANK" in idx_raw else 50)
    for opt in mapping['options']:
        if opt['strike'] == strike:
            state.ce_sym, state.pe_sym = f"NSE:{opt['ce_trading_symbol']}", f"NSE:{opt['pe_trading_symbol']}"
            for k, s in [(opt['ce'], state.ce_sym), (opt['pe'], state.pe_sym)]:
                state.market_state.instrument_keys[s] = k
                state.market_state.rev_instrument_keys[k] = s
        state.strike_map[opt['strike']] = {"ce_key": opt['ce'], "pe_key": opt['pe']}
        state.market_state.rev_instrument_keys[opt['ce']] = f"CE_{opt['strike']}"
        state.market_state.rev_instrument_keys[opt['pe']] = f"PE_{opt['strike']}"

async def replay_engine(cursor):
    last_emit_time = 0
    for doc in cursor:
        if not state.is_playing: break
        await process_tick(doc)
        curr_ts = doc['_insertion_time'].timestamp()
        if curr_ts - last_emit_time >= 1.0:
            if state.websocket: await state.websocket.send_json(clean_json(state.market_state.to_dict()))
            last_emit_time = curr_ts
            await asyncio.sleep(0.01)

async def process_tick(doc):
    key = doc.get('instrumentKey') or doc.get('instrument_key')
    ff = doc.get('fullFeed', {})
    data = ff.get('marketFF') or ff.get('indexFF')
    if not data: return

    sym = state.market_state.rev_instrument_keys.get(key)
    ltp = data.get('ltpc', {}).get('ltp')
    if ltp is None: return

    tick = calculate_tick_metrics(key, data, ltp)

    closed = False
    if sym == state.index_sym:
        state.market_state.underlying['tick'] = tick
        closed = update_history(state.index_sym, state.market_state.underlying['history'], ltp, tick['vtt'], doc['_insertion_time'])
    elif sym == state.ce_sym:
        state.market_state.ceOption['tick'] = tick
        closed = update_history(state.ce_sym, state.market_state.ceOption['history'], ltp, tick['vtt'], doc['_insertion_time'])
    elif sym == state.pe_sym:
        state.market_state.peOption['tick'] = tick
        closed = update_history(state.pe_sym, state.market_state.peOption['history'], ltp, tick['vtt'], doc['_insertion_time'])

    if closed: await trigger_engine(doc['_insertion_time'])
    check_trade_exits(tick, sym)
    update_oi_data(key, tick)

def calculate_tick_metrics(key, data, ltp):
    current_oi = int(data.get('oi', 0))
    start_oi = state.market_state.session_start_oi.get(key)
    if start_oi is None:
        state.market_state.session_start_oi[key] = current_oi
        start_oi = current_oi

    oi_change = current_oi - start_oi
    tick = {
        "ltp": ltp, "ltq": int(data.get('ltpc', {}).get('ltq', 0)),
        "atp": data.get('atp', ltp), "vtt": int(data.get('vtt', 0)),
        "oi": current_oi, "oiChange": oi_change,
        "oiChangePct": round((oi_change/start_oi*100) if start_oi>0 else 0, 2),
        "iv": 0, "tbq": int(data.get('tbq', 0)), "tsq": int(data.get('tsq', 0))
    }
    prev_p, prev_oi = state.market_state.last_price.get(key, ltp), state.market_state.last_oi.get(key, current_oi)
    tick['buildup'] = calculate_buildup(ltp - prev_p, current_oi - prev_oi)
    state.market_state.last_price[key], state.market_state.last_oi[key] = ltp, current_oi

    greeks = data.get('optionGreeks', {})
    tick.update({k: greeks.get(k, 0) for k in ['delta', 'theta', 'gamma', 'vega']})
    return tick

def update_history(sym, history, price, vtt, timestamp):
    iso_time = timestamp.replace(second=0, microsecond=0, tzinfo=timezone.utc).isoformat()
    if not history or history[-1]['time'] != iso_time:
        state.market_state.candle_start_vtt[sym] = vtt
        history.append({"time": iso_time, "open": price, "high": price, "low": price, "close": price, "volume": 0})
        if len(history) > 100: history.pop(0)
        return True
    else:
        candle = history[-1]
        candle['high'], candle['low'], candle['close'] = max(candle['high'], price), min(candle['low'], price), price
        candle['volume'] = max(0, vtt - state.market_state.candle_start_vtt.get(sym, vtt))
        return False

def check_trade_exits(tick, sym):
    for trade in state.active_trades[:]:
        if trade.symbol == sym:
            lp, closed = tick['ltp'], False
            if lp <= trade.sl: closed, reason = True, "SL"
            elif lp >= trade.target: closed, reason = True, "TARGET"
            if closed:
                trade.close(lp, datetime.now(timezone.utc).timestamp(), reason)
                asyncio.create_task(receive_signal({"strat_name": trade.strategy_name, "symbol": trade.symbol, "entry_price": lp, "type": "EXIT", "reason": reason}))
                state.active_trades.remove(trade)

def update_oi_data(key, tick):
    for strike, keys in state.strike_map.items():
        if key in [keys['ce_key'], keys['pe_key']]:
            side = 'callOi' if key == keys['ce_key'] else 'putOi'
            found = False
            for row in state.market_state.oiData:
                if row['strike'] == strike:
                    row[side], row[side+'Change'], found = tick['oi'], tick['oiChange'], True
                    break
            if not found:
                state.market_state.oiData.append({"strike": strike, "callOi": tick['oi'] if side=='callOi' else 0, "putOi": tick['oi'] if side=='putOi' else 0, "callOiChange": tick['oiChange'] if side=='callOi' else 0, "putOiChange": tick['oiChange'] if side=='putOi' else 0})

    total_c = sum(row['callOi'] for row in state.market_state.oiData)
    total_p = sum(row['putOi'] for row in state.market_state.oiData)
    if total_c > 0:
        new_pcr = round(total_p / total_c, 2)
        state.market_state.pcrChange, state.market_state.pcr = round(new_pcr - state.market_state.pcr, 4), new_pcr

async def trigger_engine(timestamp):
    payload = {
        "index_sym": state.index_sym, "ce_sym": state.ce_sym, "pe_sym": state.pe_sym,
        "index_data": state.market_state.underlying['history'], "ce_data": state.market_state.ceOption['history'], "pe_data": state.market_state.peOption['history'],
        "pcr_insights": {"pcr": state.market_state.pcr, "pcr_change": state.market_state.pcrChange, "buildup_status": state.market_state.underlying['tick'].get('buildup', 'Neutral')},
        "candle_time": int(timestamp.timestamp()) + 19800
    }
    try:
        async with httpx.AsyncClient() as client: await client.post(ENGINE_URL, json=payload, timeout=1.0)
    except: pass

async def handle_fetch_live(data):
    state.is_playing, state.is_live = False, True
    def callback(upd): asyncio.run_coroutine_threadsafe(process_tick_live(upd), asyncio.get_event_loop())
    feed_manager.subscribe(callback)
    # Subscription logic would go here

async def process_tick_live(update):
    # Map update fields to MongoDB-like doc and call process_tick
    doc = {
        "instrumentKey": update['symbol'],
        "_insertion_time": datetime.now(timezone.utc),
        "fullFeed": {"marketFF": {"ltpc": {"ltp": update['price'], "ltq": update.get('ltq', 0)}, "vtt": update.get('volume', 0), "oi": update.get('oi', 0)}}
    }
    await process_tick(doc)

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8001)
