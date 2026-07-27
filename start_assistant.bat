@echo off
setlocal
set "ROOT=%~dp0"
set "PY="

if defined AI_BUDDY_PYTHON (
    set "PY=%AI_BUDDY_PYTHON%"
) else if exist "%ROOT%python\python.exe" (
    REM A private handoff carries its own interpreter. Prefer it so the
    REM launcher remains self-contained on a recipient's clean computer.
    set "PY=%ROOT%python\python.exe"
) else if exist "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" (
    set "PY=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
) else (
    set "PY=python"
)

cd /d "%ROOT%assistant"
"%PY%" main.py
pause
