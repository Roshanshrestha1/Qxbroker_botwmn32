"""
QxBroker API Server - FastAPI REST API for QxBroker data.
Provides endpoints for candles, prices, balance, assets, and sentiment.
"""

import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List, Dict, Any

# Import from our clean client module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.qx_client import (
    connect_client,
    fetch_historical_candles,
    fetch_latest_candles,
    fetch_realtime_candle,
    fetch_realtime_price,
    fetch_sentiment,
    fetch_balance,
    fetch_all_assets,
    fetch_payouts,
)


# -------------------------------------------------------
# Startup: connect to QxBroker when API server starts
# -------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("Starting QxBroker API Server...")
    print("=" * 50)
    try:
        await connect_client()
        print("✓ API server ready!")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        print("API will start but data requests will fail until connected.")
    yield
    print("Shutting down API server...")


app = FastAPI(
    title="QxBroker Trading API",
    description="Private local API for QxBroker - Real-time candles, prices, and trading data",
    version="2.0.0",
    lifespan=lifespan,
)

# Allow localhost connections only (private API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# -------------------------------------------------------
# ENDPOINTS
# -------------------------------------------------------

@app.get("/")
async def root():
    """API status endpoint."""
    return {
        "status": "running",
        "service": "QxBroker Trading API",
        "version": "2.0.0",
        "docs": "http://localhost:8000/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/balance")
async def get_balance():
    """Get current account balance."""
    try:
        return await fetch_balance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/assets")
async def get_assets():
    """Get list of all available trading assets."""
    try:
        assets = await fetch_all_assets()
        
        # Handle different asset formats
        if isinstance(assets, dict):
            asset_list = list(assets.keys())
        elif isinstance(assets, list):
            asset_list = assets
        else:
            asset_list = []
        
        # Separate normal and OTC
        normal = [a for a in asset_list if not str(a).endswith("_otc")]
        otc = [a for a in asset_list if str(a).endswith("_otc")]
        
        return {
            "total": len(asset_list),
            "normal": sorted([str(a) for a in normal]),
            "otc": sorted([str(a) for a in otc]),
            "all": sorted([str(a) for a in asset_list]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/payouts")
async def get_payouts():
    """Get payout % for all assets."""
    try:
        return await fetch_payouts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/candles/{asset}")
async def get_candles(
    asset: str,
    period: int = Query(default=60, description="Candle period in seconds"),
    hours: int = Query(default=1, description="Hours of history (1-24)"),
):
    """
    Fetch historical OHLCV candles from QxBroker.
    
    Examples:
      /candles/EURUSD?period=60&hours=2
      /candles/BTCUSD_otc?period=300&hours=1
    """
    if hours < 1 or hours > 24:
        raise HTTPException(status_code=400, detail="hours must be between 1 and 24")
    
    valid_periods = [5, 10, 15, 30, 60, 120, 180, 240, 300, 600, 900, 1800, 3600, 14400, 86400]
    if period not in valid_periods:
        raise HTTPException(status_code=400, detail=f"period must be one of: {valid_periods}")
    
    try:
        candles = await fetch_historical_candles(
            asset=asset.upper(), 
            hours=hours, 
            period=period
        )
        return {
            "asset": asset.upper(),
            "period": period,
            "hours": hours,
            "count": len(candles),
            "candles": candles,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/candles/{asset}/latest")
async def get_latest_candles(
    asset: str,
    period: int = Query(default=60),
    count: int = Query(default=100, description="Number of candles (max 200)"),
):
    """Fetch latest N candles (max 200)."""
    if count > 200:
        raise HTTPException(status_code=400, detail="count cannot exceed 200")
    
    try:
        candles = await fetch_latest_candles(
            asset=asset.upper(), 
            count=count, 
            period=period
        )
        return {
            "asset": asset.upper(),
            "period": period,
            "count": len(candles),
            "candles": candles,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/candles/{asset}/live")
async def get_live_candle(asset: str, period: int = Query(default=60)):
    """Get the current live candle being formed."""
    try:
        candle = await fetch_realtime_candle(asset=asset.upper(), period=period)
        return {"asset": asset.upper(), "period": period, "candle": candle}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/price/{asset}")
async def get_price(asset: str, period: int = Query(default=60)):
    """Get the latest tick price for an asset."""
    try:
        price = await fetch_realtime_price(asset=asset.upper(), period=period)
        return {"asset": asset.upper(), "data": price}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sentiment/{asset}")
async def get_sentiment(asset: str):
    """Get market sentiment (% buy vs sell)."""
    try:
        sentiment = await fetch_sentiment(asset.upper())
        return {"asset": asset.upper(), "sentiment": sentiment}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# Run with: uvicorn src.api.main:app --host 127.0.0.1 --port 8000
# -------------------------------------------------------
