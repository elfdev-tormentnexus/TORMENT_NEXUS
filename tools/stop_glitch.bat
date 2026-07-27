@echo off
REM Stop the icon glitcher and put the resting icon back.
REM
REM Matches on the command line rather than killing every pythonw, so an
REM unrelated Python program running windowless is left alone. The name
REM filter matters: without it the PowerShell running this very query
REM matches its own command line and kills itself.

cd /d "%~dp0.."

set "PY=python"
if defined AI_BUDDY_PYTHON (
    set "PY=%AI_BUDDY_PYTHON%"
) else if exist "%~dp0..\python\python.exe" (
    set "PY=%~dp0python\python.exe"
) else if exist "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" (
    set "PY=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
)

powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and $_.CommandLine -like '*glitch_icon.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('stopped pid ' + $_.ProcessId) }"

"%PY%" "%~dp0glitch_icon.py" --restore
