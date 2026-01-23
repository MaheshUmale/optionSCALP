import asyncio
from data.gathering.data_manager import DataManager
from datetime import datetime, timedelta
import pandas as pd

async def test_timezone():
    dm = DataManager()
    ref_date = datetime(2026, 1, 23, 15, 30)
    df = dm.get_data("NIFTY", n_bars=10, reference_date=ref_date)
    
    print(f"Dataframe Index Example: {df.index[-1]}")
    print(f"Index type: {type(df.index)}")
    print(f"Sample Time: {df.index[-1].time()}")
    
    # Check between_time behavior
    print(f"\nTesting between_time('03:45', '10:00'):")
    df_utc = df.between_time('03:45', '10:00')
    print(f"Result count: {len(df_utc)}")
    if not df_utc.empty:
        print(f"Range: {df_utc.index[0]} to {df_utc.index[-1]}")
        
    print(f"\nTesting between_time('09:15', '15:30'):")
    df_ist = df.between_time('09:15', '15:30')
    print(f"Result count: {len(df_ist)}")
    if not df_ist.empty:
        print(f"Range: {df_ist.index[0]} to {df_ist.index[-1]}")

if __name__ == "__main__":
    asyncio.run(test_timezone())
