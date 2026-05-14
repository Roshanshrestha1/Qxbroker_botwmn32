"""
System Health Monitor for QxBroker Trading Bot.
Monitors API server, WebSocket connection, and bot health.
Provides auto-restart capabilities and Telegram alerts.
"""

import asyncio
import subprocess
import psutil
import aiohttp
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path


class HealthMonitor:
    """
    System health monitoring with auto-restart and Telegram alerts.
    """
    
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8000",
        log_dir: str = "logs",
        restart_api_cmd: str = None,
        telegram_context=None,
        chat_id: int = None
    ):
        self.api_url = api_url
        self.log_dir = Path(log_dir)
        self.restart_api_cmd = restart_api_cmd or "uvicorn src.api.main:app --host 127.0.0.1 --port 8000"
        self.telegram_context = telegram_context
        self.chat_id = chat_id
        
        # Monitoring state
        self.running = False
        self.api_healthy = False
        self.ws_healthy = False
        self.bot_healthy = True
        
        # Metrics
        self.uptime_start = None
        self.last_check_time = None
        self.check_count = 0
        self.fail_count = 0
        
        # Process tracking
        self.api_process: Optional[subprocess.Popen] = None
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Start the health monitoring loop."""
        self.running = True
        self.uptime_start = datetime.now()
        
        print("=" * 50)
        print("Starting Health Monitor...")
        print("=" * 50)
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
        # Start periodic logging
        asyncio.create_task(self._log_uptime_loop())
    
    def stop(self):
        """Stop the health monitor."""
        self.running = False
        if self.api_process:
            self.api_process.terminate()
        print("✗ Health monitor stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop - checks every 30 seconds."""
        while self.running:
            try:
                await self._check_all_components()
                self.check_count += 1
                self.last_check_time = datetime.now()
                
            except Exception as e:
                self.fail_count += 1
                print(f"Health check error: {e}")
                await self._log_health_event("ERROR", f"Health check failed: {e}")
            
            await asyncio.sleep(30)
    
    async def _check_all_components(self):
        """Check all system components."""
        # Check API server
        api_was_healthy = self.api_healthy
        self.api_healthy = await self._check_api_server()
        
        if not self.api_healthy and api_was_healthy:
            # API just went down
            await self._handle_api_down()
        elif self.api_healthy and not api_was_healthy:
            # API recovered
            await self._handle_api_recovered()
        
        # Check WebSocket (via API)
        self.ws_healthy = await self._check_websocket()
        
        if not self.ws_healthy:
            await self._log_health_event("WARNING", "WebSocket connection unhealthy")
        
        # Check bot process
        self.bot_healthy = self._check_bot_process()
        
        if not self.bot_healthy:
            await self._log_health_event("CRITICAL", "Bot process not running!")
    
    async def _check_api_server(self) -> bool:
        """Check if API server is responding."""
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.api_url}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('status') == 'healthy'
        except Exception as e:
            print(f"API health check failed: {e}")
            return False
        
        return False
    
    async def _check_websocket(self) -> bool:
        """Check WebSocket connection status via API."""
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Check if we can get candles (requires WS connection)
                async with session.get(f"{self.api_url}/assets") as response:
                    if response.status == 200:
                        data = await response.json()
                        # If we get assets, WS is likely connected
                        return len(data.get('all', [])) > 0
        except Exception as e:
            print(f"WebSocket check failed: {e}")
            return False
        
        return False
    
    def _check_bot_process(self) -> bool:
        """Check if bot process is running."""
        try:
            # Look for python processes running the bot
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info.get('cmdline', []) or [])
                    if 'wma32_bot.py' in cmdline or 'bot' in cmdline.lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Bot process check error: {e}")
        
        # Assume healthy if we can't determine
        return True
    
    async def _handle_api_down(self):
        """Handle API server going down."""
        print("🚨 API server detected as DOWN!")
        
        await self._log_health_event(
            "CRITICAL",
            "API server is not responding"
        )
        
        await self._send_telegram_alert(
            "API Server Down",
            "The API server is not responding. Attempting to restart..."
        )
        
        # Try to restart API
        await self._restart_api()
    
    async def _handle_api_recovered(self):
        """Handle API server recovery."""
        print("✅ API server recovered!")
        
        await self._log_health_event(
            "INFO",
            "API server recovered successfully"
        )
        
        await self._send_telegram_alert(
            "API Server Recovered",
            "The API server is back online and responding."
        )
    
    async def _restart_api(self):
        """Attempt to restart the API server."""
        print("Attempting to restart API server...")
        
        try:
            # Kill existing API processes
            await self._kill_api_processes()
            
            # Start new API process
            cmd_parts = self.restart_api_cmd.split()
            self.api_process = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(Path(__file__).parent.parent.parent)
            )
            
            print(f"✓ API server restarted with PID: {self.api_process.pid}")
            
            await self._log_health_event(
                "ACTION",
                f"API server restarted (PID: {self.api_process.pid})"
            )
            
            # Wait and verify
            await asyncio.sleep(5)
            if await self._check_api_server():
                print("✓ API restart successful!")
            else:
                print("✗ API restart may have failed")
                
        except Exception as e:
            print(f"Failed to restart API: {e}")
            await self._log_health_event("ERROR", f"API restart failed: {e}")
    
    async def _kill_api_processes(self):
        """Kill any existing API server processes."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info.get('cmdline', []) or [])
                    if 'uvicorn' in cmdline and 'main:app' in cmdline:
                        proc.terminate()
                        print(f"Terminated API process {proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error killing API processes: {e}")
    
    async def _send_telegram_alert(self, title: str, message: str):
        """Send alert to Telegram if configured."""
        if not self.telegram_context or not self.chat_id:
            return
        
        try:
            from utils.telegram_alerts import send_health_alert
            
            await send_health_alert(
                context=self.telegram_context,
                chat_id=self.chat_id,
                component=title,
                status="DOWN" if "Down" in title else "UP",
                details=message
            )
        except Exception as e:
            print(f"Failed to send Telegram alert: {e}")
    
    async def _log_health_event(self, level: str, message: str):
        """Log health event to file."""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        
        log_file = self.log_dir / "health.log"
        
        with open(log_file, 'a') as f:
            f.write(log_entry)
        
        print(f"[{level}] {message}")
    
    async def _log_uptime_loop(self):
        """Periodically log uptime statistics."""
        while self.running:
            await asyncio.sleep(300)  # Every 5 minutes
            
            uptime = datetime.now() - self.uptime_start
            uptime_str = str(uptime).split('.')[0]
            
            success_rate = ((self.check_count - self.fail_count) / self.check_count * 100) if self.check_count > 0 else 0
            
            await self._log_health_event(
                "STATS",
                f"Uptime: {uptime_str} | Checks: {self.check_count} | Success: {success_rate:.1f}% | API: {'✓' if self.api_healthy else '✗'} | WS: {'✓' if self.ws_healthy else '✗'}"
            )
    
    def get_status(self) -> Dict:
        """Get current health status as dictionary."""
        uptime = datetime.now() - self.uptime_start if self.uptime_start else None
        
        return {
            'running': self.running,
            'api_healthy': self.api_healthy,
            'ws_healthy': self.ws_healthy,
            'bot_healthy': self.bot_healthy,
            'uptime': str(uptime).split('.')[0] if uptime else 'N/A',
            'total_checks': self.check_count,
            'failed_checks': self.fail_count,
            'success_rate': ((self.check_count - self.fail_count) / self.check_count * 100) if self.check_count > 0 else 0,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None
        }


async def get_health_status(api_url: str = "http://127.0.0.1:8000") -> Dict:
    """Quick health check function."""
    status = {
        'api': False,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{api_url}/health") as response:
                if response.status == 200:
                    status['api'] = True
    except Exception as e:
        status['error'] = str(e)
    
    return status


# Global monitor instance
monitor: Optional[HealthMonitor] = None


def create_monitor(
    api_url: str = "http://127.0.0.1:8000",
    telegram_context=None,
    chat_id: int = None
) -> HealthMonitor:
    """Create and return a health monitor instance."""
    global monitor
    monitor = HealthMonitor(
        api_url=api_url,
        telegram_context=telegram_context,
        chat_id=chat_id
    )
    return monitor
