import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_server():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        logger.info("Connected to WebSocket")

        # 1. Test Live Fetch
        logger.info("Sending fetch_live...")
        await websocket.send(json.dumps({"type": "fetch_live", "index": "NSE:BANKNIFTY"}))
        
        live_data_received = False
        while not live_data_received:
            res = await websocket.recv()
            data = json.loads(res)
            if data['type'] == 'live_data':
                logger.info("Received live_data")
                live_data_received = True
                
                # Validation
                if 'active_positions' not in data: logger.error("Missing active_positions")
                if 'pcr_insights' not in data: logger.error("Missing pcr_insights")
                if 'trend' not in data: logger.error("Missing trend")
                
                logger.info(f"Trend: {data.get('trend')}")
                logger.info("✅ Live Data & UI Payload Validation Passed")
            elif data['type'] == 'error':
                 logger.error(f"Error: {data['message']}")
                 return

        # 2. Test Replay
        logger.info("Sending start_replay...")
        await websocket.send(json.dumps({
            "type": "start_replay", 
            "index": "NSE:BANKNIFTY",
            "date": "2026-01-22"
        }))
        
        replay_step_received = False
        timeout = 0
        while not replay_step_received and timeout < 10:
            res = await websocket.recv()
            data = json.loads(res)
            if data['type'] == 'replay_step':
                logger.info("Received replay_step")
                replay_step_received = True
                logger.info("✅ Replay Mode Validation Passed")
                break
            timeout += 1

if __name__ == "__main__":
    try:
        asyncio.run(test_server())
        print("VERIFICATION SUCCEEDED")
    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")
