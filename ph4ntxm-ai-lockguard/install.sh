#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
SERVICE_NAME="ph4ntxm-lockguard.service"
USER_SERVICE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
USER_SERVICE_PATH="$USER_SERVICE_DIR/$SERVICE_NAME"

if [ "$(id -u)" -eq 0 ]; then
    echo "Do not run install.sh with sudo. Run it as your normal user."
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

"$VENV_DIR/bin/python" "$PROJECT_DIR/download_model.py"

chmod +x "$PROJECT_DIR/panic.sh"

touch "$PROJECT_DIR/panic.log"
touch "$PROJECT_DIR/ph4ntxm_lockguard.log"

mkdir -p "$USER_SERVICE_DIR"

sed "s|%INSTALL_DIR%|$PROJECT_DIR|g" \
    "$PROJECT_DIR/ph4ntxm-lockguard.service" > "$USER_SERVICE_PATH"

systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"