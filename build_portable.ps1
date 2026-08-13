$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root "src"
python -m pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
pyinstaller --noconfirm --clean --windowed --name "IGRIS OS V2.O" --icon "assets\igris_icon_v2.ico" --paths src --add-data "assets;assets" --hidden-import PyQt6 igris_panel.py
exit $LASTEXITCODE
