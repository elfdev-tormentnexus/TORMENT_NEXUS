"""Build the optional /ask history-guard patch for Beta 6.

The Beta 6 archive was built from 97711ca. The history-reference guard landed
in 10c1b73, after the 12 GB package was already zipped and split. Rebuilding
the whole archive for a 37-line change to one file is the same bad trade the
documentation patch and the interface-mode add-on already refused, so this
ships in the same shape: an installer with the payload's SHA-256 baked in,
plus the payload.

It differs from those two in one way that has to be stated rather than
buried. The documentation patch touches documentation only, which is what
lets the release notes claim an installed tree still matches the published
archive checksum. This patch replaces assistant/main.py, a file the release
manifest hashes. Applying it therefore makes the installed tree diverge from
the published manifest on purpose. That is a real trade and the operator
should make it knowingly, which is why this is a separate manual asset that
the reassembler does not apply on its own.

The installer refuses to guess. It checks the main.py already installed
against the two hashes it knows -- the shipped Beta 6 file and the patched
file -- and stops if it is neither, rather than overwriting a tree somebody
has already modified. It keeps a backup either way.
"""

import hashlib
import os
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
VERSION = "v0.2.0-beta.6"
PACKAGED_COMMIT = "97711ca"
PAYLOAD = os.path.join(DIST, f"TORMENT_NEXUS-{VERSION}-ask-guard-patch.zip")
INSTALLER = os.path.join(DIST, "INSTALL_ASK_GUARD_PATCH.bat")

SOURCE = os.path.join("assistant", "main.py")
BACKUP_NAME = "main.py.pre-ask-guard"

DOC = """# /ask history-guard patch

## What this fixes

Asked a vague question about the past -- "what did we discuss before this
request?", "what did you tell me earlier?" -- the read-only agent interface
would produce a fluent, specific account of a conversation that never
happened. It has no conversation history in that mode, and says so correctly
when asked directly, which is what made the failure easy to miss.

The cause was that the /ask path handed the model an advisory system message
saying it could not see live history, and then sampled an answer anyway. An
advisory is a request. A small model asked to discount context it cannot see
is the reasoning that already failed once in this project, in the persona-shot
fusion that Beta 6 fixed. This is the same bug one layer further out.

## What it changes

`assistant/main.py` only, and within it only the agent interface:

- A short list of literal history-reference phrases is matched against the
  casefolded question. A hit returns a fixed boundary answer with
  `history_limited: true`, does not reserve the director slot, and never
  calls the model at all. The guard is Python and it fails closed.
- `/memory/search` gains a top-level note that its results are retrieval
  candidates rather than verified facts. The knowledge route already returned
  review and staleness metadata; the memory route returned bare strings, so a
  connected agent had no way to tell how tentative a candidate was without
  treating its text as evidence.

Ordinary conversation is untouched. Nothing outside the agent interface
changes behaviour.

## What it costs

This replaces a file the release manifest hashes. After applying it, the
installed tree no longer matches the published archive checksum, by design.
That is why it is a separate manual step rather than something the
reassembler applies for you.

The installer writes the original file beside it as `main.py.pre-ask-guard`.
To undo the patch, delete the patched `main.py` and rename that backup back.

## Verification

640 tests pass with the guard in place. The guard test was confirmed by
re-injecting the bug: with the phrase check forced to return False, the test
fails and reports the model call going out.
"""

INSTALLER_TEMPLATE = """@echo off
setlocal
set "HERE=%~dp0"
set "PAYLOAD=%HERE%{payload}"
set "EXPECTED={digest}"
set "PRE={pre}"
set "POST={post}"
set "TARGET=%HERE%assistant\\main.py"
set "BACKUP=%HERE%assistant\\{backup}"

echo.
echo   TORMENT_NEXUS - optional /ask history-guard patch
echo.

if not exist "%HERE%start_assistant.bat" (
    echo   Put this installer and {payload} inside your
    echo   TORMENT_NEXUS folder - the one containing start_assistant.bat -
    echo   and run it again.
    pause
    exit /b 1
)

if not exist "%PAYLOAD%" (
    echo   Missing {payload}
    echo   Download it into this folder first.
    pause
    exit /b 1
)

if not exist "%TARGET%" (
    echo   Cannot find assistant\\main.py in this folder.
    echo   Nothing has been changed.
    pause
    exit /b 1
)

echo   [1/4] Verifying the download...
set "ACTUAL="
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%PAYLOAD%" SHA256') do (
    if not defined ACTUAL set "ACTUAL=%%H"
)
set "ACTUAL=%ACTUAL: =%"
if /i not "%ACTUAL%"=="%EXPECTED%" (
    echo.
    echo   CHECKSUM MISMATCH - the download is damaged.
    echo   expected %EXPECTED%
    echo   got      %ACTUAL%
    echo.
    echo   Delete it and download again. Nothing has been installed.
    pause
    exit /b 1
)

echo   [2/4] Checking the installed main.py...
set "CURRENT="
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%TARGET%" SHA256') do (
    if not defined CURRENT set "CURRENT=%%H"
)
set "CURRENT=%CURRENT: =%"

if /i "%CURRENT%"=="%POST%" (
    echo.
    echo   This patch is already applied. Nothing to do.
    echo.
    pause
    exit /b 0
)

if /i not "%CURRENT%"=="%PRE%" (
    echo.
    echo   assistant\\main.py is not the file Beta 6 shipped.
    echo   Something has already changed it, so this patch will not
    echo   overwrite it blindly.
    echo.
    echo   expected %PRE%
    echo   found    %CURRENT%
    echo.
    echo   Nothing has been changed.
    pause
    exit /b 1
)

echo   [3/4] Backing up the original...
copy /y "%TARGET%" "%BACKUP%" >nul
if errorlevel 1 (
    echo   Could not write the backup. Nothing has been changed.
    pause
    exit /b 1
)

echo   [4/4] Applying...
set "ROOT=%HERE%"
if "%ROOT:~-1%"=="\\" set "ROOT=%ROOT:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%PAYLOAD%' -DestinationPath '%ROOT%' -Force"
if errorlevel 1 (
    echo   Could not unpack the patch. Restoring the original...
    copy /y "%BACKUP%" "%TARGET%" >nul
    pause
    exit /b 1
)

echo.
echo   Done. The /ask interface now answers history questions from a
echo   fixed boundary response instead of sampling the model.
echo.
echo   Your original file is kept as assistant\\{backup}
echo.
echo   Note: this replaces a file the release manifest hashes, so the
echo   installed tree no longer matches the published archive checksum.
echo   That is expected. See docs\\ASK_GUARD_PATCH.md.
echo.
pause
"""


def _packaged_main() -> bytes:
    """The main.py Beta 6 actually shipped, read from the packaged commit."""
    result = subprocess.run(
        ["git", "show", f"{PACKAGED_COMMIT}:assistant/main.py"],
        cwd=ROOT,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"could not read {PACKAGED_COMMIT}:assistant/main.py -- "
            + result.stderr.decode("utf-8", "replace").strip()
        )
    return result.stdout


def build():
    if not os.path.isdir(DIST):
        raise SystemExit(f"missing {DIST}")

    source = os.path.join(ROOT, SOURCE)
    if not os.path.isfile(source):
        raise SystemExit(f"missing {source}")

    with open(source, "rb") as handle:
        patched = handle.read()

    original = _packaged_main()

    if patched == original:
        raise SystemExit(
            "assistant/main.py is identical to the packaged commit -- "
            "there is nothing to patch"
        )

    pre = hashlib.sha256(original).hexdigest().upper()
    post = hashlib.sha256(patched).hexdigest().upper()

    fixed = (2026, 7, 28, 0, 0, 0)

    with zipfile.ZipFile(PAYLOAD, "w", zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo("assistant/main.py", date_time=fixed)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, patched)

        info = zipfile.ZipInfo("docs/ASK_GUARD_PATCH.md", date_time=fixed)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, DOC.encode("utf-8"))

    with open(PAYLOAD, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest().upper()

    text = INSTALLER_TEMPLATE.format(
        payload=os.path.basename(PAYLOAD),
        digest=digest,
        pre=pre,
        post=post,
        backup=BACKUP_NAME,
    )

    # Batch files are CRLF even though repository source is LF.
    with open(INSTALLER, "w", newline="\r\n", encoding="ascii") as handle:
        handle.write(text)

    print(f"wrote {PAYLOAD}")
    print(f"  {os.path.getsize(PAYLOAD)} bytes")
    print(f"  SHA-256 {digest}")
    print(f"wrote {INSTALLER}")
    print(f"  {os.path.getsize(INSTALLER)} bytes")
    print(f"  shipped  main.py SHA-256 {pre}")
    print(f"  patched  main.py SHA-256 {post}")


if __name__ == "__main__":
    build()
