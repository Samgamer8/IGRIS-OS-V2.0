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

pyinstaller --noconfirm --clean --onefile --windowed --name "IGRIS OS" `
    --icon "assets\igris_icon_v2.ico" --paths src --add-data "assets;assets" `
    --hidden-import PyQt6 main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$distDir = Join-Path $root "dist\IGRIS OS"
$onefileExe = Join-Path $root "dist\IGRIS OS.exe"
if (-not (Test-Path -LiteralPath $onefileExe)) { throw "No se genero el ejecutable" }
if (-not (Test-Path -LiteralPath $distDir)) {
    New-Item -ItemType Directory -Path $distDir | Out-Null
}
$exe = Join-Path $distDir "IGRIS OS.exe"
Copy-Item -LiteralPath $onefileExe -Destination $exe -Force
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $root "dist\IGRIS OS\SHA256SUMS.txt") `
    -Value ($hash + "  IGRIS OS.exe") -Encoding ascii
Write-Output "PORTABLE GENERADO Y VERIFICADO: $hash"
