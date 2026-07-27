@echo off
setlocal
REM This script lives in setup/, so the project root is one level up.
set "ROOT=%~dp0..\"
set "PY="

echo Running TORMENT_NEXUS regression tests...
echo.

if defined TORMENT_NEXUS_PYTHON (
    set "PY=%TORMENT_NEXUS_PYTHON%"
) else if exist "%ROOT%python\python.exe" (
    set "PY=%ROOT%python\python.exe"
) else if exist "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" (
    set "PY=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
) else (
    set "PY=python"
)

cd /d "%ROOT%assistant"
"%PY%" "%ROOT%assistant\run_regressions.py"

echo.
pause
