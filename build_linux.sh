#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python 3 was not found. Install Python 3.12 or newer first."
    exit 1
fi

if [[ ! -x ".venv-linux/bin/python" ]]; then
    "$PYTHON_BIN" -m venv .venv-linux
fi

PY=".venv-linux/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt

.venv-linux/bin/ruff check main.py helpers.py

rm -rf build dist
.venv-linux/bin/pyinstaller --clean --noconfirm GCPPixelPicker-linux.spec

BIN="dist/GCPPixelPicker"
if [[ -f "$BIN" ]]; then
    chmod +x "$BIN"
    echo
    echo "SUCCESS: $BIN"
    echo "Run with: ./$BIN"
else
    echo "BUILD FAILED: Linux executable was not created."
    exit 1
fi
