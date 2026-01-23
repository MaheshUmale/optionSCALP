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

    dt_str = exp_data['expiresDts'][0] # e.g. 29-Jan-2026
    print(f"Expiry: {dt_str}")
    
    # Try fetching "PCRO" or similar if possible? 
    # Or just inspect raw output of default call again carefully
    try:
        dt = datetime.strptime(dt_str, "%d-%b-%Y")
    except:
        dt = datetime.strptime(dt_str, "%Y-%m-%d")

    print("--- Default Buildup (Index Futures?) ---")
    data = await tl.get_buildup_5m( "NIFTY")
    if data:
        print(f"Keys: {data[0].keys()}")
        print(f"Sample: {data[0]}")
    
    print("\n--- Options Buildup? (Try to find PCR) ---")
    # There is no direct "get_pcr_history" method.
    # Maybe parameters in get_buildup_5m can be tweaked?
    # The URL is .../buildup-5/{expiry}/{symbol}/
    # params: fno_mtype=options?
    
    # We will try to call the internal client get method with modified params
    base_url = tl.base_url
    s_mapped = "NIFTY"
    fmt_exp = f"{dt.strftime('%d-%b-%Y').lower()}-near"
    url = f"{base_url}/fno/buildup-5/{fmt_exp}/{s_mapped}/"
    
    print(f"Trying URL: {url} with fno_mtype=options")
    try:
        resp = await tl.client.get(url, params={'fno_mtype': 'options'}) # Guessing param
        print(f"Status: {resp.status_code}")
        d = resp.json()
        body = d.get('body', {}).get('data_v2', [])
        if body:
            print(f"Keys: {body[0].keys()}")
            print(f"Sample: {body[0]}")
    except Exception as e:
        print(f"Error: {e}")

    await tl.aclose()

if __name__ == "__main__":
    asyncio.run(main())
