
import asyncio
import websockets
import json
import sys

async def get_report(index, date):
    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"--- Backtest Report for {index} on {date} ---")
            await websocket.send(json.dumps({
                "type": "run_backtest",
                "index": index,
                "date": date
            }))

            while True:
                resp = await asyncio.wait_for(websocket.recv(), timeout=300) # Full day takes time
                data = json.loads(resp)
                if data.get('type') == 'backtest_results':
                    stats = data.get('pnl_stats', {})
                    report = data.get('strategy_report', {})

                    print("\n[ Performance Summary ]")
                    print(f"Total PnL: ₹{stats.get('total_pnl', 0):.2f}")
                    print(f"Win Rate: {stats.get('win_rate', 0):.1f}%")
                    print(f"Total Trades: {stats.get('total_trades', 0)}")
                    print(f"Max Drawdown: ₹{stats.get('max_drawdown', 0):.2f}")

                    print("\n[ Strategy Breakdown ]")
                    for s_name, s_data in report.items():
                        print(f"- {s_name}: PnL=₹{s_data['pnl']:.2f}, WinRate={s_data['win_rate']}% ({s_data['win']}/{s_data['total']})")

                    break
                elif data.get('type') == 'error':
                    print(f"Error: {data.get('message')}")
                    break
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    idx = sys.argv[1] if len(sys.argv) > 1 else "BANKNIFTY"
    asyncio.run(get_report(idx, "2026-01-23"))
