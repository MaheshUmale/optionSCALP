
import asyncio
import websockets
import json
import time

async def test_replay():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")

        # Start Replay for NIFTY on 2026-01-23
        print("Starting Replay for NIFTY on 2026-01-23...")
        await websocket.send(json.dumps({
            "type": "start_replay",
            "index": "NIFTY",
            "date": "2026-01-23"
        }))

        # Listen for messages
        count = 0
        while count < 100: # Receive more steps to see PCR change
            try:
                resp = await asyncio.wait_for(websocket.recv(), timeout=60)
                data = json.loads(resp)
                msg_type = data.get('type')
                print(f"Received message type: {msg_type}")

                if msg_type == 'replay_step':
                    count += 1
                    market_time = data.get('market_time')
                    pcr = data.get('pcr_insights', {}).get('pcr')
                    pnl = data.get('pnl_stats', {}).get('total_pnl')
                    print(f"Step {count}: Time={market_time}, PCR={pcr}, PnL={pnl}")

                    if pcr is not None:
                        print(f"✅ PCR value received: {pcr}")

                if msg_type == 'error':
                    print(f"❌ Error: {data.get('message')}")
                    break

            except asyncio.TimeoutError:
                print("Timeout waiting for message")
                break
            except Exception as e:
                print(f"Exception: {e}")
                break

if __name__ == "__main__":
    # Note: Server must be running for this to work
    try:
        asyncio.run(test_replay())
    except Exception as e:
        print(f"Test failed: {e}")
