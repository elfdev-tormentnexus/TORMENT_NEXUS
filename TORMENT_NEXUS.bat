@echo off
setlocal EnableExtensions

REM The one door. Every mode Sable runs in is a wrapper that sets its own
REM environment and then calls start_assistant.bat, so this menu dispatches
REM to those wrappers rather than duplicating what they do -- a second copy
REM of the hazard launcher's port and key handling would drift from the
REM first one and be wrong in a way nobody noticed until it mattered.
REM
REM Each mode still works when launched directly. This exists so nobody has
REM to remember which of four filenames they wanted.

set "ROOT=%~dp0"
REM Passed to PowerShell through the environment rather than interpolated
REM into the command string, because an install path with a space or a
REM quote in it would otherwise rewrite the command being run.
set "TN_ROOT=%ROOT%"
set "TN_LEFTOVER_FILE=%TEMP%\torment_nexus_leftover.txt"

title TORMENT_NEXUS

:menu
cls
echo ==========================================================
echo   TORMENT_NEXUS
echo   Choose how to run her.
echo ==========================================================
echo.
echo    1   Sable, standard use
echo        Conversation, memory, voice, and the offline
echo        reference shelf. Nothing listens on a socket.
echo.
echo    2   Sable interlinked
echo        Standard, plus the read-only agent interface on
echo        loopback. That is a listening socket and an
echo        authentication boundary, so it gets its own door.
echo.
echo    3   Sable hazard mode
echo        Standard, plus machinespirit: per-token trajectories
echo        read against the anchor dictionary. Starts a second
echo        embedder on port 8084.
echo.
echo    4   Sable Super Dev mode
echo        Hazard, with the 14B planner and an isolated 7B
echo        patch worker. This is the self-editing surface.
echo        Choose it on purpose.
echo.
echo    Q   Quit
echo.

call :check_leftovers

set "PICK="
set /p "PICK=   Select 1-4, or Q to quit: "

REM One `goto` per branch rather than `if ... & goto :menu`. In batch the
REM `&` binds outside the `if`, so the goto would fire whatever was typed --
REM including Q, which would then never reach its own line and the menu could
REM not be quit.
if "%PICK%"=="1" goto :pick_standard
if "%PICK%"=="2" goto :pick_interlinked
if "%PICK%"=="3" goto :pick_hazard
if "%PICK%"=="4" goto :pick_superdev
if /i "%PICK%"=="Q" goto :done
goto :menu

:pick_standard
call :launch "start_assistant.bat" "standard use"
goto :menu

:pick_interlinked
call :launch "start_interface_mode.bat" "interlinked"
goto :menu

:pick_hazard
call :launch "start_assistant_hazard.bat" "hazard mode"
goto :menu

:pick_superdev
call :launch "start_super_dev_hazard.bat" "Super Dev mode"
goto :menu


:launch
REM %~1 is the wrapper, %~2 is what to call it on screen.
if not exist "%ROOT%%~1" (
    echo.
    echo   %~1 is not in this install, so that mode cannot start.
    echo   Every mode's launcher lives beside this one, in:
    echo     %ROOT%
    echo.
    pause
    goto :eof
)

cls
echo   Starting Sable -- %~2
echo.

REM `call` and not `start`, so the menu waits and comes back afterwards.
REM Each wrapper runs setlocal, which cmd pops when the called script
REM returns, so hazard's machinespirit variables cannot follow the operator
REM into standard use on the next pass through this menu.
call "%ROOT%%~1"
goto :eof


:check_leftovers
REM Modes clean up their own helper servers when they exit normally. Closing
REM a window with the X is not a normal exit, and neither is a crash, so a
REM previous session's embedder can still be holding a port. A mode that
REM finds a stranger there refuses to start rather than adopting it -- which
REM is the correct behaviour, and a baffling message if you do not know why.
REM
REM Matched on this install's own path, so a llama-server belonging to some
REM other project on the same machine is never touched.
set "LEFTOVER="
powershell -NoProfile -Command "@(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'llama*' -and $_.CommandLine -like ('*' + $env:TN_ROOT + '*') }).Count" > "%TN_LEFTOVER_FILE%" 2>nul
if exist "%TN_LEFTOVER_FILE%" set /p LEFTOVER=<"%TN_LEFTOVER_FILE%"
if not defined LEFTOVER goto :eof
if "%LEFTOVER%"=="0" goto :eof

echo   ------------------------------------------------------
echo    %LEFTOVER% model server^(s^) from an earlier session are still
echo    running in this install. That happens when a window is
echo    closed rather than exited.
echo.
set "CLEAR="
set /p "CLEAR=   Stop them first? [Y/n]: "
if /i "%CLEAR%"=="n" (
    echo.
    goto :eof
)

powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'llama*' -and $_.CommandLine -like ('*' + $env:TN_ROOT + '*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo   Stopped. Every mode now starts from nothing.
echo.
goto :eof


:done
if exist "%TN_LEFTOVER_FILE%" del "%TN_LEFTOVER_FILE%" >nul 2>&1
endlocal
exit /b 0
