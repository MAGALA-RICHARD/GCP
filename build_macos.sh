#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python 3 was not found. Install Python 3.12 or newer first."
    exit 1
fi

if [[ ! -x ".venv-macos/bin/python" ]]; then
    "$PYTHON_BIN" -m venv .venv-macos
fi

PY=".venv-macos/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt

.venv-macos/bin/ruff check main.py helpers.py

rm -rf build dist
.venv-macos/bin/pyinstaller --clean --noconfirm GCPPixelPicker-macos.spec

APP="dist/GCP Pixel Picker.app"
if [[ -d "$APP" ]]; then
    echo
    echo "SUCCESS: $APP"
    echo "Optional local launch: open \"$APP\""
else
    echo "BUILD FAILED: macOS app bundle was not created."
    exit 1
fi
