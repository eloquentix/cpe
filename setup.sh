#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/wcpe-delay"

echo "=== WCPE Time-Shifted Radio — Raspberry Pi Setup ==="
echo ""

# System dependencies
sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg python3 python3-pip python3-venv

# Copy project to install directory
sudo mkdir -p "$INSTALL_DIR"
sudo cp config.yaml recorder.py server.py cleanup.py requirements.txt "$INSTALL_DIR/"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"

# Python environment
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

# Create segments directory
mkdir -p "$INSTALL_DIR/segments"

# Install systemd units
sudo cp systemd/wcpe-recorder.service /etc/systemd/system/
sudo cp systemd/wcpe-server.service /etc/systemd/system/
sudo cp systemd/wcpe-cleanup.service /etc/systemd/system/
sudo cp systemd/wcpe-cleanup.timer /etc/systemd/system/
sudo systemctl daemon-reload

echo ""
echo "Setup complete."
echo ""
echo "Edit config before starting:"
echo "  nano $INSTALL_DIR/config.yaml"
echo ""
echo "Start services:"
echo "  sudo systemctl enable --now wcpe-recorder wcpe-server wcpe-cleanup.timer"
echo ""
echo "Check status:"
echo "  sudo systemctl status wcpe-recorder wcpe-server"
echo "  curl http://localhost:8234/status"
echo ""
echo "Stream URL (after ${delay_hours:-17}h buffer fills):"
echo "  http://\$(hostname -I | awk '{print \$1}'):8234/stream"
