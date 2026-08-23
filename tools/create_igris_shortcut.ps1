# IGRIS OS V2.0 - Crea acceso directo en el escritorio.
# Uso: powershell -ExecutionPolicy Bypass -File tools\create_igris_shortcut.ps1
# Idempotente: re-ejecutable; sobreescribe el .lnk si ya existe.

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot | Split-Path -Parent
$vbs  = Join-Path $root "launch_igris.vbs"

# Icono: el del proyecto primero (valido), fallback al del sistema.
$iconPath = Join-Path $root "assets\igris_icon_v2.ico"
if (-not (Test-Path $iconPath)) { $iconPath = "$env:SystemRoot\System32\shell32.dll" }

$lnkPath = Join-Path ([Environment]::GetFolderPath('Desktop')) "IGRIS OS V2.0.lnk"

$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
$shortcut.TargetPath       = $vbs
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation     = "$iconPath,0"
$shortcut.WindowStyle      = 7
$shortcut.Description      = "IGRIS OS V2.0 Panel de Control"
$shortcut.Save()

Write-Host "Acceso directo: $lnkPath" -ForegroundColor Green
Write-Host "Target          $vbs"      -ForegroundColor Gray
Write-Host "Icon           : $iconPath" -ForegroundColor Gray
