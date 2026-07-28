@echo off
setlocal
set "TORMENT_NEXUS_AUTONOMOUS_ON_STARTUP=1"

rem Starts the bounded 7B repair profile for one explicitly requested startup
rem cycle. start_maintenance_coder.bat keeps normal launches at zero unless
rem this wrapper (or an advanced user) deliberately opts in.
call "%~dp0start_maintenance_coder.bat"
endlocal
