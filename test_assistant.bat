@echo off
setlocal
set "ROOT=%~dp0"
set "PY="

echo Running TORMENT_NEXUS regression tests...
echo.

if defined AI_BUDDY_PYTHON (
    set "PY=%AI_BUDDY_PYTHON%"
) else if exist "%ROOT%python\python.exe" (
    set "PY=%ROOT%python\python.exe"
) else if exist "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" (
    set "PY=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
) else (
    set "PY=python"
)

cd /d "%ROOT%assistant"
"%PY%" -m unittest discover -s tests -v

echo.
pause
