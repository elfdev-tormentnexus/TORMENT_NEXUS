@echo off
setlocal
set "ROOT=%~dp0"
set "CUDA_SERVER=%ROOT%llama.cpp\runtime\desktop-cuda-12.4-b9637\llama-server.exe"
set "MODEL=%ROOT%models\Qwen3-4B-abliterated-bf16_q8_0.gguf"

if not exist "%CUDA_SERVER%" goto missing_runtime
if not exist "%MODEL%" goto missing_model

rem Experimental desktop comparison profile. The original Q5 launcher remains
rem the Pi-safe default; this script is deliberately a separate opt-in path.
set "TORMENT_NEXUS_LLAMA_SERVER=%CUDA_SERVER%"
set "TORMENT_NEXUS_MODEL_PATH=%MODEL%"
set "TORMENT_NEXUS_MODEL_DISPLAY_NAME=Qwen3-4B-Abliterated-Q8_0 / CUDA"
set "TORMENT_NEXUS_MODEL_ROLE=director"
set "TORMENT_NEXUS_LLAMA_GPU_LAYERS=99"
set "TORMENT_NEXUS_CONTEXT_SIZE=8192"
set "TORMENT_NEXUS_SERVER_ALIAS=desktop-companion-q8"
set "TORMENT_NEXUS_PROMPT_CACHE_DIR=%ROOT%assistant\cache\prompt-desktop-q8"

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
echo The experimental Q8 companion GGUF is missing:
echo %MODEL%
pause
exit /b 1
