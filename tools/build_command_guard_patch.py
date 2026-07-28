"""Build the optional near-miss command guard patch for Beta 6.

The second post-archive patch, and the same trade as the first: a small fix
that landed after the 12 GB package was built and split, shipped as a
hand-applied asset rather than as a rebuild.

What it corrects is a gap in a fix Beta 6 already shipped. near_miss_command
was written to stop unregistered input being narrated as though it had run,
and its docstring named "drop all" and "finish" as the cases it handled. It
did not handle them. The shape it matches is a real command name plus one
stray word, and nothing in the command table contains "drop", so "drop all"
could never be one word away from anything. A bare single word could not
match either: the rule needs one more word than the command name has, and no
command name is zero words long.

Live on 2026-07-28, after that fix shipped, "drop all" answered "I'm dropping
everything", "drop" answered "I'm dropping", and "finish goal" -- one
character from the real "finish goals" -- answered "I'm finishing the goal".
Nothing had run in any of them.

Independent of the /ask guard patch. That one replaces assistant/main.py;
this one replaces assistant/commands/command_handlers.py. Either may be
applied without the other, in any order.
"""

import hashlib
import os
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
VERSION = "v0.2.0-beta.6"
PACKAGED_COMMIT = "97711ca"
PAYLOAD = os.path.join(DIST, f"TORMENT_NEXUS-{VERSION}-command-guard-patch.zip")
INSTALLER = os.path.join(DIST, "INSTALL_COMMAND_GUARD_PATCH.bat")

SOURCE = os.path.join("assistant", "commands", "command_handlers.py")
SOURCE_IN_ZIP = "assistant/commands/command_handlers.py"
BACKUP_NAME = "command_handlers.py.pre-command-guard"

DOC = """# Near-miss command guard patch

## What this fixes

Typing something that looks like a command but is not one used to reach the
model, which answered as though the action had been carried out.

Beta 6 already shipped a fix for this, and that fix works -- for the exact
shape it matches. It looks for a real command name with one stray word
attached, which catches "finish goals" and does nothing at all for:

| You typed | It answered | What ran |
| --- | --- | --- |
| `drop all` | "I'm dropping everything." | nothing |
| `drop` | "I'm dropping." | nothing |
| `finish` | a stage direction | nothing |
| `finish goal` | "I'm finishing the goal." | nothing |

Two structural reasons, not missing entries. No command in the table contains
the word "drop", so "drop all" was never one word away from anything to
begin with. And a bare single word cannot match a rule that requires one more
word than the command name has, because no command name is zero words long.
"finish goal" missed for a third reason: the comparison was exact per word,
so a plural spelled differently in the table was a complete miss.

## What it changes

`assistant/commands/command_handlers.py` only:

- Words are compared allowing one typo each, so `finish goal` now resolves to
  `goals` and suggests it. Words under three characters are excluded, or
  every short token would match every other one.
- A phrase built on a state-changing verb -- drop, finish, clear, reset,
  delete, cancel and similar -- that resembles no command at all is answered
  directly: nothing is a command, and nothing ran. Any ordinary
  conversational word in the phrase disqualifies it, which is what keeps
  "can you drop me a line" and "i want to finish this" as ordinary chat.

The narrowness is deliberate and unchanged from the original design. A false
positive turns a real sentence into an error message, which is worse than a
miss.

## What it costs

This replaces a file the release manifest hashes. After applying it the
installed tree no longer matches the published archive checksum, by design.
That is why it is a separate manual step.

The installer keeps the original as `command_handlers.py.pre-command-guard`.
To undo, delete the patched file and rename that backup back.

## Relationship to the /ask guard patch

Independent. That patch replaces `assistant/main.py`; this one replaces
`assistant/commands/command_handlers.py`. Apply either, both, or neither, in
any order.

## Verification

644 tests pass with the guard in place. Each new test was confirmed by
re-injecting the bug: with the typo tolerance reduced to exact equality and
the verb set emptied, the tests fail and report the phrases falling through
to the model, which is the original symptom.
"""

INSTALLER_TEMPLATE = """@echo off
setlocal
set "HERE=%~dp0"
set "PAYLOAD=%HERE%{payload}"
set "EXPECTED={digest}"
set "PRE={pre}"
set "POST={post}"
set "TARGET=%HERE%assistant\\commands\\command_handlers.py"
set "BACKUP=%HERE%assistant\\commands\\{backup}"

echo.
echo   TORMENT_NEXUS - optional near-miss command guard patch
echo.

if not exist "%HERE%start_assistant.bat" (
    echo   Put this installer and {payload}
    echo   inside your TORMENT_NEXUS folder - the one containing
    echo   start_assistant.bat - and run it again.
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
    echo   Cannot find assistant\\commands\\command_handlers.py here.
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

echo   [2/4] Checking the installed file...
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
    echo   command_handlers.py is not the file Beta 6 shipped.
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
echo   Done. Input like "drop all" or "finish goal" is now answered
echo   directly instead of being described as though it had run.
echo.
echo   Your original file is kept as
echo   assistant\\commands\\{backup}
echo.
echo   Note: this replaces a file the release manifest hashes, so the
echo   installed tree no longer matches the published archive checksum.
echo   That is expected. See docs\\COMMAND_GUARD_PATCH.md.
echo.
pause
"""


def _packaged_source() -> bytes:
    """The file Beta 6 actually shipped, read from the packaged commit."""
    result = subprocess.run(
        ["git", "show", f"{PACKAGED_COMMIT}:{SOURCE_IN_ZIP}"],
        cwd=ROOT,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"could not read {PACKAGED_COMMIT}:{SOURCE_IN_ZIP} -- "
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

    original = _packaged_source()

    if patched == original:
        raise SystemExit(
            f"{SOURCE_IN_ZIP} is identical to the packaged commit -- "
            "there is nothing to patch"
        )

    pre = hashlib.sha256(original).hexdigest().upper()
    post = hashlib.sha256(patched).hexdigest().upper()

    fixed = (2026, 7, 28, 0, 0, 0)

    with zipfile.ZipFile(PAYLOAD, "w", zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo(SOURCE_IN_ZIP, date_time=fixed)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, patched)

        info = zipfile.ZipInfo("docs/COMMAND_GUARD_PATCH.md", date_time=fixed)
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
    print(f"  shipped  SHA-256 {pre}")
    print(f"  patched  SHA-256 {post}")


if __name__ == "__main__":
    build()
