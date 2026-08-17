@echo off
title IGRIS OS V2.O
cd /d "%~dp0src"
python -m igris_os.cli panel
if errorlevel 1 (
    echo.
    echo [IGRIS] Error al iniciar. Revisa runtime/logs/main.log
    pause
)
