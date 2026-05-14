# QxBroker Trading System

A complete trading system that connects to QxBroker via WebSocket, provides a REST API for market data, and includes a Telegram bot that scans for WMA(32) trading signals.

## 📁 Project Structure

```
/workspace/
├── src/
│   ├── api/
│   │   ├── main.py          # FastAPI server with REST endpoints
│   │   └── qx_client.py     # QxBroker WebSocket client
│   └── bot/
│       └── wma32_bot.py     # Telegram bot with WMA strategy scanner
├── config/
│   └── .env.example         # Configuration template
├── logs/                     # Log files directory
├── requirements.txt          # Python dependencies
├── start.sh                 # Startup script
└── README.md                # This file
```

## ✨ Features

### API Server (`src/api/main.py`)
- **Real-time candle data** from QxBroker WebSocket
- **REST endpoints** for:
  - Historical candles (`/candles/{asset}`)
  - Latest candles (`/candles/{asset}/latest`)
  - Live candle (`/candles/{asset}/live`)
  - Current price (`/price/{asset}`)
  - Account balance (`/balance`)
  - Available assets (`/assets`)
  - Market sentiment (`/sentiment/{asset}`)
- **Interactive API docs** at http://localhost:8000/docs

### Telegram Bot (`src/bot/wma32_bot.py`)
- **WMA(32) Strategy Scanner** - Detects trading signals based on Weighted Moving Average crossovers
- **Dual scanning modes**:
  - Full market scan every 60 seconds
  - Hot assets scan every 30 seconds
- **Signal alerts** sent directly to Telegram with:
  - Asset name
  - Direction (CALL/PUT)
  - Confidence level
  - Timestamp
- **Interactive controls** via Telegram buttons
- **Balance checking** command

## 🚀 Quick Start

### 1. Setup Configuration

```bash
# Copy the example config
cp config/.env.example .env

# Edit .env with your credentials
nano .env
```

Required settings in `.env`:
```bash
QX_ACCOUNT=PRACTICE          # or REAL
QX_EMAIL=your_email@example.com
QX_PASSWORD=your_password
TELEGRAM_BOT_TOKEN=your_bot_token
```

### 2. Install Dependencies

```bash
cd /workspace
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the System

**Option A: Use the startup script (recommended)**
```bash
./start.sh
```

**Option B: Run components separately**

Terminal 1 - Start API Server:
```bash
source venv/bin/activate
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 - Start Telegram Bot:
```bash
source venv/bin/activate
python src/bot/wma32_bot.py
```

## 📡 API Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `GET /` | API status | `curl http://localhost:8000/` |
| `GET /health` | Health check | `curl http://localhost:8000/health` |
| `GET /balance` | Account balance | `curl http://localhost:8000/balance` |
| `GET /assets` | List all assets | `curl http://localhost:8000/assets` |
| `GET /candles/EURUSD` | Historical candles | `curl http://localhost:8000/candles/EURUSD?period=60&hours=1` |
| `GET /candles/EURUSD/latest` | Latest N candles | `curl http://localhost:8000/candles/EURUSD/latest?count=50` |
| `GET /candles/EURUSD/live` | Current live candle | `curl http://localhost:8000/candles/EURUSD/live` |
| `GET /price/EURUSD` | Current price | `curl http://localhost:8000/price/EURUSD` |
| `GET /sentiment/EURUSD` | Market sentiment | `curl http://localhost:8000/sentiment/EURUSD` |

### API Parameters

**Candles endpoint:**
- `period`: Candle period in seconds (5, 15, 30, 60, 300, 900, 3600, etc.)
- `hours`: Hours of historical data (1-24)
- `count`: Number of candles (max 200)

**Asset examples:**
- `EURUSD`, `GBPUSD`, `BTCUSD` - Regular assets
- `EURUSD_otc`, `BTCUSD_otc` - OTC assets

## 🤖 Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show control menu |
| `/stop` | Stop scanning |
| `/status` | Show current status |

### Bot Buttons:
- **▶️ Start Scan** - Begin market scanning
- **⏹️ Stop Scan** - Halt scanning
- **💰 Balance** - Check account balance

## 📊 WMA(32) Strategy

The bot uses a **Weighted Moving Average (32-period)** strategy:

### Signal Rules:

**CALL Signal (🟢):**
- Price touches WMA from above
- Candle closes green (bullish)
- Indicates potential upward movement

**PUT Signal (🔴):**
- Price touches WMA from below
- Candle closes red (bearish)
- Indicates potential downward movement

### Scanning Logic:
1. **Full Scan** (every 60s): Checks all available assets
2. **Hot Scan** (every 30s): Monitors assets that recently showed signals
3. **Alert Delivery**: Sends instant Telegram notifications when signals are detected

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `QX_ACCOUNT` | Account type | `PRACTICE` |
| `QX_EMAIL` | QxBroker email | - |
| `QX_PASSWORD` | QxBroker password | - |
| `QX_SSID` | Direct SSID (optional) | - |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - |
| `API_HOST` | API server host | `127.0.0.1` |
| `API_PORT` | API server port | `8000` |

## 🐛 Troubleshooting

### API won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
kill -9 <PID>
```

### Connection failed
- Verify your QxBroker credentials in `.env`
- Check internet connection
- Try extracting SSID manually using browser dev tools

### Bot not receiving messages
- Verify TELEGRAM_BOT_TOKEN is correct
- Make sure you've started a chat with your bot
- Check bot permissions in Telegram

### No signals detected
- Ensure API server is running (`curl http://localhost:8000/health`)
- Check if markets are open (some assets trade only during specific hours)
- Verify asset names are correct (use `/assets` endpoint)

## 📝 Logs

Logs are stored in:
- `logs/api.log` - API server logs
- Console output - Bot logs

View logs in real-time:
```bash
tail -f logs/api.log
```

## ⚠️ Important Notes

1. **Private API**: This system runs locally and connects directly to QxBroker. Keep it secure.
2. **Demo vs Real**: Use `QX_ACCOUNT=PRACTICE` for testing, switch to `REAL` for live trading.
3. **Rate Limits**: The bot respects API rate limits. Don't run multiple instances simultaneously.
4. **Trading Risk**: This is an automated scanning tool. Always verify signals before trading.

## 📄 License

This project is for personal use only. Not for commercial distribution.

## 🆘 Support

For issues:
1. Check the troubleshooting section above
2. Review logs in `logs/` directory
3. Verify your configuration in `.env`

---

**Happy Trading! 📈**
