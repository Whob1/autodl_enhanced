#!/usr/bin/env bash
#
# install.sh - Setup script for the Enhanced AutoDL Telegram Bot
#
# This script automates the installation of system dependencies,
# Python packages, virtual environment creation and systemd
# service installation. It should be executed on a host running a
# Debian/Ubuntu-based distribution with sudo privileges.

set -euo pipefail

APP_DIR="$(dirname "$(realpath "$0")")/.."
ENV_FILE="$APP_DIR/.env"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="autodl-bot.service"

echo "=== Enhanced AutoDL Telegram Bot Installation ==="
echo "App directory: $APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE"
    echo "Please create a .env file with required configuration before running install.sh"
    exit 1
fi

echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip aria2 ffmpeg

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

echo "Activating virtual environment and installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "Validating environment variables..."
VALIDATION_SCRIPT=$(cat <<'VALIDATION_EOF'
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from config_manager import load_config
    
    base_dir = Path(__file__).parent
    config = load_config(str(base_dir))
    
    print(f"✓ Configuration validated successfully")
    print(f"  - Bot token: {'*' * 20}{config.token[-10:]}")
    print(f"  - Download directory: {config.download_dir}")
    print(f"  - Max concurrent downloads: {config.max_concurrent}")
    print(f"  - Admin IDs: {', '.join(config.admin_ids) if config.admin_ids and config.admin_ids[0] else 'None (unrestricted)'}")
    
    if not Path(config.download_dir).exists():
        print(f"WARNING: Download directory does not exist: {config.download_dir}")
        print(f"         Please create it manually or ensure it will be available at runtime.")
    
    sys.exit(0)
    
except Exception as e:
    print(f"✗ Configuration validation failed: {e}")
    print(f"  Please check your .env file and fix the errors above.")
    sys.exit(1)
VALIDATION_EOF
)

echo "$VALIDATION_SCRIPT" > "$APP_DIR/.validate_config.py"
"$VENV_DIR/bin/python" "$APP_DIR/.validate_config.py"
VALIDATION_RESULT=$?
rm -f "$APP_DIR/.validate_config.py"

if [ $VALIDATION_RESULT -ne 0 ]; then
    echo "ERROR: Environment validation failed. Please fix the configuration errors."
    exit 1
fi

echo "Ensuring logs and queue directories exist..."
mkdir -p "$APP_DIR/data/logs" "$APP_DIR/data/queue" "$APP_DIR/data/cookies"

if [ -f "$APP_DIR/data/cookies/cookies.txt" ]; then
    echo "Setting secure permissions on cookies file..."
    chmod 600 "$APP_DIR/data/cookies/cookies.txt"
fi

echo "Creating systemd service file..."
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
sudo bash -c "cat > $SERVICE_FILE" <<'SERVICE_EOF'
[Unit]
Description=AutoDL Telegram Bot Service
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory={{APP_DIR}}
ExecStart={{APP_DIR}}/venv/bin/python -m src.autodl_bot
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo sed -i "s|{{APP_DIR}}|$APP_DIR|g" "$SERVICE_FILE"

echo "Reloading systemd daemon and enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "To start the bot:"
echo "  sudo systemctl start $SERVICE_NAME"
echo ""
echo "To view logs:"
echo "  journalctl -u $SERVICE_NAME -f"
echo ""
echo "To check status:"
echo "  sudo systemctl status $SERVICE_NAME"