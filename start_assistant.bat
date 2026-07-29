@echo off
setlocal
set "ROOT=%~dp0"
set "PY="
set "TORMENT_NEXUS_RELEASE_VERSION=v0.2.0-beta.6"

echo.
echo TORMENT_NEXUS v0.2.0-beta.6
echo On first launch, the app presents a mandatory safety, privacy, and
echo model disclosure before ordinary use. No terminal confirmation is
echo required for the normal companion.
echo.

if defined TORMENT_NEXUS_PYTHON (
    set "PY=%TORMENT_NEXUS_PYTHON%"
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
REM Wrapper launchers have their own cleanup work to perform after the
REM assistant exits.  Do not strand their helper processes behind this
REM otherwise useful "press any key" prompt.
if not defined TORMENT_NEXUS_SKIP_LAUNCHER_PAUSE pause
