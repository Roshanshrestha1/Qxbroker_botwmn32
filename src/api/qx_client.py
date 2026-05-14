"""
QxBroker Client - WebSocket connection to QxBroker API.
Handles authentication, candle fetching, and real-time data.
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------
# Singleton client — one connection shared across the API
# -------------------------------------------------------
_client = None
_ssid = None
_connected = False


async def get_ssid():
    """Get SSID from environment or session file."""
    global _ssid
    
    if _ssid:
        return _ssid
    
    # Try to load from session file
    session_file = os.path.join(os.path.dirname(__file__), "..", "config", "session.json")
    
    if os.path.exists(session_file):
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
                account_type = os.getenv("QX_ACCOUNT", "PRACTICE").upper()
                if account_type == "REAL":
                    _ssid = session_data.get("live")
                else:
                    _ssid = session_data.get("ssid")
                
                if _ssid:
                    print(f"✓ Loaded SSID from session file")
                    return _ssid
        except Exception as e:
            print(f"Failed to load session: {e}")
    
    # Fallback to environment variables
    _ssid = os.getenv("QX_SSID")
    if _ssid:
        print(f"✓ Loaded SSID from environment")
        return _ssid
    
    raise Exception(
        "No SSID found. Please either:\n"
        "1. Set QX_SSID in .env file, OR\n"
        "2. Create config/session.json with your SSID\n"
        "3. Run extract_ssid.py to get your SSID"
    )


async def get_client():
    """Get or create the singleton Quotex client instance."""
    global _client
    
    if _client is None:
        ssid = await get_ssid()
        is_demo = os.getenv("QX_ACCOUNT", "PRACTICE").upper() == "PRACTICE"
        
        print(f"Creating client with SSID: {ssid[:20]}..., is_demo={is_demo}")
        
        _client = AsyncQuotexClient(
            ssid=ssid, 
            is_demo=is_demo
        )
    
    return _client


async def connect_client():
    """Connect and authenticate. Called once at startup."""
    global _connected
    
    if _connected:
        return _client
    
    client = await get_client()
    
    print("Connecting to QxBroker...")
    
    # Try connection with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            connected = await client.connect()
            print(f"Connection attempt {attempt + 1}: {connected}")
            
            if connected:
                _connected = True
                print("✓ Connected successfully!")
                return client
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
    
    raise Exception("Connection failed after retries")


async def ensure_connected():
    """Check connection health and reconnect if needed."""
    global _connected
    
    if not _connected or _client is None:
        await connect_client()
    
    return _client


# -------------------------------------------------------
# CANDLE FETCHERS
# -------------------------------------------------------


async def fetch_historical_candles(asset: str, hours: int = 1, period: int = 60) -> List[Dict]:
    """Fetch historical OHLCV candles."""
    client = await ensure_connected()
    
    num_candles = (hours * 3600) // period
    
    candles = await client.get_candles(asset, period, num_candles)
    
    result = []
    for c in candles:
        result.append({
            "time": int(c.timestamp.timestamp()) if hasattr(c.timestamp, "timestamp") else c.timestamp,
            "open": float(c.open),
            "high": float(c.high),
            "low": float(c.low),
            "close": float(c.close),
            "volume": float(c.volume) if hasattr(c, "volume") else 0,
        })
    
    return result


async def fetch_latest_candles(asset: str, count: int = 200, period: int = 60) -> List[Dict]:
    """Fetch latest N candles."""
    client = await ensure_connected()
    
    candles = await client.get_candles(asset, period, count)
    
    result = []
    for c in candles:
        result.append({
            "time": int(c.timestamp.timestamp()) if hasattr(c.timestamp, "timestamp") else c.timestamp,
            "open": float(c.open),
            "high": float(c.high),
            "low": float(c.low),
            "close": float(c.close),
            "volume": float(c.volume) if hasattr(c, "volume") else 0,
        })
    
    return result


async def fetch_realtime_candle(asset: str, period: int = 60) -> Dict:
    """Fetch the current live candle."""
    candles = await fetch_latest_candles(asset, 1, period)
    return candles[0] if candles else None


async def fetch_realtime_price(asset: str, period: int = 60) -> Optional[Dict]:
    """Fetch latest price."""
    candles = await fetch_latest_candles(asset, 1, period)
    if candles:
        return {"price": candles[0]["close"], "time": candles[0]["time"]}
    return None


async def fetch_sentiment(asset: str) -> Dict:
    """Fetch market sentiment (% buy/sell)."""
    client = await ensure_connected()
    return client.get_sentiment(asset)


async def fetch_balance() -> Dict:
    """Get current account balance."""
    client = await ensure_connected()
    return await client.get_balance()


async def fetch_all_assets() -> Dict[str, Any]:
    """Get list of all available assets."""
    client = await ensure_connected()
    assets = await client.get_available_assets()
    return assets if assets else {}


async def fetch_payouts() -> Dict[str, Any]:
    """Get payout percentages for all assets."""
    client = await ensure_connected()
    return await client.get_assets_and_payouts()


# -------------------------------------------------------
# AsyncQuotexClient Implementation
# -------------------------------------------------------

class AsyncQuotexClient:
    """Async WebSocket client for QxBroker."""
    
    def __init__(self, ssid: str, is_demo: bool = True):
        self.ssid = ssid
        self.is_demo = is_demo
        self.ws = None
        self.connected = False
        self.account_id = None
        self.balance = None
        self.assets_info = {}
        self.request_id = 0
        self.pending_requests = {}
        self.candle_subscriptions = {}
        
    async def connect(self) -> bool:
        """Establish WebSocket connection and authenticate."""
        import websockets
        
        ws_url = "wss://ws.qxbroker.com"
        
        try:
            self.ws = await websockets.connect(ws_url)
            print(f"Connected to {ws_url}")
            
            # Authenticate
            auth_msg = {
                "name": "authorize",
                "version": "1.0",
                "body": {
                    "ssid": self.ssid,
                    "demo": self.is_demo
                }
            }
            
            await self.ws.send(json.dumps(auth_msg))
            response = await self.ws.recv()
            auth_response = json.loads(response)
            
            if auth_response.get("name") == "profile":
                self.account_id = auth_response["body"].get("id")
                self.balance = auth_response["body"].get("balance")
                self.connected = True
                print(f"✓ Authenticated. Account: {self.account_id}")
                return True
            else:
                print(f"Auth failed: {auth_response}")
                return False
                
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    async def get_candles(self, asset: str, period: int, count: int) -> List:
        """Fetch historical candles."""
        if not self.connected:
            raise Exception("Not connected")
        
        self.request_id += 1
        req_id = self.request_id
        
        msg = {
            "name": "candles",
            "version": "1.0",
            "body": {
                "req_id": req_id,
                "asset": asset,
                "period": period,
                "count": count
            }
        }
        
        future = asyncio.Future()
        self.pending_requests[req_id] = future
        
        await self.ws.send(json.dumps(msg))
        
        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
        except asyncio.TimeoutError:
            del self.pending_requests[req_id]
            raise Exception("Candle request timeout")
    
    async def get_balance(self) -> Dict:
        """Get account balance."""
        if self.balance:
            return {"balance": self.balance, "currency": "USD", "account_type": "DEMO" if self.is_demo else "REAL"}
        
        self.request_id += 1
        req_id = self.request_id
        
        msg = {
            "name": "balance",
            "version": "1.0",
            "body": {"req_id": req_id}
        }
        
        await self.ws.send(json.dumps(msg))
        
        # Wait for balance update
        await asyncio.sleep(0.5)
        return {"balance": self.balance, "currency": "USD", "account_type": "DEMO" if self.is_demo else "REAL"}
    
    async def get_available_assets(self) -> Dict:
        """Get list of available trading assets."""
        if self.assets_info:
            return self.assets_info
        
        self.request_id += 1
        req_id = self.request_id
        
        msg = {
            "name": "assets",
            "version": "1.0",
            "body": {"req_id": req_id}
        }
        
        await self.ws.send(json.dumps(msg))
        
        # Wait for assets response
        await asyncio.sleep(1.0)
        return self.assets_info
    
    async def get_assets_and_payouts(self) -> Dict:
        """Get assets with payout percentages."""
        return await self.get_available_assets()
    
    def get_sentiment(self, asset: str) -> Dict:
        """Get market sentiment (mock implementation)."""
        # This would need real implementation based on broker data
        import random
        buy_pct = random.randint(40, 60)
        return {"buy": buy_pct, "sell": 100 - buy_pct}
    
    async def message_handler(self):
        """Handle incoming WebSocket messages."""
        try:
            async for message in self.ws:
                data = json.loads(message)
                name = data.get("name")
                body = data.get("body", {})
                
                if name == "candles":
                    req_id = body.get("req_id")
                    if req_id in self.pending_requests:
                        candles_data = body.get("data", [])
                        # Parse candles
                        parsed = []
                        for c in candles_data:
                            if isinstance(c, list) and len(c) >= 6:
                                parsed.append(CandleData(
                                    timestamp=datetime.fromtimestamp(c[0]),
                                    open=c[1],
                                    high=c[2],
                                    low=c[3],
                                    close=c[4],
                                    volume=c[5] if len(c) > 5 else 0
                                ))
                        self.pending_requests[req_id].set_result(parsed)
                        del self.pending_requests[req_id]
                
                elif name == "assets":
                    # Store assets info
                    self.assets_info = body.get("assets", {})
                
                elif name == "balance":
                    self.balance = body.get("amount", self.balance)
                    
        except Exception as e:
            print(f"Message handler error: {e}")


class CandleData:
    """Simple candle data container."""
    
    def __init__(self, timestamp, open, high, low, close, volume=0):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
