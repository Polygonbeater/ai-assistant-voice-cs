#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
  echo "Virtuální prostředí již existuje: $VENV_DIR"
else
  echo "Vytvářím virtuální prostředí..."
  python3 -m venv "$VENV_DIR"
fi

PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

"$PYTHON_BIN" -m pip install --upgrade pip
"$PIP_BIN" install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "Hotovo. Nyní zkopírujte config.example.json do config.json a upravte hodnoty."
echo "Příklady:"
echo "  cp $SCRIPT_DIR/config.example.json $SCRIPT_DIR/config.json"
echo "  $PYTHON_BIN $SCRIPT_DIR/main.py"
