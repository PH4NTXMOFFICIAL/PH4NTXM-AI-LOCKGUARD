#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="ph4ntxm-lockguard.service"
USER_SERVICE_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/$SERVICE_NAME"

if [ "$(id -u)" -eq 0 ]; then
    echo "Do not run uninstall.sh with sudo. Run it as your normal user."
    exit 1
fi

systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true

rm -f "$USER_SERVICE_PATH"

systemctl --user daemon-reload

rm -rf "$PROJECT_DIR/.venv"
rm -f "$PROJECT_DIR/face_detector.task"
rm -f "$PROJECT_DIR/face_detector.task.part"
rm -f "$PROJECT_DIR/ph4ntxm_lockguard.log"
rm -f "$PROJECT_DIR/panic.log"