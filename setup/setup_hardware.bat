@echo off
setlocal
set "ROOT=%~dp0"
set "PY="

if defined TORMENT_NEXUS_PYTHON (
    set "PY=%TORMENT_NEXUS_PYTHON%"
) else if exist "%ROOT%python\python.exe" (
    set "PY=%ROOT%python\python.exe"
) else if exist "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" (
    set "PY=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
) else (
    set "PY=python"
)

cd /d "%ROOT%"
"%PY%" assistant\hardware\setup_hardware.py
echo.
echo This window will close automatically in 20 seconds.
echo Press any key to close it sooner.
timeout /t 20 >nul
