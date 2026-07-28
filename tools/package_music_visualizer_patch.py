"""Build the additive music-visualizer repair assets for Beta 3.

The large Beta 3 archives remain immutable.  This builder creates:

* a small patch ZIP for an existing extracted/installed copy; and
* a one-click helper for new users who downloaded the two original ZIP parts.

The patcher refuses unknown file versions, backs up everything it replaces,
updates RELEASE_MANIFEST.json, verifies the copy, and can restore the backup.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
STAGED_BETA = DIST / "TORMENT_NEXUS"

BASE_TAG = "v0.1.0-beta.3"
BASE_COMMIT = "d18386eef643d000ad413dc901b49a918cb5d346"
BASE_ARCHIVE_SHA256 = (
    "AA6C748831331528C01E94F1E06A4288D1FC40C66D51FBC240EEE3609BB7ED00"
)
PATCH_ID = "music-visualizer-patch.1"
PATCH_ARCHIVE = DIST / (
    "TORMENT_NEXUS_v0.1.0-beta.3_MUSIC_VISUALIZER_PATCH.zip"
)
INSTALL_HELPER = DIST / "INSTALL_TORMENT_NEXUS_BETA3_WITH_MUSIC_PATCH.bat"

# Hashes from the published Beta 3 package, not from a mutable checkout.
# A missing baseline means the file is intentionally new in this patch.
PATCH_FILES = {
    "assistant/commands/command_handlers.py":
        "ED408C0EE58EE1997D0683D859DF9CB269542571160DC760E21E2603B37E9837",
    "assistant/core/tutorial.py":
        "30C15129D73651C034EC60159E941096643DD273CBF5FF2310189814650E7AF2",
    "assistant/tests/test_regressions.py":
        "4A14EB3D0C4E91BB8207E4A9E364CA56D36D80730D157A36EBA1F4DEA3DC6E67",
    "assistant/ui/ui.py":
        "DA1A8D8ADAB7642338CF59BD345A0CC6D12BC78F0F2B0674EB5156E5AE54D42A",
    "assistant/visualizer/audio_source.py":
        "3D3EA76CDC8D821D335433CCF91247053126C5B62300D125024F73AFE35EADC6",
    "assistant/visualizer/reactivity.py": None,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def checked_payload() -> tuple[dict, dict[str, bytes]]:
    entries = []
    payload = {}

    for rel, baseline_hash in PATCH_FILES.items():
        source = ROOT / Path(rel)
        if not source.is_file():
            raise FileNotFoundError(f"patch source is missing: {rel}")

        data = source.read_bytes()
        payload[rel] = data
        entries.append({
            "path": rel,
            "baseline_sha256": baseline_hash,
            "patch_sha256": sha256(data),
            "bytes": len(data),
        })

        staged = STAGED_BETA / Path(rel)
        if baseline_hash is None:
            if staged.exists():
                raise RuntimeError(
                    f"new patch file unexpectedly exists in Beta 3 stage: {rel}"
                )
        elif not staged.is_file():
            raise FileNotFoundError(f"Beta 3 baseline is missing: {rel}")
        else:
            actual = sha256(staged.read_bytes())
            if actual != baseline_hash:
                raise RuntimeError(
                    f"Beta 3 baseline changed for {rel}\n"
                    f"expected {baseline_hash}\nactual   {actual}"
                )

    manifest = {
        "format": 1,
        "patch_id": PATCH_ID,
        "base_release": BASE_TAG,
        "base_commit": BASE_COMMIT,
        "base_archive_sha256": BASE_ARCHIVE_SHA256,
        "patch_source_commit": git_commit(),
        "files": entries,
    }
    return manifest, payload


PATCH_README = r"""TORMENT_NEXUS BETA 3 - MUSIC VISUALIZER REPAIR
=================================================

WHAT THIS FIXES
    - Local songs now open the music visualizer automatically.
    - The terminal no longer leaks a code/log stream across the bottom.
    - The screen no longer jitters when Windows reaches the bottom-right cell.
    - Every visualizer scene reacts more dramatically to the music.
    - Music mode starts faster.

FOR AN EXISTING BETA 3 INSTALL
    1. Close TORMENT_NEXUS.
    2. Extract this patch ZIP.
    3. Double-click APPLY_MUSIC_VISUALIZER_PATCH.bat.
    4. If asked, choose the folder containing start_assistant.bat.
    5. Launch TORMENT_NEXUS normally.

    Try: play <part of a local song name>

    The visualizer should open by itself. Space plays the next local track.

SAFETY
    This patch only accepts the original Beta 3 files or files already patched
    by this exact repair. It stops before changing anything if it finds an
    unfamiliar version. Original files are copied into a timestamped folder
    under backups before replacement.

UNDOING THE PATCH
    Open the newest backups\music_visualizer_patch_beta3_* folder inside your
    TORMENT_NEXUS folder and double-click RESTORE_ORIGINAL_FILES.bat.

NEW INSTALLS
    The GitHub release also includes:

        INSTALL_TORMENT_NEXUS_BETA3_WITH_MUSIC_PATCH.bat

    Put that helper beside the two original ZIP parts and this patch ZIP, then
    double-click it. It verifies the original archive, extracts it, applies
    this repair, and launches the normal offline setup.
"""


APPLY_BAT = r"""@echo off
setlocal
title TORMENT_NEXUS Beta 3 Music Visualizer Repair
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply_music_visualizer_patch.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
    echo You can close this window.
) else (
    echo Nothing unsafe was installed. Read the message above for details.
)
pause
exit /b %RESULT%
"""


RESTORE_BAT = r"""@echo off
setlocal
title Restore TORMENT_NEXUS Beta 3 Music Visualizer Files
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore_original_files.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
"""


RESTORE_PS1 = r"""$ErrorActionPreference = "Stop"
$BackupRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackupManifestPath = Join-Path $BackupRoot "backup_manifest.json"

try {
    if (-not (Test-Path -LiteralPath $BackupManifestPath -PathType Leaf)) {
        throw "backup_manifest.json is missing."
    }

    $BackupManifest = Get-Content -LiteralPath $BackupManifestPath -Raw |
        ConvertFrom-Json
    $Target = [IO.Path]::GetFullPath([string]$BackupManifest.target)
    if (-not (Test-Path -LiteralPath (Join-Path $Target "start_assistant.bat"))) {
        throw "The original TORMENT_NEXUS folder is no longer at: $Target"
    }

    Write-Host ""
    Write-Host "Restoring the original Beta 3 visualizer files..."

    foreach ($Relative in $BackupManifest.replaced_files) {
        $Native = ([string]$Relative).Replace("/", [IO.Path]::DirectorySeparatorChar)
        $Saved = Join-Path (Join-Path $BackupRoot "original") $Native
        $Destination = Join-Path $Target $Native
        if (-not (Test-Path -LiteralPath $Saved -PathType Leaf)) {
            throw "A required backup file is missing: $Relative"
        }
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) |
            Out-Null
        Copy-Item -LiteralPath $Saved -Destination $Destination -Force
    }

    foreach ($Relative in $BackupManifest.created_files) {
        $Native = ([string]$Relative).Replace("/", [IO.Path]::DirectorySeparatorChar)
        $Destination = Join-Path $Target $Native
        if (Test-Path -LiteralPath $Destination -PathType Leaf) {
            Remove-Item -LiteralPath $Destination -Force
        }
    }

    $SavedReleaseManifest = Join-Path $BackupRoot "RELEASE_MANIFEST.json"
    if (Test-Path -LiteralPath $SavedReleaseManifest -PathType Leaf) {
        Copy-Item -LiteralPath $SavedReleaseManifest `
            -Destination (Join-Path $Target "RELEASE_MANIFEST.json") -Force
    }

    $Marker = Join-Path $Target "MUSIC_VISUALIZER_PATCH_v0.1.0-beta.3.txt"
    if (Test-Path -LiteralPath $Marker -PathType Leaf) {
        Remove-Item -LiteralPath $Marker -Force
    }

    Write-Host ""
    Write-Host "RESTORED. TORMENT_NEXUS is back to its original Beta 3 files."
    exit 0
} catch {
    Write-Host ""
    Write-Host ("RESTORE STOPPED: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host "No backup files were deleted."
    exit 1
}
"""


APPLY_PS1 = r"""param(
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"
$PatchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadRoot = Join-Path $PatchRoot "payload"
$ManifestPath = Join-Path $PatchRoot "PATCH_MANIFEST.json"

function Stop-Patch([string]$Message) {
    Write-Host ""
    Write-Host ("PATCH STOPPED: " + $Message) -ForegroundColor Red
    Write-Host "No unfamiliar file was overwritten."
    exit 1
}

function Is-TormentNexusFolder([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    return (
        (Test-Path -LiteralPath (Join-Path $Path "start_assistant.bat") -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $Path "assistant\main.py") -PathType Leaf)
    )
}

function Find-Target([string]$Requested) {
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $Resolved = [IO.Path]::GetFullPath($Requested.Trim().Trim('"'))
        if (Is-TormentNexusFolder $Resolved) { return $Resolved }
        throw "That folder is not TORMENT_NEXUS: $Resolved"
    }

    $Candidates = New-Object System.Collections.Generic.List[string]
    $Candidates.Add((Get-Location).Path)
    $Candidates.Add($PatchRoot)
    $Candidates.Add((Split-Path $PatchRoot -Parent))

    try {
        $Desktop = [Environment]::GetFolderPath("Desktop")
        $Shortcut = Join-Path $Desktop "TORMENT_NEXUS.lnk"
        if (Test-Path -LiteralPath $Shortcut -PathType Leaf) {
            $Shell = New-Object -ComObject WScript.Shell
            $Link = $Shell.CreateShortcut($Shortcut)
            if ($Link.WorkingDirectory) { $Candidates.Add($Link.WorkingDirectory) }
        }
    } catch {
        # Folder selection below remains available if shortcut inspection fails.
    }

    foreach ($Candidate in $Candidates) {
        try {
            $Resolved = [IO.Path]::GetFullPath($Candidate)
            if (Is-TormentNexusFolder $Resolved) { return $Resolved }
        } catch {
            # Continue through the other safe candidates.
        }
    }

    Add-Type -AssemblyName System.Windows.Forms
    $Picker = New-Object System.Windows.Forms.FolderBrowserDialog
    $Picker.Description = "Choose the TORMENT_NEXUS folder containing start_assistant.bat"
    $Picker.ShowNewFolderButton = $false
    if ($Picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        throw "No folder was chosen."
    }
    $Resolved = [IO.Path]::GetFullPath($Picker.SelectedPath)
    if (-not (Is-TormentNexusFolder $Resolved)) {
        throw "That folder does not contain start_assistant.bat and assistant\main.py."
    }
    return $Resolved
}

function Relative-Native([string]$Relative) {
    return $Relative.Replace("/", [IO.Path]::DirectorySeparatorChar)
}

function File-Hash([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

try {
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "PATCH_MANIFEST.json is missing. Extract the complete patch ZIP first."
    }
    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($Manifest.patch_id -ne "music-visualizer-patch.1") {
        throw "This is not the expected music visualizer patch."
    }
    $Target = Find-Target $Target
} catch {
    Stop-Patch $_.Exception.Message
}

Write-Host ""
Write-Host "TORMENT_NEXUS Beta 3 - music visualizer repair"
Write-Host ("Install folder: " + $Target)
Write-Host ""
Write-Host "Checking the patch and the installed files..."

$NeedsCopy = New-Object System.Collections.Generic.List[object]
$Replaced = New-Object System.Collections.Generic.List[string]
$Created = New-Object System.Collections.Generic.List[string]

foreach ($Entry in $Manifest.files) {
    $Relative = [string]$Entry.path
    $Native = Relative-Native $Relative
    $Payload = Join-Path $PayloadRoot $Native
    $Destination = Join-Path $Target $Native

    if (-not (Test-Path -LiteralPath $Payload -PathType Leaf)) {
        Stop-Patch "The patch is incomplete: $Relative is missing."
    }
    if ((File-Hash $Payload) -ne ([string]$Entry.patch_sha256).ToUpperInvariant()) {
        Stop-Patch "The patch payload failed its safety check: $Relative"
    }

    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        $CurrentHash = File-Hash $Destination
        if ($CurrentHash -eq ([string]$Entry.patch_sha256).ToUpperInvariant()) {
            continue
        }
        if ($null -eq $Entry.baseline_sha256 -or
            $CurrentHash -ne ([string]$Entry.baseline_sha256).ToUpperInvariant()) {
            Stop-Patch (
                "The installed copy of $Relative is not the original Beta 3 " +
                "file. This repair will not overwrite custom or unknown work."
            )
        }
        $Replaced.Add($Relative)
    } else {
        if ($null -ne $Entry.baseline_sha256) {
            Stop-Patch "A required Beta 3 file is missing: $Relative"
        }
        $Created.Add($Relative)
    }
    $NeedsCopy.Add($Entry)
}

if ($NeedsCopy.Count -eq 0) {
    Write-Host ""
    Write-Host "ALREADY PATCHED. No files needed to change." -ForegroundColor Green
    exit 0
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $Target ("backups\music_visualizer_patch_beta3_" + $Stamp)
$OriginalRoot = Join-Path $BackupRoot "original"

try {
    New-Item -ItemType Directory -Force -Path $OriginalRoot | Out-Null

    foreach ($Relative in $Replaced) {
        $Native = Relative-Native $Relative
        $Source = Join-Path $Target $Native
        $Saved = Join-Path $OriginalRoot $Native
        New-Item -ItemType Directory -Force -Path (Split-Path $Saved -Parent) |
            Out-Null
        Copy-Item -LiteralPath $Source -Destination $Saved -Force
    }

    $ReleaseManifestPath = Join-Path $Target "RELEASE_MANIFEST.json"
    if (Test-Path -LiteralPath $ReleaseManifestPath -PathType Leaf) {
        Copy-Item -LiteralPath $ReleaseManifestPath `
            -Destination (Join-Path $BackupRoot "RELEASE_MANIFEST.json") -Force
    }

    $BackupManifest = @{
        target = $Target
        patch_id = [string]$Manifest.patch_id
        replaced_files = @($Replaced)
        created_files = @($Created)
    }
    $BackupManifest | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $BackupRoot "backup_manifest.json") `
            -Encoding UTF8
    Copy-Item -LiteralPath (Join-Path $PatchRoot "restore_original_files.ps1") `
        -Destination (Join-Path $BackupRoot "restore_original_files.ps1")
    Copy-Item -LiteralPath (Join-Path $PatchRoot "RESTORE_ORIGINAL_FILES.bat") `
        -Destination (Join-Path $BackupRoot "RESTORE_ORIGINAL_FILES.bat")

    foreach ($Entry in $NeedsCopy) {
        $Native = Relative-Native ([string]$Entry.path)
        $Payload = Join-Path $PayloadRoot $Native
        $Destination = Join-Path $Target $Native
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) |
            Out-Null
        Copy-Item -LiteralPath $Payload -Destination $Destination -Force
        if ((File-Hash $Destination) -ne
            ([string]$Entry.patch_sha256).ToUpperInvariant()) {
            throw "Verification failed after copying $($Entry.path)."
        }
    }

    if (Test-Path -LiteralPath $ReleaseManifestPath -PathType Leaf) {
        $ReleaseManifest = Get-Content -LiteralPath $ReleaseManifestPath -Raw |
            ConvertFrom-Json
        foreach ($Entry in $Manifest.files) {
            $Existing = @($ReleaseManifest.files |
                Where-Object { $_.path -eq [string]$Entry.path })
            if ($Existing.Count -gt 0) {
                $Existing[0].sha256 = ([string]$Entry.patch_sha256).ToLowerInvariant()
                $Existing[0].bytes = [long]$Entry.bytes
            } else {
                $ReleaseManifest.files += [PSCustomObject]@{
                    path = [string]$Entry.path
                    bytes = [long]$Entry.bytes
                    sha256 = ([string]$Entry.patch_sha256).ToLowerInvariant()
                }
            }
        }
        $ReleaseManifest | ConvertTo-Json -Depth 6 |
            Set-Content -LiteralPath $ReleaseManifestPath -Encoding UTF8
    }

    $Python = Join-Path $Target "python\python.exe"
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "The bundled Python is missing, so the repaired files cannot be checked."
    }
    $CompileFiles = @(
        "assistant\commands\command_handlers.py",
        "assistant\core\tutorial.py",
        "assistant\ui\ui.py",
        "assistant\visualizer\audio_source.py",
        "assistant\visualizer\reactivity.py"
    ) | ForEach-Object { Join-Path $Target $_ }
    & $Python -m py_compile @CompileFiles
    if ($LASTEXITCODE -ne 0) {
        throw "The repaired Python files did not pass their startup check."
    }

    $Marker = @(
        "TORMENT_NEXUS Beta 3 music visualizer repair",
        "Patch: $($Manifest.patch_id)",
        "Applied: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
        "Backup: $BackupRoot"
    )
    $Marker | Set-Content -LiteralPath (
        Join-Path $Target "MUSIC_VISUALIZER_PATCH_v0.1.0-beta.3.txt"
    ) -Encoding UTF8

    Write-Host ""
    Write-Host "REPAIR COMPLETE." -ForegroundColor Green
    Write-Host "Local songs now open the visualizer automatically."
    Write-Host "The visualizer output leak and bottom-edge jitter are guarded."
    Write-Host ("Original files are safe in: " + $BackupRoot)
    exit 0
} catch {
    $Reason = $_.Exception.Message
    Write-Host ""
    Write-Host "The final check failed. Restoring the original files..." `
        -ForegroundColor Yellow

    foreach ($Relative in $Replaced) {
        $Native = Relative-Native $Relative
        $Saved = Join-Path $OriginalRoot $Native
        $Destination = Join-Path $Target $Native
        if (Test-Path -LiteralPath $Saved -PathType Leaf) {
            Copy-Item -LiteralPath $Saved -Destination $Destination -Force
        }
    }
    foreach ($Relative in $Created) {
        $Destination = Join-Path $Target (Relative-Native $Relative)
        if (Test-Path -LiteralPath $Destination -PathType Leaf) {
            Remove-Item -LiteralPath $Destination -Force
        }
    }
    $SavedReleaseManifest = Join-Path $BackupRoot "RELEASE_MANIFEST.json"
    if (Test-Path -LiteralPath $SavedReleaseManifest -PathType Leaf) {
        Copy-Item -LiteralPath $SavedReleaseManifest `
            -Destination (Join-Path $Target "RELEASE_MANIFEST.json") -Force
    }
    Stop-Patch $Reason
}
"""


INSTALL_BAT = rf"""@echo off
setlocal
title Install TORMENT_NEXUS Beta 3 with Music Visualizer Repair

set "HERE=%~dp0"
set "PART1=%HERE%TORMENT_NEXUS.zip.part01"
set "PART2=%HERE%TORMENT_NEXUS.zip.part02"
set "ZIP=%HERE%TORMENT_NEXUS.zip"
set "PATCH=%HERE%{PATCH_ARCHIVE.name}"
set "DEST=%HERE%TORMENT_NEXUS_BETA3_PATCHED"
set "TARGET=%DEST%\TORMENT_NEXUS"
set "PATCH_TEMP=%DEST%\_music_visualizer_patch"

echo.
echo TORMENT_NEXUS Beta 3 - patched beginner installer
echo =================================================
echo This checks the original download, extracts it, repairs the music
echo visualizer, and then starts the normal offline setup.
echo.

if not exist "%PART1%" (
    echo Missing TORMENT_NEXUS.zip.part01 in this folder.
    goto :failed
)
if not exist "%PART2%" (
    echo Missing TORMENT_NEXUS.zip.part02 in this folder.
    goto :failed
)
if not exist "%PATCH%" (
    echo Missing {PATCH_ARCHIVE.name} in this folder.
    goto :failed
)
if exist "%DEST%" (
    echo.
    echo The destination already exists:
    echo   %DEST%
    echo.
    echo Nothing was overwritten. Rename that folder or move this installer
    echo and its downloads to a fresh folder, then try again.
    goto :failed
)

if not exist "%ZIP%" (
    echo [1/5] Rebuilding the complete original ZIP...
    copy /b "%PART1%"+"%PART2%" "%ZIP%" >nul
    if errorlevel 1 (
        echo Could not rebuild TORMENT_NEXUS.zip.
        goto :failed
    )
) else (
    echo [1/5] Using the complete ZIP already in this folder...
)

echo [2/5] Checking the original Beta 3 download...
set "TN_ZIP=%ZIP%"
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -LiteralPath $env:TN_ZIP -Algorithm SHA256).Hash"`) do set "ZIP_HASH=%%H"
if /I not "%ZIP_HASH%"=="{BASE_ARCHIVE_SHA256}" (
    echo.
    echo The ZIP checksum does not match the published Beta 3 package.
    echo Expected: {BASE_ARCHIVE_SHA256}
    echo Found:    %ZIP_HASH%
    echo Nothing was extracted or installed.
    goto :failed
)

echo [3/5] Extracting the self-contained app...
set "TN_DEST=%DEST%"
powershell -NoProfile -Command "Expand-Archive -LiteralPath $env:TN_ZIP -DestinationPath $env:TN_DEST"
if errorlevel 1 goto :failed
if not exist "%TARGET%\start_assistant.bat" (
    echo The archive did not contain the expected TORMENT_NEXUS folder.
    goto :failed
)

echo [4/5] Applying the music visualizer repair...
set "TN_PATCH=%PATCH%"
set "TN_PATCH_TEMP=%PATCH_TEMP%"
powershell -NoProfile -Command "Expand-Archive -LiteralPath $env:TN_PATCH -DestinationPath $env:TN_PATCH_TEMP"
if errorlevel 1 goto :failed
powershell -NoProfile -ExecutionPolicy Bypass -File "%PATCH_TEMP%\apply_music_visualizer_patch.ps1" -Target "%TARGET%"
if errorlevel 1 goto :failed

echo [5/5] Starting the normal offline setup...
echo.
call "%TARGET%\setup.bat"
if errorlevel 1 goto :failed

echo.
echo COMPLETE. Launch TORMENT_NEXUS from the desktop shortcut.
pause
exit /b 0

:failed
echo.
echo INSTALLER STOPPED. The message above explains what needs attention.
echo No existing TORMENT_NEXUS installation was changed.
pause
exit /b 1
"""


def zip_write(
    archive: zipfile.ZipFile,
    name: str,
    data: bytes,
) -> None:
    info = zipfile.ZipInfo(name, date_time=(2026, 7, 27, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def build() -> None:
    manifest, payload = checked_payload()
    DIST.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(PATCH_ARCHIVE, "w") as archive:
        zip_write(archive, "README.txt", PATCH_README.encode("utf-8"))
        zip_write(
            archive,
            "PATCH_MANIFEST.json",
            (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        )
        zip_write(
            archive,
            "APPLY_MUSIC_VISUALIZER_PATCH.bat",
            APPLY_BAT.replace("\n", "\r\n").encode("utf-8"),
        )
        zip_write(
            archive,
            "apply_music_visualizer_patch.ps1",
            APPLY_PS1.replace("\n", "\r\n").encode("utf-8"),
        )
        zip_write(
            archive,
            "RESTORE_ORIGINAL_FILES.bat",
            RESTORE_BAT.replace("\n", "\r\n").encode("utf-8"),
        )
        zip_write(
            archive,
            "restore_original_files.ps1",
            RESTORE_PS1.replace("\n", "\r\n").encode("utf-8"),
        )
        for rel, data in payload.items():
            zip_write(archive, f"payload/{rel}", data)

    INSTALL_HELPER.write_bytes(
        INSTALL_BAT.replace("\n", "\r\n").encode("utf-8")
    )

    print(f"Patch ZIP: {PATCH_ARCHIVE}")
    print(f"  bytes:   {PATCH_ARCHIVE.stat().st_size}")
    print(f"  SHA-256: {sha256(PATCH_ARCHIVE.read_bytes())}")
    print(f"Installer: {INSTALL_HELPER}")
    print(f"  bytes:   {INSTALL_HELPER.stat().st_size}")
    print(f"  SHA-256: {sha256(INSTALL_HELPER.read_bytes())}")


if __name__ == "__main__":
    build()
