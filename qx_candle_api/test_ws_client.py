"""
Test websocket-client library for QxBroker connection.
"""

import websocket
import ssl
import json
import threading
import time


def on_message(ws, message):
    print(f"Received: {message[:100]}...")


def on_error(ws, error):
    print(f"Error: {error}")


def on_close(ws, close_status_code, close_msg):
    print(f"Closed: {close_status_code} - {close_msg}")


def on_open(ws):
    print("Connected!")
    # Send a test message
    ws.send('40{"event":"app"}')


# QxBroker WebSocket URL
ws_url = "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket"

# Create SSL context that doesn't verify certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

print(f"Connecting to {ws_url}...")

ws = websocket.WebSocketApp(
    ws_url, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open
)

# Run the WebSocket connection
ws.run_forever(ssl_context=ssl_context)
