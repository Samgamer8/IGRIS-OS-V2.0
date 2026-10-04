@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Este prototipo necesita Node.js para abrirse localmente.
    pause
    exit /b 1
)
node "tools\serve-snapshot.mjs"