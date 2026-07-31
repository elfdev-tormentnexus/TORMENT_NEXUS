"""Generate the small, resumable downloader for a completed researchC cut.

This is deliberately a *post-cut* tool.  It reads the release directory that
will actually be uploaded, so the public fetcher cannot contain a remembered
part count or checksum.  Its output is a plain Windows batch file using the
built-in ``curl.exe`` and ``certutil`` tools, rather than an unsigned
executable that security software is likely to distrust.

The normal fetcher downloads only the required Windows installation.  The
optional 14B maintenance companion is intentionally excluded: it is large,
needs a deliberate choice, and remains available as separately listed release
assets.  ``--include-optional-14b`` can generate an explicitly named variant
only when an operator chooses to offer that path.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "researchC"
REPOSITORY = "elfdev-tormentnexus/TORMENT_NEXUS"
PREFIX = "SABLERESEARCHC"
DEFAULT_RELEASE_DIR = ROOT / PREFIX / "release"
DEFAULT_FETCHER_NAME = f"FETCH_{PREFIX}.bat"
OPTIONAL_FETCHER_NAME = f"FETCH_{PREFIX}_WITH_14B.bat"
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class FetcherError(RuntimeError):
    """The final release folder cannot truthfully produce a fetcher."""


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest().upper()


def _record(path: Path) -> tuple[str, int, str]:
    if not path.is_file():
        raise FetcherError(f"required release asset is missing: {path.name}")
    if not _SAFE_NAME.fullmatch(path.name):
        raise FetcherError(f"unsafe release asset name: {path.name!r}")
    return path.name, path.stat().st_size, _digest(path)


def _numbered_parts(release_dir: Path, stem: str) -> list[Path]:
    """Return one complete consecutive ``.partNN.png`` set, or refuse."""
    pattern = re.compile(re.escape(stem) + r"\.part(\d+)\.png\Z")
    parts: list[tuple[int, Path]] = []
    suspicious: list[str] = []
    for candidate in release_dir.iterdir():
        if not candidate.name.startswith(stem + "."):
            continue
        match = pattern.fullmatch(candidate.name)
        if match is None:
            suspicious.append(candidate.name)
            continue
        parts.append((int(match.group(1)), candidate))

    if suspicious:
        raise FetcherError(
            f"unexpected {stem} asset name(s): " + ", ".join(sorted(suspicious))
        )
    if not parts:
        raise FetcherError(f"no {stem}.partNN.png assets in {release_dir}")

    parts.sort(key=lambda item: item[0])
    expected = list(range(1, len(parts) + 1))
    actual = [number for number, _ in parts]
    if actual != expected:
        raise FetcherError(
            f"{stem} parts are not consecutive from 01: "
            + ", ".join(f"{number:02d}" for number in actual)
        )
    return [path for _, path in parts]


def discover_assets(
    release_dir: str | os.PathLike[str], *, include_optional_14b: bool = False
) -> list[tuple[str, int, str]]:
    """Discover required public assets and bind them to current SHA-256s."""
    folder = Path(release_dir)
    if not folder.is_dir():
        raise FetcherError(f"release directory does not exist: {folder}")

    required = [
        folder / "machinesoul.py",
        folder / f"DECOMPILE_SABLE_{RELEASE_VERSION}.bat",
        folder / f"{PREFIX}-MANIFEST.png",
        folder / f"{PREFIX}-REASSEMBLER.png",
        *_numbered_parts(folder, f"{PREFIX}-WINDOWS"),
    ]
    if include_optional_14b:
        required.extend(_numbered_parts(folder, f"{PREFIX}-14B"))
    return [_record(path) for path in required]


def _batch_text(
    assets: list[tuple[str, int, str]], *, tag: str, include_optional_14b: bool
) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", tag):
        raise FetcherError(f"unsafe GitHub release tag: {tag!r}")

    total_bytes = sum(size for _, size, _ in assets)
    total_gib = total_bytes / (1024 ** 3)
    base = f"https://github.com/{REPOSITORY}/releases/download/{tag}"
    lines = [
        "@echo off",
        # Delayed expansion corrupts otherwise-valid Windows paths containing
        # ``!``.  Asset names are constrained above, and the subroutines below
        # are deliberately structured so ordinary percent expansion is safe.
        "setlocal EnableExtensions DisableDelayedExpansion",
        'set "HERE=%~dp0"',
        'if "%HERE:~-1%"=="\\" set "HERE=%HERE:~0,-1%"',
        f'set "BASE={base}"',
        'set "FAILED="',
        "",
        "echo.",
        f"echo   TORMENT_NEXUS {RELEASE_VERSION} - verified capsule fetcher",
        "echo.",
        f"echo   This downloads {len(assets)} required release assets ({total_gib:.1f} GiB)",
        "echo   into this folder, resumes interrupted transfers, and verifies",
        "echo   each file against the SHA-256 recorded at the cut.",
        "echo.",
        "echo   Do not screenshot, optimise, or re-encode a capsule image.",
        "echo   Its ordered pixels are the payload and machinesoul verifies them.",
        "echo.",
    ]
    if include_optional_14b:
        lines.extend((
            "echo   This explicitly includes the optional 14B maintenance companion.",
            "echo   It needs additional disk space and is not required for ordinary use.",
            "echo.",
        ))
    else:
        lines.extend((
            "echo   The optional 14B maintenance companion is not included here.",
            "echo   Download its numbered capsules separately only if you want it.",
            "echo.",
        ))
    lines.extend((
        "pause",
        "",
        "where curl.exe >nul 2>&1",
        "if errorlevel 1 (",
        "    echo   curl.exe was not found. It ships with Windows 10 1803 and later.",
        f"    echo   Download the release assets manually: https://github.com/{REPOSITORY}/releases/tag/{tag}",
        "    pause",
        "    exit /b 1",
        ")",
        "",
    ))
    for number, (name, size, digest) in enumerate(assets, 1):
        lines.extend((
            f'call :fetch "{name}" "{digest}" {size} {number} {len(assets)}',
            'if errorlevel 1 call set "FAILED=%%FAILED%% %s"' % name,
        ))
    lines.extend((
        "",
        "if defined FAILED (",
        "    echo.",
        "    echo   These assets did not download or verify:",
        "    echo   %FAILED%",
        "    echo.",
        "    echo   Run this fetcher again. Verified files are skipped; only",
        "    echo   missing or damaged files are retried.",
        "    pause",
        "    exit /b 1",
        ")",
        "",
        "echo.",
        "echo   Every required asset downloaded and SHA-256 verified.",
        f"echo   Next: double-click DECOMPILE_SABLE_{RELEASE_VERSION}.bat",
        "pause",
        "exit /b 0",
        "",
        ":fetch",
        'set "NAME=%~1"',
        'set "WANT=%~2"',
        'set "SIZE=%~3"',
        'set "TARGET=%HERE%\\%NAME%"',
        'set "PART=%HERE%\\%NAME%.partial"',
        "",
        'if not exist "%TARGET%" goto :check_partial',
        "echo   [%~4/%~5] %NAME% - already here, checking...",
        'call :digest "%TARGET%"',
        'call :matches "%WANT%"',
        "if not errorlevel 1 goto :verified_existing",
        "echo         checksum mismatch; removing damaged file.",
        'del /f /q "%TARGET%" >nul 2>&1',
        "",
        ":check_partial",
        'if not exist "%PART%" goto :download',
        'call :digest "%PART%"',
        'call :matches "%WANT%"',
        "if not errorlevel 1 goto :promote",
        'for %%Z in ("%PART%") do set "PART_SIZE=%%~zZ"',
        'if "%PART_SIZE%"=="%SIZE%" goto :restart_partial',
        "echo         resuming existing %PART_SIZE%-byte partial file.",
        "goto :download",
        "",
        ":restart_partial",
        "echo         complete-size partial failed verification; restarting it.",
        'del /f /q "%PART%" >nul 2>&1',
        "",
        ":download",
        "echo   [%~4/%~5] %NAME%",
        'curl.exe --fail -L -C - --retry 5 --retry-delay 5 --retry-connrefused --progress-bar -o "%PART%" "%BASE%/%NAME%"',
        "if errorlevel 1 goto :download_failed",
        'call :digest "%PART%"',
        'call :matches "%WANT%"',
        "if errorlevel 1 goto :checksum_failed",
        "",
        ":promote",
        'move /y "%PART%" "%TARGET%" >nul',
        "if errorlevel 1 goto :promote_failed",
        "echo         verified.",
        "exit /b 0",
        "",
        ":verified_existing",
        'if exist "%PART%" del /f /q "%PART%" >nul 2>&1',
        "echo         verified, skipping.",
        "exit /b 0",
        "",
        ":download_failed",
        "echo         download interrupted; keeping the partial file for resume.",
        "exit /b 1",
        "",
        ":checksum_failed",
        "echo         CHECKSUM MISMATCH - removing damaged partial file.",
        'del /f /q "%PART%" >nul 2>&1',
        "exit /b 1",
        "",
        ":promote_failed",
        "echo         verified download could not be moved into place.",
        "exit /b 1",
        "",
        ":digest",
        'set "GOT="',
        "for /f \"skip=1 tokens=* delims=\" %%H in ('certutil -hashfile \"%~1\" SHA256') do (",
        '    if not defined GOT set "GOT=%%H"',
        ")",
        'call set "GOT=%%GOT: =%%"',
        "exit /b 0",
        "",
        ":matches",
        'if /i "%GOT%"=="%~1" exit /b 0',
        "exit /b 1",
        "",
    ))
    return "\r\n".join(lines)


def build(
    release_dir: str | os.PathLike[str], *, tag: str = RELEASE_VERSION,
    out_path: str | os.PathLike[str] | None = None,
    include_optional_14b: bool = False,
) -> Path:
    """Write the fetcher beside the final assets, replacing only itself."""
    folder = Path(release_dir)
    assets = discover_assets(folder, include_optional_14b=include_optional_14b)
    output = Path(out_path) if out_path is not None else folder / (
        OPTIONAL_FETCHER_NAME if include_optional_14b else DEFAULT_FETCHER_NAME
    )
    if output.parent.resolve() != folder.resolve():
        raise FetcherError("fetcher output must stay beside the release assets")
    if output.name not in {DEFAULT_FETCHER_NAME, OPTIONAL_FETCHER_NAME}:
        raise FetcherError("fetcher output must use the published versioned name")

    text = _batch_text(assets, tag=tag, include_optional_14b=include_optional_14b)
    descriptor, temporary = tempfile.mkstemp(
        prefix=output.name + ".", suffix=".tmp", dir=folder, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="") as handle:
            handle.write(text)
        os.replace(temporary, output)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--release-dir", default=str(DEFAULT_RELEASE_DIR),
        help="completed Research C release asset directory",
    )
    parser.add_argument(
        "--tag", default=RELEASE_VERSION,
        help="GitHub Release tag the generated fetcher downloads",
    )
    parser.add_argument(
        "--include-optional-14b", action="store_true",
        help="generate the explicitly named variant that also downloads 14B",
    )
    args = parser.parse_args(argv)
    try:
        output = build(
            args.release_dir, tag=args.tag,
            include_optional_14b=args.include_optional_14b,
        )
    except FetcherError as exc:
        parser.exit(1, f"researchC fetcher failed: {exc}\n")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
