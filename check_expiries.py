"""
Quick script to fetch and compare NIFTY and BANKNIFTY expiry dates
"""
import sys
import asyncio
sys.path.insert(0, 'd:/optionSCALP')

from trendlyne_client import TrendlyneClient

async def main():
    client = TrendlyneClient()

    # Get NIFTY expiry dates
    print("=" * 60)
    print("FETCHING NIFTY EXPIRY DATES")
    print("=" * 60)
    nifty_stock_id = await client.get_stock_id_for_symbol("NIFTY")
    print(f"NIFTY Stock ID: {nifty_stock_id}")

    nifty_expiries = await client.get_expiry_dates(nifty_stock_id)
    print(f"\nNIFTY Expiry Dates ({len(nifty_expiries)} total):")
    for exp in nifty_expiries[:10]:  # Show first 10
        print(f"  - {exp}")
    if len(nifty_expiries) > 10:
        print(f"  ... and {len(nifty_expiries) - 10} more")

    # Get BANKNIFTY expiry dates
    print("\n" + "=" * 60)
    print("FETCHING BANKNIFTY EXPIRY DATES")
    print("=" * 60)
    banknifty_stock_id = await client.get_stock_id_for_symbol("BANKNIFTY")
    print(f"BANKNIFTY Stock ID: {banknifty_stock_id}")

    banknifty_expiries = await client.get_expiry_dates(banknifty_stock_id)
    print(f"\nBANKNIFTY Expiry Dates ({len(banknifty_expiries)} total):")
    for exp in banknifty_expiries[:10]:  # Show first 10
        print(f"  - {exp}")
    if len(banknifty_expiries) > 10:
        print(f"  ... and {len(banknifty_expiries) - 10} more")

    # Compare expiry patterns
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    print(f"NIFTY has {len(nifty_expiries)} expiries")
    print(f"BANKNIFTY has {len(banknifty_expiries)} expiries")

    # Find expiries around Jan 20-22, 2026
    print("\nExpiries around 2026-01-20 to 2026-01-27:")
    target_expiries = [e for e in nifty_expiries if "2026-01-2" in e and int(e.split("-")[2]) >= 20]
    print(f"NIFTY: {target_expiries[:5]}")

    target_expiries_bn = [e for e in banknifty_expiries if "2026-01-2" in e and int(e.split("-")[2]) >= 20]
    print(f"BANKNIFTY: {target_expiries_bn[:5]}")

if __name__ == "__main__":
    asyncio.run(main())
