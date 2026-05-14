#!/bin/bash
# Start QxBroker Trading System
# This script starts both the API server and the Telegram bot

set -e

echo "=============================================="
echo "  QxBroker Trading System"
echo "=============================================="
echo ""

# Change to workspace directory
cd /workspace

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "   Copy config/.env.example to .env and fill in your credentials"
    echo ""
fi

# Start API server in background
echo "Starting API Server on http://127.0.0.1:8000..."
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 > logs/api.log 2>&1 &
API_PID=$!
echo "✓ API Server started (PID: $API_PID)"

# Wait for API to be ready
echo "Waiting for API to initialize..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "✓ API is ready!"
        break
    fi
    sleep 1
done

if ! curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "✗ API failed to start. Check logs/api.log for details."
    kill $API_PID 2>/dev/null
    exit 1
fi

echo ""
echo "=============================================="
echo "Starting Telegram Bot..."
echo "=============================================="
echo ""

# Start Telegram bot (runs in foreground)
python src/bot/wma32_bot.py

# Cleanup when bot stops
echo ""
echo "Stopping API server..."
kill $API_PID 2>/dev/null || true
echo "✓ System stopped"
