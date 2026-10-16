@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher ^(py^) was not found. Install Python 3.12 or newer first.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

ruff format main.py helpers.py
ruff check --fix main.py helpers.py

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller --clean --noconfirm GCPPixelPicker.spec

if exist "dist\GCPPixelPicker.exe" (
    echo.
    echo SUCCESS: dist\GCPPixelPicker.exe
) else (
    echo.
    echo BUILD FAILED.
    exit /b 1
)
endlocal
