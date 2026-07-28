"""Build the one-double-click downloader for the Beta 6 release assets.

A button on the release page is not possible: GitHub sanitises release-notes
markdown, so no script, form or handler in that body can ever run. The
nearest real thing is an asset small enough to fetch by hand that then fetches
everything else, which is what this builds.

Generated, not hand-written, for the reason the reassembler is generated: a
hand-made helper in this project once knew about two parts when there were
more, and every recipient got a corrupt archive. The asset list and every
SHA-256 below are read from the files actually built, so a downloader that
disagrees with the release is a build failure rather than a support thread.

Uses curl.exe, which ships in Windows 10 1803 and later. It resumes with
-C -, which matters at 2 GB a part on a connection that drops, and retries
without giving the operator a half-file that looks complete. Every part is
checked against its digest after transfer, and an existing valid file is
skipped, so re-running after an interruption costs only what is missing.
"""

import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
VERSION = "v0.2.0-beta.6"
REPO = "elfdev-tormentnexus/TORMENT_NEXUS"
PACKAGE_NAME = "TORMENT_NEXUS"
ARCHIVE_STEM = f"{PACKAGE_NAME}-{VERSION}-windows-x64"
DOWNLOADER = os.path.join(DIST, f"DOWNLOAD_{PACKAGE_NAME}_{VERSION}.bat")

# Everything a normal install needs. The 14B full-maintenance pack is
# deliberately excluded: it is 8.4 GB, it is for advanced users who have
# read what it does, and quietly adding it to a bulk download would be the
# opposite of the disclosure the rest of this release is built around.
REQUIRED = [f"{ARCHIVE_STEM}.zip.part0{n}" for n in range(1, 7)] + [
    f"REASSEMBLE_{ARCHIVE_STEM}.bat",
]

OPTIONAL = [
    f"{PACKAGE_NAME}-{VERSION}-docs-patch.zip",
    "INSTALL_ASK_GUARD_PATCH.bat",
    f"{PACKAGE_NAME}-{VERSION}-ask-guard-patch.zip",
    "INSTALL_COMMAND_GUARD_PATCH.bat",
    f"{PACKAGE_NAME}-{VERSION}-command-guard-patch.zip",
]


def _digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def build():
    if not os.path.isdir(DIST):
        raise SystemExit(f"missing {DIST}")

    assets = []
    total = 0

    for name in REQUIRED + OPTIONAL:
        path = os.path.join(DIST, name)
        if not os.path.isfile(path):
            raise SystemExit(
                f"missing {name} -- build every asset before the downloader, "
                "or it will ship a list the release cannot satisfy"
            )
        size = os.path.getsize(path)
        assets.append((name, size, _digest(path)))
        total += size

    base = f"https://github.com/{REPO}/releases/download/{VERSION}"
    gigabytes = total / (1024 ** 3)

    lines = [
        "@echo off",
        "setlocal EnableDelayedExpansion",
        'set "HERE=%~dp0"',
        'if "%HERE:~-1%"=="\\" set "HERE=%HERE:~0,-1%"',
        f'set "BASE={base}"',
        'set "FAILED="',
        "",
        "echo.",
        f"echo   {PACKAGE_NAME} {VERSION} - downloader",
        "echo.",
        f"echo   This fetches all {len(assets)} files the Windows package needs,",
        f"echo   about {gigabytes:.1f} GB in total, into this folder:",
        "echo.",
        "echo     %HERE%",
        "echo.",
        "echo   Each file is checked against its SHA-256 after download.",
        "echo   Anything already here and intact is skipped, so running this",
        "echo   again after an interruption only fetches what is missing.",
        "echo.",
        "echo   Allow roughly 40 GB free overall: the parts, the joined ZIP",
        "echo   and the extracted folder briefly exist at the same time.",
        "echo.",
        "echo   The optional 14B full-maintenance model is NOT included here.",
        "echo   It is a separate 8.4 GB download for advanced users.",
        "echo.",
        "pause",
        "echo.",
        "",
        "REM curl.exe ships with Windows 10 1803 and later. Without it there",
        "REM is no resume, and a dropped 2 GB transfer would start over.",
        'where curl.exe >nul 2>&1',
        "if errorlevel 1 (",
        "    echo   curl.exe was not found. It ships with Windows 10 1803",
        "    echo   and later. Download the assets manually from:",
        f"    echo     https://github.com/{REPO}/releases/tag/{VERSION}",
        "    pause",
        "    exit /b 1",
        ")",
        "",
    ]

    for index, (name, size, digest) in enumerate(assets, 1):
        lines.extend((
            f'call :fetch "{name}" "{digest}" {index} {len(assets)}',
        ))

    lines.extend((
        "",
        "if defined FAILED (",
        "    echo.",
        "    echo   Some files did not download or did not verify:",
        "    echo   !FAILED!",
        "    echo.",
        "    echo   Run this again - intact files are skipped, so it will",
        "    echo   only retry what is missing.",
        "    pause",
        "    exit /b 1",
        ")",
        "",
        "echo.",
        "echo   All files downloaded and verified.",
        "echo.",
        f'set "JOINER=%HERE%\\REASSEMBLE_{ARCHIVE_STEM}.bat"',
        'if not exist "%JOINER%" goto :nojoiner',
        "echo   Next: the reassembler joins the parts, verifies the archive,",
        "echo   extracts it and applies the documentation patch.",
        "echo.",
        'set "GO="',
        'set /p "GO=Run it now? [Y/n] "',
        'if /i "!GO!"=="n" goto :manual',
        "echo.",
        'call "%JOINER%"',
        "goto :eof",
        "",
        ":manual",
        "echo.",
        f"echo   Run REASSEMBLE_{ARCHIVE_STEM}.bat",
        "echo   when you are ready.",
        "pause",
        "goto :eof",
        "",
        ":nojoiner",
        "echo   The reassembler is missing. Run this downloader again.",
        "pause",
        "goto :eof",
        "",
        "REM ---------------------------------------------------------------",
        "REM  %~1 name   %~2 expected SHA-256   %~3 index   %~4 total",
        "REM ---------------------------------------------------------------",
        ":fetch",
        'set "NAME=%~1"',
        'set "WANT=%~2"',
        'set "TARGET=%HERE%\\%NAME%"',
        "",
        'if not exist "%TARGET%" goto :download',
        "echo   [%~3/%~4] %NAME% - already here, checking...",
        'call :digest "%TARGET%"',
        'if /i "!GOT!"=="%WANT%" (',
        "    echo         verified, skipping.",
        "    goto :eof",
        ")",
        "echo         does not match, downloading again.",
        'del /f /q "%TARGET%" >nul 2>&1',
        "",
        ":download",
        "echo   [%~3/%~4] %NAME%",
        'curl.exe -L -C - --retry 5 --retry-delay 5 --retry-connrefused '
        '--progress-bar -o "%TARGET%" "%BASE%/%NAME%"',
        "if errorlevel 1 (",
        "    echo         download failed.",
        '    set "FAILED=!FAILED! %NAME%"',
        "    goto :eof",
        ")",
        'call :digest "%TARGET%"',
        'if /i not "!GOT!"=="%WANT%" (',
        "    echo         CHECKSUM MISMATCH - the file is damaged.",
        "    echo         expected %WANT%",
        "    echo         got      !GOT!",
        '    del /f /q "%TARGET%" >nul 2>&1',
        '    set "FAILED=!FAILED! %NAME%"',
        "    goto :eof",
        ")",
        "echo         verified.",
        "goto :eof",
        "",
        ":digest",
        'set "GOT="',
        "for /f \"skip=1 tokens=* delims=\" %%H in "
        "('certutil -hashfile \"%~1\" SHA256') do (",
        '    if not defined GOT set "GOT=%%H"',
        ")",
        'set "GOT=!GOT: =!"',
        "goto :eof",
        "",
    ))

    text = "\n".join(lines)

    # Batch files are CRLF even though repository source is LF.
    with open(DOWNLOADER, "w", newline="\r\n", encoding="ascii") as handle:
        handle.write(text)

    print(f"wrote {DOWNLOADER}")
    print(f"  {os.path.getsize(DOWNLOADER)} bytes")
    print(f"  SHA-256 {_digest(DOWNLOADER)}")
    print(f"  {len(assets)} assets, {gigabytes:.2f} GiB")
    for name, size, digest in assets:
        print(f"    {size:>13,}  {name}")


if __name__ == "__main__":
    build()
