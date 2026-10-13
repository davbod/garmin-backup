#!/usr/bin/env bash
# Convenience shell wrapper for Garmin Backup
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/garmin_backup.py"

echo "Running Garmin Backup..."
python3 "$PYTHON_SCRIPT" "$@"
