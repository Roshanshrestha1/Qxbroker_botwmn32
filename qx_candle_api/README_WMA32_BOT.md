# WMA(32) Telegram Bot - Integrated with Your QxBroker API

## Overview
This bot uses your actual qxbroker API to scan all assets every 60 seconds using WMA(32) on 1-minute candles. When a candle touches the WMA line from below + closes red → sends PUT alert. When touches from above + closes green → sends CALL alert.

## Features
- **Full market scan** every 60 seconds across all assets
- **Hot asset monitoring** every 30 seconds for 2 minutes after a signal
- **Telegram integration** with clickable buttons (Start/Stop Scan)
- **Your actual qxbroker API** integrated (no placeholders)

## Setup

### 1. Install Dependencies
```bash
cd /home/roshan/Music/wma32\ stg/qxbrokerapi/qx_candle_api
pip install -r requirements.txt
```

### 2. Verify Your .env Configuration
Your `.env` file should contain:
```
QX_EMAIL=bcdoy9@gmail.com
QX_PASSWORD=roshAN@123@@
QX_ACCOUNT=PRACTICE
```

### 3. Run the Bot
```bash
python wma32_bot.py
```

## Usage

1. **Start the bot** - Run the script above
2. **Open Telegram** - Find your bot and send `/start`
3. **Click "▶️ Start Scan"** - Begins full market scanning
4. **Receive alerts** - When WMA(32) signals appear, you'll get:
   ```
   🟢 WMA(32) Strategy Alert
   Asset: EURUSD_otc
   Action: CALL
   Time: 14:35:22
   ```
5. **Stop scanning** - Click "🛑 Stop Scan" anytime

## How It Works

### Signal Detection
- Calculates WMA(32) on 1-minute candles
- Detects when price touches WMA line
- **Touch from below + red candle** → PUT signal
- **Touch from above + green candle** → CALL signal

### Scanning Schedule
- **Full scan**: All assets every 60 seconds
- **Hot scan**: Assets with recent signals every 30 seconds for 2 minutes

### Your API Integration
The bot uses your existing `qx_client.py` functions:
- `fetch_all_assets()` - Gets all tradable assets
- `fetch_latest_candles(asset, count, period)` - Gets candle data

## Customization

Edit `wma32_bot.py` to adjust:

- **Hot asset duration**: Change `120` seconds in `hot_scan()` method
- **Scan intervals**: Modify `asyncio.sleep(60)` and `asyncio.sleep(30)`
- **WMA period**: Change `wma_period=32` in signal detection
- **Timeframe**: Change `timeframe="1m"` to other timeframes

## Troubleshooting

### Connection Issues
If the bot fails to connect to QxBroker:
1. Check your `.env` credentials
2. Ensure your API session is valid
3. Check the logs for specific error messages

### No Signals Appearing
- Verify assets are available and market is open
- Check that candle data is being fetched correctly
- Adjust WMA period or signal logic if needed

## Files
- `wma32_bot.py` - Main bot script
- `qx_client.py` - Your qxbroker API wrapper
- `.env` - Your credentials
- `requirements.txt` - Python dependencies

## Security Notes
- Your Telegram bot token is hardcoded in the script
- Your QxBroker credentials are in `.env` (not committed to git)
- Keep both secure and never share publicly
