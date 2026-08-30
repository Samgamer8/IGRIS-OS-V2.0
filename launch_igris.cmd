@echo off
setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

rem Prefer the packaged desktop executable when present.
if exist "%ROOT%\dist\IGRIS OS\IGRIS OS.exe" (
    start "" "%ROOT%\dist\IGRIS OS\IGRIS OS.exe"
    exit /b 0
)

if exist "%ROOT%\dist\IGRIS OS.exe" (
    start "" "%ROOT%\dist\IGRIS OS.exe"
    exit /b 0
)

rem Fallback to source launch using pythonw and explicit root path.
set "PYTHONPATH=%ROOT%\src"
set "QT_QPA_PLATFORM=windows"
if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%ROOT%\main.py"
    exit /b 0
)
if exist "C:\Windows\pyw.exe" (
    start "" "C:\Windows\pyw.exe" "%ROOT%\main.py"
    exit /b 0
)

rem Last resort: normal python if no pythonw is available.
if exist "C:\Python314\python.exe" (
    start "" "C:\Python314\python.exe" "%ROOT%\main.py"
    exit /b 0
)

rem If nothing works, show a clear error.
color 0C
echo IGRIS OS no pudo encontrar un launcher viable.
echo Comprueba que Python 3.14 o el ejecutable portable esten instalados.
pause
exit /b 1
