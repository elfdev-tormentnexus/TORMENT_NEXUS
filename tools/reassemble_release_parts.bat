@echo off
setlocal
set "HERE=%~dp0"
set "PART1=%HERE%TORMENT_NEXUS.zip.part01"
set "PART2=%HERE%TORMENT_NEXUS.zip.part02"
set "ZIP=%HERE%TORMENT_NEXUS.zip"

REM The closing quote matters. Without it the variable expands and the
REM opening "(" is swallowed into the quoted filename, so cmd loses the
REM start of the block and the script fails in a way that points nowhere
REM near the actual line.
if not exist "%PART1%" (
    echo Missing TORMENT_NEXUS.zip.part01 in this folder.
    pause
    exit /b 1
)

if not exist "%PART2%" (
    echo Missing TORMENT_NEXUS.zip.part02 in this folder.
    pause
    exit /b 1
)

echo Reassembling the complete beta package...
copy /b "%PART1%"+"%PART2%" "%ZIP%" >nul
if errorlevel 1 (
    echo Could not create TORMENT_NEXUS.zip.
    pause
    exit /b 1
)

echo.
echo Complete: %ZIP%
echo Verify the SHA-256 shown in the GitHub Release notes, then extract the ZIP and run setup.bat.
pause
