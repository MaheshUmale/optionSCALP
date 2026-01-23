import asyncio
from trendlyneAdvClient import TrendlyneScalper
from datetime import datetime

async def main():
    tl = TrendlyneScalper()
    stock_id = await tl.get_stock_id("NIFTY")
    print(f"Stock ID: {stock_id}")
    
    exp_data = await tl.get_expiry_data(stock_id)
    if not exp_data['expiresDts']:
        print("No expiry dates found.")
        return

    dt_str = exp_data['expiresDts'][0]
    try:
        dt = datetime.strptime(dt_str, "%d-%b-%Y")
    except:
        dt = datetime.strptime(dt_str, "%Y-%m-%d")
        
    api_expiry_str = dt.strftime("%Y-%m-%d")
    print(f"Fetching live OI snapshot for {api_expiry_str}...")
    
    data = await tl.get_live_oi_snapshot(stock_id, api_expiry_str)
    
    if data and 'body' in data:
        body = data['body']
        print(f"Body Keys: {body.keys()}")
        
        # Check specific keys that might hold history
        if 'pcrData' in body:
            print("Found 'pcrData'!")
            print(f"Sample: {body['pcrData'][:2] if isinstance(body['pcrData'], list) else 'Not a list'}")
        
        if 'chartData' in body:
             print("Found 'chartData'!")
        
        if 'oiChartData' in body:
             print("Found 'oiChartData'!")
             
        # Inspect overallData structure just in case
        print(f"OverallData Keys: {body.get('overallData', {}).keys()}")
        
    else:
        print("No body in response")

    await tl.aclose()

if __name__ == "__main__":
    asyncio.run(main())
