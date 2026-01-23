import asyncio
from trendlyneAdvClient import TrendlyneScalper
from datetime import datetime

async def main():
    tl = TrendlyneScalper()
    stock_id = await tl.get_stock_id("NIFTY")
    
    exp_data = await tl.get_expiry_data(stock_id)
    dt_str = exp_data['expiresDts'][0]
    try:
         dt = datetime.strptime(dt_str, "%d-%b-%Y")
    except:
         dt = datetime.strptime(dt_str, "%Y-%m-%d")
    api_expiry_str = dt.strftime("%Y-%m-%d")

    print(f"Fetching for {api_expiry_str}")
    data = await tl.get_live_oi_snapshot(stock_id, api_expiry_str)
    
    if data and 'body' in data and 'oiData' in data['body']:
        oi_data = data['body']['oiData']
        print(f"oiData type: {type(oi_data)}")
        if isinstance(oi_data, list) and len(oi_data) > 0:
            print(f"Rec 1: {oi_data[0]}")
        elif isinstance(oi_data, dict):
            print(f"Keys: {oi_data.keys()}")
            # It might be dict of timestamps? or dict of 'lines'?
            for k in list(oi_data.keys())[:2]:
                print(f"{k}: {oi_data[k]}")

    await tl.aclose()

if __name__ == "__main__":
    asyncio.run(main())
