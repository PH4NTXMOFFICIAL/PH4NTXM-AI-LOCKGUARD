#!/bin/bash
# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SERVICE_NAME="ph4ntxm-lockguard.service"
USER_SERVICE_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/$SERVICE_NAME"

if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' "Run uninstall.sh as your normal user."
    exit 1
fi

if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    systemctl --user stop "$SERVICE_NAME"
fi
systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
rm -f -- "$USER_SERVICE_PATH"
systemctl --user daemon-reload
rm -rf -- "$PROJECT_DIR/.venv"
rm -f -- "$PROJECT_DIR/face_detector.task" "$PROJECT_DIR/face_detector.task.part"
rm -f -- "$PROJECT_DIR/panic.log" "$PROJECT_DIR/ph4ntxm_lockguard.log" "$PROJECT_DIR/ph4ntxm_lockguard.log.1" "$PROJECT_DIR/ph4ntxm_lockguard.log.2"
printf '%s\n' "Removed the user service, environment, model and legacy local logs."
