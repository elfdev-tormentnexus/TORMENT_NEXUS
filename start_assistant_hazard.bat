@echo off
REM ---------------------------------------------------------------
REM HAZARD MODE
REM
REM Starts TORMENT_NEXUS in experimental mode, running the
REM machinespirit representation: per-token embedding trajectories
REM read against a fixed anchor dictionary. SABLE7 is the container
REM that stores such a path; machinespirit is the language it carries.
REM
REM This is slower than the ordinary launcher, on purpose, and keeps a
REM second embedding server resident. That is the trade: more semantic
REM detail, less speed.
REM
REM What it adds today, stated plainly so nobody expects more:
REM
REM   'trace <text>' shows which concept appeared at which token. The
REM   ordinary averaged vector cannot do this at all -- averaging is
REM   exactly what destroys the position of a meaning.
REM
REM What it does NOT do: change retrieval. Keeping the path has not
REM been shown to retrieve better, only to say more about where a
REM meaning sat, so trajectories run alongside the ordinary retrieval
REM rather than replacing it. See docs/VECTOR_TRANSLATION_RESEARCH.md
REM for the measurements, including the ones that came out negative.
REM
REM start_assistant.bat uses setlocal, which isolates what it sets
REM internally but does not block what this script already set, so the
REM variables below reach config.py normally.
REM ---------------------------------------------------------------
setlocal
title TORMENT_NEXUS_HAZARD (experimental, two embedding servers)

set "ROOT=%~dp0"
set "UNPOOLED_PORT=8084"
set "EMBED_MODEL=%ROOT%models\embedding\bge-small-en-v1.5-q8_0.gguf"
set "LLAMA=%ROOT%llama.cpp\build\bin\Release\llama-server.exe"

if not exist "%LLAMA%" set "LLAMA=%ROOT%llama.cpp\llama-server.exe"

if not exist "%LLAMA%" goto :missing_llama
if not exist "%EMBED_MODEL%" goto :missing_model

echo.
echo   TORMENT_NEXUS_HAZARD
echo   machinespirit: per-token trajectories, SABLE7, anchor traces.
echo   First time here? Type 'tutorial' for the hazard walkthrough.
echo   Slower on purpose. Retrieval is unchanged - trajectories shadow it.
echo.
echo   Starting unpooled embedder on port %UNPOOLED_PORT% ...

REM llama.cpp fixes pooling when the process starts, so a trajectory
REM cannot come from the ordinary pooled embedder. This is a second
REM instance of the same small model, which is cheap beside the director.
start "machinespirit-embedder" /min "%LLAMA%" -m "%EMBED_MODEL%" ^
    --embedding --pooling none --alias machinespirit ^
    -c 512 -ub 512 --host 127.0.0.1 --port %UNPOOLED_PORT% ^
    -ngl 0 -t 2 --api-key machinespirit

set "TORMENT_NEXUS_EXPERIMENTAL=1"
set "TORMENT_NEXUS_MACHINESPIRIT_URL=http://127.0.0.1:%UNPOOLED_PORT%"
set "TORMENT_NEXUS_MACHINESPIRIT_KEY=machinespirit"

call "%ROOT%start_assistant.bat"

echo.
echo   Stopping the unpooled embedder ...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*--alias machinespirit*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
goto :eof

:missing_llama
echo.
echo   llama-server.exe was not found. Hazard mode needs it to run the
echo   unpooled embedder that machinespirit reads trajectories from.
echo   The ordinary launcher, start_assistant.bat, does not need it.
echo.
pause
goto :eof

:missing_model
echo.
echo   The embedding model was not found at:
echo     %EMBED_MODEL%
echo   Hazard mode needs it for machinespirit trajectories.
echo.
pause
goto :eof
