@echo off
REM Start the desktop icon glitcher with no console window.
REM pythonw is the windowless interpreter, so nothing appears in the
REM taskbar -- use stop_glitch.bat to stop it again.

cd /d "%~dp0.."

set PYW=
if defined TORMENT_NEXUS_PYTHON (
    set "PYW=%TORMENT_NEXUS_PYTHON:python.exe=pythonw.exe%"
) else if exist "%~dp0..\python\pythonw.exe" (
    REM The private handoff carries this interpreter beside the launcher.
    set "PYW=%~dp0..\python\pythonw.exe"
) else if exist "%LocalAppData%\Python\pythoncore-3.14-64\pythonw.exe" (
    set "PYW=%LocalAppData%\Python\pythoncore-3.14-64\pythonw.exe"
) else (
    set "PYW=pythonw"
)

start "" "%PYW%" "%~dp0glitch_icon.py"
echo Icon glitcher started. Run stop_glitch.bat to stop it.
