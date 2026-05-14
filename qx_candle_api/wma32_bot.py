import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Set
import sys
import os
import aiohttp

import pandas as pd
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ----------------------------------------------------------------------
# 1. LOCAL API WRAPPER (uses localhost:8000)
# ----------------------------------------------------------------------
class QxBrokerAPI:
    """Wrapper for your local QxBroker API server."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.session = None
    
    async def _get_session(self):
        """Get or create aiohttp session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
    
    async def get_all_assets(self) -> List[str]:
        """Return list of all tradable asset names."""
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/assets") as response:
                if response.status == 200:
                    data = await response.json()
                    # Return all assets (normal + otc)
                    return data.get("all", [])
                else:
                    logging.error(f"Failed to get assets: {response.status}")
                    return []
        except Exception as e:
            logging.error(f"Error fetching assets: {e}")
            return []
    
    async def get_candles(self, asset: str, timeframe: str = "1m", count: int = 100) -> pd.DataFrame:
        """
        Return DataFrame with columns: timestamp, open, high, low, close.
        timeframe = '1m' (1 minute). count = number of candles.
        """
        session = await self._get_session()
        
        # Convert timeframe to period in seconds
        period_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
        }
        period = period_map.get(timeframe, 60)
        
        try:
            async with session.get(
                f"{self.base_url}/candles/{asset}/latest",
                params={"period": period, "count": count}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    candles_data = data.get("candles", [])
                    
                    if not candles_data:
                        return pd.DataFrame()
                    
                    df = pd.DataFrame(candles_data)
                    
                    # Rename columns to match expected format
                    df = df.rename(columns={
                        "time": "timestamp",
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close"
                    })
                    
                    # Convert timestamp to datetime if it's a unix timestamp
                    if "timestamp" in df.columns:
                        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                    
                    # Ensure we have the required columns
                    required_cols = ["timestamp", "open", "high", "low", "close"]
                    for col in required_cols:
                        if col not in df.columns:
                            df[col] = np.nan
                    
                    return df[required_cols]
                else:
                    logging.error(f"Failed to get candles for {asset}: {response.status}")
                    return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error fetching candles for {asset}: {e}")
            return pd.DataFrame()

# Initialize your API
api = QxBrokerAPI()

# ----------------------------------------------------------------------
# 2. WMA(32) CALCULATION & SIGNAL DETECTION
# ----------------------------------------------------------------------
def weighted_moving_average(close_prices: pd.Series, period: int = 32) -> pd.Series:
    """Calculate Weighted Moving Average (WMA)."""
    weights = np.arange(1, period + 1)
    def wma(arr):
        if len(arr) < period:
            return np.nan
        return np.sum(arr * weights) / weights.sum()
    return close_prices.rolling(window=period).apply(wma, raw=True)

def check_wma_signal(candles: pd.DataFrame, wma_period: int = 32) -> Dict:
    """
    Check if the last completed candle (index -2 because index -1 is still forming)
    touched the WMA line and closed in the correct direction.
    Returns: {'signal': 'CALL' or 'PUT' or None, 'asset': str}
    """
    if len(candles) < wma_period + 1:
        return None
    
    # Calculate WMA on 'close' prices
    candles = candles.copy()
    candles['wma'] = weighted_moving_average(candles['close'], wma_period)
    
    # Last COMPLETED candle (index -2) - the one that closed 1 minute ago
    # Index -1 is the current, still open candle
    last_completed = candles.iloc[-2]
    prev_candle = candles.iloc[-3] if len(candles) > 2 else None
    
    # Conditions for touch:
    # From below: previous low <= wma <= current close? Actually "candle touched from below"
    # Means the price moved from under the line to hit/touch it. We check:
    #   prev_candle.close <= wma <= last_completed.close OR candle low <= wma <= candle high
    wma_val = last_completed['wma']
    if pd.isna(wma_val):
        return None
    
    low = last_completed['low']
    high = last_completed['high']
    close = last_completed['close']
    open_price = last_completed['open']
    is_red = close < open_price
    is_green = close > open_price
    
    # Touch detection: the candle's price range includes the WMA line
    touched = low <= wma_val <= high
    
    if not touched:
        return None
    
    # Signal rules from your video:
    # Touch from below + closes red -> DOWN (PUT)
    # Touch from above + closes green -> UP (CALL)
    # We need direction: did price approach from below or above?
    # Use previous candle's close relative to WMA
    if prev_candle is not None:
        prev_close = prev_candle['close']
        if prev_close <= wma_val and is_red and touched:
            return {'signal': 'PUT', 'asset': None}  # asset will be set outside
        elif prev_close >= wma_val and is_green and touched:
            return {'signal': 'CALL', 'asset': None}
    
    # Alternative if prev_candle missing, just use open vs close
    if is_red and touched:
        # Check if open was above or below WMA? Usually below -> PUT
        if open_price <= wma_val:
            return {'signal': 'PUT', 'asset': None}
    elif is_green and touched:
        if open_price >= wma_val:
            return {'signal': 'CALL', 'asset': None}
    
    return None

# ----------------------------------------------------------------------
# 3. SCANNING ENGINE (Async, runs every 60s, + per‑asset 30s follow‑up)
# ----------------------------------------------------------------------
class Scanner:
    def __init__(self):
        self.is_scanning = False
        self.scan_task = None
        self.hot_assets: Set[str] = set()      # assets currently being monitored every 30s
        self.hot_asset_last_seen: Dict[str, datetime] = {}
        self.hot_task = None
        
    async def full_scan(self, context: ContextTypes.DEFAULT_TYPE):
        """Scan all assets every 60 seconds."""
        if not self.is_scanning:
            return
        
        try:
            assets = await api.get_all_assets()
            logging.info(f"Full scan: checking {len(assets)} assets")
            for asset in assets:
                candles = await api.get_candles(asset, timeframe="1m", count=50)
                signal_info = check_wma_signal(candles)
                if signal_info and signal_info['signal']:
                    signal_info['asset'] = asset
                    await self.send_signal_alert(context, signal_info)
                    # Add to hot assets for 30-second monitoring (next 2 minutes)
                    self.hot_assets.add(asset)
                    self.hot_asset_last_seen[asset] = datetime.now()
        except Exception as e:
            logging.error(f"Full scan error: {e}")
    
    async def send_signal_alert(self, context: ContextTypes.DEFAULT_TYPE, signal_info: Dict):
        """Send Telegram message with inline stop button."""
        asset = signal_info['asset']
        direction = signal_info['signal']  # CALL or PUT
        emoji = "🟢" if direction == "CALL" else "🔴"
        message_text = (
            f"{emoji} *WMA(32) Strategy Alert*\n"
            f"Asset: `{asset}`\n"
            f"Action: *{direction}*\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Stop Scan", callback_data="stop_scan")]
        ])
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    async def hot_scan(self, context: ContextTypes.DEFAULT_TYPE):
        """Scan hot assets every 30 seconds for additional signals."""
        if not self.is_scanning:
            return
        now = datetime.now()
        to_remove = []
        for asset in list(self.hot_assets):
            # Remove after 2 minutes of no new signal (or just keep for 2 min)
            if (now - self.hot_asset_last_seen.get(asset, now)).total_seconds() > 120:
                to_remove.append(asset)
                continue
            try:
                candles = await api.get_candles(asset, timeframe="1m", count=50)
                signal_info = check_wma_signal(candles)
                if signal_info and signal_info['signal']:
                    signal_info['asset'] = asset
                    await self.send_signal_alert(context, signal_info)
                    self.hot_asset_last_seen[asset] = now  # refresh timer
            except Exception as e:
                logging.error(f"Hot scan error for {asset}: {e}")
        for asset in to_remove:
            self.hot_assets.discard(asset)
            self.hot_asset_last_seen.pop(asset, None)
    
    def start(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
        if self.is_scanning:
            return
        self.is_scanning = True
        loop = asyncio.get_event_loop()
        # Schedule full scan every 60 seconds
        self.scan_task = loop.create_task(self._run_full_scan_periodic(chat_id, context))
        # Schedule hot scan every 30 seconds
        self.hot_task = loop.create_task(self._run_hot_scan_periodic(chat_id, context))
        logging.info("Scanner started")
    
    async def _run_full_scan_periodic(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
        while self.is_scanning:
            await self.full_scan(context)
            await asyncio.sleep(60)
    
    async def _run_hot_scan_periodic(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
        while self.is_scanning:
            await self.hot_scan(context)
            await asyncio.sleep(30)
    
    def stop(self):
        self.is_scanning = False
        self.hot_assets.clear()
        self.hot_asset_last_seen.clear()
        logging.info("Scanner stopped")

# Global scanner instance
scanner = Scanner()

# ----------------------------------------------------------------------
# 4. TELEGRAM BOT HANDLERS
# ----------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send Start/Stop buttons."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Scan", callback_data="start_scan")],
        [InlineKeyboardButton("⏹️ Stop Scan", callback_data="stop_scan")]
    ])
    await update.message.reply_text(
        "WMA(32) Scanner",
        reply_markup=keyboard
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    
    if data == "start_scan":
        if scanner.is_scanning:
            await query.edit_message_text("⚠️ Scan is already running.")
        else:
            scanner.start(chat_id, context)
            await query.edit_message_text(
                "✅ *Scanning started*\n\n"
                "Full market scan every 60s.\n"
                "Hot assets every 30s.\n"
                "Use Stop Scan to halt.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏹️ Stop Scan", callback_data="stop_scan")]
                ])
            )
    elif data == "stop_scan":
        scanner.stop()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Start Scan", callback_data="start_scan")]
        ])
        await query.edit_message_text(
            "🛑 *Scanning stopped.* Press Start to resume.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await query.edit_message_text("Unknown command.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scanner.stop()
    await update.message.reply_text("Scanning stopped. Use /start to restart.")

# ----------------------------------------------------------------------
# 5. MAIN
# ----------------------------------------------------------------------
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Your Telegram bot token
    TOKEN = "8457562228:AAHcF6VsqfApj7sqAZwPNJDz7xUGSj0Pvk0"
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logging.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
