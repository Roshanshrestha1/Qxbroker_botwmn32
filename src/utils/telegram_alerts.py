"""
Enhanced Telegram Alert System for QxBroker Trading Bot.
Sends rich formatted signal messages with emojis, confidence stars, and inline buttons.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
from typing import Optional, Dict


# Asset flag emoji mapping
ASSET_FLAGS = {
    'EURUSD': '🇪🇺🇺🇸',
    'GBPUSD': '🇬🇧🇺🇸',
    'USDJPY': '🇺🇸🇯🇵',
    'AUDUSD': '🇦🇺🇺🇸',
    'USDCAD': '🇺🇸🇨🇦',
    'USDCHF': '🇺🇸🇨🇭',
    'NZDUSD': '🇳🇿🇺🇸',
    'BTCUSD': '₿',
    'ETHUSD': 'Ξ',
    'XAUUSD': '🥇',
    'XAGUSD': '🥈',
    'OIL': '🛢️',
    'NATGAS': '⚡',
}


def get_asset_flag(asset: str) -> str:
    """Get flag emoji for an asset."""
    asset_upper = asset.upper().replace('_OTC', '').replace('_otc', '')
    
    # Check direct match first
    if asset_upper in ASSET_FLAGS:
        return ASSET_FLAGS[asset_upper]
    
    # Try partial matches
    for key, flag in ASSET_FLAGS.items():
        if key in asset_upper or asset_upper in key:
            return flag
    
    # Default flag for unknown assets
    return '📊'


def format_confidence_stars(stars: int) -> str:
    """Format confidence as star emojis."""
    stars = max(1, min(5, stars))  # Clamp between 1-5
    return '⭐' * stars


def get_direction_emoji(direction: str) -> str:
    """Get colored arrow emoji for signal direction."""
    if direction.upper() == 'CALL':
        return '🟢▲'
    elif direction.upper() == 'PUT':
        return '🔴▼'
    return '⚪➡'


async def send_signal(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    signal_data: Dict,
    countdown_seconds: int = 8
) -> bool:
    """
    Send a rich formatted signal alert to Telegram.
    
    Args:
        context: Telegram bot context
        chat_id: Target chat ID
        signal_data: Dict containing signal information
        countdown_seconds: Seconds until entry
    
    Returns:
        True if message sent successfully
    """
    try:
        # Extract signal data
        asset = signal_data.get('asset', 'UNKNOWN')
        direction = signal_data.get('signal', 'CALL')
        entry_price = signal_data.get('entry_price', 0)
        wma_value = signal_data.get('wma_value', 0)
        rsi_value = signal_data.get('rsi_value', 0)
        confidence_stars = signal_data.get('confidence_stars', 3)
        timestamp = signal_data.get('timestamp', datetime.now())
        expiry_seconds = signal_data.get('expiry_seconds', 60)
        
        # Get emojis and formatting
        flag = get_asset_flag(asset)
        direction_emoji = get_direction_emoji(direction)
        stars = format_confidence_stars(confidence_stars)
        
        # Format expiry time suggestion
        if expiry_seconds <= 60:
            expiry_text = "1 minute"
        elif expiry_seconds <= 300:
            expiry_text = f"{expiry_seconds // 60} minutes"
        else:
            expiry_text = f"{expiry_seconds // 60} min"
        
        # Build message text using HTML parse mode
        message_text = (
            f"{direction_emoji} <b>WMA(32) SIGNAL ALERT</b> {direction_emoji}\n\n"
            f"{flag} <b>{asset}</b>\n\n"
            f"Direction: <b>{direction}</b>\n"
            f"Entry Price: <code>{entry_price:.5f}</code>\n"
            f"WMA Level: <code>{wma_value:.5f}</code>\n"
            f"RSI(7): <code>{rsi_value:.1f}</code>\n\n"
            f"{stars} <b>Confidence: {confidence_stars}/5</b>\n\n"
            f"⏱️ <b>Enter in: {countdown_seconds} seconds</b>\n"
            f"⏲️ <b>Expiry: {expiry_text}</b>\n\n"
            f"<i>Enter trade on next candle open</i>"
        )
        
        # Add filters info if available
        filters_passed = signal_data.get('filters_passed', [])
        filters_failed = signal_data.get('filters_failed', [])
        
        if filters_passed or filters_failed:
            message_text += f"\n\n<b>Filters:</b>\n"
            if filters_passed:
                passed_str = ', '.join(filters_passed[:4])  # Show max 4
                message_text += f"✅ <i>{passed_str}</i>\n"
            if filters_failed:
                failed_str = ', '.join(filters_failed[:2])  # Show max 2
                message_text += f"❌ <i>{failed_str}</i>"
        
        # Create inline keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Traded", callback_data=f"traded_{asset}_{direction}"),
                InlineKeyboardButton("❌ Skipped", callback_data=f"skipped_{asset}_{direction}")
            ],
            [
                InlineKeyboardButton("📊 Chart", callback_data=f"chart_{asset}"),
                InlineKeyboardButton("📈 Stats", callback_data=f"stats_{asset}")
            ],
            [
                InlineKeyboardButton("🛑 Stop Scanning", callback_data="stop_scan")
            ]
        ])
        
        # Send message
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML',
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
        print(f"✓ Signal sent: {direction} on {asset} ({confidence_stars}⭐)")
        return True
        
    except Exception as e:
        print(f"✗ Failed to send signal: {e}")
        return False


async def send_win_loss_notification(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    result_data: Dict
) -> bool:
    """
    Send win/loss notification after signal outcome.
    
    Args:
        context: Telegram bot context
        chat_id: Target chat ID
        result_data: Dict with result information
    
    Returns:
        True if message sent successfully
    """
    try:
        asset = result_data.get('asset', 'UNKNOWN')
        direction = result_data.get('direction', 'CALL')
        result = result_data.get('result', 'WIN')
        entry_price = result_data.get('entry_price', 0)
        exit_price = result_data.get('exit_price', 0)
        
        # Determine emoji based on result
        if result == 'WIN':
            result_emoji = '🎉'
            result_color = '<b>WIN! 🟢</b>'
        else:
            result_emoji = '😞'
            result_color = '<b>LOSS 🔴</b>'
        
        flag = get_asset_flag(asset)
        direction_emoji = get_direction_emoji(direction)
        
        message_text = (
            f"{result_emoji} <b>Trade Result</b>\n\n"
            f"{flag} <b>{asset}</b>\n"
            f"{direction_emoji} <b>{direction}</b>\n\n"
            f"Result: {result_color}\n"
            f"Entry: <code>{entry_price:.5f}</code>\n"
            f"Exit: <code>{exit_price:.5f}</code>\n\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 View Stats", callback_data="stats")]
        ])
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        return True
        
    except Exception as e:
        print(f"Failed to send result notification: {e}")
        return False


async def send_stats_summary(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    stats_data: Dict
) -> bool:
    """
    Send trading statistics summary.
    
    Args:
        context: Telegram bot context
        chat_id: Target chat ID
        stats_data: Dict with statistics
    
    Returns:
        True if message sent successfully
    """
    try:
        total = stats_data.get('total_trades', 0)
        wins = stats_data.get('wins', 0)
        losses = stats_data.get('losses', 0)
        win_rate = stats_data.get('win_rate', 0.0)
        current_streak = stats_data.get('current_streak', 0)
        best_streak = stats_data.get('best_streak', 0)
        best_asset = stats_data.get('best_asset', 'N/A')
        
        # Streak emoji
        if current_streak > 0:
            streak_emoji = '🔥'
        else:
            streak_emoji = '💤'
        
        message_text = (
            f"📊 <b>Trading Statistics</b>\n\n"
            f"<b>Total Trades:</b> {total}\n"
            f"<b>Wins:</b> {wins} ✅\n"
            f"<b>Losses:</b> {losses} ❌\n\n"
            f"<b>Win Rate:</b> {win_rate:.1f}%\n\n"
            f"{streak_emoji} <b>Current Streak:</b> {current_streak}\n"
            f"🏆 <b>Best Streak:</b> {best_streak}\n"
            f"⭐ <b>Best Asset:</b> {best_asset}\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="stats")],
            [InlineKeyboardButton("📈 Asset Stats", callback_data="asset_stats")]
        ])
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        return True
        
    except Exception as e:
        print(f"Failed to send stats: {e}")
        return False


async def send_health_alert(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    component: str,
    status: str,
    details: str = ""
) -> bool:
    """
    Send system health alert.
    
    Args:
        context: Telegram bot context
        chat_id: Target chat ID
        component: Component name (API, Bot, WebSocket)
        status: Status (UP/DOWN)
        details: Additional details
    
    Returns:
        True if message sent successfully
    """
    try:
        if status.upper() == 'DOWN':
            emoji = '🚨'
            color = '<b>DOWN 🔴</b>'
        else:
            emoji = '✅'
            color = '<b>UP 🟢</b>'
        
        message_text = (
            f"{emoji} <b>System Alert</b>\n\n"
            f"Component: <b>{component}</b>\n"
            f"Status: {color}\n"
        )
        
        if details:
            message_text += f"\n<i>{details}</i>"
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML'
        )
        
        return True
        
    except Exception as e:
        print(f"Failed to send health alert: {e}")
        return False
