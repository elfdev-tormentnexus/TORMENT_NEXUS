@echo off
setlocal
set "ROOT=%~dp0"
set "CUDA_SERVER=%ROOT%llama.cpp\runtime\desktop-cuda-12.4-b9637\llama-server.exe"
set "MODEL=%ROOT%models\Qwen3-4B-Instruct-2507-Q5_K_M.gguf"

if not exist "%CUDA_SERVER%" goto missing_runtime
if not exist "%MODEL%" goto missing_model

set "TORMENT_NEXUS_LLAMA_SERVER=%CUDA_SERVER%"
set "TORMENT_NEXUS_MODEL_PATH=%MODEL%"
set "TORMENT_NEXUS_MODEL_DISPLAY_NAME=Qwen3-4B-I-2507-Abliterated-Q5_K_M / CUDA"
set "TORMENT_NEXUS_MODEL_ROLE=director"
set "TORMENT_NEXUS_LLAMA_GPU_LAYERS=99"
set "TORMENT_NEXUS_CONTEXT_SIZE=8192"
set "TORMENT_NEXUS_SERVER_ALIAS=desktop-companion"
set "TORMENT_NEXUS_PROMPT_CACHE_DIR=%ROOT%assistant\cache\prompt-desktop"

call "%ROOT%start_assistant.bat"
endlocal
exit /b

:missing_runtime
echo The desktop CUDA runtime is missing:
echo %CUDA_SERVER%
echo Reinstall the isolated llama.cpp CUDA runtime before using this launcher.
pause
exit /b 1

:missing_model
echo The companion GGUF is missing:
echo %MODEL%
pause
exit /b 1
