#!/bin/bash
# Copyright (C) PH4NTXM
# Licensed under the GNU General Public License v3.0.

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
exec bash "$PROJECT_DIR/ph4ntxm-ai-lockguard/install.sh" "$@"
