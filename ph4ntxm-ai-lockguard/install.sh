#!/bin/bash
# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

set -euo pipefail
umask 077

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
SERVICE_NAME="ph4ntxm-lockguard.service"
USER_SERVICE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
START_SERVICE=false

fail() {
    printf 'Installation stopped: %s\n' "$*" >&2
    exit 1
}

case "${1:-}" in
    --start) START_SERVICE=true ;;
    --help|-h)
        printf '%s\n' "Usage: ./build.sh [--start]" "Installs dependencies and the user service. --start also enables and starts camera protection."
        exit 0
        ;;
    "") ;;
    *) fail "Unknown option: $1" ;;
esac
[ "$#" -le 1 ] || fail "Too many arguments."
[ "$(id -u)" -ne 0 ] || fail "Run as your graphical-session user without sudo; only package installation uses sudo."
[ -w "$PROJECT_DIR" ] || fail "The application directory is not writable by $(id -un). Correct its ownership before installing."
case "$(uname -m)" in
    x86_64|aarch64) ;;
    *) fail "Supported architectures: x86_64 and aarch64." ;;
esac
command -v apt-get >/dev/null || fail "Automatic package installation requires Debian or Ubuntu."
command -v dpkg-query >/dev/null || fail "dpkg-query is required."
command -v systemctl >/dev/null || fail "A systemd user session is required."
systemctl --user show-environment >/dev/null || fail "The systemd user manager is unavailable. Run from your desktop session."

PACKAGES=(procps python3 python3-venv ca-certificates libseccomp2 libgl1 libglib2.0-0t64 libportaudio2)
if command -v python3 >/dev/null; then
    PYTHON_VENV_PACKAGE="$(python3 -c 'import sys; print("python%d.%d-venv" % sys.version_info[:2])')"
    PACKAGES+=("$PYTHON_VENV_PACKAGE")
fi
MISSING=()
for package in "${PACKAGES[@]}"; do
    if [ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" != "install ok installed" ]; then
        MISSING+=("$package")
    fi
done
if [ "${#MISSING[@]}" -gt 0 ]; then
    command -v sudo >/dev/null || fail "sudo is required to install missing system packages."
    printf 'Installing system packages: %s\n' "${MISSING[*]}"
    sudo apt-get update
    sudo apt-get install --no-install-recommends -y "${MISSING[@]}"
fi

command -v loginctl >/dev/null || fail "loginctl is required."
python3 - "$PROJECT_DIR" <<'PYTHON'
import sys
assert sys.version_info >= (3, 11), "Python 3.11 or newer is required"
if any(not (char.isalnum() or char in "/ ._-%") for char in sys.argv[1]):
    raise SystemExit("Installation path contains unsupported characters")
PYTHON

LOCK_BACKEND="$(python3 - "$PROJECT_DIR/lockguard.toml" <<'PYTHON'
from pathlib import Path
import sys
import tomllib
print(tomllib.loads(Path(sys.argv[1]).read_text()).get("lock_backend", "light-locker"))
PYTHON
)"
case "$LOCK_BACKEND" in
    light-locker)
        if ! command -v light-locker-command >/dev/null; then
            command -v sudo >/dev/null || fail "sudo is required to install light-locker."
            sudo apt-get update
            sudo apt-get install --no-install-recommends -y light-locker
        fi
        ;;
    loginctl) ;;
    *) fail "Unsupported lock_backend in lockguard.toml." ;;
esac

[ ! -L "$VENV_DIR" ] || fail "Refusing to modify a symlinked .venv."
[ ! -e "$VENV_DIR" ] || [ -w "$VENV_DIR" ] || fail "The existing .venv is not writable by your user."
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    printf '%s\n' "Stopping LockGuard for the update; protection is temporarily inactive."
    systemctl --user stop "$SERVICE_NAME"
    START_SERVICE=true
fi
trap 'printf "%s\n" "Installation failed. Protection has not been started; fix the error above and rerun the installer." >&2' ERR
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m ensurepip --upgrade
"$VENV_DIR/bin/python" -m pip --version >/dev/null
"$VENV_DIR/bin/python" -m pip install --only-binary=:all: -r "$PROJECT_DIR/requirements.txt"
"$VENV_DIR/bin/python" "$PROJECT_DIR/download_model.py"
mkdir -p "$USER_SERVICE_DIR"

"$VENV_DIR/bin/python" - "$PROJECT_DIR" "$USER_SERVICE_DIR/$SERVICE_NAME" <<'PYTHON'
from pathlib import Path
import os
import sys
import tempfile

source = Path(sys.argv[1])
def quote(value):
    if any(not (char.isalnum() or char in "/ ._-%") for char in value):
        raise SystemExit("Installation path contains unsupported characters")
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'
content = (source / "ph4ntxm-lockguard.service").read_text()
content = content.replace("%PYTHON%", quote(str(source / ".venv/bin/python")))
content = content.replace("%SCRIPT%", quote(str(source / "ph4ntxm_lockguard.py")))
target = Path(sys.argv[2])
fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".lockguard-service-")
with os.fdopen(fd, "w") as handle:
    handle.write(content)
os.replace(temporary, target)
PYTHON

systemctl --user daemon-reload
if [ "$START_SERVICE" = true ]; then
    if [ "$LOCK_BACKEND" = light-locker ]; then
        pgrep -u "$(id -u)" -x light-locker >/dev/null || fail "light-locker is not running. Log out and back into LightDM, test the screen lock, then rerun with --start."
    fi
    "$VENV_DIR/bin/python" "$PROJECT_DIR/ph4ntxm_lockguard.py" --check
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user restart "$SERVICE_NAME"
    systemctl --user is-active --quiet "$SERVICE_NAME"
    printf '%s\n' "User service enabled and started. Check --status for camera readiness."
else
    printf '%s\n' "Installed. Camera protection has not been started."
    printf '%s\n' "Test ./panic.sh from the application directory, then run ./build.sh --start from the repository root."
fi
