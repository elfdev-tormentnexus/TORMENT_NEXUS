"""Build the optional interface-mode add-on for Beta 6.

Interface mode is the ordinary assistant with the read-only agent API open.
Its launcher lives at the repository root, outside the staged tree the
packager copies, so Beta 6 shipped without it. Rather than rebuild a 13 GB
archive for one batch file, it ships as a small optional add-on in the same
shape as the 14B model pack: an installer with the payload's SHA-256 baked
in, plus the payload itself.

Everything interface mode depends on is already in the base package -- the
agent interface module, the AGENT_WATCH echo, and start_assistant.bat, which
is the fallback path taken whenever the desktop CUDA runtime is absent, and
it always is in the published CPU package. The add-on therefore carries only
the launcher and its icon.

Payload paths are relative to the install root because the installer runs
from inside the extracted TORMENT_NEXUS folder, the same way the 14B
installer does. The documentation patch is the opposite case: it is applied
by the reassembler, which sits one level above.
"""

import hashlib
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
VERSION = "v0.2.0-beta.6"
PAYLOAD = os.path.join(DIST, f"TORMENT_NEXUS-{VERSION}-interface-mode.zip")
INSTALLER = os.path.join(DIST, "INSTALL_INTERFACE_MODE.bat")

FILES = {
    "start_interface_mode.bat": "start_interface_mode.bat",
    os.path.join("assets", "assistant_icon_interface.ico"):
        "assets/assistant_icon_interface.ico",
}

DOC = """# Interface mode

Interface mode is the ordinary assistant with the read-only agent interface
open on loopback. It exists as its own launcher because that interface is a
listening socket and an authentication boundary: which windows have it open
should be something you can see, not something you have to remember. The
window title and the inverted icon both say so.

While it is running, a connected agent can read state, search memory and the
knowledge library, and ask the director a question. Nothing on that interface
writes, edits, or restarts anything. The bearer token is written to
`assistant\\.agent_token`. Closing the window closes the interface.

Starting the assistant by any other launcher leaves the interface closed.
"""

INSTALLER_TEMPLATE = """@echo off
setlocal
set "HERE=%~dp0"
set "PAYLOAD=%HERE%{payload}"
set "EXPECTED={digest}"

echo.
echo   TORMENT_NEXUS - optional interface mode
echo.

if not exist "%HERE%start_assistant.bat" (
    echo   Put this installer and {payload} inside your TORMENT_NEXUS
    echo   folder - the one containing start_assistant.bat - and run it
    echo   again.
    pause
    exit /b 1
)

if not exist "%PAYLOAD%" (
    echo   Missing {payload}
    echo   Download it into this folder first.
    pause
    exit /b 1
)

echo   [1/3] Verifying...
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

echo   [2/3] Installing...
set "ROOT=%HERE%"
if "%ROOT:~-1%"=="\\" set "ROOT=%ROOT:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%PAYLOAD%' -DestinationPath '%ROOT%' -Force"
if errorlevel 1 (
    echo   Could not unpack the add-on.
    pause
    exit /b 1
)

echo   [3/3] Creating the desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'TORMENT_NEXUS interface mode.lnk')); $s.TargetPath=[IO.Path]::Combine('%ROOT%','start_interface_mode.bat'); $s.WorkingDirectory='%ROOT%'; $s.IconLocation=[IO.Path]::Combine('%ROOT%','assets','assistant_icon_interface.ico'); $s.Description='TORMENT_NEXUS with the read-only agent interface open'; $s.Save()"
if errorlevel 1 (
    echo.
    echo   Installed, but the desktop shortcut could not be created.
    echo   Start it with start_interface_mode.bat in this folder.
    pause
    exit /b 0
)

echo.
echo   Done. Interface mode is installed.
echo.
echo   It opens a read-only agent interface on loopback while it runs.
echo   Every other launcher leaves that interface closed. See
echo   docs\\INTERFACE_MODE.md.
echo.
pause
"""


def build():
    if not os.path.isdir(DIST):
        raise SystemExit(f"missing {DIST}")

    missing = [s for s in FILES if not os.path.isfile(os.path.join(ROOT, s))]
    if missing:
        raise SystemExit("missing source files: " + ", ".join(missing))

    fixed = (2026, 7, 28, 0, 0, 0)

    with zipfile.ZipFile(PAYLOAD, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, dest in sorted(FILES.items()):
            with open(os.path.join(ROOT, source), "rb") as handle:
                data = handle.read()
            info = zipfile.ZipInfo(dest, date_time=fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

        info = zipfile.ZipInfo("docs/INTERFACE_MODE.md", date_time=fixed)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, DOC.encode("utf-8"))

    with open(PAYLOAD, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest().upper()

    text = INSTALLER_TEMPLATE.format(
        payload=os.path.basename(PAYLOAD),
        digest=digest,
    )

    # Batch files are CRLF even though repository source is LF.
    with open(INSTALLER, "w", newline="\r\n", encoding="ascii") as handle:
        handle.write(text)

    print(f"wrote {PAYLOAD}")
    print(f"  {os.path.getsize(PAYLOAD)} bytes")
    print(f"  SHA-256 {digest}")
    print(f"wrote {INSTALLER}")
    print(f"  {os.path.getsize(INSTALLER)} bytes")


if __name__ == "__main__":
    build()
