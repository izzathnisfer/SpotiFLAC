#!/bin/bash
# SpotiFLAC Telegram Bot Setup Script
# For Ubuntu/Debian-based systems

set -e

echo "======================================"
echo "SpotiFLAC Telegram Bot Setup"
echo "======================================"

# Update system
echo ""
echo "[1/5] Updating system packages..."
sudo apt update

# Install Python
echo ""
echo "[2/5] Installing Python 3.11+..."
sudo apt install -y python3 python3-pip python3-venv

# Install FFmpeg
echo ""
echo "[3/5] Installing FFmpeg..."
sudo apt install -y ffmpeg

# Verify FFmpeg
if command -v ffmpeg &> /dev/null; then
    echo "✓ FFmpeg installed: $(ffmpeg -version | head -n1)"
else
    echo "✗ FFmpeg installation failed"
    exit 1
fi

# Install Go (if not installed)
echo ""
echo "[4/5] Checking Go installation..."
if ! command -v go &> /dev/null; then
    echo "Installing Go..."
    wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz
    sudo rm -rf /usr/local/go
    sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz
    rm go1.21.5.linux-amd64.tar.gz
    export PATH=$PATH:/usr/local/go/bin
    echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
fi
echo "✓ Go installed: $(go version)"

# Setup Python virtual environment
echo ""
echo "[5/5] Setting up Python virtual environment..."
cd "$(dirname "$0")/.."
python3 -m venv bot/.venv
source bot/.venv/bin/activate
pip install --upgrade pip
pip install -r bot/requirements.txt

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Copy bot/.env.example to bot/.env"
echo "2. Fill in your Telegram credentials:"
echo "   - API_ID and API_HASH from my.telegram.org"
echo "   - BOT_TOKEN from @BotFather"
echo "   - CACHE_CHANNEL_ID (create a private channel)"
echo ""
echo "To start the bot:"
echo "  Terminal 1: go run ./cmd/api"
echo "  Terminal 2: source bot/.venv/bin/activate && python bot/main.py"
echo ""
