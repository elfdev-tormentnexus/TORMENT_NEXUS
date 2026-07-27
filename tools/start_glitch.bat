@echo off
REM Start the desktop icon glitcher with no console window.
REM pythonw is the windowless interpreter, so nothing appears in the
REM taskbar -- use stop_glitch.bat to stop it again.

cd /d "%~dp0.."

set PYW=
if defined AI_BUDDY_PYTHON (
    set "PYW=%AI_BUDDY_PYTHON:python.exe=pythonw.exe%"
) else if exist "%~dp0..\python\pythonw.exe" (
    REM The private handoff carries this interpreter beside the launcher.
    set "PYW=%~dp0python\pythonw.exe"
) else if exist "%LocalAppData%\Python\pythoncore-3.14-64\pythonw.exe" (
    set "PYW=%LocalAppData%\Python\pythoncore-3.14-64\pythonw.exe"
) else (
    set "PYW=pythonw"
)

start "" "%PYW%" "%~dp0glitch_icon.py"
echo Icon glitcher started. Run stop_glitch.bat to stop it.
