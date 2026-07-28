@echo off
setlocal
set "ROOT=%~dp0"
set "CUDA_SERVER=%ROOT%llama.cpp\runtime\desktop-cuda-12.4-b9637\llama-server.exe"

if defined TORMENT_NEXUS_CODER_MODEL_PATH goto coder_model_ready
set "TORMENT_NEXUS_CODER_MODEL_PATH=%ROOT%models\Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf"

:coder_model_ready
if not exist "%CUDA_SERVER%" goto missing_runtime
if not exist "%TORMENT_NEXUS_CODER_MODEL_PATH%" goto missing_model

set "TORMENT_NEXUS_LLAMA_SERVER=%CUDA_SERVER%"
set "TORMENT_NEXUS_MODEL_PATH=%TORMENT_NEXUS_CODER_MODEL_PATH%"
set "TORMENT_NEXUS_MODEL_DISPLAY_NAME=Qwen2.5-Coder-7B-Abliterated-Q8_0 / AUTONOMOUS"
set "TORMENT_NEXUS_MODEL_ROLE=autonomous-coder"
set "TORMENT_NEXUS_LLAMA_GPU_LAYERS=16"
set "TORMENT_NEXUS_CONTEXT_SIZE=4096"
set "TORMENT_NEXUS_LLAMA_FLASH_ATTN=on"
set "TORMENT_NEXUS_LLAMA_CACHE_TYPE_K=q8_0"
set "TORMENT_NEXUS_LLAMA_CACHE_TYPE_V=q8_0"
set "TORMENT_NEXUS_SERVER_ALIAS=maintenance-coder"
set "TORMENT_NEXUS_PROMPT_CACHE_DIR=%ROOT%assistant\cache\prompt-maintenance"
if not defined TORMENT_NEXUS_AUTONOMOUS_ON_STARTUP set "TORMENT_NEXUS_AUTONOMOUS_ON_STARTUP=0"

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
echo The abliterated Qwen2.5-Coder GGUF is missing:
echo %TORMENT_NEXUS_CODER_MODEL_PATH%
echo Set TORMENT_NEXUS_CODER_MODEL_PATH if you moved it somewhere else.
pause
exit /b 1
