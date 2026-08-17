@echo off
title IGRIS OS V2.O
set PYTHONPATH=C:\Users\samva\OneDrive\Escritorio\IGRIS OS V2.O\src
cd /d "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V2.O"
python -m igris_os.cli panel
if errorlevel 1 (
    echo.
    echo [IGRIS] Error al iniciar.
    pause
)
