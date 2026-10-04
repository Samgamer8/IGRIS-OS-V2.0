@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.14 -m venv .venv
    if errorlevel 1 py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 goto :fail
)

set "PY=%CD%\.venv\Scripts\python.exe"
"%PY%" -m ensurepip --upgrade
if errorlevel 1 goto :fail

"%PY%" -m pip install --disable-pip-version-check -e .
if errorlevel 1 goto :fail

"%PY%" main.py health
if errorlevel 1 goto :fail

powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $link=$ws.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'IGRIS OS.lnk')); $link.TargetPath=[IO.Path]::Combine('%CD%','launch_igris.cmd'); $link.WorkingDirectory='%CD%'; $link.Save()" >nul 2>nul
echo IGRIS OS instalado y verificado.
exit /b 0

:fail
echo Error al instalar o verificar IGRIS OS.
pause
exit /b 1