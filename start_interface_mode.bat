@echo off
setlocal
set "ROOT=%~dp0"

rem INTERLINKED is the normal assistant with the read-only agent API on.
rem It exists as its own launcher because that API is a listening socket and
rem an authentication boundary: which windows have it open should be a thing
rem the operator can see, not a thing they have to remember. The window
rem title and the inverted shortcut icon both say so.

set "TORMENT_NEXUS_AGENT_API=1"
title TORMENT_NEXUS_INTERLINKED (read-only agent interface open)

echo ==========================================================
echo  TORMENT_NEXUS_INTERLINKED
echo ==========================================================
echo  The read-only agent interface will listen on loopback.
echo  A connected agent can read state, search memory and the
echo  knowledge library, and ask the director questions.
echo.
echo  Nothing on that interface writes, edits, or restarts.
echo  The bearer token is written to:
echo    assistant\.agent_token
echo.
echo  First time here? Type 'tutorial' for the interlinked
echo  walkthrough. Close this window to close the interface.
echo ==========================================================
echo.

rem Prefer the desktop CUDA director, which is what this machine runs, but
rem fall back rather than refusing to start: interface mode is useful on a
rem plain CPU install too, and a missing CUDA runtime is not a reason to
rem deny the operator the diagnostic surface.
set "CUDA_SERVER=%ROOT%llama.cpp\runtime\desktop-cuda-12.4-b9637\llama-server.exe"

if exist "%CUDA_SERVER%" (
    call "%ROOT%start_desktop_cuda.bat"
) else (
    echo Desktop CUDA runtime not found; starting the portable CPU profile.
    echo.
    call "%ROOT%start_assistant.bat"
)

endlocal
exit /b
