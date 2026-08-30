$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root "src"

python tools\release_check.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m compileall -q src production_main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Las pruebas no permiten generar la RC" }

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    throw "PyInstaller no esta instalado en el entorno activo"
}

pyinstaller --noconfirm --clean --onefile --windowed `
    --name "IGRIS OS RC1" `
    --icon "assets\igris_icon_v2.ico" --paths src `
    --add-data "assets;assets" --hidden-import PyQt6 production_main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$source = Join-Path $root "dist\IGRIS OS RC1.exe"
$bundle = Join-Path $root "dist\IGRIS OS RC1"
if (-not (Test-Path -LiteralPath $source)) { throw "No se genero el EXE RC" }
if (-not (Test-Path -LiteralPath $bundle)) {
    New-Item -ItemType Directory -Path $bundle | Out-Null
}
$target = Join-Path $bundle "IGRIS OS RC1.exe"
Copy-Item -LiteralPath $source -Destination $target -Force
$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $bundle "SHA256SUMS.txt") `
    -Value ($hash + "  IGRIS OS RC1.exe") -Encoding ascii
Write-Output "RC PRODUCCION GENERADA: $hash"
