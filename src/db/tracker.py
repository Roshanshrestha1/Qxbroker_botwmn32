"""
Win/Loss Tracking System for QxBroker Trading Bot.
Records signals, tracks outcomes, and provides statistics via Telegram.
Uses SQLite for persistent storage with async support.
"""

import asyncio
import aiosqlite
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from pathlib import Path


# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'signals.db')


async def init_database():
    """Initialize the SQLite database with required tables."""
    db_dir = os.path.dirname(DB_PATH)
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                timestamp DATETIME NOT NULL,
                expiry_seconds INTEGER DEFAULT 60,
                confidence_stars INTEGER,
                wma_value REAL,
                rsi_value REAL,
                status TEXT DEFAULT 'PENDING',
                exit_price REAL,
                result TEXT,
                profit_loss REAL,
                checked_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS stats_cache (
                id INTEGER PRIMARY KEY,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                best_asset TEXT,
                last_updated DATETIME
            )
        ''')
        
        # Insert initial cache row if not exists
        await db.execute('''
            INSERT OR IGNORE INTO stats_cache (id, total_trades, wins, losses)
            VALUES (1, 0, 0, 0)
        ''')
        
        await db.commit()
    
    print(f"✓ Database initialized at {DB_PATH}")


async def record_signal(
    asset: str,
    direction: str,
    entry_price: float,
    timestamp: datetime,
    confidence_stars: int = 3,
    wma_value: float = None,
    rsi_value: float = None,
    expiry_seconds: int = 60
) -> int:
    """
    Record a new signal in the database.
    
    Returns:
        Signal ID
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO signals 
            (asset, direction, entry_price, timestamp, confidence_stars, wma_value, rsi_value, expiry_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (asset, direction, entry_price, timestamp, confidence_stars, wma_value, rsi_value, expiry_seconds))
        
        signal_id = cursor.lastrowid
        await db.commit()
    
    return signal_id


async def check_signal_outcome(signal_id: int, current_price: float) -> Dict:
    """
    Check the outcome of a pending signal.
    
    Args:
        signal_id: ID of the signal to check
        current_price: Current market price
    
    Returns:
        Dict with result details
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Get signal details
        cursor = await db.execute('''
            SELECT asset, direction, entry_price, expiry_seconds, timestamp
            FROM signals
            WHERE id = ? AND status = 'PENDING'
        ''', (signal_id,))
        
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        asset, direction, entry_price, expiry_seconds, timestamp = row
        timestamp = datetime.fromisoformat(timestamp)
        
        # Check if expiry time has passed
        now = datetime.now()
        elapsed = (now - timestamp).total_seconds()
        
        if elapsed < expiry_seconds:
            return None  # Not yet expired
        
        # Determine result
        if direction == 'CALL':
            result = 'WIN' if current_price > entry_price else 'LOSS'
        else:  # PUT
            result = 'WIN' if current_price < entry_price else 'LOSS'
        
        profit_loss = 1.0 if result == 'WIN' else -1.0
        
        # Update database
        await db.execute('''
            UPDATE signals
            SET status = ?, exit_price = ?, result = ?, profit_loss = ?, checked_at = ?
            WHERE id = ?
        ''', (result, current_price, result, profit_loss, now, signal_id))
        
        # Update stats cache
        await _update_stats_cache(db)
        
        await db.commit()
        
        return {
            'signal_id': signal_id,
            'asset': asset,
            'direction': direction,
            'result': result,
            'entry_price': entry_price,
            'exit_price': current_price,
            'profit_loss': profit_loss
        }


async def _update_stats_cache(db):
    """Update the statistics cache with latest data."""
    # Calculate totals
    cursor = await db.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses
        FROM signals
        WHERE status != 'PENDING'
    ''')
    
    row = await cursor.fetchone()
    total, wins, losses = row
    wins = wins or 0
    losses = losses or 0
    
    win_rate = (wins / total * 100) if total > 0 else 0.0
    
    # Calculate current streak
    cursor = await db.execute('''
        SELECT result
        FROM signals
        WHERE status != 'PENDING'
        ORDER BY checked_at DESC
        LIMIT 20
    ''')
    
    results = [r[0] for r in await cursor.fetchall()]
    
    current_streak = 0
    for result in results:
        if result == 'WIN':
            current_streak += 1
        else:
            break
    
    # Calculate best streak
    cursor = await db.execute('''
        SELECT result
        FROM signals
        WHERE status != 'PENDING'
        ORDER BY timestamp ASC
    ''')
    
    all_results = [r[0] for r in await cursor.fetchall()]
    
    best_streak = 0
    temp_streak = 0
    for result in all_results:
        if result == 'WIN':
            temp_streak += 1
            best_streak = max(best_streak, temp_streak)
        else:
            temp_streak = 0
    
    # Find best asset
    cursor = await db.execute('''
        SELECT asset, 
               SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
               COUNT(*) as total
        FROM signals
        WHERE status != 'PENDING'
        GROUP BY asset
        HAVING total >= 5
        ORDER BY CAST(wins AS FLOAT) / total DESC
        LIMIT 1
    ''')
    
    best_row = await cursor.fetchone()
    best_asset = best_row[0] if best_row else 'N/A'
    
    # Update cache
    await db.execute('''
        UPDATE stats_cache
        SET total_trades = ?, wins = ?, losses = ?, win_rate = ?,
            current_streak = ?, best_streak = ?, best_asset = ?,
            last_updated = ?
        WHERE id = 1
    ''', (total, wins, losses, win_rate, current_streak, best_streak, best_asset, datetime.now()))


async def get_stats() -> Dict:
    """Get current trading statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM stats_cache WHERE id = 1')
        row = await cursor.fetchone()
        
        if not row:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'current_streak': 0,
                'best_streak': 0,
                'best_asset': 'N/A',
                'last_updated': None
            }
        
        return {
            'total_trades': row[1],
            'wins': row[2],
            'losses': row[3],
            'win_rate': row[4],
            'current_streak': row[5],
            'best_streak': row[6],
            'best_asset': row[7],
            'last_updated': row[8]
        }


async def get_recent_signals(limit: int = 10) -> List[Dict]:
    """Get recent signals with their results."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT asset, direction, entry_price, timestamp, status, result, confidence_stars
            FROM signals
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        signals = []
        async for row in cursor:
            signals.append({
                'asset': row[0],
                'direction': row[1],
                'entry_price': row[2],
                'timestamp': row[3],
                'status': row[4],
                'result': row[5],
                'confidence_stars': row[6]
            })
        
        return signals


async def get_asset_stats(asset: str = None) -> Dict:
    """Get statistics for a specific asset or all assets."""
    async with aiosqlite.connect(DB_PATH) as db:
        if asset:
            cursor = await db.execute('''
                SELECT 
                    asset,
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses
                FROM signals
                WHERE asset = ? AND status != 'PENDING'
                GROUP BY asset
            ''', (asset,))
        else:
            cursor = await db.execute('''
                SELECT 
                    asset,
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses
                FROM signals
                WHERE status != 'PENDING'
                GROUP BY asset
                ORDER BY total DESC
            ''')
        
        stats = {}
        async for row in cursor:
            asset_name = row[0]
            total = row[1]
            wins = row[2] or 0
            losses = row[3] or 0
            win_rate = (wins / total * 100) if total > 0 else 0.0
            
            stats[asset_name] = {
                'total': total,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate
            }
        
        return stats


class WinLossTracker:
    """
    Async win/loss tracker that automatically monitors signals.
    """
    
    def __init__(self, api_client=None):
        self.api_client = api_client
        self.pending_checks = {}  # signal_id -> check_task
        self.running = False
    
    async def start(self):
        """Start the tracker background task."""
        self.running = True
        asyncio.create_task(self._check_loop())
        print("✓ Win/Loss tracker started")
    
    def stop(self):
        """Stop the tracker."""
        self.running = False
        for task in self.pending_checks.values():
            task.cancel()
        self.pending_checks.clear()
        print("✗ Win/Loss tracker stopped")
    
    async def track_signal(
        self,
        asset: str,
        direction: str,
        entry_price: float,
        timestamp: datetime,
        confidence_stars: int = 3,
        wma_value: float = None,
        rsi_value: float = None,
        expiry_seconds: int = 65
    ):
        """Track a new signal and schedule outcome check."""
        signal_id = await record_signal(
            asset=asset,
            direction=direction,
            entry_price=entry_price,
            timestamp=timestamp,
            confidence_stars=confidence_stars,
            wma_value=wma_value,
            rsi_value=rsi_value,
            expiry_seconds=expiry_seconds
        )
        
        # Schedule check after expiry + buffer
        check_delay = expiry_seconds + 5
        task = asyncio.create_task(self._delayed_check(signal_id, check_delay))
        self.pending_checks[signal_id] = task
        
        return signal_id
    
    async def _delayed_check(self, signal_id: int, delay: int):
        """Wait and then check signal outcome."""
        await asyncio.sleep(delay)
        
        if not self.running:
            return
        
        # Get current price from API
        if self.api_client:
            try:
                # Extract base asset name (remove _otc suffix if present)
                asset = await self._get_signal_asset(signal_id)
                if asset:
                    price_data = await self.api_client.get_price(asset)
                    if price_data and 'price' in price_data:
                        await check_signal_outcome(signal_id, price_data['price'])
            except Exception as e:
                print(f"Error checking signal {signal_id}: {e}")
        
        # Remove from pending
        self.pending_checks.pop(signal_id, None)
    
    async def _get_signal_asset(self, signal_id: int) -> Optional[str]:
        """Get asset name for a signal."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                'SELECT asset FROM signals WHERE id = ?',
                (signal_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def _check_loop(self):
        """Background loop to periodically check pending signals."""
        while self.running:
            try:
                # Get all pending signals
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute('''
                        SELECT id, asset, expiry_seconds, timestamp
                        FROM signals
                        WHERE status = 'PENDING'
                    ''')
                    
                    async for row in cursor:
                        signal_id, asset, expiry_seconds, timestamp = row
                        timestamp = datetime.fromisoformat(timestamp)
                        elapsed = (datetime.now() - timestamp).total_seconds()
                        
                        if elapsed >= expiry_seconds and signal_id not in self.pending_checks:
                            # Schedule check
                            task = asyncio.create_task(self._delayed_check(signal_id, 0))
                            self.pending_checks[signal_id] = task
                
            except Exception as e:
                print(f"Check loop error: {e}")
            
            await asyncio.sleep(10)  # Check every 10 seconds


# Initialize database on module load
async def setup():
    """Setup function to initialize database."""
    await init_database()
