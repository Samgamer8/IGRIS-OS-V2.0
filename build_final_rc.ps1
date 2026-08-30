$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root "src"

python tools\release_check.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m compileall -q src production_main_final.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Las pruebas no permiten generar la RC final" }

pyinstaller --noconfirm --clean --onefile --windowed `
    --name "IGRIS OS FINAL RC" `
    --icon "assets\igris_icon_v2.ico" --paths src `
    --add-data "assets;assets" --hidden-import PyQt6 production_main_final.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$source = Join-Path $root "dist\IGRIS OS FINAL RC.exe"
$bundle = Join-Path $root "dist\IGRIS OS FINAL RC"
if (-not (Test-Path -LiteralPath $source)) { throw "No se genero el EXE final" }
if (-not (Test-Path -LiteralPath $bundle)) { New-Item -ItemType Directory -Path $bundle | Out-Null }
$target = Join-Path $bundle "IGRIS OS FINAL RC.exe"
Copy-Item -LiteralPath $source -Destination $target -Force
$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $bundle "SHA256SUMS.txt") `
    -Value ($hash + "  IGRIS OS FINAL RC.exe") -Encoding ascii
Write-Output "RC FINAL GENERADA: $hash"
