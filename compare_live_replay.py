import pandas as pd
import asyncio
from datetime import datetime, timezone, timedelta
from main import SessionState, evaluate_all_strategies, dm, format_records, fetch_pcr_insights, IST_TZ, check_trade_exits
from tvDatafeed import Interval
import json

async def simulate_live(index_sym, date_str, strike):
    print(f"--- Simulating LIVE for {index_sym} on {date_str} with strike {strike} ---")
    state = SessionState()
    ref_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=15, minute=30)

    # 1. Fetch Data
    idx_df = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
    if idx_df.empty: return []
    idx_df = idx_df.between_time('03:45', '10:00')

    ce_sym = dm.get_option_symbol(index_sym, strike, 'C', reference_date=ref_date)
    pe_sym = dm.get_option_symbol(index_sym, strike, 'P', reference_date=ref_date)
    state.index_sym = f"NSE:{index_sym}"
    state.ce_sym = f"NSE:{ce_sym}"
    state.pe_sym = f"NSE:{pe_sym}"

    ce_df = dm.get_data(ce_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
    pe_df = dm.get_data(pe_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
    if ce_df.empty or pe_df.empty: return []
    ce_df = ce_df.between_time('03:45', '10:00')
    pe_df = pe_df.between_time('03:45', '10:00')

    # Fetch PCR
    pcr_res = await fetch_pcr_insights(index_sym, ref_date=ref_date)
    state.pcr_insights = pcr_res.get('insights', {})
    state.buildup_history = pcr_res.get('buildup_list', [])

    # Initialize TF main
    state.tf_main.update_params(index_sym)

    # 2. History Initialization (Warmup)
    idx_recs = format_records(idx_df)
    ce_recs = format_records(ce_df)
    pe_recs = format_records(pe_df)

    # Simulate Live mode warmup
    start_bar_warmup = 50
    for i in range(start_bar_warmup, len(ce_df)):
        last_time = ce_df.index[i]
        sub_idx = idx_df.iloc[:i+1]
        sub_ce = ce_df.iloc[:i+1]
        sub_pe = pe_df.iloc[:i+1]
        c_time = ce_recs[i]['time']

        check_trade_exits(state, sub_idx, sub_ce, sub_pe)
        evaluate_all_strategies(state, sub_idx, sub_ce, sub_pe, last_time, c_time, record_trades=True, store_db=False)

    return state.pnl_tracker.trades

async def simulate_replay(index_sym, date_str, strike):
    print(f"--- Simulating REPLAY for {index_sym} on {date_str} with strike {strike} ---")
    state = SessionState()
    ref_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=15, minute=30)

    # Fetch Data
    state.replay_data_idx = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
    if state.replay_data_idx.empty: return []
    state.replay_data_idx = state.replay_data_idx.between_time('03:45', '10:00')

    state.index_sym = f"NSE:{index_sym}"
    state.ce_sym = f"NSE:{dm.get_option_symbol(index_sym, strike, 'C', reference_date=ref_date)}"
    state.pe_sym = f"NSE:{dm.get_option_symbol(index_sym, strike, 'P', reference_date=ref_date)}"

    state.replay_data_ce = dm.get_data(state.ce_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
    state.replay_data_pe = dm.get_data(state.pe_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
    if state.replay_data_ce.empty: return []
    state.replay_data_ce = state.replay_data_ce.between_time('03:45', '10:00')
    state.replay_data_pe = state.replay_data_pe.between_time('03:45', '10:00')

    pcr_res = await fetch_pcr_insights(index_sym, ref_date=ref_date)
    state.pcr_insights = pcr_res.get('insights', {})
    state.buildup_history = pcr_res.get('buildup_list', [])

    max_len = min(len(state.replay_data_ce), len(state.replay_data_pe))
    for i in range(50, max_len):
        sub_ce = state.replay_data_ce.iloc[:i+1]
        sub_pe = state.replay_data_pe.iloc[:i+1]
        last_time = sub_ce.index[-1]
        sub_idx = state.replay_data_idx[state.replay_data_idx.index <= last_time]

        ce_recs = format_records(sub_ce)
        c_time = ce_recs[-1]['time']

        check_trade_exits(state, sub_idx, sub_ce, sub_pe)
        evaluate_all_strategies(state, sub_idx, sub_ce, sub_pe, last_time, c_time, record_trades=True, store_db=False)

    return state.pnl_tracker.trades

async def main():
    date_str = "2026-01-22"
    index = "BANKNIFTY"
    strike = 59500 # Fixed strike for exact comparison

    live_trades = await simulate_live(index, date_str, strike)
    replay_trades = await simulate_replay(index, date_str, strike)

    print(f"\nResults for {index} on {date_str}:")
    print(f"LIVE Trades Count: {len(live_trades)}")
    print(f"REPLAY Trades Count: {len(replay_trades)}")

    # Comparison
    match = True
    if len(live_trades) != len(replay_trades):
        match = False
        print("DIFFERENCE: Count mismatch!")
    else:
        for l, r in zip(live_trades, replay_trades):
            if l.strategy_name != r.strategy_name or l.entry_time != r.entry_time or abs(l.entry_price - r.entry_price) > 0.01:
                match = False
                print(f"DIFFERENCE: {l.strategy_name} @ {l.entry_time} vs {r.strategy_name} @ {r.entry_time}")
                break

    if match:
        print("SUCCESS: Live and Replay trades/signals are EXACTLY identical!")
    else:
        print("FAILURE: Discrepancies found.")

    # Show some trades
    print("\nSample Trades:")
    for t in live_trades[:5]:
        print(f"  {t.strategy_name} | Entry: {t.entry_time} | Status: {t.status} | PnL: {t.pnl}")

if __name__ == "__main__":
    asyncio.run(main())
