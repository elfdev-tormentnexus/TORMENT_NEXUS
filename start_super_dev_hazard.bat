@echo off
setlocal
title TORMENT_NEXUS_HAZARD - SUPER DEV

REM ----------------------------------------------------------------
REM SUPER DEV HAZARD
REM
REM This is an intentionally narrow two-model development harness, not a
REM general "do anything" switch.  The foreground 14B model plans one small
REM allowlisted improvement; the local 7B worker drafts its exact patch.  The
REM Python edit guard owns every actual permission, backup, test, rollback,
REM and Git boundary.  Nothing is pushed automatically.
REM ----------------------------------------------------------------

set "ROOT=%~dp0"
set "CUDA_SERVER=%ROOT%llama.cpp\runtime\desktop-cuda-12.4-b9637\llama-server.exe"
set "CPU_SERVER=%ROOT%llama.cpp\build\bin\Release\llama-server.exe"
set "PLANNER_MODEL=%ROOT%models\Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf"
set "WORKER_MODEL=%ROOT%models\Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf"
set "WORKER_PORT=8093"

if exist "%CUDA_SERVER%" (
    set "LLAMA_SERVER=%CUDA_SERVER%"
    set "PLANNER_GPU_LAYERS=20"
    set "WORKER_GPU_LAYERS=16"
) else if exist "%CPU_SERVER%" (
    set "LLAMA_SERVER=%CPU_SERVER%"
    set "PLANNER_GPU_LAYERS=0"
    set "WORKER_GPU_LAYERS=0"
) else (
    goto missing_runtime
)
if not exist "%PLANNER_MODEL%" goto missing_planner
if not exist "%WORKER_MODEL%" goto missing_worker

echo.
echo ================================================================
echo HAZARD - SUPER DEV (two local coder models)
echo ================================================================
echo 14B plans one grounded, small repair.  7B drafts the exact patch.
echo Trusted guards enforce the allowlist, syntax, capability rules,
echo backups, a fixed regression gate, and rollback.
echo.
echo This does NOT grant shell, network, credential, model-weight, Git,
echo or unrestricted file authority. It never pushes a change to GitHub.
echo The numeric Super Dev key is created or checked inside the app and
echo stored only as a salted local verifier.
echo.
echo Keep a separate backup, close other project editors, and do not run
echo this launcher as Administrator. Both coding models are abliterated and
echo can be confidently wrong; a green test suite is evidence, not proof.
echo.
set "LAUNCH_CONFIRMATION="
set /p "LAUNCH_CONFIRMATION=Type START SUPER DEV HAZARD to continue: "
if /i not "%LAUNCH_CONFIRMATION%"=="START SUPER DEV HAZARD" goto cancelled

for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"`) do set "WORKER_KEY=%%K"
if not defined WORKER_KEY goto key_failure

if not exist "%ROOT%assistant\logs" mkdir "%ROOT%assistant\logs"
echo Starting isolated 7B patch worker on port %WORKER_PORT% ...
start "" /b "%LLAMA_SERVER%" -m "%WORKER_MODEL%" ^
    --alias super-dev-worker -c 4096 -ub 512 --host 127.0.0.1 --port %WORKER_PORT% ^
    -ngl %WORKER_GPU_LAYERS% -t 4 --api-key "%WORKER_KEY%" ^
    > "%ROOT%assistant\logs\super_dev_worker.log" 2>&1

set "TORMENT_NEXUS_MODEL_PATH=%PLANNER_MODEL%"
set "TORMENT_NEXUS_MODEL_DISPLAY_NAME=Qwen2.5-Coder-14B-Abliterated-Q4_K_M / SUPER DEV"
set "TORMENT_NEXUS_MODEL_ROLE=super-dev"
set "TORMENT_NEXUS_LLAMA_SERVER=%LLAMA_SERVER%"
set "TORMENT_NEXUS_LLAMA_GPU_LAYERS=%PLANNER_GPU_LAYERS%"
set "TORMENT_NEXUS_CONTEXT_SIZE=4096"
set "TORMENT_NEXUS_LLAMA_FLASH_ATTN=on"
set "TORMENT_NEXUS_LLAMA_CACHE_TYPE_K=q8_0"
set "TORMENT_NEXUS_LLAMA_CACHE_TYPE_V=q8_0"
set "TORMENT_NEXUS_SERVER_ALIAS=super-dev-planner"
set "TORMENT_NEXUS_PROMPT_CACHE_DIR=%ROOT%assistant\cache\prompt-super-dev"
set "TORMENT_NEXUS_SUPER_DEV_WORKER_URL=http://127.0.0.1:%WORKER_PORT%"
set "TORMENT_NEXUS_SUPER_DEV_WORKER_KEY=%WORKER_KEY%"

call "%ROOT%start_assistant_hazard.bat"

echo.
echo Stopping isolated Super Dev 7B worker ...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*--alias super-dev-worker*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
endlocal
exit /b

:cancelled
echo.
echo Super Dev hazard launch cancelled. No model was started.
endlocal
exit /b 2

:key_failure
echo.
echo Could not create the temporary worker credential. No model was started.
endlocal
exit /b 1

:missing_runtime
echo No compatible llama-server runtime was found. Checked:
echo %CUDA_SERVER%
echo %CPU_SERVER%
pause
endlocal
exit /b 1

:missing_planner
echo The 14B planner GGUF is missing:
echo %PLANNER_MODEL%
pause
endlocal
exit /b 1

:missing_worker
echo The 7B patch-worker GGUF is missing:
echo %WORKER_MODEL%
pause
endlocal
exit /b 1
