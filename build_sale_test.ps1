$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root "src"
$product = "IGRIS OS SALE TEST"

python tools\release_check.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m compileall -q src production_main_release.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Las pruebas no permiten generar la edicion de test" }

pyinstaller --noconfirm --clean --onefile --windowed `
    --name $product `
    --icon "assets\igris_icon_v2.ico" --paths src `
    --add-data "assets;assets" --hidden-import PyQt6 production_main_release.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$source = Join-Path $root ("dist\" + $product + ".exe")
$bundle = Join-Path $root ("dist\" + $product)
if (-not (Test-Path -LiteralPath $source)) { throw "No se genero el ejecutable" }
if (-not (Test-Path -LiteralPath $bundle)) {
    New-Item -ItemType Directory -Path $bundle | Out-Null
}
$target = Join-Path $bundle ($product + ".exe")
Copy-Item -LiteralPath $source -Destination $target -Force
$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $bundle "SHA256SUMS.txt") `
    -Value ($hash + "  " + $product + ".exe") -Encoding ascii
$zip = Join-Path $root ("dist\" + $product + " Windows x64.zip")
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -LiteralPath $bundle -DestinationPath $zip -CompressionLevel Optimal
$zipHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
Write-Output ("EJECUTABLE_SHA256=" + $hash)
Write-Output ("ZIP_SHA256=" + $zipHash)
