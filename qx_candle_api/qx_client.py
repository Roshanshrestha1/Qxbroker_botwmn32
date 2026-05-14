"""
QxBroker Client - Fixed version.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------
# Singleton client — one connection shared across the API
# -------------------------------------------------------
_client = None
_ssid = None


async def get_ssid():
    """Get SSID - try to use existing session first."""
    global _ssid

    # Use current directory for session file
    session_file = os.path.join(os.path.dirname(__file__), "session.json")

    if _ssid is None:
        from api_quotex import get_ssid as playwright_get_ssid

        email = os.getenv("QX_EMAIL")
        password = os.getenv("QX_PASSWORD")

        print(f"Logging in via Playwright...")

        # Try existing session first
        if os.path.exists(session_file):
            print("Trying existing session...")
            try:
                from api_quotex import get_ssid as validate_ssid

                success, ssid_info = await validate_ssid(email=email, password=password)
                if success:
                    account_type = os.getenv("QX_ACCOUNT", "PRACTICE").upper()
                    if account_type == "REAL":
                        _ssid = ssid_info.get("live")
                    else:
                        _ssid = ssid_info.get("ssid")
                    if _ssid:
                        print(f"Got SSID from existing session: {_ssid[:30]}...")
                        return _ssid
            except:
                pass

        # Fresh login
        print("Doing fresh login...")
        success, ssid_info = await playwright_get_ssid(email=email, password=password)

        if not success:
            raise Exception("Failed to get SSID")

        account_type = os.getenv("QX_ACCOUNT", "PRACTICE").upper()
        if account_type == "REAL":
            _ssid = ssid_info.get("live")
        else:
            _ssid = ssid_info.get("ssid")

        print(f"Got SSID: {_ssid[:30]}..." if _ssid else "No SSID")

    return _ssid


async def get_client():
    """Get or create the singleton Quotex client instance."""
    global _client

    if _client is None:
        from api_quotex import AsyncQuotexClient

        ssid = await get_ssid()
        is_demo = os.getenv("QX_ACCOUNT", "PRACTICE").upper() == "PRACTICE"

        print(f"Creating client with SSID: {ssid[:30] if ssid else 'None'}..., is_demo={is_demo}")

        _client = AsyncQuotexClient(
            ssid=ssid, 
            is_demo=is_demo
        )

    return _client


async def connect_client():
    """Connect and authenticate. Called once at startup."""
    client = await get_client()

    print("Connecting to QxBroker...")
    
    # Try connection with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            connected = await client.connect()
            print(f"Connection attempt {attempt + 1}: {connected}")
            
            if connected:
                print("Connected successfully!")
                return client
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
    
    raise Exception("Connection failed after retries")


async def ensure_connected():
    """Check connection health."""
    client = await get_client()
    return client


# -------------------------------------------------------
# CANDLE FETCHERS
# -------------------------------------------------------


async def fetch_historical_candles(asset: str, hours: int = 1, period: int = 60):
    """Fetch historical OHLCV candles."""
    client = await ensure_connected()

    num_candles = (hours * 3600) // period

    candles = await client.get_candles(asset, period, num_candles)

    result = []
    for c in candles:
        result.append(
            {
                "time": int(c.timestamp.timestamp())
                if hasattr(c.timestamp, "timestamp")
                else c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume) if hasattr(c, "volume") else 0,
            }
        )

    return result


async def fetch_latest_candles(asset: str, count: int = 200, period: int = 60):
    """Fetch latest N candles."""
    client = await ensure_connected()

    candles = await client.get_candles(asset, period, count)

    result = []
    for c in candles:
        result.append(
            {
                "time": int(c.timestamp.timestamp())
                if hasattr(c.timestamp, "timestamp")
                else c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume) if hasattr(c, "volume") else 0,
            }
        )

    return result


async def fetch_realtime_candle(asset: str, period: int = 60):
    """Fetch the current live candle."""
    return await fetch_latest_candles(asset, 1, period)


async def fetch_realtime_price(asset: str, period: int = 60):
    """Fetch latest price."""
    candles = await fetch_latest_candles(asset, 1, period)
    if candles:
        return {"price": candles[0]["close"], "time": candles[0]["time"]}
    return None


async def fetch_sentiment(asset: str):
    """Fetch market sentiment."""
    client = await ensure_connected()
    return client.get_sentiment(asset)


async def fetch_balance():
    """Get current account balance."""
    client = await ensure_connected()
    return await client.get_balance()


async def fetch_all_assets():
    """Get list of all available assets."""
    client = await ensure_connected()
    # Use the correct method - returns list
    assets = await client.get_available_assets()
    return assets if assets else []


async def fetch_payouts():
    """Get payout percentages for all assets."""
    client = await ensure_connected()
    # Use the correct method
    return await client.get_assets_and_payouts()
