"""
Build an optional add-on model download that GitHub will actually host.

Some models are deliberately not in the beta payload. The 14B full-maintenance
coder is 8.6 GB on its own -- nearly three times the entire rest of the
package -- and most people will never run a test-driven repair pass. Bundling
it would triple the download for everyone to serve a minority.

But "not bundled" must not mean "unobtainable", and a bare GGUF cannot simply
be attached to a release: GitHub rejects any asset over 2 GiB, so an 8.6 GB
model needs the same split-and-rejoin treatment as the main archive.

This produces that: numbered parts, a generated installer that joins them,
verifies the result against a checksum baked in at build time, and puts the
file exactly where the launcher looks for it.

    python tools/package_model_pack.py models/<model>.gguf

The verification is the point. A recipient who joins five parts wrongly and
only finds out when a 14B model fails to load has no way to tell a bad
download from a bad model from a bad launcher. The installer refuses instead.
"""

import argparse
import glob
import hashlib
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "modelpacks")

# Matches package_release.py. GitHub rejects an asset over 2 GiB; the margin
# covers the difference between its accounting and ours.
MAX_ASSET_BYTES = 2 * 1024**3 - 64 * 1024**2

CHUNK = 8 * 1024**2


def _hash_file(path):
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)

    return digest.hexdigest()


def _installer(model_name, parts, checksum):
    """A .bat that joins, verifies, and installs -- in that order.

    Order matters. Joining into models/ directly would leave a half-written
    GGUF sitting exactly where the launcher expects a good one, so the join
    happens beside the parts and the file only moves after the checksum
    matches.
    """
    checks = "\n\n".join(
        f'if not exist "%HERE%{name}" (\n'
        f'    echo Missing {name}\n'
        f'    echo Download every numbered part into this folder first.\n'
        f'    pause\n'
        f'    exit /b 1\n'
        f')'
        for name in parts
    )
    joined = "+".join(f'"%HERE%{name}"' for name in parts)

    return f"""@echo off
setlocal
title TORMENT_NEXUS - optional model download
set "HERE=%~dp0"
set "TEMPFILE=%HERE%{model_name}.joining"

echo.
echo   TORMENT_NEXUS optional model
echo   {model_name}
echo.

{checks}

echo   [1/3] Joining {len(parts)} parts...
copy /b {joined} "%TEMPFILE%" >nul
if errorlevel 1 (
    echo   Could not join the parts. Is there enough disk space?
    pause
    exit /b 1
)

echo   [2/3] Verifying...
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%TEMPFILE%" SHA256') do (
    if not defined ACTUAL set "ACTUAL=%%H"
)
set "ACTUAL=%ACTUAL: =%"
if /i not "%ACTUAL%"=="{checksum}" (
    echo.
    echo   CHECKSUM MISMATCH - the download is damaged.
    echo   expected {checksum}
    echo   got      %ACTUAL%
    echo.
    echo   Delete the parts and download them again. The model has NOT
    echo   been installed.
    del "%TEMPFILE%" >nul 2>&1
    pause
    exit /b 1
)

echo   [3/3] Installing...
if not exist "%HERE%models\\" (
    echo.
    echo   Put this installer and its parts inside your TORMENT_NEXUS
    echo   folder - the one containing start_assistant.bat - and run it
    echo   again. It needs to place the model in models\\.
    pause
    exit /b 1
)
move /y "%TEMPFILE%" "%HERE%models\\{model_name}" >nul

echo.
echo   Done. {model_name} is installed.
echo   The parts can be deleted now.
echo.
pause
"""


def build(model_path, label):
    if not os.path.isfile(model_path):
        print(f"No such model: {model_path}")
        return 1

    name = os.path.basename(model_path)
    total = os.path.getsize(model_path)
    count = max(1, -(-total // MAX_ASSET_BYTES))
    size = -(-total // count)

    os.makedirs(DIST, exist_ok=True)

    for stale in glob.glob(os.path.join(DIST, name + ".part*")):
        os.remove(stale)

    print(f"{name}\n  {total / 1024**3:.2f} GB -> {count} part(s)\n")
    print("  hashing...", flush=True)
    checksum = _hash_file(model_path).upper()

    parts = []

    with open(model_path, "rb") as source:
        for index in range(1, count + 1):
            part = f"{name}.part{index:02d}"
            written = 0

            with open(os.path.join(DIST, part), "wb") as target:
                while written < size:
                    block = source.read(min(CHUNK, size - written))

                    if not block:
                        break

                    target.write(block)
                    written += len(block)

            parts.append(part)
            print(f"  wrote {part}  ({written / 1024**2:,.0f} MB)")

    # Derived names are ambiguous here -- two of the three models are
    # "Coder" -- so the label says what the download is FOR, not what it is.
    installer = f"INSTALL_{label}.bat"

    with open(os.path.join(DIST, installer), "w",
              encoding="utf-8", newline="\r\n") as handle:
        handle.write(_installer(name, parts, checksum))

    print(f"  wrote {installer}")

    # Prove the parts rejoin before anyone uploads them. A split that does not
    # rejoin reaches 100% of downloads, and at this size a recipient has spent
    # a very long time before finding out.
    print("\n  verifying the parts rejoin...", flush=True)
    rejoined = hashlib.sha256()

    for part in parts:
        with open(os.path.join(DIST, part), "rb") as piece:
            for block in iter(lambda: piece.read(CHUNK), b""):
                rejoined.update(block)

    if rejoined.hexdigest().upper() != checksum:
        print("  PARTS DO NOT REJOIN - do not upload")
        return 1

    print("  verified byte-identical\n")
    print(f"  SHA256  {name}\n          {checksum}\n")

    for part in parts:
        print(f"  SHA256  {part}\n"
              f"          {_hash_file(os.path.join(DIST, part)).upper()}")

    print(f"\nUpload from {DIST}:")
    print(f"  {installer}")

    for part in parts:
        print(f"  {part}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Split an optional model into GitHub-sized parts with a "
                    "verifying installer.",
    )
    parser.add_argument("model", help="path to the .gguf to package")
    parser.add_argument("--label", default="OPTIONAL_MODEL",
                        help="names the installer, e.g. "
                             "FULL_MAINTENANCE_14B")

    args = parser.parse_args()

    return build(args.model, args.label)


if __name__ == "__main__":
    raise SystemExit(main())
