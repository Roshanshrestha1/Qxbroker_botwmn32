"""
Smart Asset Filter for QxBroker Trading Bot.
Pre-filters assets before WMA scanning based on:
- Spread filtering
- Volatility (ATR) thresholds
- Recent signal quality ranking
- Top N selection
- OTC asset switching during low-liquidity hours
"""

import asyncio
from datetime import datetime, time
from typing import List, Dict, Optional, Tuple
import aiohttp


class SmartAssetFilter:
    """
    Smart asset pre-filter that ranks and selects the best assets for scanning.
    """
    
    def __init__(self, api_base_url: str = "http://127.0.0.1:8000"):
        self.api_base_url = api_base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.asset_cache: Dict = {}
        self.signal_history: Dict[str, List[bool]] = {}  # asset -> [win, loss, ...]
        self.max_history = 50  # Keep last 50 signals per asset
        
        # Filter thresholds
        self.max_spread_pips = 3.0
        self.min_atr = 0.0001  # Minimum ATR for volatility
        self.top_n_assets = 10
    
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
        """Fetch all available assets from API."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.api_base_url}/assets") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("all", [])
                return []
        except Exception as e:
            print(f"Error fetching assets: {e}")
            return []
    
    async def get_payouts(self) -> Dict[str, float]:
        """Fetch payout percentages for all assets."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.api_base_url}/payouts") as response:
                if response.status == 200:
                    data = await response.json()
                    # Parse payouts - adjust based on actual API response format
                    payouts = {}
                    if isinstance(data, dict):
                        for asset, info in data.items():
                            if isinstance(info, dict):
                                payouts[asset] = info.get('payout', 0.0)
                            elif isinstance(info, (int, float)):
                                payouts[asset] = info
                    return payouts
                return {}
        except Exception as e:
            print(f"Error fetching payouts: {e}")
            return {}
    
    async def estimate_spread(self, asset: str) -> float:
        """
        Estimate spread by comparing bid/ask simulation.
        Uses recent candle data to approximate spread.
        
        Returns spread in pips.
        """
        try:
            session = await self._get_session()
            
            # Fetch 1-minute candles
            async with session.get(
                f"{self.api_base_url}/candles/{asset}/latest",
                params={"period": 60, "count": 10}
            ) as response:
                if response.status != 200:
                    return 999.0  # High spread to filter out
                
                data = await response.json()
                candles = data.get("candles", [])
                
                if len(candles) < 2:
                    return 999.0
                
                # Estimate spread from candle gaps
                spreads = []
                for i in range(1, len(candles)):
                    prev_close = candles[i-1]['close']
                    curr_open = candles[i]['open']
                    spread = abs(curr_open - prev_close)
                    spreads.append(spread)
                
                avg_spread = sum(spreads) / len(spreads) if spreads else 0
                
                # Convert to pips (approximate for forex)
                if asset.endswith('_otc'):
                    pips = avg_spread * 100000  # OTC might have different pricing
                else:
                    pips = avg_spread * 10000
                
                return pips
                
        except Exception as e:
            return 999.0
    
    async def calculate_atr(self, asset: str, period: int = 14) -> float:
        """
        Calculate Average True Range for volatility measurement.
        
        Returns:
            ATR value
        """
        try:
            session = await self._get_session()
            
            async with session.get(
                f"{self.api_base_url}/candles/{asset}/latest",
                params={"period": 60, "count": period + 10}
            ) as response:
                if response.status != 200:
                    return 0.0
                
                data = await response.json()
                candles = data.get("candles", [])
                
                if len(candles) < period + 1:
                    return 0.0
                
                # Calculate ATR
                true_ranges = []
                for i in range(1, len(candles)):
                    high = candles[i]['high']
                    low = candles[i]['low']
                    prev_close = candles[i-1]['close']
                    
                    tr1 = high - low
                    tr2 = abs(high - prev_close)
                    tr3 = abs(low - prev_close)
                    
                    true_range = max(tr1, tr2, tr3)
                    true_ranges.append(true_range)
                
                if len(true_ranges) < period:
                    return 0.0
                
                atr = sum(true_ranges[-period:]) / period
                return atr
                
        except Exception as e:
            return 0.0
    
    def is_low_liquidity_hours(self) -> bool:
        """
        Check if current time is during low-liquidity hours.
        Low liquidity: Weekends and nights (22:00-06:00 UTC)
        """
        now = datetime.utcnow()
        
        # Weekend check
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return True
        
        # Night hours check (22:00-06:00 UTC)
        hour = now.hour
        if hour >= 22 or hour <= 6:
            return True
        
        return False
    
    def should_use_otc(self) -> bool:
        """
        Determine if OTC assets should be prioritized.
        Use OTC during low-liquidity hours when normal markets are closed.
        """
        return self.is_low_liquidity_hours()
    
    async def get_recent_signal_quality(self, asset: str) -> float:
        """
        Get recent signal quality score for an asset.
        Based on historical win rate from tracked signals.
        
        Returns:
            Quality score 0.0-1.0
        """
        if asset not in self.signal_history or len(self.signal_history[asset]) == 0:
            return 0.5  # Default score for new assets
        
        wins = sum(self.signal_history[asset])
        total = len(self.signal_history[asset])
        
        return wins / total if total > 0 else 0.5
    
    def record_signal_result(self, asset: str, won: bool):
        """Record a signal result for quality tracking."""
        if asset not in self.signal_history:
            self.signal_history[asset] = []
        
        self.signal_history[asset].append(won)
        
        # Trim history
        if len(self.signal_history[asset]) > self.max_history:
            self.signal_history[asset] = self.signal_history[asset][-self.max_history:]
    
    async def filter_and_rank_assets(
        self,
        use_otc: bool = None
    ) -> List[Tuple[str, float]]:
        """
        Filter and rank assets based on spread, volatility, and signal quality.
        
        Args:
            use_otc: Force OTC mode. If None, auto-detect based on time.
        
        Returns:
            List of (asset, score) tuples sorted by score descending
        """
        if use_otc is None:
            use_otc = self.should_use_otc()
        
        # Get all assets
        all_assets = await self.get_all_assets()
        
        if not all_assets:
            return []
        
        # Filter by OTC preference
        if use_otc:
            filtered = [a for a in all_assets if a.endswith('_otc')]
        else:
            filtered = [a for a in all_assets if not a.endswith('_otc')]
        
        # If no OTC assets available but we need them, fall back to all
        if use_otc and not filtered:
            filtered = all_assets
        
        ranked_assets = []
        
        for asset in filtered:
            # Check spread
            spread = await self.estimate_spread(asset)
            if spread > self.max_spread_pips:
                continue
            
            # Check volatility
            atr = await self.calculate_atr(asset)
            if atr < self.min_atr:
                continue
            
            # Get signal quality
            quality = await self.get_recent_signal_quality(asset)
            
            # Calculate composite score
            # Higher quality = better, Lower spread = better, Higher ATR = better (to a point)
            spread_score = max(0, (self.max_spread_pips - spread) / self.max_spread_pips)
            atr_score = min(1.0, atr / (self.min_atr * 10))  # Normalize ATR
            quality_score = quality
            
            # Weighted composite score
            composite_score = (
                quality_score * 0.5 +      # 50% weight on quality
                spread_score * 0.3 +       # 30% weight on spread
                atr_score * 0.2            # 20% weight on volatility
            )
            
            ranked_assets.append((asset, composite_score))
        
        # Sort by score descending
        ranked_assets.sort(key=lambda x: x[1], reverse=True)
        
        return ranked_assets
    
    async def get_top_assets(self, count: int = None) -> List[str]:
        """
        Get top N ranked assets for scanning.
        
        Args:
            count: Number of assets to return (default: self.top_n_assets)
        
        Returns:
            List of asset names
        """
        if count is None:
            count = self.top_n_assets
        
        ranked = await self.filter_and_rank_assets()
        return [asset for asset, score in ranked[:count]]
    
    async def refresh_cache(self):
        """Refresh the asset cache with latest data."""
        assets = await self.get_all_assets()
        payouts = await self.get_payouts()
        
        self.asset_cache = {
            'assets': assets,
            'payouts': payouts,
            'last_updated': datetime.now()
        }
    
    def get_cached_assets(self, max_age_seconds: int = 300) -> List[str]:
        """
        Get assets from cache if not too old.
        
        Args:
            max_age_seconds: Maximum age of cache in seconds
        
        Returns:
            List of asset names or empty list if cache is stale
        """
        if not self.asset_cache:
            return []
        
        last_updated = self.asset_cache.get('last_updated')
        if not last_updated:
            return []
        
        age = (datetime.now() - last_updated).total_seconds()
        if age > max_age_seconds:
            return []
        
        return self.asset_cache.get('assets', [])


async def run_asset_filter_demo():
    """Demo function to test the asset filter."""
    filter = SmartAssetFilter()
    
    print("=" * 50)
    print("Smart Asset Filter Demo")
    print("=" * 50)
    
    # Test low liquidity detection
    is_low_liq = filter.is_low_liquidity_hours()
    print(f"\nLow liquidity hours: {is_low_liq}")
    print(f"Should use OTC: {filter.should_use_otc()}")
    
    # Get top assets
    print("\nFetching top assets...")
    top_assets = await filter.get_top_assets(10)
    
    print(f"\nTop {len(top_assets)} assets for scanning:")
    for i, asset in enumerate(top_assets, 1):
        print(f"  {i}. {asset}")
    
    await filter.close()


if __name__ == "__main__":
    asyncio.run(run_asset_filter_demo())
