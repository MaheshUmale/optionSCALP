import asyncio
from datetime import datetime
from trendlyneAdvClient import TrendlyneScalper

async def test_pcr_fetch():
    tl = TrendlyneScalper()
    
    # Use EXACT parameters from user's working example
    test_date = datetime(2026, 1, 27, 15, 30)  # 27 Jan - the "near" expiry
    atm_strike = 25700  # User's exact strike
    
    print(f"\n=== Testing with USER'S EXACT PARAMS ===")
    print(f"Date: {test_date.date()}, Strike: {atm_strike}\n")
    
    print(f"Fetching CE data...")
    ce_data = await tl.get_buildup_5m( "NIFTY", strike=atm_strike, o_type="Call")
    
    print(f"\n✅ SUCCESS! Got {len(ce_data)} CE records")
    
    if ce_data and len(ce_data) > 0:
        print(f"\n=== Sample Record ===")
        sample = ce_data[0]
        print(f"Interval: {sample.get('interval')}")
        print(f"Buildup: {sample.get('buildup')}")
        print(f"OI: {sample.get('oi') or sample.get('open_interest')}")
        print(f"Close Price: {sample.get('close_price')}")
        
        print(f"\n=== Fetching PE data ===")
        pe_data = await tl.get_buildup_5m( "NIFTY", strike=atm_strike, o_type="Put")
        print(f"Got {len(pe_data)} PE records")
        
        if pe_data and len(pe_data) > 0:
            print(f"\n=== Calculating PCR for first interval ===")
            ce_oi = ce_data[0].get('oi') or ce_data[0].get('open_interest', 0)
            pe_oi = pe_data[0].get('oi') or pe_data[0].get('open_interest', 0)
            if ce_oi > 0:
                pcr = pe_oi / ce_oi
                print(f"PCR = {pe_oi} / {ce_oi} = {pcr:.2f}")
    else:
        print(f"❌ FAILED - Still getting 0 records")
    
    await tl.aclose()

if __name__ == "__main__":
    asyncio.run(test_pcr_fetch())
