
import asyncio
import websockets
import json
import time

async def verify_incremental():
    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")

            # Start Replay for BANKNIFTY on 2026-01-23
            print("Starting Replay for BANKNIFTY on 2026-01-23...")
            await websocket.send(json.dumps({
                "type": "start_replay",
                "index": "BANKNIFTY",
                "date": "2026-01-23"
            }))

            prev_len = 0
            steps = 0
            while steps < 10:
                try:
                    resp = await asyncio.wait_for(websocket.recv(), timeout=20)
                    data = json.loads(resp)
                    if data.get('type') == 'replay_step':
                        steps += 1
                        idx_data = data.get('index_data', [])
                        curr_len = len(idx_data)
                        market_time = data.get('market_time')

                        print(f"Step {steps}: Time={market_time}, Candle Count={curr_len}")

                        if curr_len > prev_len:
                            print(f"✅ Incremental growth confirmed: {prev_len} -> {curr_len}")
                        elif curr_len == prev_len:
                            print(f"⚠️ No growth in this step (Count: {curr_len})")
                        else:
                            print(f"❌ REGRESSION: Data shrank! {prev_len} -> {curr_len}")

                        prev_len = curr_len
                except asyncio.TimeoutError:
                    print("Timeout waiting for replay_step")
                    break
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_incremental())
