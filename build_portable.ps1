$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root "src"
python tools\quality_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
pyinstaller --noconfirm --clean --windowed --name "IGRIS OS V2.O" --icon "assets\igris_icon_v2.ico" --paths src --add-data "assets;assets" --hidden-import PyQt6 igris_panel.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$exe = Join-Path $root "dist\IGRIS OS V2.O\IGRIS OS V2.O.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "No se genero el ejecutable" }
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $root "dist\IGRIS OS V2.O\SHA256SUMS.txt") `
    -Value ($hash + "  IGRIS OS V2.O.exe") -Encoding ascii
Write-Output "PORTABLE GENERADO Y VERIFICADO: $hash"
exit 0
