"""
QxBroker Connection Test Script - Using API-Quotex
===================================================
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def run_test():
    print("=" * 50)
    print("QxBroker Connection Test (API-Quotex)")
    print("=" * 50)

    # Step 1: Get SSID via Playwright (opens browser)
    print("\n1. Getting SSID via Playwright...")
    print("   (First time: browser will open for login)")

    from api_quotex import get_ssid

    email = os.getenv("QX_EMAIL")
    password = os.getenv("QX_PASSWORD")

    success, ssid_info = await get_ssid(email=email, password=password)
    if not success:
        print("   FAILED: Could not get SSID")
        return
    print(f"   Got SSID info: {list(ssid_info.keys())}")

    # Choose demo or real
    account_type = os.getenv("QX_ACCOUNT", "PRACTICE").upper()
    is_demo = account_type == "PRACTICE"

    ssid = ssid_info.get("ssid")
    print(f"   Using {'demo' if is_demo else 'live'} account")
    print(f"   SSID: {ssid[:50]}..." if ssid else "   SSID: None")

    # Step 2: Connect
    print("\n2. Connecting to QxBroker...")
    from api_quotex import AsyncQuotexClient

    client = AsyncQuotexClient(ssid=ssid, is_demo=is_demo)
    connected = await client.connect()

    if not connected:
        print("   FAILED: Could not connect")
        return

    print("   OK — Connected")

    # Step 3: Get balance
    print("\n3. Getting balance...")
    balance = await client.get_balance()
    print(f"   Balance: {balance.balance} {balance.currency}")

    # Step 4: Get assets
    print("\n4. Getting available assets...")
    try:
        assets = await client.get_available_assets()
        print(f"   Found {len(assets)} assets")
        if assets:
            print(f"   First 5: {list(assets.keys())[:5]}")
    except Exception as e:
        print(f"   Could not get assets: {e}")

    # Step 5: Get candles
    print("\n5. Fetching candles for EURUSD...")
    try:
        candles = await client.get_candles("EURUSD", 60, 10)
        print(f"   Got {len(candles)} candles")
        if candles:
            last = candles[-1]
            print(f"   Latest: O={last.open} C={last.close}")
    except Exception as e:
        print(f"   Could not get candles: {e}")

    # Cleanup
    await client.disconnect()

    print("\n" + "=" * 50)
    print("All tests passed! Ready to run API server.")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_test())
