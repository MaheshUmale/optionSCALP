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

    # Pick first expiry
    dt_str = exp_data['expiresDts'][0]
    try:
        dt = datetime.strptime(dt_str, "%d-%b-%Y")
    except:
        dt = datetime.strptime(dt_str, "%Y-%m-%d")

    print(f"Fetching buildup for {dt.date()}...")
    data = await tl.get_buildup_5m( "NIFTY")
    
    if data:
        print("First record structure:")
        print(data[0])
    else:
        print("No buildup data returned.")

    await tl.aclose()

if __name__ == "__main__":
    asyncio.run(main())
