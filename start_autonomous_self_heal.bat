@echo off
setlocal

echo.
echo ================================================================
echo HIGH-RISK ADVANCED MODE - ONE AUTONOMOUS REPAIR CYCLE
echo ================================================================
echo This starts Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0 and opts
echo directly into one bounded autonomous repair cycle at startup.
echo The model may inspect, modify, validate, and roll back project files
echo without asking for approval at every individual edit.
echo.
echo "Abliterated" means refusal behaviour may be weakened. The model can
echo be confidently wrong. Guardrails, backups, tests, and rollback reduce
echo risk but are not a security sandbox or a guarantee against data loss.
echo.
echo Close every other project editor. Keep a separate backup. Do not run
echo as Administrator. Remove credentials and irreplaceable files from the
echo project, and inspect the resulting diff and test report afterward.
echo.
set "LAUNCH_CONFIRMATION="
set /p "LAUNCH_CONFIRMATION=Type RUN ONE AUTONOMOUS REPAIR to continue: "
if /i not "%LAUNCH_CONFIRMATION%"=="RUN ONE AUTONOMOUS REPAIR" goto launch_cancelled

set "TORMENT_NEXUS_AUTONOMOUS_ON_STARTUP=1"
set "TORMENT_NEXUS_ADVANCED_LAUNCH_CONFIRMED=ONE_CYCLE_AUTONOMOUS_REPAIR"

rem The wrapper has already shown the stronger warning and collected the
rem exact typed acknowledgement, so the maintenance launcher does not repeat
rem its own prompt.
call "%~dp0start_maintenance_coder.bat"
endlocal
exit /b

:launch_cancelled
echo.
echo Autonomous repair cancelled. No model was started and no files changed.
endlocal
exit /b 2
