@echo off
setlocal

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
    exit /b 0
)
if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%~dp0main.py"
    exit /b 0
)
echo [ERROR] Falta Python. Ejecuta INSTALAR_IGRIS_OS.cmd.
pause
exit /b 1
