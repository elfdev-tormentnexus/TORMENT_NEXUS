"""
Build a self-contained, fully offline copy of the assistant to hand to
someone else.

The output folder installs with one run of setup.bat and touches nothing
on the target machine: no system Python, no PATH, no registry. Everything
-- interpreter, wheels, model weights, llama.cpp binaries -- travels in
the package, because the whole point of this project is that it works with
no network.

Three things drive the design:

Bundled interpreter. This project runs on Python 3.14, which almost nobody
has yet, and offline wheels are built for one exact version. Rather than
demand the recipient install a specific Python, the package carries the
embeddable distribution matching the wheels.

Privacy by default. The source tree contains real conversation history,
extracted memories, and a generated API key. Those are excluded by an
explicit denylist, and `--verify` re-scans the finished package for them
rather than trusting that the copy did the right thing.

Nothing is guessed about what to include. Anything not named is left out,
so a new stray folder cannot silently end up in a package sent to someone
else.

    python package_release.py                 build into dist/
    python package_release.py --archive       ... and zip it
    python package_release.py --verify-only   re-check an existing build
    python package_release.py --skip-download reuse cached wheels/python
"""

import argparse
import fnmatch
import hashlib
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone

# Files that could not be copied because something held them open. The
# usual cause is a process still running out of dist/ -- the glitch
# animator started with the packaged interpreter will do it.
LOCKED = []

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
PACKAGE_NAME = "TORMENT_NEXUS"
STAGE = os.path.join(DIST, PACKAGE_NAME)
CACHE = os.path.join(DIST, ".cache")
MANIFEST_NAME = "RELEASE_MANIFEST.json"

PYTHON_VERSION = "3.14.6"
EMBED_URL = (f"https://www.python.org/ftp/python/{PYTHON_VERSION}"
             f"/python-{PYTHON_VERSION}-embed-amd64.zip")
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Only these are copied. Everything else is left behind on purpose.
INCLUDE_DIRS = [
    ("assistant", "assistant"),
    ("icon_anim", "icon_anim"),
    ("llama.cpp/build/bin/Release", "llama.cpp/build/bin/Release"),
    ("models/voice/piper", "models/voice/piper"),
    ("models/voice/sherpa-onnx-moonshine-tiny-en-int8",
     "models/voice/sherpa-onnx-moonshine-tiny-en-int8"),
]

INCLUDE_FILES = [
    # The project's own documentation, not just the installer's README.
    # A package built for someone to review is missing its most useful
    # file if the front door is left behind.
    "README.md",
    "README_DIGITALBIOHAZARD.txt",
    "RELEASE_HANDOFF.md",
    "BENCHMARKS.md",
    "requirements.txt",
    "requirements-voice.txt",
    "requirements-hardware.txt",
    "requirements-release-windows.txt",
    "start_assistant.bat",
    "test_assistant.bat",
    "glitch_icon.py",
    "start_glitch.bat",
    "stop_glitch.bat",
    "assistant_icon.ico",
    "assistant_icon_animated.gif",
    "models/Qwen3-4B-Instruct-2507-Q5_K_M.gguf",
    "models/voice/silero_vad.onnx",
]

# Never ship these. Checked again by --verify against the built package.
#
# The music library is excluded for a different reason than the rest: it
# is not private, it is someone else's copyright. Redistributing a music
# mix inside a package handed around to friends is the sender's call to
# make deliberately, not something a build script should do quietly. The
# folder still ships (empty) so the feature works on arrival.
DENY_PATTERNS = [
    "*/memory/conversation_history.txt*",
    "*/memory/memories.json*",
    "*/memory/plan_*.txt",
    "*/memory/change_plans/*",
    "*/backups/*",
    "*/assistant/music/*",
    "*.model_api_key",
    ".model_api_key",
    "*.dev_passcode",
    ".dev_passcode",
    "*.tdeck_ble_pin",
    ".tdeck_ble_pin",
    "*.spotify_token",
    ".spotify_token",
    "*.tutorial_state.json",
    "*/logs/*",
    "*/cache/prompt/*",
    "*__pycache__*",
    "*.pyc",
    "*.pyo",
    "*.bak",
    "*.backup",
    "*/.claude/*",
    "*.env",
    "*secrets*",
]

# These files are never valid in a handoff, regardless of where a future
# feature writes them. Keeping the basename list beside the deny patterns
# gives verify() a second independent check instead of trusting copy_tree().
PRIVATE_RUNTIME_BASENAMES = {
    ".model_api_key",
    ".dev_passcode",
    ".tdeck_ble_pin",
    ".spotify_token",
    ".tutorial_state.json",
    "conversation_history.txt",
    "memories.json",
}

# Unused alternate voices. The tuned pipeline only uses hfc_female, and
# these are 200MB of dead weight in an already large package.
SKIP_NAMES = [
    "en_GB-vctk-medium.onnx",
    "en_GB-vctk-medium.onnx.json",
    "en_US-lessac-medium.onnx",
    "en_US-lessac-medium.onnx.json",
    "en_US-libritts_r-medium.onnx",
    "en_US-libritts_r-medium.onnx.json",
]


def denied(relpath):
    posix = relpath.replace("\\", "/")
    return any(
        fnmatch.fnmatch(posix, pattern) or fnmatch.fnmatch(
            "/" + posix, pattern)
        for pattern in DENY_PATTERNS
    )


def copy_tree(src, dst, report):
    if not os.path.isdir(src):
        report.append(f"  MISSING dir  {src}")
        return 0, 0

    copied = skipped = 0

    for folder, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, ROOT)

            if denied(rel) or name in SKIP_NAMES:
                skipped += 1
                continue

            target = os.path.join(dst, os.path.relpath(full, src))
            os.makedirs(os.path.dirname(target), exist_ok=True)

            # A locked file must never be silently omitted: that ships a
            # package missing pieces nobody notices until it fails on
            # someone else's machine. Retry briefly, then record it so the
            # build can refuse to continue.
            for attempt in range(3):
                try:
                    shutil.copy2(full, target)
                    copied += 1
                    break
                except PermissionError:
                    if attempt == 2:
                        LOCKED.append(rel)
                    else:
                        time.sleep(0.4 * (attempt + 1))
                except OSError as error:
                    LOCKED.append(f"{rel} ({error})")
                    break

    return copied, skipped


def _rmtree_stubborn(path, attempts=6):
    """
    Delete a tree that Windows may still be holding.

    A just-written 3GB folder is routinely locked for a few seconds by
    antivirus or a lingering shell, and a plain rmtree turns that into a
    hard failure halfway through a long build.
    """
    import stat
    import time

    def clear_readonly(func, target, _):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    for attempt in range(attempts):
        try:
            shutil.rmtree(path, onexc=clear_readonly)
            return True
        except (PermissionError, OSError):
            if attempt == attempts - 1:
                raise
            time.sleep(1.5 * (attempt + 1))

    return False


def stage(report):
    if os.path.isdir(STAGE):
        _rmtree_stubborn(STAGE)
    os.makedirs(STAGE)

    total_copied = total_skipped = 0

    for src_rel, dst_rel in INCLUDE_DIRS:
        src = os.path.join(ROOT, src_rel.replace("/", os.sep))
        dst = os.path.join(STAGE, dst_rel.replace("/", os.sep))
        copied, skipped = copy_tree(src, dst, report)
        total_copied += copied
        total_skipped += skipped
        report.append(f"  {src_rel:52s} {copied:5d} files"
                      + (f"  ({skipped} withheld)" if skipped else ""))

    for rel in INCLUDE_FILES:
        src = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(src):
            report.append(f"  MISSING file {rel}")
            continue
        dst = os.path.join(STAGE, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        total_copied += 1

    # Empty working folders, so the recipient's TORMENT_NEXUS starts with a blank
    # history instead of inheriting someone else's -- and so the music
    # feature has somewhere to look on first run.
    for sub in ("logs", "cache/prompt", "music"):
        os.makedirs(os.path.join(STAGE, "assistant", sub.replace("/", os.sep)),
                    exist_ok=True)

    return total_copied, total_skipped


def fetch(url, dest, report):
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        report.append(f"  cached  {os.path.basename(dest)}")
        return True

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        with open(dest, "wb") as handle:
            handle.write(data)
        report.append(f"  fetched {os.path.basename(dest)} "
                      f"({len(data)/1e6:.1f} MB)")
        return True
    except Exception as error:
        report.append(f"  FAILED  {url}: {error}")
        return False


def bundle_python(report):
    embed_zip = os.path.join(CACHE, os.path.basename(EMBED_URL))
    get_pip = os.path.join(CACHE, "get-pip.py")

    if not fetch(EMBED_URL, embed_zip, report):
        return False
    if not fetch(GET_PIP_URL, get_pip, report):
        return False

    target = os.path.join(STAGE, "python")
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(embed_zip) as archive:
        archive.extractall(target)

    # The embeddable build disables site-packages by default; without this
    # pip installs land somewhere the interpreter will not look.
    for name in os.listdir(target):
        if name.endswith("._pth"):
            path = os.path.join(target, name)
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            text = text.replace("#import site", "import site")
            if "import site" not in text:
                text += "\nimport site\n"
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            report.append(f"  enabled site in {name}")

    shutil.copy2(get_pip, os.path.join(target, "get-pip.py"))
    report.append(f"  embedded Python {PYTHON_VERSION} staged")
    return True


def bundle_wheels(report):
    wheels = os.path.join(STAGE, "wheels")
    os.makedirs(wheels, exist_ok=True)

    reqs = [os.path.join(ROOT, "requirements-release-windows.txt")]

    command = [sys.executable, "-m", "pip", "download",
               "--dest", wheels,
               "--only-binary", ":all:",
               "--python-version", ".".join(PYTHON_VERSION.split(".")[:2]),
               "--platform", "win_amd64",
               "--implementation", "cp"]
    for req in reqs:
        command += ["-r", req]
    command += ["pip", "setuptools", "wheel"]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        report.append("  pip download FAILED:")
        report.append("  " + result.stderr.strip()[-900:])
        return False

    count = len([n for n in os.listdir(wheels) if n.endswith((".whl", ".zip"))])
    size = sum(os.path.getsize(os.path.join(wheels, n))
               for n in os.listdir(wheels)) / 1e6
    report.append(f"  {count} wheels ({size:.0f} MB)")
    return True


RUNTIME_ARTIFACTS = (
    "assistant/.model_api_key",
    "assistant/.dev_passcode",
    "assistant/.tdeck_ble_pin",
    "assistant/.spotify_token",
    "assistant/memory/conversation_history.txt",
    "assistant/memory/memories.json",
    # Its absence is what marks a fresh install. Shipping it would rob the
    # recipient of the first-run walkthrough entirely.
    "assistant/.tutorial_state.json",
)


def sanitize(report):
    """
    Remove files the app creates the moment it is run.

    Building a clean package is not enough on its own. Test-running
    setup.bat inside the staged folder makes the assistant generate an API
    key and initialise its memory store, so a sensible build-test-send
    sequence would ship exactly the files the denylist exists to keep out.
    This is run at the end of every build, and can be run on its own after
    testing a package by hand.
    """
    removed = []

    manifest_path = os.path.join(STAGE, MANIFEST_NAME)
    if os.path.isfile(manifest_path):
        os.remove(manifest_path)
        removed.append(MANIFEST_NAME)

    for rel in RUNTIME_ARTIFACTS:
        path = os.path.join(STAGE, rel.replace("/", os.sep))
        if os.path.isfile(path):
            os.remove(path)
            removed.append(rel)

    for folder, dirs, files in os.walk(STAGE):
        for name in list(dirs):
            if name == "__pycache__":
                shutil.rmtree(os.path.join(folder, name), ignore_errors=True)
                dirs.remove(name)
                removed.append(os.path.relpath(
                    os.path.join(folder, name), STAGE))

        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, STAGE)
            if denied(rel):
                os.remove(full)
                removed.append(rel)

    if removed:
        report.append(f"  removed {len(removed)} runtime artifact(s)")
        for item in removed[:6]:
            report.append(f"    - {item}")
    else:
        report.append("  nothing to clean")

    return removed


def verify(report):
    """Re-scan the built package for anything personal that slipped in."""
    problems = []
    scanned = 0

    for folder, dirs, files in os.walk(STAGE):
        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, STAGE)
            scanned += 1

            if denied(rel):
                problems.append(f"denylisted file present: {rel}")

            if name in PRIVATE_RUNTIME_BASENAMES:
                problems.append(f"personal file present: {rel}")

    report.append(f"  scanned {scanned} files in the package")

    for label, path in (
        ("memory dir", os.path.join(STAGE, "assistant", "memory")),
    ):
        if os.path.isdir(path):
            leftovers = [n for n in os.listdir(path)
                         if n in ("memories.json", "conversation_history.txt")]
            if leftovers:
                problems.append(f"{label} still holds {leftovers}")

    _verify_release_launchers(report, problems)
    _verify_manifest(report, problems)

    return problems


def _verify_release_launchers(report, problems):
    """Ensure the handoff starts with its embedded interpreter, not the host."""
    expectations = {
        "start_assistant.bat": "python\\python.exe",
        "start_glitch.bat": "python\\pythonw.exe",
        "stop_glitch.bat": "python\\python.exe",
        "test_assistant.bat": "python\\python.exe",
        "setup.bat": "requirements-release-windows.txt",
    }

    for name, required_text in expectations.items():
        path = os.path.join(STAGE, name)
        try:
            with open(path, "r", encoding="utf-8") as source:
                contents = source.read().lower()
        except OSError:
            problems.append(f"missing release launcher: {name}")
            continue

        if required_text.lower() not in contents:
            problems.append(
                f"release launcher does not use the self-contained setup: {name}"
            )

    report.append(f"  checked {len(expectations)} self-contained launchers")


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(report):
    """Record every shipped file so a handoff can be checked later."""
    entries = []

    for folder, _, files in os.walk(STAGE):
        for name in sorted(files):
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, STAGE).replace("\\", "/")

            if rel == MANIFEST_NAME:
                continue

            entries.append({
                "path": rel,
                "bytes": os.path.getsize(full),
                "sha256": _hash_file(full),
            })

    payload = {
        "format": 1,
        "package": PACKAGE_NAME,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }
    path = os.path.join(STAGE, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")

    report.append(f"  wrote {MANIFEST_NAME} ({len(entries)} file hashes)")


def _verify_manifest(report, problems):
    path = os.path.join(STAGE, MANIFEST_NAME)

    if not os.path.isfile(path):
        problems.append(f"missing {MANIFEST_NAME}")
        return

    try:
        with open(path, "r", encoding="utf-8") as source:
            payload = json.load(source)
        entries = payload.get("files")
        if payload.get("format") != 1 or not isinstance(entries, list):
            raise ValueError("unsupported manifest format")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        problems.append(f"invalid {MANIFEST_NAME}: {error}")
        return

    listed = set()
    for entry in entries:
        rel = entry.get("path") if isinstance(entry, dict) else None
        expected = entry.get("sha256") if isinstance(entry, dict) else None

        if not isinstance(rel, str) or not isinstance(expected, str):
            problems.append(f"invalid manifest entry: {entry!r}")
            continue

        normalized = os.path.normpath(rel)
        if os.path.isabs(normalized) or normalized.startswith(".." + os.sep):
            problems.append(f"unsafe manifest path: {rel}")
            continue

        full = os.path.join(STAGE, normalized)
        listed.add(rel.replace("\\", "/"))
        if not os.path.isfile(full):
            problems.append(f"manifest file missing: {rel}")
        elif _hash_file(full) != expected:
            problems.append(f"manifest hash mismatch: {rel}")

    actual = set()
    for folder, _, files in os.walk(STAGE):
        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, STAGE).replace("\\", "/")
            if rel != MANIFEST_NAME:
                actual.add(rel)

    for rel in sorted(actual - listed):
        problems.append(f"manifest missing file: {rel}")
    for rel in sorted(listed - actual):
        problems.append(f"manifest lists absent file: {rel}")

    report.append(
        f"  manifest checked: {len(listed)} listed, {len(actual)} present"
    )


def write_launcher(report):
    for name, body in (
        ("setup.bat", SETUP_BAT),
        ("make_shortcut.ps1", MAKE_SHORTCUT_PS1),
        ("verify_install.py", VERIFY_INSTALL_PY),
        ("README.txt", README),
    ):
        with open(os.path.join(STAGE, name), "w",
                  encoding="utf-8", newline="\r\n") as handle:
            handle.write(body)
        report.append(f"  wrote {name}")


SETUP_BAT = r"""@echo off
setlocal
title TORMENT_NEXUS setup

echo.
echo   TORMENT_NEXUS - offline install
echo   ==========================
echo.

cd /d "%~dp0"

set "PY=%~dp0python\python.exe"
if not exist "%PY%" (
    echo   ERROR: bundled Python missing. Extract the whole archive first.
    pause
    exit /b 1
)

echo   [1/4] Preparing the bundled Python...
if not exist "%~dp0python\Scripts\pip.exe" (
    "%PY%" "%~dp0python\get-pip.py" --no-index --find-links "%~dp0wheels" --quiet
    if errorlevel 1 (
        echo   ERROR: could not set up pip.
        pause
        exit /b 1
    )
)

echo   [2/4] Installing packages from the bundled wheels...
"%PY%" -m pip install --no-index --find-links "%~dp0wheels" ^
    -r "%~dp0requirements-release-windows.txt" ^
    --quiet --no-warn-script-location
if errorlevel 1 (
    echo   ERROR: package install failed.
    pause
    exit /b 1
)

echo   [3/4] Checking the install...
if not exist "%~dp0models\Qwen3-4B-Instruct-2507-Q5_K_M.gguf" (
    echo   ERROR: the language model is missing from this package.
    pause
    exit /b 1
)
"%PY%" "%~dp0verify_install.py"
if errorlevel 1 (
    echo   ERROR: the install did not come out working. See above.
    pause
    exit /b 1
)

echo   [4/4] Creating the desktop shortcut...
REM %~dp0 ends with a backslash, which escapes the closing quote when
REM passed to PowerShell and silently corrupts the path. Strip it.
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1" -Root "%ROOT%"
if errorlevel 1 (
    echo.
    echo   Everything installed, but the desktop shortcut could not be
    echo   created. Launch it with start_assistant.bat in this folder.
    pause
    exit /b 0
)

echo.
echo   Done. 'TORMENT_NEXUS' is on your desktop.
echo.
echo   Everything lives in this folder and nothing else on your PC was
echo   changed - no system Python, no PATH, no registry. To uninstall,
echo   delete this folder and the desktop shortcut.
echo.
pause
"""


# Kept as its own file rather than inlined into the batch script: escaping
# a multi-line PowerShell command through cmd silently mangled it, and the
# batch then reported success for a shortcut that was never created.
MAKE_SHORTCUT_PS1 = r"""param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = "Stop"

# Defensive: a trailing backslash arriving from cmd can carry a stray
# quote with it, which CreateShortcut rejects with an error that names
# neither the path nor the reason.
$Root = $Root.Trim().TrimEnd('"').TrimEnd('\')

try {
    if (-not (Test-Path $Root)) {
        Write-Host "  install folder not found: $Root"
        exit 1
    }

    $desktop = [Environment]::GetFolderPath('Desktop')
    $path = Join-Path $desktop 'TORMENT_NEXUS.lnk'

    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = (Join-Path $Root 'start_assistant.bat')
    $link.WorkingDirectory = $Root
    $link.IconLocation = (Join-Path $Root 'assistant_icon.ico') + ',0'
    $link.Description = 'A private, offline AI companion'
    $link.Save()

    if (-not (Test-Path $path)) {
        Write-Host "  shortcut was not created"
        exit 1
    }

    Write-Host "  created: $path"
    exit 0
} catch {
    Write-Host ("  shortcut failed: " + $_.Exception.Message)
    exit 1
}
"""


# Runs inside the freshly built environment, so a package that installs
# but cannot actually import its own dependencies fails loudly at install
# time rather than the first time the recipient double-clicks it.
VERIFY_INSTALL_PY = r'''"""Check the bundled environment really works."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "assistant"))

failures = []

for module in ("numpy", "requests", "sounddevice", "soundcard",
               "piper", "sherpa_onnx"):
    try:
        __import__(module)
    except Exception as error:
        failures.append(f"import {module}: {error}")

try:
    import core.config as config
    for label, path in (
        ("language model", config.MODEL_PATH
         if hasattr(config, "MODEL_PATH") else None),
        ("voice model", config.VOICE_TTS_MODEL),
    ):
        if path and not os.path.isfile(path):
            failures.append(f"{label} missing at {path}")
except Exception as error:
    failures.append(f"assistant config: {error}")

if failures:
    print("  install verification FAILED:")
    for item in failures:
        print("    - " + item)
    raise SystemExit(1)

print("  verified: dependencies import and model files are present")
'''

README = r"""TORMENT_NEXUS - a private, offline AI companion
==========================================

WHAT THIS IS
    A local AI assistant that runs entirely on your machine. No account, no
    cloud, no internet needed once installed. It talks, listens, remembers,
    searches your files, edits its own code, and plays music.

INSTALLING
    1. Extract this whole archive somewhere with ~4 GB free.
       (Keep the folder together - setup needs everything beside it.)
    2. Run setup.bat
    3. Launch "TORMENT_NEXUS" from your desktop.

    Setup takes a couple of minutes and needs no internet.

WHAT IT TOUCHES
    Nothing outside this folder, plus one desktop shortcut. It does not use
    or modify your system Python, PATH, or registry. Python itself is
    bundled inside the "python" folder here. To uninstall, delete this
    folder and the shortcut.

FIRST RUN
    The model loads into RAM and takes a moment on the first message. 8 GB
    of RAM is comfortable; 16 GB is better if you want the voice running at
    the same time.

    Type "help" to see the commands.

SOME THINGS TO TRY
    help              list every command
    dev mode          unlock the developer tools
    music library     list local tracks it can play offline
    audio mode        talk to it out loud
    sing daisy bell   ask politely

VOICE
    Speech runs through a vocoder that separates pitch from vocal tract,
    tuned against a reference recording. If it is not to your taste, three
    environment variables retune it without touching code:

        AI_BUDDY_CARRIER_HZ       pitch of the carrier (default 145)
        AI_BUDDY_PITCH_FLATTEN    monotone-ness, 0 to 1 (default 0.45)
        AI_BUDDY_VOWEL_STRETCH    how drawn-out vowels are (default 1.6)

THE GLITCHING ICON (optional)
    start_glitch.bat makes the desktop icon corrupt itself now and then.
    stop_glitch.bat stops it and restores the normal icon. It is off unless
    you start it, and it does not survive a reboot.

PRIVACY
    This package contains no conversation history, memories, developer
    passcode verifier, device pairing PIN, API key, or music from the person
    who sent it. TORMENT_NEXUS starts with a blank slate. The included
    RELEASE_MANIFEST.json records a SHA-256 hash for every shipped file.
"""


def main():
    parser = argparse.ArgumentParser(description="Build a shareable package.")
    parser.add_argument("--archive", action="store_true",
                        help="zip the package when done")
    parser.add_argument("--skip-download", action="store_true",
                        help="reuse cached Python and wheels")
    parser.add_argument("--verify-only", action="store_true",
                        help="re-check an existing build")
    parser.add_argument("--sanitize", action="store_true",
                        help="strip runtime artifacts, then re-verify "
                             "(run this if you test-ran setup.bat)")
    args = parser.parse_args()

    report = []

    if args.verify_only or args.sanitize:
        if not os.path.isdir(STAGE):
            print("Nothing built yet.")
            return 1

        if args.sanitize:
            print("Sanitizing...")
            sanitize(report)
            write_manifest(report)
            print("\n".join(report))
            report.clear()
            print()

        print("Verifying...")
        problems = verify(report)
        print("\n".join(report))
        if problems:
            print("\nPROBLEMS:")
            for p in problems:
                print("  " + p)
            if not args.sanitize:
                print("\nRun with --sanitize to strip these, "
                      "then verify again.")
            return 1
        print("\nClean - safe to send.")
        return 0

    os.makedirs(CACHE, exist_ok=True)

    print("Staging files...")
    copied, withheld = stage(report)
    print("\n".join(report))
    report.clear()
    print(f"  -> {copied} files copied, {withheld} withheld by the denylist\n")

    if LOCKED:
        print(f"REFUSING TO SHIP - {len(LOCKED)} file(s) were locked and "
              f"could not be copied:")
        for item in LOCKED[:10]:
            print("  " + item)
        print("\nSomething is running out of the project or dist folder.")
        print("Stop it and rebuild -- a package missing files would fail")
        print("on the recipient's machine instead of here.")
        return 1

    print("Bundling Python...")
    if not bundle_python(report):
        print("\n".join(report))
        return 1
    print("\n".join(report))
    report.clear()
    print()

    print("Downloading wheels...")
    if not bundle_wheels(report):
        print("\n".join(report))
        return 1
    print("\n".join(report))
    report.clear()
    print()

    print("Writing installer...")
    write_launcher(report)
    print("\n".join(report))
    report.clear()
    print()

    print("Sanitizing runtime artifacts...")
    sanitize(report)
    print("\n".join(report))
    report.clear()
    print()

    print("Writing release manifest...")
    write_manifest(report)
    print("\n".join(report))
    report.clear()
    print()

    print("Verifying no personal data leaked...")
    problems = verify(report)
    print("\n".join(report))
    if problems:
        print("\nREFUSING TO SHIP - problems found:")
        for p in problems:
            print("  " + p)
        return 1
    print("  clean\n")

    size = sum(
        os.path.getsize(os.path.join(f, n))
        for f, _, files in os.walk(STAGE) for n in files
    )
    print(f"Package: {STAGE}")
    print(f"Size:    {size/1e9:.2f} GB")

    if args.archive:
        print("\nArchiving (this takes a while at this size)...")
        base = os.path.join(DIST, PACKAGE_NAME)
        path = shutil.make_archive(base, "zip", DIST, PACKAGE_NAME)
        print(f"Archive: {path} ({os.path.getsize(path)/1e9:.2f} GB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
