# IGRIS OS - Crea acceso directo robusto en el escritorio.
# Uso: powershell -ExecutionPolicy Bypass -File tools\create_igris_shortcut.ps1
# Idempotente: re-ejecutable; sobreescribe el .lnk si ya existe.

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot | Split-Path -Parent
$launcher = Join-Path $root "launch_igris.cmd"

# Prioridad: ejecutable portable si existe; luego launcher CMD; luego .vbs.
$target = Join-Path $root "dist\IGRIS OS\IGRIS OS.exe"
if (-not (Test-Path $target)) {
    $target = Join-Path $root "dist\IGRIS OS.exe"
}
if (-not (Test-Path $target)) {
    $target = $launcher
}

# Icono: el del proyecto primero (valido), fallback al del sistema.
$iconPath = Join-Path $root "assets\igris_icon_v2.ico"
if (-not (Test-Path $iconPath)) { $iconPath = "$env:SystemRoot\System32\shell32.dll" }

$lnkPath = Join-Path ([Environment]::GetFolderPath('Desktop')) "IGRIS OS.lnk"

$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
$shortcut.TargetPath       = $target
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation     = "$iconPath,0"
$shortcut.WindowStyle      = 7
$shortcut.Description      = "IGRIS OS Panel de Control"
$shortcut.Save()

Write-Host "Acceso directo: $lnkPath" -ForegroundColor Green
Write-Host "Target          $target"    -ForegroundColor Gray
Write-Host "Icon           : $iconPath" -ForegroundColor Gray
