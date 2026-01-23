import asyncio
from trendlyneAdvClient import TrendlyneScalper
from datetime import datetime

async def inspect():
    tl = TrendlyneScalper()
    symbol = "NIFTY"
    # Current ATM roughly
    atm = 23500 
    
    strikes = [atm - 100, atm, atm + 100]
    
    print(f"=== Inspecting OI for {symbol} ===")
    for strike in strikes:
        print(f"\nSTRIKE: {strike}")
        ce = await tl.get_buildup_5m(symbol, strike=strike, o_type="Call")
        pe = await tl.get_buildup_5m(symbol, strike=strike, o_type="Put")
        
        if ce:
            print(f"  CE Last Record: {ce[-1].get('interval')} | OI: {ce[-1].get('open_interest')} | Keys: {list(ce[-1].keys())}")
        else:
            print("  CE: NO DATA")
            
        if pe:
            print(f"  PE Last Record: {pe[-1].get('interval')} | OI: {pe[-1].get('open_interest')} | Keys: {list(pe[-1].keys())}")
        else:
            print("  PE: NO DATA")

if __name__ == "__main__":
    asyncio.run(inspect())
