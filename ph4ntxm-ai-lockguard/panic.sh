#!/bin/bash
set -u

LOGFILE="$(dirname "$(readlink -f "$0")")/panic.log"

{
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
    echo "USER=$(whoami)"
    echo "UID=$(id -u)"
    echo "DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-<unset>}"
    echo "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-<unset>}"

    echo "--- sessions ---"
    loginctl list-sessions --no-legend

    echo "--- lock session 2 ---"
    loginctl lock-session 2
    echo "EXIT_CODE=$?"
} >> "$LOGFILE" 2>&1

exit 0