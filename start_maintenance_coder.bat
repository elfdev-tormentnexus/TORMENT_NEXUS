@echo off
setlocal
set "ROOT=%~dp0"
set "CUDA_SERVER=%ROOT%llama.cpp\runtime\desktop-cuda-12.4-b9637\llama-server.exe"
set "CPU_SERVER=%ROOT%llama.cpp\build\bin\Release\llama-server.exe"

if defined TORMENT_NEXUS_CODER_MODEL_PATH goto coder_model_ready
set "TORMENT_NEXUS_CODER_MODEL_PATH=%ROOT%models\Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf"

:coder_model_ready
if exist "%CUDA_SERVER%" (
    set "LLAMA_SERVER=%CUDA_SERVER%"
    set "GPU_LAYERS=16"
) else if exist "%CPU_SERVER%" (
    set "LLAMA_SERVER=%CPU_SERVER%"
    set "GPU_LAYERS=0"
) else (
    goto missing_runtime
)
if not exist "%TORMENT_NEXUS_CODER_MODEL_PATH%" goto missing_model

set "TORMENT_NEXUS_LLAMA_SERVER=%LLAMA_SERVER%"
set "TORMENT_NEXUS_MODEL_PATH=%TORMENT_NEXUS_CODER_MODEL_PATH%"
set "TORMENT_NEXUS_MODEL_DISPLAY_NAME=Qwen2.5-Coder-7B-Abliterated-Q8_0 / AUTONOMOUS"
set "TORMENT_NEXUS_MODEL_ROLE=autonomous-coder"
set "TORMENT_NEXUS_LLAMA_GPU_LAYERS=%GPU_LAYERS%"
set "TORMENT_NEXUS_CONTEXT_SIZE=4096"
set "TORMENT_NEXUS_LLAMA_FLASH_ATTN=on"
set "TORMENT_NEXUS_LLAMA_CACHE_TYPE_K=q8_0"
set "TORMENT_NEXUS_LLAMA_CACHE_TYPE_V=q8_0"
set "TORMENT_NEXUS_SERVER_ALIAS=maintenance-coder"
set "TORMENT_NEXUS_PROMPT_CACHE_DIR=%ROOT%assistant\cache\prompt-maintenance"
if not defined TORMENT_NEXUS_AUTONOMOUS_ON_STARTUP set "TORMENT_NEXUS_AUTONOMOUS_ON_STARTUP=0"

if "%GPU_LAYERS%"=="0" (
    echo CUDA runtime not found. Starting the bundled 7B coder on CPU; this will be slower.
)

call "%ROOT%start_assistant.bat"
endlocal
exit /b

:missing_runtime
echo No compatible llama-server runtime was found. Checked:
echo %CUDA_SERVER%
echo %CPU_SERVER%
pause
exit /b 1

:missing_model
echo The abliterated Qwen2.5-Coder GGUF is missing:
echo %TORMENT_NEXUS_CODER_MODEL_PATH%
echo Set TORMENT_NEXUS_CODER_MODEL_PATH if you moved it somewhere else.
pause
exit /b 1
