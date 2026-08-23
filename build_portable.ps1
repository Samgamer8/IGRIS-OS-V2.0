$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root "src"

python tools\release_check.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m compileall -q src
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Las pruebas no permiten generar la distribucion" }

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    throw "PyInstaller no esta instalado en el entorno activo"
}

pyinstaller --noconfirm --clean --windowed --name "IGRIS OS v4.0" `
    --icon "assets\igris_icon_v2.ico" --paths src --add-data "assets;assets" `
    --hidden-import PyQt6 main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = Join-Path $root "dist\IGRIS OS v4.0\IGRIS OS v4.0.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "No se genero el ejecutable" }
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $root "dist\IGRIS OS v4.0\SHA256SUMS.txt") `
    -Value ($hash + "  IGRIS OS v4.0.exe") -Encoding ascii
Write-Output "PORTABLE GENERADO Y VERIFICADO: $hash"
