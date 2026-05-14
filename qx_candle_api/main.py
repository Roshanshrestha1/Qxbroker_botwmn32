"""
QxBroker Private Candle API Server
===================================
A private local API that fetches real candle data from QxBroker via WebSocket.

Run: uvicorn main:app --host 127.0.0.1 --port 8000

Endpoints:
    GET /                       - API status
    GET /docs                   - Interactive API docs (Swagger UI)
    GET /balance                - Account balance
    GET /assets                 - List all available assets
    GET /payouts                - Payout percentages for all assets
    GET /candles/{asset}        - Historical candles (hours of data)
    GET /candles/{asset}/latest - Latest N candles
    GET /candles/{asset}/live   - Current live candle
    GET /price/{asset}          - Latest tick price
    GET /sentiment/{asset}      - Market sentiment (% buy/sell)
"""

import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from qx_client import (
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
    print("Connecting to QxBroker...")
    await connect_client()
    print("API ready.")
    yield
    print("Shutting down.")


app = FastAPI(
    title="QxBroker Private Candle API",
    description="Private local API — fetches real candle data from QxBroker via WebSocket",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow only localhost — this keeps it private
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_methods=["GET"],
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
        "note": "Private QxBroker candle API",
        "docs": "http://localhost:8000/docs",
    }


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

        # Separate normal and OTC
        normal = [a for a in assets.keys() if not a.endswith("_otc")]
        otc = [a for a in assets.keys() if a.endswith("_otc")]

        return {
            "total": len(assets),
            "normal": sorted(normal),
            "otc": sorted(otc),
            "all": sorted(assets.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/payouts")
async def get_payouts():
    """Get payout % for all assets. Shows which are open/closed."""
    try:
        return await fetch_payouts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/candles/{asset}")
async def get_candles(
    asset: str,
    period: int = Query(
        default=60,
        description="Candle period in seconds: 5,15,30,60,300,900,3600,86400",
    ),
    hours: int = Query(
        default=1, description="How many hours of history to fetch (1-24)"
    ),
):
    """
    Fetch historical OHLCV candles from QxBroker.

    Example: /candles/EURUSD?period=60&hours=2

    Asset examples:
      EURUSD, GBPUSD, USDJPY, XAUUSD, BTCUSD
      Add _otc suffix for OTC version: EURUSD_otc

    Period examples (seconds):
      5=5s  60=1min  300=5min  900=15min  3600=1hr  86400=1day
    """
    if hours < 1 or hours > 24:
        raise HTTPException(status_code=400, detail="hours must be between 1 and 24")

    valid_periods = [
        5,
        10,
        15,
        30,
        60,
        120,
        180,
        240,
        300,
        600,
        900,
        1800,
        3600,
        14400,
        86400,
    ]
    if period not in valid_periods:
        raise HTTPException(
            status_code=400, detail=f"period must be one of: {valid_periods}"
        )

    try:
        candles = await fetch_historical_candles(
            asset=asset.upper(), hours=hours, period=period
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
    """
    Fetch latest N candles (max 200).

    Example: /candles/EURUSD/latest?period=60&count=50
    """
    if count > 200:
        raise HTTPException(status_code=400, detail="count cannot exceed 200")

    try:
        candles = await fetch_latest_candles(
            asset=asset.upper(), count=count, period=period
        )
        return {
            "asset": asset.upper(),
            "period": period,
            "count": len(candles),
            "candles": candles,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/candles/{asset}/max")
async def get_max_candles(
    asset: str,
    period: int = Query(default=60, description="Candle period in seconds"),
):
    """
    Fetch maximum 200 candles at once (broker limit).

    Example: /candles/EURUSD/max?period=60
    Returns 200 candles (or up to broker limit ~199)
    """
    try:
        candles = await fetch_latest_candles(
            asset=asset.upper(), count=200, period=period
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
async def get_live_candle(
    asset: str,
    period: int = Query(default=60),
):
    """
    Get the current live candle being formed right now.

    Example: /candles/EURUSD/live?period=60
    """
    try:
        candle = await fetch_realtime_candle(asset=asset.upper(), period=period)
        return {"asset": asset.upper(), "period": period, "candle": candle}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/price/{asset}")
async def get_price(
    asset: str,
    period: int = Query(default=60),
):
    """
    Get the latest tick price for an asset.

    Example: /price/EURUSD
    """
    try:
        price = await fetch_realtime_price(asset=asset.upper(), period=period)
        return {"asset": asset.upper(), "data": price}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sentiment/{asset}")
async def get_sentiment(asset: str):
    """
    Get real market sentiment — % of real traders buying vs selling.

    Example: /sentiment/EURUSD
    Response: {"buy": 62, "sell": 38}
    """
    try:
        sentiment = await fetch_sentiment(asset.upper())
        return {"asset": asset.upper(), "sentiment": sentiment}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# Run: uvicorn main:app --host 127.0.0.1 --port 8000
# -------------------------------------------------------
