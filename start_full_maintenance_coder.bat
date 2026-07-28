@echo off
setlocal
set "ROOT=%~dp0"
set "CUDA_SERVER=%ROOT%llama.cpp\runtime\desktop-cuda-12.4-b9637\llama-server.exe"

if defined TORMENT_NEXUS_FULL_MAINTENANCE_MODEL_PATH goto maintenance_model_ready
set "TORMENT_NEXUS_FULL_MAINTENANCE_MODEL_PATH=%ROOT%models\Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf"

:maintenance_model_ready
if not exist "%CUDA_SERVER%" goto missing_runtime
if not exist "%TORMENT_NEXUS_FULL_MAINTENANCE_MODEL_PATH%" goto missing_model

echo.
echo ================================================================
echo HIGH-RISK ADVANCED MODE - FULL MAINTENANCE
echo ================================================================
echo This launches Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M in
echo the full-maintenance role. It is an optional experimental model,
echo distributed as a separate add-on rather than used for ordinary chat.
echo.
echo "Abliterated" means refusal behaviour may be weakened. The model may
echo produce unsafe or confidently wrong plans. Full maintenance can apply
echo multiple source changes during a test-driven repair session.
echo Guardrails, backups, validation, and rollback reduce risk but are not
echo a security sandbox and cannot guarantee a safe result.
echo.
echo Close every other project editor. Keep a separate backup. Do not run
echo as Administrator. Remove credentials and irreplaceable files from the
echo project. Review the plan, final diff, rollback status, and complete
echo regression report before trusting any result.
echo.
set "LAUNCH_CONFIRMATION="
set /p "LAUNCH_CONFIRMATION=Type START FULL MAINTENANCE to continue: "
if /i not "%LAUNCH_CONFIRMATION%"=="START FULL MAINTENANCE" goto launch_cancelled

set "TORMENT_NEXUS_LLAMA_SERVER=%CUDA_SERVER%"
set "TORMENT_NEXUS_MODEL_PATH=%TORMENT_NEXUS_FULL_MAINTENANCE_MODEL_PATH%"
set "TORMENT_NEXUS_MODEL_DISPLAY_NAME=Qwen2.5-Coder-14B-Abliterated-Q4_K_M / FULL MAINTENANCE"
set "TORMENT_NEXUS_MODEL_ROLE=full-maintenance"
set "TORMENT_NEXUS_LLAMA_GPU_LAYERS=20"
set "TORMENT_NEXUS_CONTEXT_SIZE=4096"
set "TORMENT_NEXUS_LLAMA_FLASH_ATTN=on"
set "TORMENT_NEXUS_LLAMA_CACHE_TYPE_K=q8_0"
set "TORMENT_NEXUS_LLAMA_CACHE_TYPE_V=q8_0"
set "TORMENT_NEXUS_SERVER_ALIAS=full-maintenance-coder"
set "TORMENT_NEXUS_PROMPT_CACHE_DIR=%ROOT%assistant\cache\prompt-full-maintenance"
set "TORMENT_NEXUS_AUTONOMOUS_ON_STARTUP=0"

call "%ROOT%start_assistant.bat"
endlocal
exit /b

:launch_cancelled
echo.
echo Full-maintenance launch cancelled. No model was started.
endlocal
exit /b 2

:missing_runtime
echo The desktop CUDA runtime is missing:
echo %CUDA_SERVER%
echo Reinstall the isolated llama.cpp CUDA runtime before using this launcher.
pause
exit /b 1

:missing_model
echo The 14B full-maintenance GGUF is missing:
echo %TORMENT_NEXUS_FULL_MAINTENANCE_MODEL_PATH%
echo Set TORMENT_NEXUS_FULL_MAINTENANCE_MODEL_PATH if you store it elsewhere.
pause
exit /b 1
