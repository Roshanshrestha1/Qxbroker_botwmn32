"""
WMA32 Trading Bot - Telegram bot that scans for trading signals.
Connects to the local QxBroker API for real-time market data.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes


# ----------------------------------------------------------------------
# 1. LOCAL API WRAPPER (connects to localhost:8000)
# ----------------------------------------------------------------------
class QxBrokerAPI:
    """Wrapper for the local QxBroker API server."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_all_assets(self) -> List[str]:
        """Return list of all tradable asset names."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/assets") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("all", [])
                else:
                    logging.error(f"Failed to get assets: HTTP {response.status}")
                    return []
        except Exception as e:
            logging.error(f"Error fetching assets: {e}")
            return []
    
    async def get_candles(
        self, 
        asset: str, 
        timeframe: str = "1m", 
        count: int = 100
    ) -> pd.DataFrame:
        """
        Return DataFrame with columns: timestamp, open, high, low, close.
        
        Args:
            asset: Asset name (e.g., 'EURUSD', 'BTCUSD_otc')
            timeframe: '1m', '5m', '15m', '1h'
            count: Number of candles to fetch
        
        Returns:
            DataFrame with OHLCV data
        """
        # Convert timeframe to period in seconds
        period_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
        }
        period = period_map.get(timeframe, 60)
        
        try:
            session = await self._get_session()
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
                    
                    # Standardize column names
                    df = df.rename(columns={
                        "time": "timestamp",
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close"
                    })
                    
                    # Convert timestamp to datetime if needed
                    if "timestamp" in df.columns:
                        # Check if timestamps are Unix timestamps (integers)
                        if df["timestamp"].dtype in ['int64', 'float64']:
                            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                    
                    # Ensure required columns exist
                    required_cols = ["timestamp", "open", "high", "low", "close"]
                    for col in required_cols:
                        if col not in df.columns:
                            df[col] = np.nan
                    
                    return df[required_cols]
                
                else:
                    logging.error(f"Failed to get candles for {asset}: HTTP {response.status}")
                    return pd.DataFrame()
        
        except Exception as e:
            logging.error(f"Error fetching candles for {asset}: {e}")
            return pd.DataFrame()
    
    async def get_balance(self) -> Dict:
        """Get account balance."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/balance") as response:
                if response.status == 200:
                    return await response.json()
                return {}
        except Exception as e:
            logging.error(f"Error fetching balance: {e}")
            return {}


# Initialize API client
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


def check_wma_signal(candles: pd.DataFrame, wma_period: int = 32) -> Optional[Dict]:
    """
    Check for WMA crossover signals on the last completed candle.
    
    Signal Rules:
    - Price touches WMA from below + closes red (bearish) → PUT signal
    - Price touches WMA from above + closes green (bullish) → CALL signal
    
    Args:
        candles: DataFrame with OHLCV data
        wma_period: WMA calculation period (default: 32)
    
    Returns:
        Dict with 'signal' ('CALL' or 'PUT') or None if no signal
    """
    if len(candles) < wma_period + 2:
        return None
    
    # Calculate WMA
    candles = candles.copy()
    candles['wma'] = weighted_moving_average(candles['close'], wma_period)
    
    # Use second-to-last candle (last completed candle)
    # Last candle (-1) is still forming
    last_completed = candles.iloc[-2]
    prev_candle = candles.iloc[-3] if len(candles) > 2 else None
    
    wma_val = last_completed['wma']
    if pd.isna(wma_val):
        return None
    
    low = last_completed['low']
    high = last_completed['high']
    close = last_completed['close']
    open_price = last_completed['open']
    
    is_red = close < open_price
    is_green = close > open_price
    
    # Check if candle touched the WMA line
    touched = low <= wma_val <= high
    
    if not touched:
        return None
    
    # Determine signal direction
    if prev_candle is not None:
        prev_close = prev_candle['close']
        
        # Touch from below + red close = PUT
        if prev_close <= wma_val and is_red:
            return {'signal': 'PUT', 'confidence': 'high'}
        
        # Touch from above + green close = CALL
        elif prev_close >= wma_val and is_green:
            return {'signal': 'CALL', 'confidence': 'high'}
    
    # Fallback logic
    if is_red and open_price <= wma_val:
        return {'signal': 'PUT', 'confidence': 'medium'}
    elif is_green and open_price >= wma_val:
        return {'signal': 'CALL', 'confidence': 'medium'}
    
    return None


# ----------------------------------------------------------------------
# 3. SCANNING ENGINE
# ----------------------------------------------------------------------
class Scanner:
    """Async scanner that monitors assets for trading signals."""
    
    def __init__(self):
        self.is_scanning = False
        self.scan_task = None
        self.hot_assets: Set[str] = set()
        self.hot_asset_last_seen: Dict[str, datetime] = {}
        self.hot_task = None
        self.chat_id: Optional[int] = None
        self.context: Optional[ContextTypes.DEFAULT_TYPE] = None
    
    async def full_scan(self) -> List[Dict]:
        """Scan all assets for signals."""
        signals = []
        
        try:
            assets = await api.get_all_assets()
            logging.info(f"Full scan: checking {len(assets)} assets")
            
            for asset in assets:
                try:
                    candles = await api.get_candles(asset, timeframe="1m", count=50)
                    
                    if candles.empty:
                        continue
                    
                    signal_info = check_wma_signal(candles)
                    
                    if signal_info and signal_info.get('signal'):
                        signal_info['asset'] = asset
                        signal_info['timestamp'] = datetime.now()
                        signals.append(signal_info)
                        
                        # Add to hot assets for intensified monitoring
                        self.hot_assets.add(asset)
                        self.hot_asset_last_seen[asset] = datetime.now()
                
                except Exception as e:
                    logging.debug(f"Error scanning {asset}: {e}")
                    continue
        
        except Exception as e:
            logging.error(f"Full scan error: {e}")
        
        return signals
    
    async def hot_scan(self) -> List[Dict]:
        """Scan hot assets more frequently."""
        signals = []
        now = datetime.now()
        to_remove = []
        
        for asset in list(self.hot_assets):
            # Remove assets after 2 minutes of no activity
            if (now - self.hot_asset_last_seen.get(asset, now)).total_seconds() > 120:
                to_remove.append(asset)
                continue
            
            try:
                candles = await api.get_candles(asset, timeframe="1m", count=50)
                
                if candles.empty:
                    continue
                
                signal_info = check_wma_signal(candles)
                
                if signal_info and signal_info.get('signal'):
                    signal_info['asset'] = asset
                    signal_info['timestamp'] = now
                    signals.append(signal_info)
                    self.hot_asset_last_seen[asset] = now  # Refresh timer
            
            except Exception as e:
                logging.debug(f"Hot scan error for {asset}: {e}")
        
        # Clean up old hot assets
        for asset in to_remove:
            self.hot_assets.discard(asset)
            self.hot_asset_last_seen.pop(asset, None)
        
        return signals
    
    async def send_signal_alert(self, signal_info: Dict):
        """Send Telegram alert for a trading signal."""
        if not self.context or not self.chat_id:
            return
        
        asset = signal_info['asset']
        direction = signal_info['signal']
        confidence = signal_info.get('confidence', 'medium')
        timestamp = signal_info.get('timestamp', datetime.now())
        
        emoji = "🟢" if direction == "CALL" else "🔴"
        arrow = "⬆️" if direction == "CALL" else "⬇️"
        
        message_text = (
            f"{emoji} *WMA(32) Signal Alert* {arrow}\n\n"
            f"Asset: `{asset}`\n"
            f"Direction: *{direction}*\n"
            f"Confidence: {confidence.upper()}\n"
            f"Time: {timestamp.strftime('%H:%M:%S')}\n\n"
            f"_Enter trade on next candle open_"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Stop Scanning", callback_data="stop_scan")]
        ])
        
        try:
            await self.context.bot.send_message(
                chat_id=self.chat_id,
                text=message_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            logging.info(f"Signal sent: {direction} on {asset}")
        except Exception as e:
            logging.error(f"Failed to send signal alert: {e}")
    
    def start(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Start the scanning process."""
        if self.is_scanning:
            return
        
        self.is_scanning = True
        self.chat_id = chat_id
        self.context = context
        
        loop = asyncio.get_event_loop()
        
        # Start full scan task (every 60 seconds)
        self.scan_task = loop.create_task(self._run_full_scan_loop())
        
        # Start hot scan task (every 30 seconds)
        self.hot_task = loop.create_task(self._run_hot_scan_loop())
        
        logging.info("✓ Scanner started")
    
    async def _run_full_scan_loop(self):
        """Run full market scans periodically."""
        while self.is_scanning:
            try:
                signals = await self.full_scan()
                
                # Send alerts for new signals
                for signal in signals:
                    await self.send_signal_alert(signal)
                
            except Exception as e:
                logging.error(f"Full scan loop error: {e}")
            
            await asyncio.sleep(60)
    
    async def _run_hot_scan_loop(self):
        """Run hot asset scans more frequently."""
        while self.is_scanning:
            try:
                signals = await self.hot_scan()
                
                for signal in signals:
                    await self.send_signal_alert(signal)
            
            except Exception as e:
                logging.error(f"Hot scan loop error: {e}")
            
            await asyncio.sleep(30)
    
    def stop(self):
        """Stop the scanning process."""
        self.is_scanning = False
        self.hot_assets.clear()
        self.hot_asset_last_seen.clear()
        self.chat_id = None
        self.context = None
        logging.info("✗ Scanner stopped")


# Global scanner instance
scanner = Scanner()


# ----------------------------------------------------------------------
# 4. TELEGRAM BOT HANDLERS
# ----------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show control buttons."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Scan", callback_data="start_scan")],
        [InlineKeyboardButton("⏹️ Stop Scan", callback_data="stop_scan")],
        [InlineKeyboardButton("💰 Balance", callback_data="check_balance")],
    ])
    
    welcome_text = (
        "*WMA(32) Trading Bot*\n\n"
        "This bot scans the market for trading opportunities using the Weighted Moving Average strategy.\n\n"
        "Commands:\n"
        "/start - Show this menu\n"
        "/stop - Stop scanning\n"
        "/status - Show current status\n\n"
        "Press a button below to get started!"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command."""
    scanner.stop()
    await update.message.reply_text("🛑 Scanning stopped. Use /start to restart.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    status_text = (
        "*Bot Status*\n\n"
        f"Scanning: {'✅ Active' if scanner.is_scanning else '❌ Stopped'}\n"
        f"Hot Assets: {len(scanner.hot_assets)}\n"
        f"Last Update: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    await update.message.reply_text(status_text, parse_mode="Markdown")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
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
                "✅ *Scanning Started!*\n\n"
                "• Full market scan every 60s\n"
                "• Hot assets monitored every 30s\n"
                "• You'll receive alerts when signals are detected\n\n"
                "Press Stop to halt scanning.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏹️ Stop Scan", callback_data="stop_scan")]
                ])
            )
    
    elif data == "stop_scan":
        scanner.stop()
        
        await query.edit_message_text(
            "🛑 *Scanning Stopped*\n\n"
            "Press Start to resume scanning.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Start Scan", callback_data="start_scan")]
            ])
        )
    
    elif data == "check_balance":
        try:
            balance = await api.get_balance()
            if balance:
                balance_text = (
                    f"*Account Balance*\n\n"
                    f"Balance: ${balance.get('balance', 'N/A')}\n"
                    f"Currency: {balance.get('currency', 'USD')}\n"
                    f"Account: {balance.get('account_type', 'DEMO')}"
                )
            else:
                balance_text = "Unable to fetch balance. Is the API server running?"
            
            await query.edit_message_text(balance_text, parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"Error fetching balance: {e}")


# ----------------------------------------------------------------------
# 5. MAIN ENTRY POINT
# ----------------------------------------------------------------------
def main():
    """Main function to start the Telegram bot."""
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Get bot token from environment or use default
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8457562228:AAHcF6VsqfApj7sqAZwPNJDz7xUGSj0Pvk0")
    
    if not TOKEN or TOKEN.startswith("YOUR_"):
        logging.error("Please set TELEGRAM_BOT_TOKEN environment variable!")
        return
    
    # Build application
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    logging.info("=" * 50)
    logging.info("Starting WMA32 Trading Bot...")
    logging.info("=" * 50)
    logging.info("Bot is running. Press Ctrl+C to stop.")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
