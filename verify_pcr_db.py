
import asyncio
from datetime import datetime
from data.database import DatabaseManager

async def verify():
    db = DatabaseManager()
    symbol = "TEST_PCR"
    timestamp = int(datetime.now().timestamp())
    pcr = 1.23
    call_oi = 1000.0
    put_oi = 1230.0

    print("Storing PCR history...")
    db.store_pcr_history(symbol, timestamp, pcr, call_oi, put_oi)

    print("Retrieving PCR history...")
    df = db.get_pcr_history(symbol)
    print("Retrieved DF:")
    print(df)

    if not df.empty and df.iloc[0]['pcr'] == 1.23:
        print("✅ PCR Data verification successful!")
    else:
        print("❌ PCR Data verification failed!")

if __name__ == "__main__":
    asyncio.run(verify())
