#!/bin/bash
# Start API server and WMA32 Telegram Bot

echo "========================================="
echo "Starting QX Broker API Server..."
echo "========================================="

cd /home/roshan/Music/wma32\ stg/qxbrokerapi/qx_candle_api
source venv/bin/activate
nohup uvicorn main:app --host 127.0.0.1 --port 8000 > api.log 2>&1 &
API_PID=$!

echo "API Server started (PID: $API_PID)"

# Wait for API to be ready
echo "Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/ > /dev/null 2>&1; then
        echo "API is ready!"
        break
    fi
    sleep 1
done

echo ""
echo "========================================="
echo "Starting WMA32 Telegram Bot..."
echo "========================================="

python wma32_bot.py

# If bot stops, kill API
kill $API_PID 2>/dev/null
echo "API server stopped"