#!/usr/bin/env bash
# Polygon Beater Voice CS — Click-and-Run Desktop Launcher
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Zajištění běhu ve virtuálním prostředí venv
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    exec "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/start_app.py" "$@"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/start_app.py" "$@"
else
    exec python3 "$SCRIPT_DIR/start_app.py" "$@"
fi
