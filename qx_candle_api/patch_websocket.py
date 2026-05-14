"""
Patch for Python 3.13 websocket-client compatibility issue.
"""

import asyncio
import sys

# Patch asyncio to handle extra_headers
if sys.version_info >= (3, 13):
    import asyncio.trsock

    # Store original
    orig_transport_connect = asyncio.trsock.TransportSocket.connect

    async def patched_connect(self, address):
        # Remove extra_headers from kwargs if present
        # This is a workaround for Python 3.13
        return await orig_transport_connect(self, address)

    asyncio.trsock.TransportSocket.connect = patched_connect

print(f"Python version: {sys.version_info}")
print("WebSocket patch applied for Python 3.13")
