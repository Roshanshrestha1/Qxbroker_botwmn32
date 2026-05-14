"""
Fix for Python 3.13 + websockets 16 compatibility issue.
The issue is that extra_headers is passed to create_connection but Python 3.13
has changed how this parameter works.
"""

import sys
import asyncio

if sys.version_info >= (3, 13):
    # Patch asyncio.BaseEventLoop.create_connection to handle extra_headers
    _original_create_connection = asyncio.BaseEventLoop.create_connection

    async def _patched_create_connection(self, transport_factory, *args, **kwargs):
        # Remove extra_headers if present - it's not supported in Python 3.13
        kwargs.pop("extra_headers", None)
        return await _original_create_connection(
            self, transport_factory, *args, **kwargs
        )

    asyncio.BaseEventLoop.create_connection = _patched_create_connection
    print("Applied Python 3.13 websocket patch")
else:
    print(f"Python {sys.version_info.major}.{sys.version_info.minor} - no patch needed")
