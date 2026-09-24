#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/config.json" ]; then
  echo "Chybí config.json. Vytvořte ho z config.example.json:"
  echo "  cp config.example.json config.json"
  exit 1
fi

if [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
  exec "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/main.py"
fi

exec python3 "$SCRIPT_DIR/main.py"
