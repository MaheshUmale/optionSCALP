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
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PCR Cache Setup
PCR_CACHE_DIR = Path(__file__).parent / "data" / "pcr_cache"
PCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

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
db = DatabaseManager(db_path=config.DB_PATH)
tl_client = TrendlyneClient()
tl_adv = TrendlyneScalper()

class SessionState:
    def __init__(self):
        self.reset_strategies()
        self.reset_trading_state()
        self.pcr_insights = {}
        self.buildup_history = []
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
        self.last_idx_candle = None
        self.last_ce_candle = None
        self.last_pe_candle = None
        self.idx_history = []
        self.ce_history = []
        self.pe_history = []
        self.last_total_volumes = {} # Track cumulative volumes to calculate deltas
        self.upstox_client = None
        self.websocket = None
        self.subscribed_symbols = set()
        self.last_subscribed_candle = {} # symbol -> candle
        self.subscribed_history = {} # symbol -> list of candles
        self.last_trendlyne_fetch = 0 # timestamp
        self.cached_delta_signals = None
        self.last_pcr_store_ts = 0
        self.daily_pcr_history = {} # timestamp_str (HH:MM) -> {pcr, pcr_change, call_oi, put_oi}

    def reset_strategies(self):
        """Recreate strategy instances to clear internal variables."""
        self.strategies = {
            "CE": [s() for s in STRATEGIES],
            "PE": [s() for s in STRATEGIES],
            "INDEX": [s() for s in STRATEGIES]
        }
        self.tf_main = TrendFollowingStrategy()

    def load_trades_from_db(self):
        """Load trades from DB into PnLTracker for UI consistency."""
        # DISABLED to ensure PnL starts from 0 in replay/backtest
        return
        # try:
        #     trades_df = db.get_trades()
        #     if trades_df.empty: return
        #
        #     # Filter for today or relevant session if needed
        #     # For now, we load all to show history or filtered by strategy
        #     for _, row in trades_df.iterrows():
        #         t = Trade(
        #             symbol=row['symbol'],
        #             entry_price=row['entry_price'],
        #             strategy_name=row['strategy_name'],
        #             trade_type=row['trade_type'],
        #             time=row['entry_time']
        #         )
        #         t.status = row['status']
        #         t.exit_price = row['exit_price']
        #         t.exit_time = row['exit_time']
        #         t.sl = row['sl']
        #         t.target = row['target']
        #         t.pnl = row['pnl'] if row['pnl'] else 0.0
        #         t.exit_reason = row['exit_reason']
        #         t.db_id = row['id']
        #         
        #         self.pnl_tracker.trades.append(t)
        #         if t.status == "OPEN":
        #             self.active_trades.append(t)
        #     
        #     self.pnl_tracker.update_stats()
        #     logger.info(f"Loaded {len(self.pnl_tracker.trades)} trades from DB.")
        # except Exception as e:
        #     logger.error(f"Error loading trades from DB: {e}")

    def reset_trading_state(self):
        """Reset trades, PnL, and markers."""
        self.active_trades = []
        self.pnl_tracker = PnLTracker()  # Create fresh instance to reset to 0
        self.last_trade_close_times = {}
        self.ce_markers = []
        self.pe_markers = []
        self.last_total_volumes = {}

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Main professional dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Legacy routes (deprecated - kept for backwards compatibility)
@app.get("/live", response_class=HTMLResponse)
async def get_live(request: Request):
    return templates.TemplateResponse("live.html", {"request": request})

@app.get("/live_index", response_class=HTMLResponse)
async def get_live_index(request: Request):
    return templates.TemplateResponse("live_index.html", {"request": request})

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
                    state.reset_strategies()
                    state.reset_trading_state()
                    await websocket.send_json({"type": "reset_ui"})
                    
                    # Load historical trades from DB to populate panels
                    state.load_trades_from_db()

                    index_raw = data['index'].replace("NSE:", "")
                    state.index_sym = f"NSE:{index_raw}"
                    index_sym = index_raw # base symbol for DataManager
                    state.tf_main.update_params(index_sym)

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
                        check_trade_exits(state, sub_idx, sub_ce, sub_pe, store_db=False)

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
                            "type": "LONG" if "PE" not in t.symbol else "SHORT",
                            "reason": getattr(t, 'reason', '')
                        })

                    # Build strategy performance report
                    strategy_report = {}
                    for t in state.pnl_tracker.trades:
                        s_name = t.strategy_name
                        if s_name not in strategy_report:
                            strategy_report[s_name] = {"pnl": 0, "win": 0, "loss": 0, "total": 0}
                        strategy_report[s_name]["total"] += 1
                        if t.status == 'CLOSED':
                            strategy_report[s_name]["pnl"] += t.pnl
                            if t.pnl > 0:
                                strategy_report[s_name]["win"] += 1
                            else:
                                strategy_report[s_name]["loss"] += 1

                    for s in strategy_report:
                        strategy_report[s]["win_rate"] = round(
                            (strategy_report[s]["win"] / strategy_report[s]["total"] * 100), 1
                        ) if strategy_report[s]["total"] > 0 else 0
                        strategy_report[s]["pnl"] = round(strategy_report[s]["pnl"], 2)

                    # Build active positions list
                    active_positions = []
                    for t in state.active_trades:
                        active_positions.append({
                            "symbol": t.symbol,
                            "entry_price": t.entry_price,
                            "current_price": t.entry_price,  # Will be updated by live ticks
                            "quantity": getattr(t, 'quantity', 1),
                            "pnl": 0,  # Will be calculated on updates
                            "strategy": t.strategy_name
                        })

                    try:
                        if websocket.client_state == WebSocketState.CONNECTED:
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
                                "trend": state.tf_main.get_trend(idx_df.iloc[-50:], state.pcr_insights) if not idx_df.empty else "NEUTRAL",
                                "delta_signals": delta_signals,
                                "pcr_insights": state.pcr_insights,
                                "pnl_stats": state.pnl_tracker.get_stats(),
                                "new_signals": historical_signals,
                                "strategy_report": strategy_report,
                                "active_positions": active_positions # Send positions
                            }))
                    except (RuntimeError, WebSocketDisconnect):
                        logger.warning("WebSocket closed during send. Stopping loop.")
                        break
                    except Exception as e:
                        # Catch ClientDisconnected from uvicorn which might not be imported but happens
                        if "ClientDisconnected" in str(e) or "1006" in str(e):
                             logger.warning("Client disconnected.")
                             break
                        logger.error(f"Error in listen loop: {e}")
                        continue

                    feed_manager.subscribe(live_callback)
                    
                    # Start PCR Sync Task
                    asyncio.create_task(pcr_update_task(websocket, state))


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
                    index_raw = data['index'].replace("NSE:", "")
                    logger.info(f"Starting replay for {index_raw} at {data.get('date', 'now')}")
                    state.is_playing = False
                    state.is_live = False
                    # Reset state for new replay
                    state.reset_strategies()
                    state.reset_trading_state()
                    await websocket.send_json({"type": "reset_ui"})

                    state.index_sym = f"NSE:{index_raw}"
                    index_sym = index_raw

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
                    
                    # Fetch Full Day 5-min PCR Map
                    logger.info(f"About to fetch historical PCR for {index_sym}...")
                    state.daily_pcr_history = await fetch_historical_pcr(index_sym, ref_date or datetime.now())
                    logger.info(f"Loaded {len(state.daily_pcr_history)} historical PCR records for replay.")
                    
                    # Debug: Print first few entries
                    if state.daily_pcr_history:
                        sample_keys = list(state.daily_pcr_history.keys())[:3]
                        for k in sample_keys:
                            logger.info(f"  Sample PCR at {k}: {state.daily_pcr_history[k]}")

                    logger.info(f"Replay init for {index_sym} on {data.get('date')}")
                    state.tf_main.update_params(index_sym)
                    state.replay_data_idx = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
                    if not state.replay_data_idx.empty:
                        state.replay_data_idx = state.replay_data_idx.between_time('03:45', '10:00')

                    if state.replay_data_idx.empty:
                        await websocket.send_json({"type": "error", "message": f"No data found for {index_sym} in market hours."})
                        return

                    strike = dm.get_atm_strike(state.replay_data_idx['close'].iloc[0], step=100 if "BANK" in index_sym else 50)

                    # Ensure consistent prefixing for Replay mode
                    state.ce_sym = f"NSE:{dm.get_option_symbol(index_sym, strike, 'C', reference_date=ref_date)}"
                    state.pe_sym = f"NSE:{dm.get_option_symbol(index_sym, strike, 'P', reference_date=ref_date)}"
                    state.replay_data_ce = dm.get_data(state.ce_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
                    state.replay_data_pe = dm.get_data(state.pe_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)

                    if not state.replay_data_ce.empty: state.replay_data_ce = state.replay_data_ce.between_time('03:45', '10:00')
                    if not state.replay_data_pe.empty: state.replay_data_pe = state.replay_data_pe.between_time('03:45', '10:00')

                    if state.replay_data_ce.empty or state.replay_data_pe.empty:
                        logger.error(f"Replay Error: Missing options data. CE: {len(state.replay_data_ce)}, PE: {len(state.replay_data_pe)}")
                        await websocket.send_json({"type": "error", "message": f"Option data not found for {state.ce_sym} or {state.pe_sym} in market hours."})
                        return

                    state.replay_idx = 1
                    state.ce_markers = []
                    state.pe_markers = []
                    state.is_playing = True
                    
                    logger.info(f"Replay ready. Max Index: {min(len(state.replay_data_ce), len(state.replay_data_pe))}")

                    # Start Replay Loop
                    asyncio.create_task(replay_loop(websocket, state))


                    await websocket.send_json({
                        "type": "replay_info",
                        "max_idx": min(len(state.replay_data_ce), len(state.replay_data_pe)),
                        "current_idx": state.replay_idx
                    })
                    await send_replay_step(websocket, state)

                elif data['type'] == 'replay_control':
                    action = data.get('action')
                    if action == 'play':
                        state.is_playing = True
                        asyncio.create_task(replay_loop(websocket, state))
                        logger.info("Replay RESUMED")
                    elif action == 'pause':
                        state.is_playing = False
                        logger.info("Replay PAUSED")

                elif data['type'] == 'run_backtest':
                    await run_full_backtest(websocket, state, data['index'], data.get('date', '2026-01-22'))


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
                        logger.info(f"Resolved {sub_sym} to Upstox key: {inst_key}")
                        if inst_key:
                             # Resolve the actual trading symbol from the master to ensure consistency
                             live_feed.add_symbols([{"symbol": sub_sym, "key": inst_key}])
                        else:
                             # Fallback: use sub_sym as both if not found in master
                             logger.warning(f"Could not resolve Upstox key for {sub_sym}, using fallback")
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

                        # Also send existing MARKERS for this symbol
                        markers_to_send = []
                        if sub_sym == state.ce_sym:
                            markers_to_send = state.ce_markers
                        elif sub_sym == state.pe_sym:
                            markers_to_send = state.pe_markers
                        
                        if markers_to_send:
                            await websocket.send_json(clean_json({
                                "type": "marker_history",
                                "symbol": sub_sym,
                                "markers": markers_to_send
                            }))
                            logger.info(f"Sent {len(markers_to_send)} historical markers for {sub_sym}")


        except Exception as e:
            logger.exception("Listen Error")


    try:
        await listen_task()
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

def get_sentiment_from_buildup(buildup_status):
    """
    Maps buildup status to sentiment for UI coloring.
    
    SHORT COVERING & LONG BUILD = BULLISH (Price ↑, buyers active)
    SHORT BUILD & LONG UNWINDING = BEARISH (Price ↓, sellers active)
    
    Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    if not buildup_status:
        return 'NEUTRAL'
    
    status_upper = str(buildup_status).upper()
    
    # BULLISH scenarios: Prices rising, buyers entering/sellers fleeing
    if 'LONG BUILD' in status_upper or 'SHORT COVER' in status_upper:
        return 'BULLISH'
    
    # BEARISH scenarios: Prices falling, sellers entering/buyers fleeing
    if 'LONG UNWINDING' in status_upper or 'SHORT BUILD' in status_upper or 'LONG UNWIND' in status_upper:
        return 'BEARISH'
    
    return 'NEUTRAL'

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

async def send_replay_step(websocket, state, send=True):
    try:
        # 1. Basic Validation
        if send and websocket.client_state != WebSocketState.CONNECTED: return
        if state.replay_data_ce is None or state.replay_data_pe is None or state.replay_data_idx is None: return

        # 2. Slice Data (Send all data from the start of the day up to the current replay index)
        sub_ce = state.replay_data_ce.iloc[0:state.replay_idx]
        sub_pe = state.replay_data_pe.iloc[0:state.replay_idx]
        if sub_ce.empty or sub_pe.empty: return

        last_time = sub_ce.index[-1]
        # Matching slice for index
        sub_idx = state.replay_data_idx[state.replay_data_idx.index <= last_time]
        
        if sub_ce.empty or sub_pe.empty:
            with open("replay_debug.log", "a") as f:
                f.write(f"ABORT OPTION: Idx={state.replay_idx}, CE={len(sub_ce)}, PE={len(sub_pe)}\n")
            logger.warning(f"Replay Step Aborted: Options slice empty. CE={len(sub_ce)}, PE={len(sub_pe)}")
            return

        if sub_idx.empty:
             with open("replay_debug.log", "a") as f:
                f.write(f"ABORT INDEX: Idx={state.replay_idx}, Time={last_time}, IndexLen={len(idx_full)}\n")
             logger.warning(f"Replay Step Aborted: Index slice empty for time {last_time} (Index Len: {len(idx_full)})")
             return

        # 3. Initialize Context
        if not state.pcr_insights:
            state.pcr_insights = {'pcr': 1.0, 'pcr_change': 1.0, 'buildup_status': 'NEUTRAL'}

        # Update buildup status from history if available
        hist_buildup = get_buildup_for_time(state.buildup_history, last_time)
        if hist_buildup:
            state.pcr_insights['buildup_status'] = hist_buildup
            # Add sentiment based on buildup
            state.pcr_insights['sentiment'] = get_sentiment_from_buildup(hist_buildup)
            print(f"DEBUG: Buildup: {hist_buildup}, Sentiment: {state.pcr_insights['sentiment']}")
        else:
            state.pcr_insights.setdefault('sentiment', 'NEUTRAL')
            
        # Update PCR from Historical Map (Smart Fallback)
        # Convert UTC last_time to IST for matching with PCR history keys
        time_str = last_time.astimezone(IST_TZ).strftime("%H:%M")
        
        if state.daily_pcr_history:
            # Try exact match first
            if time_str in state.daily_pcr_history:
                rec = state.daily_pcr_history[time_str]
                state.pcr_insights['pcr'] = rec['pcr']
                state.pcr_insights['call_oi'] = rec.get('call_oi') or rec.get('total_call_oi')
                state.pcr_insights['put_oi'] = rec.get('put_oi') or rec.get('total_put_oi')
            else:
                # Smart fallback: find nearest PCR within 5 minutes
                nearest_pcr = find_nearest_pcr(state.daily_pcr_history, last_time.astimezone(IST_TZ), max_gap_minutes=5)
                
                if nearest_pcr:
                    state.pcr_insights['pcr'] = nearest_pcr['pcr']
                    logger.debug(f"Using PCR {nearest_pcr['pcr']} from {nearest_pcr['time']} (gap: {nearest_pcr['gap_mins']:.1f}m)")
                else:
                    # No PCR within 5 mins, check if gap > 15 mins to go NEUTRAL
                    # For now, keep last known PCR if gap < 15 mins
                    logger.debug(f"No PCR within 5 mins of {time_str}, keeping last known")
        else:
            logger.warning(f"No PCR history available")

        # 4. Check Active Trades
        old_trades_count = len(state.active_trades)
        check_trade_exits(state, sub_idx, sub_ce, sub_pe, store_db=False) # Replay doesn't write to primary trade DB
        
        # Prepare current prices for PnL update
        current_prices = {}
        if not sub_ce.empty: current_prices[state.ce_sym] = sub_ce['close'].iloc[-1]
        if not sub_pe.empty: current_prices[state.pe_sym] = sub_pe['close'].iloc[-1]
        
        # Final Update PnL stats for the current state (Including Unrealized)
        state.pnl_tracker.update_stats(state.active_trades, current_prices)

        # Volume PCR using per-strike data is INVALID for overall market context
        # We rely 100% on Overall Chain PCR from daily_pcr_history
        # print(f"DEBUG: Current PCR for {time_str}: {state.pcr_insights.get('pcr')}")
        
        # Note: If historical PCR wasn't fetched or isn't available for this time,
        # state.pcr_insights will retain the last known value or default.
        # Volume PCR using per-strike data is INVALID and has been removed.
        
        # Store PCR Insights for analysis

        # EOD Square-off check
        if is_market_closing(last_time):
            for trade in state.active_trades[:]:
                if trade.symbol == state.ce_sym: df = sub_ce
                elif trade.symbol == state.pe_sym: df = sub_pe
                else: df = sub_idx # fallback to index if needed

                if df.empty: continue
                last_price = df['close'].iloc[-1]
                last_time_shifted = int(df.index[-1].timestamp()) + 19800
                trade.close(last_price, last_time_shifted, "EOD_SQUAREOFF")
                db.store_trade(trade)
                state.active_trades.remove(trade)

        # Store PCR Insights for analysis (Optimized)
        last_time_ts = int(last_time.timestamp())
        if last_time_ts > state.last_pcr_store_ts:
            db.store_pcr_insight(state.index_sym.replace("NSE:", ""), last_time_ts, state.pcr_insights, state.buildup_history)
            state.last_pcr_store_ts = last_time_ts

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
            "market_time": last_time.strftime("%H:%M:%S"),
            "index_data": idx_recs,
            "ce_data": ce_recs,
            "pe_data": pe_recs,
            "ce_markers": state.ce_markers,
            "pe_markers": state.pe_markers,
            "ce_symbol": state.ce_sym,
            "pe_symbol": state.pe_sym,
            "index_symbol": state.index_sym,
            "trend": trend,
            "max_idx": min(len(state.replay_data_ce), len(state.replay_data_pe)),
            "current_idx": state.replay_idx,
            "pnl_stats": state.pnl_tracker.get_stats(),
            "new_signals": new_signals,
            "pcr_insights": state.pcr_insights
        }

        if send:
            json_msg = clean_json(msg)
            # logger.info(f"Sending replay_step: Index={len(idx_recs)}, CE={len(ce_recs)}, PE={len(pe_recs)}")
            with open("replay_debug.log", "a") as f:
                f.write(f"SENT: Idx={state.replay_idx}, CE={len(ce_recs)}, PE={len(pe_recs)}\n")
            await websocket.send_json(json_msg)
    except Exception as e:
        logger.error(f"ERROR in send_replay_step: {e}")
        import traceback
        traceback.print_exc()

async def replay_loop(websocket, state):
    """Background task to drive the replay."""
    logger.info("Starting Replay Loop")
    try:
        while state.is_playing and websocket.client_state == WebSocketState.CONNECTED:
            await send_replay_step(websocket, state)
            state.replay_idx += 1
            
            # Check if we reached end
            max_len = min(len(state.replay_data_ce), len(state.replay_data_pe))
            if state.replay_idx >= max_len:
                logger.info("Replay Finished")
                state.is_playing = False
                await websocket.send_json({"type": "replay_finished"})
                break
                
            await asyncio.sleep(0.5) # Speed of replay
    except Exception as e:
        logger.error(f"Replay Loop Error: {e}")

async def pcr_update_task(websocket, state):
    """Background task to update PCR every minute."""
    logger.info("Starting PCR Update Task")
    try:
        while state.is_live and websocket.client_state == WebSocketState.CONNECTED:
            if state.index_sym:
                index_raw = state.index_sym.replace("NSE:", "")
                pcr_res = await fetch_pcr_insights(index_raw)
                
                # Update State
                state.pcr_insights = pcr_res.get('insights', {})
                state.buildup_history = pcr_res.get('buildup_list', [])
                
                # Send Update
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "pcr_update",
                        "pcr_insights": state.pcr_insights,
                        "trend": state.tf_main.get_trend(None, state.pcr_insights) # Just update trend based on new PCR
                    })
            
            await asyncio.sleep(60) # Update every minute
    except Exception as e:
        logger.error(f"PCR Update Task Error: {e}")


async def run_full_backtest(websocket, state, index_sym, date_str):
    try:
        logger.info(f"Running full day backtest for {index_sym} on {date_str}")
        state.reset_strategies()
        state.reset_trading_state()

        ref_date = datetime.strptime(date_str, "%Y-%m-%d")
        # Ensure we cover full market hours
        ref_date_eod = ref_date.replace(hour=15, minute=30)

        # 1. Fetch Full Day Data
        idx_df = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date_eod)
        if not idx_df.empty: idx_df = idx_df.between_time('03:45', '10:00')
        if idx_df.empty:
            await websocket.send_json({"type": "error", "message": f"No data found for {index_sym} on {date_str}"})
            return
            
        # Fetch Historical PCR Map
        logger.info(f"[Backtest] About to fetch historical PCR for {index_sym}...")
        state.daily_pcr_history = await fetch_historical_pcr(index_sym, ref_date_eod)
        logger.info(f"[Backtest] Loaded {len(state.daily_pcr_history)} PCR records.")
        if state.daily_pcr_history:
            sample_keys = list(state.daily_pcr_history.keys())[:3]
            for k in sample_keys:
                logger.info(f"  [Backtest] Sample PCR at {k}: {state.daily_pcr_history[k]}")

        strike = dm.get_atm_strike(idx_df['close'].iloc[0], step=100 if "BANK" in index_sym else 50)
        ce_sym = dm.get_option_symbol(index_sym, strike, "C", reference_date=ref_date_eod)
        pe_sym = dm.get_option_symbol(index_sym, strike, "P", reference_date=ref_date_eod)

        # Clean and Re-prefix to ensure single NSE: prefix
        clean_idx = index_sym.replace("NSE:", "")
        state.index_sym = f"NSE:{clean_idx}"
        state.ce_sym = f"NSE:{ce_sym.replace('NSE:', '')}"
        state.pe_sym = f"NSE:{pe_sym.replace('NSE:', '')}"

        ce_df = dm.get_data(ce_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date_eod)
        pe_df = dm.get_data(pe_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date_eod)
        if not ce_df.empty: ce_df = ce_df.between_time('03:45', '10:00')
        if not pe_df.empty: pe_df = pe_df.between_time('03:45', '10:00')

        if ce_df.empty or pe_df.empty:
            await websocket.send_json({"type": "error", "message": f"Option data not found for {ce_sym} or {pe_sym}"})
            return

        # Fetch PCR Insights for the full day (or representative snapshot)
        pcr_res = await fetch_pcr_insights(index_sym, ref_date=ref_date_eod)
        state.pcr_insights = pcr_res.get('insights', {})
        state.buildup_history = pcr_res.get('buildup_list', [])

        # 2. Sequential Simulation (All at once)
        max_len = min(len(ce_df), len(pe_df))
        start_idx = 50

        for i in range(start_idx, max_len):
            sub_ce = ce_df.iloc[max(0, i-100):i]
            sub_pe = pe_df.iloc[max(0, i-100):i]
            last_time = sub_ce.index[-1]
            # Precise index slice for this timestamp
            idx_full = idx_df[idx_df.index <= last_time]
            sub_idx = idx_full.iloc[-100:]

            # Use shifted timestamp for logic consistency
            c_time = int(last_time.timestamp()) + 19800

            # PCR & Buildup Sync
            hist_buildup = get_buildup_for_time(state.buildup_history, last_time)
            if hist_buildup: state.pcr_insights['buildup_status'] = hist_buildup
            
            # Update PCR from Historical Map
            time_str = last_time.astimezone(IST_TZ).strftime("%H:%M")
            if time_str in state.daily_pcr_history:
                rec = state.daily_pcr_history[time_str]
                state.pcr_insights['pcr'] = rec['pcr']
                state.pcr_insights['call_oi'] = rec['call_oi']
                state.pcr_insights['put_oi'] = rec['put_oi']

            # Exits and Strategy Check
            check_trade_exits(state, sub_idx, sub_ce, sub_pe, store_db=False)
            new_sigs = evaluate_all_strategies(state, sub_idx, sub_ce, sub_pe, last_time, c_time, record_trades=True, store_db=False)

            for sig in new_sigs:
                color = "#2196F3" if sig['strat_name'] == "TREND_FOLLOWING" else "#FF9800"
                marker = {"time": sig['time'], "position": "belowBar", "color": color, "shape": "arrowUp", "text": sig['strat_name']}
                if sig.get('is_pe'):
                    state.pe_markers.append(marker)
                else:
                    state.ce_markers.append(marker)

        # 3. Compile Strategy Performance Report
        report = {}
        for t in state.pnl_tracker.trades:
            s_name = t.strategy_name
            if s_name not in report: report[s_name] = {"pnl": 0, "win": 0, "loss": 0, "total": 0}
            report[s_name]["total"] += 1
            if t.status == 'CLOSED':
                report[s_name]["pnl"] += t.pnl
                if t.pnl > 0: report[s_name]["win"] += 1
                else: report[s_name]["loss"] += 1

        for s in report:
            report[s]["win_rate"] = round((report[s]["win"] / report[s]["total"] * 100), 1) if report[s]["total"] > 0 else 0
            report[s]["pnl"] = round(report[s]["pnl"], 2)

        # 4. Final Payload
        all_signals = []
        for t in state.pnl_tracker.trades:
            all_signals.append({
                "strat_name": t.strategy_name,
                "time": t.entry_time,
                "entry_price": t.entry_price,
                "sl": t.sl,
                "type": "LONG" if "PE" not in t.symbol else "SHORT",
                "reason": getattr(t, 'reason', 'Technical breakout confirmed.') # Fallback
            })

        msg = {
            "type": "backtest_results",
            "index_symbol": index_sym,
            "ce_symbol": f"NSE:{ce_sym}",
            "pe_symbol": f"NSE:{pe_sym}",
            "index_data": format_records(idx_df),
            "ce_data": format_records(ce_df),
            "pe_data": format_records(pe_df),
            "ce_markers": state.ce_markers,
            "pe_markers": state.pe_markers,
            "ce_symbol": ce_sym,
            "pe_symbol": pe_sym,
            "pnl_stats": state.pnl_tracker.get_stats(),
            "new_signals": all_signals,
            "strategy_report": report
        }
        await websocket.send_json(clean_json(msg))

    except Exception as e:
        logger.exception("Full Backtest Error")
        await websocket.send_json({"type": "error", "message": str(e)})

def clean_json(obj):
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_json(i) for i in obj]
    elif isinstance(obj, (np.float64, np.float32, np.float16, float)):
        if np.isnan(obj) or np.isinf(obj):
            return None
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

        insights = {}
        # Only fetch live snapshot if it's for today
        if not ref_date or ref_date.date() == datetime.now().date():
            # For live, we can try snapshot but if it fails/historical we need defaults
            insights = {'pcr': 1.0, 'pcr_change': 1.0, 'buildup_status': 'NEUTRAL'}
        else:
            insights = {'pcr': 1.0, 'pcr_change': 1.0, 'buildup_status': 'NEUTRAL'}

        # Fetch 5m buildup - use latest client signature
        buildup_list = await tl_adv.get_buildup_5m(index_sym)

        # Normalize buildup status text for latest insight
        if buildup_list and len(buildup_list) > 0:
            latest = buildup_list[0]
            # Handle both list and dict formats
            status = "NEUTRAL"
            if isinstance(latest, list) and len(latest) > 1:
                status = latest[1]
            elif isinstance(latest, dict):
                status = latest.get('buildup') or latest.get('status') or "NEUTRAL"
            
            insights['buildup_status'] = normalize_buildup(status)
            insights['sentiment'] = get_sentiment_from_buildup(insights['buildup_status'])
            # Note: PCR will be updated by the historical map/smart fallback later
        
        return {"insights": insights, "buildup_list": buildup_list}
    except Exception as e:
        import traceback
        traceback.print_exc()   
        logger.error(f"Error fetching PCR insights: {e}")
    return {"insights": {}, "buildup_list": []}

def get_pcr_cache_path(index_sym, date):
    """Get cache file path for index and date."""
    date_str = date.strftime("%Y-%m-%d")
    filename = f"{index_sym}_{date_str}_pcr.json"
    return PCR_CACHE_DIR / filename

def save_pcr_to_cache(index_sym, date, pcr_history):
    """Save PCR history to disk."""
    try:
        cache_path = get_pcr_cache_path(index_sym, date)
        with open(cache_path, 'w') as f:
            json.dump(pcr_history, f, indent=2)
        logger.info(f"💾 Saved PCR cache: {cache_path.name} ({len(pcr_history)} intervals)")
    except Exception as e:
        logger.error(f"Failed to save PCR cache: {e}")

def load_pcr_from_cache(index_sym, date):
    """Load PCR history from disk if exists."""
    try:
        cache_path = get_pcr_cache_path(index_sym, date)
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                pcr_history = json.load(f)
            logger.info(f"📂 Loaded PCR cache: {cache_path.name} ({len(pcr_history)} intervals)")
            return pcr_history
    except Exception as e:
        logger.error(f"Failed to load PCR cache: {e}")
    return None

def find_nearest_pcr(pcr_history, target_time, max_gap_minutes=5):
    """
    Find nearest PCR record within max_gap_minutes of target_time.
    Returns: {'pcr': float, 'time': str, 'gap_mins': float} or None
    """
    if not pcr_history:
        return None
    
    target_time_only = target_time.time()
    best_match = None
    min_gap = float('inf')
    
    for time_str, pcr_data in pcr_history.items():
        try:
            # Parse time string "HH:MM"
            pcr_time = datetime.strptime(time_str, "%H:%M").time()
            
            # Calculate gap in minutes
            pcr_dt = datetime.combine(target_time.date(), pcr_time)
            target_dt = datetime.combine(target_time.date(), target_time_only)
            gap_seconds = abs((target_dt - pcr_dt).total_seconds())
            gap_minutes = gap_seconds / 60
            
            # Only consider if within max gap and it's the nearest so far
            if gap_minutes <= max_gap_minutes and gap_minutes < min_gap:
                min_gap = gap_minutes
                best_match = {
                    'pcr': pcr_data['pcr'],
                    'time': time_str,
                    'gap_mins': gap_minutes
                }
        except Exception as e:
            continue
    
    return best_match

async def fetch_historical_pcr(index_sym, ref_date):
    """
    Fetches full day 5-min Overall Chain PCR history.
    Uses Database if available, otherwise fetches from API and stores result.
    """
    # 1. Try DB first
    # For DB query, we need start and end of the reference day in UTC
    start_of_day = ref_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = ref_date.replace(hour=23, minute=59, second=59, microsecond=0)
    
    # Convert to Unix timestamps (assuming ref_date is in IST but dm treats it as UTC-comparable)
    # Actually, dm uses 19800 shift for UI. For DB storage we should be consistent.
    # Let's use simple naive comparison for now or consistent localization.
    start_ts = int(start_of_day.timestamp())
    end_ts = int(end_of_day.timestamp())

    clean_sym = index_sym.replace("NSE:", "")
    db_history = db.get_pcr_history(clean_sym, start_ts, end_ts)

    if not db_history.empty:
        logger.info(f"✅ Using DB cached PCR data for {clean_sym} ({len(db_history)} intervals)")
        # Convert back to interval-map format: "HH:MM" -> {pcr, call_oi, put_oi}
        history = {}
        for _, row in db_history.iterrows():
            # Convert timestamp back to IST string HH:MM
            dt = datetime.fromtimestamp(row['timestamp'], tz=IST_TZ)
            time_key = dt.strftime("%H:%M")
            history[time_key] = {
                "pcr": row['pcr'],
                "call_oi": row['total_call_oi'],
                "put_oi": row['total_put_oi']
            }
        return history

    # 2. If no DB cache, fetch from API
    logger.info(f"🌐 No DB cache found for {clean_sym} on {ref_date.date()}, fetching from Trendlyne...")
    history = await _fetch_pcr_from_api(index_sym, ref_date)

    # History is already stored in DB inside _fetch_pcr_from_api
    return history

async def _fetch_pcr_from_api(index_sym, ref_date):
    """
    Fetches PCR by summing absolute OI across ATM ± 20 strikes per 5-min interval.
    Stores results in DB for persistent caching.
    """
    try:
        # 1. Determine ATM Strike
        stock_id = await tl_adv.get_stock_id(index_sym)
        idx_df = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1, reference_date=ref_date)
        if idx_df.empty:
            logger.error(f"❌ No index data for {index_sym} on {ref_date}")
            return {}
        
        spot_price = idx_df['close'].iloc[0]
        step = 100 if "BANK" in index_sym.upper() else 50
        atm_strike = int(round(spot_price / step) * step)
        
        logger.info(f"📊 Calculating Overall Chain PCR | {index_sym} | ATM: {atm_strike} | Date: {ref_date.date()}")
        
        # 2. Generate Strike Range: ATM ± 20 strikes (41 total)
        strikes = [atm_strike + (i * step) for i in range(-20, 21)]
        
        # 3. Fetch ALL strikes with limited concurrency to avoid 503 errors
        sem = asyncio.Semaphore(5)

        async def throttled_fetch(strike, o_type):
            async with sem:
                # Add a tiny sleep to further spread requests
                await asyncio.sleep(0.2)
                return await tl_adv.get_buildup_5m(index_sym, strike=strike, o_type=o_type)

        tasks = []
        for strike in strikes:
            tasks.append(throttled_fetch(strike, "Call"))
            tasks.append(throttled_fetch(strike, "Put"))
        
        logger.info(f"🌐 Fetching buildup for {len(strikes)} strikes (82 API calls) with concurrency limit 5...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. Extract and Organize Data
        interval_map = {}
        
        for i, strike in enumerate(strikes):
            ce_res = results[i * 2]
            pe_res = results[i * 2 + 1]
            
            # CE Summation
            if not isinstance(ce_res, Exception) and ce_res:
                for row in ce_res:
                    iv = row.get('interval')
                    if not iv: continue
                    val = float(row.get('oi') or row.get('open_interest', 0))
                    if val > 0:
                        if iv not in interval_map:
                            interval_map[iv] = {"CE": 0.0, "PE": 0.0, "CE_count": 0, "PE_count": 0}
                        interval_map[iv]["CE"] += val
                        interval_map[iv]["CE_count"] += 1
            
            # PE Summation
            if not isinstance(pe_res, Exception) and pe_res:
                for row in pe_res:
                    iv = row.get('interval')
                    if not iv: continue
                    val = float(row.get('oi') or row.get('open_interest', 0))
                    if val > 0:
                        if iv not in interval_map:
                            interval_map[iv] = {"CE": 0.0, "PE": 0.0, "CE_count": 0, "PE_count": 0}
                        interval_map[iv]["PE"] += val
                        interval_map[iv]["PE_count"] += 1

        # 5. Final Calculation and DB Storage
        history = {}
        clean_sym = index_sym.replace("NSE:", "")
        logger.info(f"📈 Processing {len(interval_map)} intervals and storing to DB...")
        
        for iv, totals in sorted(interval_map.items()):
            # Only calculate if we have data from at least 5 strikes on each side to avoid outliers
            if totals["CE_count"] > 5 and totals["PE_count"] > 5:
                pcr = round(totals["PE"] / totals["CE"], 2)
                
                # Extract end time: "15:25 TO 15:30" -> "15:30"
                parts = iv.split(" TO ")
                if len(parts) == 2:
                    time_key = parts[1]
                    history[time_key] = {
                        "pcr": pcr,
                        "call_oi": totals["CE"],
                        "put_oi": totals["PE"]
                    }

                    # Convert time_key "HH:MM" to Unix timestamp for the reference day
                    try:
                        h, m = map(int, time_key.split(":"))
                        # Create datetime for the specific time on ref_date
                        dt = ref_date.replace(hour=h, minute=m, second=0, microsecond=0)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=IST_TZ)
                        ts = int(dt.timestamp())

                        # Store in DB
                        db.store_pcr_history(clean_sym, ts, pcr, totals["CE"], totals["PE"])
                    except Exception as e:
                        logger.error(f"Error storing PCR history for {time_key}: {e}")

                    if pcr > 5:
                        logger.warning(f"⚠️ High PCR alert at {time_key}: {pcr} (CE: {totals['CE']:.0f} [{totals['CE_count']} strikes], PE: {totals['PE']:.0f} [{totals['PE_count']} strikes])")
            else:
                logger.debug(f"⏭️ Skipping interval {iv} due to insufficient strike data")

        logger.info(f"✅ PCR calculation complete. Generated and stored {len(history)} intervals.")
        return history
    except Exception as e:
        logger.error(f"❌ Critical error in PCR calculation: {e}")
        import traceback
        traceback.print_exc()
        return {}

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
    
    if not is_within_trading_window(last_time):
        return new_signals

    # 1. Update Primary Trend (Unified)
    trend = state.tf_main.get_trend(idx_df, state.pcr_insights)
    state.tf_main.update_params(state.index_sym)

    # 2. Check Trend Following (Unified)
    # CE
    if not ce_df.empty: 
        ce_tf = state.tf_main.check_setup_unified(idx_df, ce_df, state.pcr_insights, "CE")
        if ce_tf and check_option_ema_filter(ce_df):
             ce_tf['strat_name'] = "TREND_FOLLOWING"
             ce_tf['time'] = candle_time
             ce_tf['is_pe'] = False
             if handle_new_trade(state, "TREND_FOLLOWING", state.ce_sym, ce_tf, candle_time, store=record_trades, store_db=store_db):
                 logger.info(f"SIGNAL FIRED: TREND_FOLLOWING on {state.ce_sym}")
                 new_signals.append(ce_tf)

    # PE
    if not pe_df.empty:
        pe_tf = state.tf_main.check_setup_unified(idx_df, pe_df, state.pcr_insights, "PE")
        if pe_tf and check_option_ema_filter(pe_df):
             pe_tf['strat_name'] = "TREND_FOLLOWING"
             pe_tf['time'] = candle_time
             pe_tf['is_pe'] = True
             if handle_new_trade(state, "TREND_FOLLOWING", state.pe_sym, pe_tf, candle_time, store=record_trades, store_db=store_db):
                 logger.info(f"SIGNAL FIRED: TREND_FOLLOWING on {state.pe_sym}")
                 new_signals.append(pe_tf)

    # 3. Check Other Strategies (Index Driven)
    if not idx_df.empty and len(idx_df) >= 20:
        for strat in state.strategies["INDEX"]:
            # Skip old TrendLogic if present to avoid dupes
            if strat.name == "TREND_FOLLOWING": continue
            
            if strat.is_index_driven: # Simplified check
                setup = strat.check_setup(idx_df, state.pcr_insights)
                if setup:
                    s_type = setup.get('type', '').upper()
                    is_pe_trade = ("SHORT" in s_type) or ("PE" in s_type)
                    target_df = pe_df if is_pe_trade else ce_df
                    target_sym = state.pe_sym if is_pe_trade else state.ce_sym

                    if target_df.empty or not check_option_ema_filter(target_df): continue

                    setup['strat_name'] = strat.name
                    setup['time'] = candle_time
                    # CRITICAL FIX: Use option price, not index price for entry
                    # Index-driven strategies analyze index but we trade OPTIONS
                    setup['entry_price'] = target_df['close'].iloc[-1]  # Option premium

                    # CRITICAL FIX: Index-driven strategies return SL/Target based on Index points.
                    # We MUST override them to be relative to the OPTION price to prevent PnL glitches.
                    is_bn = "BANK" in state.index_sym.upper()
                    sl_pts = 30 if is_bn else 20
                    tgt_pts = 60 if is_bn else 40

                    setup['sl'] = setup['entry_price'] - sl_pts
                    setup['target'] = setup['entry_price'] + tgt_pts
                    setup['is_pe'] = is_pe_trade

                    if handle_new_trade(state, strat.name, target_sym, setup, candle_time, store=record_trades, store_db=store_db):
                        logger.info(f"SIGNAL FIRED: {strat.name} on {target_sym}")
                        new_signals.append(setup)

    # 4. Check Other Strategies (Option Driven)
    for side, df, strat_list, sym in [("CE", ce_df, state.strategies["CE"], state.ce_sym), ("PE", pe_df, state.strategies["PE"], state.pe_sym)]:
        if df.empty or len(df) < 20: continue
        for strat in strat_list:
            if strat.name == "TREND_FOLLOWING": continue
            
            if not strat.is_index_driven:
                setup = strat.check_setup(df, state.pcr_insights)
                if setup and check_option_ema_filter(df):
                    setup['strat_name'] = strat.name
                    setup['time'] = candle_time
                    setup['entry_price'] = setup.get('entry_price') or df['close'].iloc[-1]

                    # Apply codified risk management
                    is_bn = "BANK" in state.index_sym.upper()
                    sl_pts = 30 if is_bn else 20
                    tgt_pts = 60 if is_bn else 40

                    setup['sl'] = setup['entry_price'] - sl_pts
                    setup['target'] = setup['entry_price'] + tgt_pts
                    setup['is_pe'] = (side == "PE")

                    if handle_new_trade(state, strat.name, sym, setup, candle_time, store=record_trades, store_db=store_db):
                        logger.info(f"SIGNAL FIRED: {strat.name} on {sym}")
                        new_signals.append(setup)

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
                # Use candle time for trading window check inside evaluate_all_strategies for parity

                # Use sliding window for strategy calculation (matching warmup and replay)
                s_idx = idx_df.iloc[-50:]
                s_ce = ce_df.iloc[-50:]
                s_pe = pe_df.iloc[-50:]

                # Convert target_candle time (IST-shifted UTC) back to naive for window check
                # Note: evaluate_all_strategies expects a datetime for the 'last_time' window check
                dt_for_window = pd.to_datetime(target_candle['time'] - 19800, unit='s', utc=True)

                new_live_signals = evaluate_all_strategies(state, s_idx, s_ce, s_pe, dt_for_window, target_candle['time'])

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
            
            # Caching Trendlyne Fetch (Once every 60 seconds)
            current_now = datetime.now().timestamp()
            if current_now - state.last_trendlyne_fetch > 60:
                delta_signals = await fetch_trendlyne_signals(clean_symbol, strike)
                pcr_res = await fetch_pcr_insights(clean_symbol)
                state.pcr_insights = pcr_res.get('insights', {})
                state.buildup_history = pcr_res.get('buildup_list', [])
                state.cached_delta_signals = delta_signals
                state.last_trendlyne_fetch = current_now
            else:
                delta_signals = state.cached_delta_signals

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
                "trend": state.tf_main.get_trend(pd.DataFrame(state.idx_history).iloc[-50:], state.pcr_insights) if state.idx_history else None
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
                # Live mode always stores trades in DB
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
    trade.reason = setup.get('reason', 'Strategy conditions met.')
    # Persist trade to DB if requested
    if store_db:
        db.store_trade(trade)
    state.active_trades.append(trade)
    state.pnl_tracker.add_trade(trade)
    return True

def check_trade_exits(state, sub_idx, sub_ce, sub_pe, store_db=True):
    for trade in state.active_trades[:]:
        # Determine which data to use based on trade symbol
        if trade.symbol == state.ce_sym:
            df = sub_ce
        elif trade.symbol == state.pe_sym:
            df = sub_pe
        elif trade.symbol == state.index_sym:
            df = sub_idx
        else:
            # Fallback to symbol matching ignoring NSE: prefix
            t_sym = trade.symbol.replace("NSE:", "")
            if t_sym == state.ce_sym.replace("NSE:", ""): df = sub_ce
            elif t_sym == state.pe_sym.replace("NSE:", ""): df = sub_pe
            elif t_sym == state.index_sym.replace("NSE:", ""): df = sub_idx
            else:
                logger.warning(f"No data slice found for trade symbol {trade.symbol}")
                continue

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
            # Update trade in DB if requested
            if store_db:
                db.store_trade(trade)
            state.last_trade_close_times[(trade.strategy_name, trade.symbol)] = last_time
            state.active_trades.remove(trade)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
