import pandas as pd
import asyncio
from datetime import datetime
from main import SessionState, send_replay_step, dm, STRATEGIES, fetch_pcr_insights
from tvDatafeed import Interval
from starlette.websockets import WebSocketState
import json

async def run_automated_backtest(index_sym="BANKNIFTY", date_str="2026-01-21"):
    print(f"--- Starting Automated Backtest for {index_sym} on {date_str} ---")
    state = SessionState()
    ref_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=15, minute=30)

    # Fetch Data
    state.replay_data_idx = dm.get_data(index_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
    if state.replay_data_idx.empty:
        print("Error: Index data empty")
        return

    strike = dm.get_atm_strike(state.replay_data_idx['close'].iloc[0], step=100 if "BANK" in index_sym else 50)
    state.ce_sym = dm.get_option_symbol(index_sym, strike, "C", reference_date=ref_date)
    state.pe_sym = dm.get_option_symbol(index_sym, strike, "P", reference_date=ref_date)

    state.replay_data_ce = dm.get_data(state.ce_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)
    state.replay_data_pe = dm.get_data(state.pe_sym, interval=Interval.in_1_minute, n_bars=1000, reference_date=ref_date)

    if state.replay_data_ce.empty or state.replay_data_pe.empty:
        print("Error: Option data empty")
        return

    # Fetch PCR/Buildup for historical date to make it realistic
    pcr_res = await fetch_pcr_insights(index_sym, ref_date=ref_date)
    state.pcr_insights = pcr_res.get('insights', {})
    state.buildup_history = pcr_res.get('buildup_list', [])

    # Mock WebSocket to capture messages
    class MockWS:
        def __init__(self):
            self.client_state = WebSocketState.CONNECTED
            self.messages = []
        async def send_json(self, data):
            self.messages.append(data)

    ws = MockWS()

    # Iterate through data
    max_len = min(len(state.replay_data_ce), len(state.replay_data_pe))
    print(f"Processing {max_len} candles...")

    for i in range(50, max_len):
        state.replay_idx = i
        await send_replay_step(ws, state)

    # Force close any remaining open trades for the report
    if state.active_trades:
        print(f"Closing {len(state.active_trades)} open trades...")
        for t in state.active_trades[:]:
            t.close(t.entry_price, 0, "BACKTEST_END")

    # Generate Report
    stats = state.pnl_tracker.get_stats()
    report = f"""
# BACKTEST REPORT: {index_sym}
**Date:** {date_str}
**Expiry:** {dm.get_next_expiry(index_sym, reference_date=ref_date)}

## Summary Stats
- **Total Trades:** {stats['total_trades']}
- **Closed Trades:** {stats['total_closed']}
- **Total PnL:** ₹{stats['total_pnl']}
- **Win Rate:** {stats['win_rate']}%
- **Wins:** {stats['win_count']}
- **Losses:** {stats['loss_count']}

## Strategy Breakdown
"""
    strat_perf = {}
    for t in state.pnl_tracker.trades:
        if t.status == 'CLOSED':
            name = t.strategy_name
            if name not in strat_perf: strat_perf[name] = {"pnl": 0, "wins": 0, "losses": 0}
            strat_perf[name]["pnl"] += t.pnl
            if t.pnl > 0: strat_perf[name]["wins"] += 1
            else: strat_perf[name]["losses"] += 1

    for name, p in strat_perf.items():
        report += f"- **{name}**: PnL: ₹{round(p['pnl'], 2)} | Wins: {p['wins']} | Losses: {p['losses']}\n"

    print(report)
    filename = f"backtest_report_{index_sym}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
    return report

if __name__ == "__main__":
    async def run_all():
        b_report = await run_automated_backtest("BANKNIFTY", "2026-01-21")
        n_report = await run_automated_backtest("NIFTY", "2026-01-21")
        with open("backtest_report.md", "w", encoding="utf-8")as f:
            f.write("# FULL BACKTEST REPORT\n" + b_report + "\n---\n" + n_report)

    asyncio.run(run_all())
