#!/bin/bash
# Install SpotiFLAC as systemd services
# Run with: sudo ./install-services.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing SpotiFLAC services..."

# Copy service files
sudo cp "$SCRIPT_DIR/spotiflac-api.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/spotiflac-bot.service" /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable spotiflac-api
sudo systemctl enable spotiflac-bot

echo ""
echo "Services installed! Commands:"
echo ""
echo "  Start:   sudo systemctl start spotiflac-api spotiflac-bot"
echo "  Stop:    sudo systemctl stop spotiflac-bot spotiflac-api"
echo "  Status:  sudo systemctl status spotiflac-api spotiflac-bot"
echo "  Logs:    sudo journalctl -u spotiflac-bot -f"
echo ""
echo "Starting services now..."
sudo systemctl start spotiflac-api
sleep 2
sudo systemctl start spotiflac-bot

echo ""
echo "✅ SpotiFLAC is now running as a background service!"
echo "   It will auto-start on reboot."
