$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    try { py -3.12 -m venv .venv } catch { py -3 -m venv .venv }
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\ruff.exe format main.py helpers.py
& .\.venv\Scripts\ruff.exe check --fix main.py helpers.py

Remove-Item build, dist -Recurse -Force -ErrorAction SilentlyContinue
& .\.venv\Scripts\pyinstaller.exe --clean --noconfirm GCPPixelPicker.spec

if (-not (Test-Path "dist\GCPPixelPicker.exe")) { throw "Build failed: EXE was not created." }
Write-Host "SUCCESS: dist\GCPPixelPicker.exe" -ForegroundColor Green
