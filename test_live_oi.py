import asyncio
from trendlyneAdvClient import TrendlyneScalper
import json

async def test_live_oi():
    tl = TrendlyneScalper()
    stock_id = await tl.get_stock_id("NIFTY")
    
    # Try fetching for a date
    url = f"{tl.base_url}/live-oi-data/"
    # Note: Trendlyne often uses 'expDateList' for the expiry, and 'minTime'/'maxTime' for filtering
    # But usually it's for today's snapshot. Let's see if it gives history.
    params = {
        'stockId': stock_id,
        'expDateList': '2026-01-27',
        'minTime': '09:15',
        'maxTime': '10:00'
    }
    
    print(f"Calling: {url}")
    print(f"Params: {params}")
    
    headers = {
        'Cookie': 'csrftoken=TxzIO3d7zB6Mhq7nVxN98vKEPp6qp8BLmtN0ZnuIfHlPNBeWeSue3qqpVym9eKRm'
    }
    
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # print(json.dumps(data, indent=2))
            body = data.get('body', {})
            print(f"Body keys: {list(body.keys())}")
            
            # Check for history in overallData or similar
            overall = body.get('overallData', {})
            print(f"OverallData keys: {list(overall.keys())}")
            
            # If strikeWiseData is a list of snapshots?
            strike_wise = body.get('strikeWiseData', {})
            print(f"StrikeWiseData count: {len(strike_wise)}")

if __name__ == "__main__":
    asyncio.run(test_live_oi())
