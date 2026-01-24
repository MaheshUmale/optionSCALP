from fastapi import FastAPI, Request
import pandas as pd
import uvicorn
import logging
from core.strategies.master_strategies import STRATEGIES
from core.strategies.trend_following import TrendFollowingStrategy
import pandas_ta as ta
import httpx
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OptionScalp: Strategy Engine")

# Central Hub URL - where we send signals
ACQUISITION_URL = "http://localhost:8001/api/signal"

class Engine:
    def __init__(self):
        self.strategies = {
            "CE": [s() for s in STRATEGIES],
            "PE": [s() for s in STRATEGIES],
            "INDEX": [s() for s in STRATEGIES]
        }
        self.tf_main = TrendFollowingStrategy()

engine = Engine()

@app.post("/evaluate")
async def evaluate(request: Request):
    data = await request.json()

    idx_df = pd.DataFrame(data['index_data'])
    ce_df = pd.DataFrame(data['ce_data'])
    pe_df = pd.DataFrame(data['pe_data'])
    pcr_insights = data['pcr_insights']
    index_sym = data['index_sym']
    ce_sym = data['ce_sym']
    pe_sym = data['pe_sym']
    candle_time = data['candle_time']

    # 1. Update Trend
    engine.tf_main.update_params(index_sym)

    # 2. Evaluate Trend Following
    for side, df, sym in [("CE", ce_df, ce_sym), ("PE", pe_df, pe_sym)]:
        if df.empty: continue
        setup = engine.tf_main.check_setup_unified(idx_df, df, pcr_insights, side)
        if setup and check_option_ema_filter(df):
            await report_signal(setup, "TREND_FOLLOWING", sym, candle_time, is_pe=(side=="PE"))

    # 3. Evaluate Other Strategies (Simplified version of evaluate_all_strategies)
    is_bn = "BANK" in index_sym.upper()
    sl_pts = 30 if is_bn else 20
    tgt_pts = 60 if is_bn else 40

    if not idx_df.empty and len(idx_df) >= 20:
        for strat in engine.strategies["INDEX"]:
            if strat.name == "TREND_FOLLOWING": continue
            if strat.is_index_driven:
                setup = strat.check_setup(idx_df, pcr_insights)
                if setup:
                    is_pe = ("SHORT" in setup.get('type', '').upper()) or ("PE" in setup.get('type', '').upper())
                    target_df = pe_df if is_pe else ce_df
                    target_sym = pe_sym if is_pe else ce_sym

                    if not target_df.empty and check_option_ema_filter(target_df):
                        setup['entry_price'] = target_df['close'].iloc[-1]
                        setup['sl'] = setup['entry_price'] - sl_pts
                        setup['target'] = setup['entry_price'] + tgt_pts
                        await report_signal(setup, strat.name, target_sym, candle_time, is_pe=is_pe)

    return {"status": "ok"}

async def report_signal(setup, strat_name, symbol, candle_time, is_pe=False):
    payload = {
        "strat_name": strat_name,
        "symbol": symbol,
        "entry_price": setup['entry_price'],
        "sl": setup.get('sl'),
        "target": setup.get('target'),
        "reason": setup.get('reason'),
        "time": candle_time,
        "is_pe": is_pe,
        "type": "BUY" # We always buy options
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(ACQUISITION_URL, json=payload, timeout=2.0)
    except Exception as e:
        logger.error(f"Failed to report signal: {e}")

def check_option_ema_filter(df):
    if df is None or len(df) < 15: return False
    try:
        ema9 = ta.ema(df['close'], length=9)
        ema14 = ta.ema(df['close'], length=14)
        if ema9 is None or ema14 is None or pd.isna(ema9.iloc[-1]) or pd.isna(ema14.iloc[-1]): return False
        last_close = df['close'].iloc[-1]
        last_ema9 = ema9.iloc[-1]
        prev_ema9 = ema9.iloc[-2] if len(ema9) > 1 else last_ema9
        last_ema14 = ema14.iloc[-1]
        above_ema = (last_close > last_ema9) or (last_close > last_ema14)
        ema_condition = (last_ema9 > prev_ema9) or (last_ema9 > last_ema14)
        return above_ema and ema_condition
    except: return False

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
