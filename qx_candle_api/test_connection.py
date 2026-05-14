import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    """Test QxBroker connection step by step."""
    
    print("=" * 50)
    print("Testing QxBroker Connection")
    print("=" * 50)
    
    # Step 1: Check credentials
    print("\n1. Checking credentials...")
    email = os.getenv("QX_EMAIL")
    password = os.getenv("QX_PASSWORD")
    account_type = os.getenv("QX_ACCOUNT", "PRACTICE")
    
    print(f"   Email: {email}")
    print(f"   Password: {'*' * len(password) if password else 'None'}")
    print(f"   Account: {account_type}")
    
    if not email or not password:
        print("   ❌ ERROR: Missing credentials!")
        return
    
    print("   ✅ Credentials found")
    
    # Step 2: Get SSID
    print("\n2. Getting SSID...")
    try:
        from api_quotex import get_ssid as playwright_get_ssid
        
        success, ssid_info = await playwright_get_ssid(email=email, password=password)
        
        print(f"   Success: {success}")
        print(f"   SSID Info: {ssid_info}")
        
        if not success:
            print("   ❌ ERROR: Failed to get SSID!")
            return
        
        account_type_upper = account_type.upper()
        if account_type_upper == "REAL":
            ssid = ssid_info.get("live")
        else:
            ssid = ssid_info.get("ssid")
        
        print(f"   SSID: {ssid[:30] if ssid else 'None'}...")
        
        if not ssid:
            print("   ❌ ERROR: No SSID in response!")
            return
            
        print("   ✅ SSID obtained")
        
    except Exception as e:
        print(f"   ❌ ERROR getting SSID: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 3: Create client
    print("\n3. Creating AsyncQuotexClient...")
    try:
        from api_quotex import AsyncQuotexClient
        
        is_demo = account_type_upper == "PRACTICE"
        print(f"   is_demo: {is_demo}")
        
        client = AsyncQuotexClient(ssid=ssid, is_demo=is_demo)
        print("   ✅ Client created")
        
    except Exception as e:
        print(f"   ❌ ERROR creating client: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Connect
    print("\n4. Connecting to QxBroker...")
    try:
        connected = await client.connect()
        print(f"   Connected: {connected}")
        
        if not connected:
            print("   ❌ ERROR: Connection failed!")
            print("   Trying alternative connection methods...")
            
            # Try without any special parameters
            print("   Attempting basic connection...")
            # The client might already be connected, try to get assets directly
            try:
                assets = await client.get_available_assets()
                print(f"   ✅ Got {len(assets)} assets (connection might be working)")
                print(f"   Sample assets: {list(assets.keys())[:5]}")
                return
            except Exception as e2:
                print(f"   ❌ Still failed: {e2}")
                return
        
        print("   ✅ Connected successfully!")
        
    except Exception as e:
        print(f"   ❌ ERROR connecting: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 5: Test getting assets
    print("\n5. Testing get_available_assets()...")
    try:
        assets = await client.get_available_assets()
        print(f"   ✅ Got {len(assets)} assets")
        print(f"   Sample: {list(assets.keys())[:5]}")
        
    except Exception as e:
        print(f"   ❌ ERROR getting assets: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 6: Test getting candles
    print("\n6. Testing get_candles()...")
    try:
        if assets:
            first_asset = list(assets.keys())[0]
            print(f"   Testing with asset: {first_asset}")
            
            candles = await client.get_candles(first_asset, 60, 10)
            print(f"   ✅ Got {len(candles)} candles")
            if candles:
                print(f"   First candle: {candles[0]}")
        
    except Exception as e:
        print(f"   ❌ ERROR getting candles: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_connection())
