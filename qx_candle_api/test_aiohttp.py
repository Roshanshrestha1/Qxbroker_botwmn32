"""
Test aiohttp WebSocket connection to QxBroker.
"""

import asyncio
import aiohttp
import ssl
import json


async def test_aiohttp_ws():
    print("Testing aiohttp WebSocket connection...")

    # QxBroker WebSocket URL
    ws_url = "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket"

    # Create SSL context that doesn't verify certificates
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url, ssl=ssl_context) as ws:
                print(f"Connected!")

                # Try to receive a message
                msg = await ws.receive()
                print(f"Received: {msg.data}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_aiohttp_ws())
