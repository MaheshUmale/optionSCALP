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

    # Set up params for NIFTY ATM (approx 23300 or whatever current price is)
    # I'll just pick a likely strike to test, say 24500 or 25000 based on previous logs?
    # Previous log showed close price ~25080. So 25100 ATM.
    strike = 25100
    
    print(f"Fetching CE Buildup for NIFTY {strike} {dt.date()}...")
    ce_data = await tl.get_buildup_5m( "NIFTY", strike=strike, o_type="Call")
    
    if ce_data:
        print(f"CE Records: {len(ce_data)}")
        print(f"Sample CE: {ce_data[0]}")
    else:
        print("No CE data found.")

    print(f"Fetching PE Buildup for NIFTY {strike} {dt.date()}...")
    pe_data = await tl.get_buildup_5m("NIFTY", strike=strike, o_type="Put")
    if pe_data:
         print(f"PE Records: {len(pe_data)}")
         print(f"Sample PE: {pe_data[0]}")
    
    await tl.aclose()

if __name__ == "__main__":
    asyncio.run(main())
