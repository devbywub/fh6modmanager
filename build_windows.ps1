$ErrorActionPreference = "Stop"

Write-Host "Building FH6 Mod Manager..."
python -m pip install --upgrade pyinstaller
python -m PyInstaller fh6mm.spec --noconfirm
Write-Host "Build complete. Output: dist/FH6MM/FH6MM.exe"
