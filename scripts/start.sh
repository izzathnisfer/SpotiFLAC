#!/bin/bash
# SpotiFLAC Telegram Bot - Single Start Script
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo "  SpotiFLAC Telegram Bot Launcher"
echo "======================================"

# Check if .env exists
if [ ! -f "$PROJECT_DIR/bot/.env" ]; then
    echo "ERROR: bot/.env file not found!"
    echo ""
    echo "Please create it first:"
    echo "  cp bot/.env.example bot/.env"
    echo "  nano bot/.env"
    echo ""
    echo "Required values:"
    echo "  API_ID=<from my.telegram.org>"
    echo "  API_HASH=<from my.telegram.org>"
    echo "  BOT_TOKEN=<from @BotFather>"
    echo "  CACHE_CHANNEL_ID=<your private channel>"
    exit 1
fi

# Check for required tools
command -v go >/dev/null 2>&1 || { echo "ERROR: Go is not installed"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: Python3 is not installed"; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "WARNING: FFmpeg not found. Some features may not work."; }

# Create/activate virtual environment if needed
if [ ! -d "$PROJECT_DIR/bot/venv" ]; then
    echo "[1/3] Creating Python virtual environment..."
    python3 -m venv "$PROJECT_DIR/bot/venv"
    source "$PROJECT_DIR/bot/venv/bin/activate"
    pip install -q -r "$PROJECT_DIR/bot/requirements.txt"
else
    source "$PROJECT_DIR/bot/venv/bin/activate"
fi

echo "[2/3] Starting Go API server on port 8765..."
cd "$PROJECT_DIR"
go run ./cmd/api &
API_PID=$!

# Wait for API to start
sleep 2

# Check if API started successfully
if ! kill -0 $API_PID 2>/dev/null; then
    echo "ERROR: Go API failed to start"
    exit 1
fi

echo "[3/3] Starting Telegram bot..."
cd "$PROJECT_DIR/bot"
python main.py &
BOT_PID=$!

echo ""
echo "======================================"
echo "  Both services started!"
echo "======================================"
echo ""
echo "Go API PID: $API_PID"
echo "Bot PID: $BOT_PID"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Handle shutdown
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $API_PID 2>/dev/null || true
    kill $BOT_PID 2>/dev/null || true
    echo "Done."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for both processes
wait
