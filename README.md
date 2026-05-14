# QxBroker Bot - WMA32 Trading System

A complete trading bot system for QxBroker that uses Weighted Moving Average (WMA) strategy to scan market assets and send trading signals via Telegram.

## Overview

This project consists of two main components:

1. **QxBroker Private Candle API** (`qx_candle_api/main.py`) - A local FastAPI server that fetches real candle data from QxBroker via WebSocket
2. **WMA32 Telegram Bot** (`qx_candle_api/wma32_bot.py`) - A Telegram bot that scans all assets using WMA(32) strategy and sends trading alerts

## Features

### API Server
- Real-time candle data from QxBroker WebSocket
- Multiple endpoints for candles, prices, sentiment, and account info
- Supports all timeframes (5s to 1day)
- Historical and live candle fetching
- Market sentiment data (% buy/sell)
- Account balance and payout information

### Telegram Bot
- **Full market scan** every 60 seconds across all assets
- **Hot asset monitoring** every 30 seconds for 2 minutes after a signal
- **WMA(32) Strategy** on 1-minute candles:
  - Touch from below + red candle → PUT signal
  - Touch from above + green candle → CALL signal
- Interactive Telegram buttons (Start/Stop Scan)
- Real-time alerts with asset name, action, and timestamp

## Project Structure

```
/workspace
├── README.md                    # This file
├── start_all.sh                 # Script to start API server and bot together
└── qx_candle_api/
    ├── main.py                  # FastAPI server
    ├── wma32_bot.py             # Telegram bot
    ├── qx_client.py             # QxBroker API wrapper
    ├── requirements.txt         # Python dependencies
    ├── Dockerfile               # Docker configuration
    └── README_WMA32_BOT.md      # Detailed bot documentation
```

## Quick Start

### Option 1: Run Everything Together

```bash
./start_all.sh
```

This script starts both the API server and the Telegram bot.

### Option 2: Run Components Separately

#### 1. Start the API Server

```bash
cd qx_candle_api
source venv/bin/activate  # If using virtual environment
uvicorn main:app --host 127.0.0.1 --port 8000
```

#### 2. Start the Telegram Bot

```bash
cd qx_candle_api
python wma32_bot.py
```

## Installation

### Prerequisites
- Python 3.8+
- QxBroker account credentials
- Telegram Bot Token (from @BotFather)

### Steps

1. **Navigate to the API directory:**
   ```bash
   cd qx_candle_api
   ```

2. **Create and activate virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   
   Create a `.env` file in `qx_candle_api/`:
   ```
   QX_EMAIL=your_email@example.com
   QX_PASSWORD=your_password
   QX_ACCOUNT=PRACTICE  # or REAL
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

## API Endpoints

Once the API server is running, access:

- **Status**: http://localhost:8000/
- **Interactive Docs**: http://localhost:8000/docs

### Available Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | API status |
| `GET /balance` | Account balance |
| `GET /assets` | List all available assets |
| `GET /payouts` | Payout percentages |
| `GET /candles/{asset}` | Historical candles |
| `GET /candles/{asset}/latest` | Latest N candles |
| `GET /candles/{asset}/live` | Current live candle |
| `GET /price/{asset}` | Latest tick price |
| `GET /sentiment/{asset}` | Market sentiment |

### Example Requests

```bash
# Get all assets
curl http://localhost:8000/assets

# Get latest 50 candles for EURUSD (1min)
curl "http://localhost:8000/candles/EURUSD/latest?period=60&count=50"

# Get live candle for BTCUSD
curl "http://localhost:8000/candles/BTCUSD/live?period=60"

# Get market sentiment
curl http://localhost:8000/sentiment/EURUSD
```

## Telegram Bot Usage

1. **Start the bot** - Run `python wma32_bot.py`
2. **Open Telegram** - Find your bot and send `/start`
3. **Click "▶️ Start Scan"** - Begins full market scanning
4. **Receive alerts** - When WMA(32) signals appear:
   ```
   🟢 WMA(32) Strategy Alert
   Asset: EURUSD_otc
   Action: CALL
   Time: 14:35:22
   ```
5. **Stop scanning** - Click "🛑 Stop Scan" anytime

## Configuration

### WMA Strategy Parameters

Edit `wma32_bot.py` to customize:

- **WMA Period**: Change `wma_period=32` for different moving average length
- **Timeframe**: Change `timeframe="1m"` to other timeframes
- **Scan Intervals**: Modify `asyncio.sleep(60)` for full scan frequency
- **Hot Asset Duration**: Change `120` seconds in `hot_scan()` method

### API Server

Modify `main.py` to:
- Change port (default: 8000)
- Add authentication
- Enable CORS for remote access

## Docker Support

Build and run using Docker:

```bash
cd qx_candle_api
docker build -t qxbroker-bot .
docker run -p 8000:8000 --env-file .env qxbroker-bot
```

## Troubleshooting

### Connection Issues
- Verify QxBroker credentials in `.env`
- Check if API session is valid
- Review logs for specific error messages

### No Signals Appearing
- Ensure market is open and assets are available
- Verify candle data is being fetched correctly
- Adjust WMA period or signal detection logic

### API Not Starting
- Check if port 8000 is available
- Ensure all dependencies are installed
- Run `pip install -r requirements.txt` again

## Security Notes

⚠️ **Important Security Considerations:**

- Keep your `.env` file secure and never commit it to version control
- Your Telegram bot token should be kept private
- QxBroker credentials should use a dedicated account if possible
- The API server runs on localhost by default for security
- Consider adding authentication for production use

## Files Reference

| File | Description |
|------|-------------|
| `main.py` | FastAPI server with all endpoints |
| `wma32_bot.py` | Telegram bot with WMA strategy |
| `qx_client.py` | QxBroker WebSocket client wrapper |
| `requirements.txt` | Python package dependencies |
| `start_all.sh` | Shell script to run both services |
| `Dockerfile` | Docker container configuration |
| `.env` | Environment variables (credentials) |

## Additional Documentation

- See `qx_candle_api/README_WMA32_BOT.md` for detailed bot documentation
- Access interactive API docs at http://localhost:8000/docs when server is running

## License

This project is for educational and personal use only. Trading involves risk; use at your own discretion.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the detailed bot documentation in `README_WMA32_BOT.md`
3. Examine log files for error messages