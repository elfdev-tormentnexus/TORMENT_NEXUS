"""Generate the one-click Research B decompiler from the final cut manifest.

The launcher is a post-cut artifact.  It learns every capsule and decoded
segment name from the combined manifest rather than from a remembered part
count, and it refuses a partial optional 14B set.  The public launcher remains
plain batch because it must bootstrap the machinesoul decompiler before any
encoded release tool can be recovered.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "researchB"
PREFIX = "SABLERESEARCHB"
COMBINED_FORMAT = "SABLERESEARCHA_MANIFEST1"  # published wire format
COMPONENT_FORMAT = "MACHINESOUL_RELEASE1"
DEFAULT_RELEASE_DIR = ROOT / PREFIX / "release"
DEFAULT_MANIFEST = ROOT / PREFIX / "MANIFEST_COMBINED.json"
OUTPUT_NAME = f"DECOMPILE_SABLE_{RELEASE_VERSION}.bat"
# Python packages legitimately contain ``__init__.py`` and other
# underscore-led leaves.  The separator and dot-segment checks below provide
# the traversal boundary; requiring the first character to be alphanumeric
# rejected the real post-cut manifest while adding no safety.
_SAFE_LEAF = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*\Z")


class DecompilerError(RuntimeError):
    """The final cut cannot truthfully produce its one-click launcher."""


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DecompilerError(f"unsafe manifest path: {value!r}")
    pieces = value.split("/")
    if any(not _SAFE_LEAF.fullmatch(piece) or piece in {".", ".."} for piece in pieces):
        raise DecompilerError(f"unsafe manifest path: {value!r}")
    return value


def _component(manifest: dict, name: str, prefix: str) -> dict:
    components = manifest.get("components")
    if not isinstance(components, dict) or not isinstance(components.get(name), dict):
        raise DecompilerError(f"combined manifest is missing {name}")
    component = components[name]
    if component.get("format") != COMPONENT_FORMAT:
        raise DecompilerError(f"{name} is not a machinesoul release manifest")
    if component.get("prefix") != prefix:
        raise DecompilerError(f"{name} manifest has the wrong capsule prefix")

    capsules = component.get("capsules")
    files = component.get("files")
    if not isinstance(capsules, list) or not capsules:
        raise DecompilerError(f"{name} manifest contains no capsules")
    if not isinstance(files, list) or not files:
        raise DecompilerError(f"{name} manifest contains no files")

    expected_numbers = list(range(1, len(capsules) + 1))
    actual_numbers = []
    seen_decoded = set()
    pattern = re.compile(re.escape(prefix) + r"\.part(\d+)\.png\Z")
    for capsule in capsules:
        if not isinstance(capsule, dict):
            raise DecompilerError(f"invalid {name} capsule record")
        capsule_name = capsule.get("name")
        decoded_name = capsule.get("decoded_name")
        match = pattern.fullmatch(capsule_name or "")
        if match is None or not _SAFE_LEAF.fullmatch(decoded_name or ""):
            raise DecompilerError(f"unsafe {name} capsule record")
        actual_numbers.append(int(match.group(1)))
        if decoded_name in seen_decoded:
            raise DecompilerError(f"duplicate decoded segment: {decoded_name}")
        seen_decoded.add(decoded_name)
    if actual_numbers != expected_numbers:
        raise DecompilerError(f"{name} capsule parts are not consecutive from 01")

    file_paths = []
    for record in files:
        if not isinstance(record, dict):
            raise DecompilerError(f"invalid {name} file record")
        file_paths.append(_safe_relative(record.get("path")))
    if len(file_paths) != len(set(file_paths)):
        raise DecompilerError(f"{name} manifest contains duplicate file paths")
    return component


def inspect_manifest(manifest_path: str | os.PathLike[str]) -> tuple[dict, dict]:
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DecompilerError(f"cannot read combined manifest: {error}") from error
    if manifest.get("format") != COMBINED_FORMAT:
        raise DecompilerError("not the published combined machinesoul manifest")

    windows = _component(manifest, "windows", f"{PREFIX}-WINDOWS")
    optional = _component(manifest, "optional_14b", f"{PREFIX}-14B")
    windows_paths = {_safe_relative(item["path"]) for item in windows["files"]}
    optional_paths = {_safe_relative(item["path"]) for item in optional["files"]}
    if "setup.bat" not in windows_paths:
        raise DecompilerError("Windows component does not contain setup.bat")
    if windows_paths & optional_paths:
        raise DecompilerError("optional 14B files overlap the Windows component")
    if any(not path.startswith("models/") for path in optional_paths):
        raise DecompilerError("optional 14B component must install below models/")
    return windows, optional


def _batch_text(windows: dict, optional: dict) -> str:
    windows_capsules = [
        (item["name"], item["decoded_name"]) for item in windows["capsules"]
    ]
    optional_capsules = [
        (item["name"], item["decoded_name"]) for item in optional["capsules"]
    ]
    optional_files = sorted(_safe_relative(item["path"]) for item in optional["files"])

    lines = [
        "@echo off",
        "setlocal EnableExtensions DisableDelayedExpansion",
        f"title TORMENT_NEXUS {RELEASE_VERSION} - machinesoul installer",
        'set "HERE=%~dp0"',
        'if "%HERE:~-1%"=="\\" set "HERE=%HERE:~0,-1%"',
        'set "DECODER=%HERE%\\machinesoul.py"',
        f'set "MANIFEST_IMAGE=%HERE%\\{PREFIX}-MANIFEST.png"',
        f'set "REASSEMBLER_IMAGE=%HERE%\\{PREFIX}-REASSEMBLER.png"',
        f'set "WORK=%HERE%\\.{PREFIX}-decompile-work"',
        f'set "TARGET=%HERE%\\TORMENT_NEXUS-{RELEASE_VERSION}"',
        "set \"OPTIONAL_PRESENT=\"",
        "set \"OPTIONAL_MISSING=\"",
        "",
        "echo.",
        f"echo   TORMENT_NEXUS {RELEASE_VERSION} - machinesoul decompiler and installer",
        "echo   This reconstructs and verifies the installation directly from",
        "echo   the lossless PNG/APNG vector fields, then runs setup.bat.",
        "echo.",
        "pause",
        "where python >nul 2>&1",
        "if errorlevel 1 goto :no_python",
        'if not exist "%DECODER%" goto :missing_required',
        'if not exist "%MANIFEST_IMAGE%" goto :missing_required',
        'if not exist "%REASSEMBLER_IMAGE%" goto :missing_required',
    ]
    for capsule, _decoded in windows_capsules:
        lines.append(f'if not exist "%HERE%\\{capsule}" goto :missing_required')
    for capsule, _decoded in optional_capsules:
        lines.extend((
            f'if exist "%HERE%\\{capsule}" set "OPTIONAL_PRESENT=1"',
            f'if not exist "%HERE%\\{capsule}" set "OPTIONAL_MISSING=1"',
        ))
    lines.extend((
        "if defined OPTIONAL_PRESENT if defined OPTIONAL_MISSING goto :partial_optional",
        'if exist "%TARGET%" goto :target_exists',
        'if exist "%WORK%" rmdir /s /q "%WORK%"',
        'mkdir "%WORK%\\segments"',
        "if errorlevel 1 goto :failed",
        "",
        "echo   [1/5] Recovering the manifest and reassembler...",
        'python "%DECODER%" extract "%MANIFEST_IMAGE%" --out "%WORK%\\manifest.json"',
        "if errorlevel 1 goto :failed",
        'python "%DECODER%" extract "%REASSEMBLER_IMAGE%" --out "%WORK%\\machinesoul_release.py"',
        "if errorlevel 1 goto :failed",
        'copy /y "%DECODER%" "%WORK%\\machinesoul.py" >nul',
        "if errorlevel 1 goto :failed",
        "",
        "echo   [2/5] Decompiling the required Windows vector fields...",
    ))
    for capsule, decoded in windows_capsules:
        lines.extend((
            f'python "%DECODER%" extract "%HERE%\\{capsule}" --out "%WORK%\\segments\\{decoded}"',
            "if errorlevel 1 goto :failed",
        ))
    lines.extend((
        "",
        "echo   [3/5] Reassembling and verifying the installation tree...",
        'python "%WORK%\\machinesoul_release.py" reassemble "%WORK%\\manifest.json" "%WORK%\\segments" --out "%TARGET%" --component windows',
        "if errorlevel 1 goto :failed",
        "if not defined OPTIONAL_PRESENT goto :run_setup",
        "",
        "echo   [4/5] Decompiling and installing the optional 14B companion...",
    ))
    for capsule, decoded in optional_capsules:
        lines.extend((
            f'python "%DECODER%" extract "%HERE%\\{capsule}" --out "%WORK%\\segments\\{decoded}"',
            "if errorlevel 1 goto :failed",
        ))
    lines.extend((
        'python "%WORK%\\machinesoul_release.py" reassemble "%WORK%\\manifest.json" "%WORK%\\segments" --out "%WORK%\\optional_14b" --component optional_14b',
        "if errorlevel 1 goto :failed",
    ))
    for relative in optional_files:
        windows_relative = relative.replace("/", "\\")
        parent = relative.rsplit("/", 1)[0].replace("/", "\\")
        lines.extend((
            f'if exist "%TARGET%\\{windows_relative}" goto :optional_collision',
            f'if not exist "%TARGET%\\{parent}" mkdir "%TARGET%\\{parent}"',
            f'move /y "%WORK%\\optional_14b\\{windows_relative}" "%TARGET%\\{windows_relative}" >nul',
            "if errorlevel 1 goto :failed",
        ))
    lines.extend((
        "",
        ":run_setup",
        "echo   [5/5] Running the verified setup...",
        'call "%TARGET%\\setup.bat"',
        "if errorlevel 1 goto :setup_failed",
        'rmdir /s /q "%WORK%"',
        "echo.",
        "echo   Installation complete. Every reconstructed file passed its digest.",
        "pause",
        "exit /b 0",
        "",
        ":no_python",
        "echo   Python 3 was not found. Install standard Python 3 and rerun this file.",
        "goto :refused",
        "",
        ":missing_required",
        "echo   A required machinesoul capsule or bootstrap file is missing.",
        "goto :refused",
        "",
        ":partial_optional",
        "echo   Only part of the optional 14B capsule set is present.",
        "echo   Download all optional parts or remove all of them, then rerun.",
        "goto :refused",
        "",
        ":target_exists",
        f"echo   TORMENT_NEXUS-{RELEASE_VERSION} already exists beside this launcher.",
        "echo   Nothing was overwritten. Move or remove that exact folder before retrying.",
        "goto :refused",
        "",
        ":optional_collision",
        "echo   The optional model would overwrite an existing reconstructed file.",
        "goto :failed",
        "",
        ":setup_failed",
        "echo   Reconstruction passed, but setup.bat reported a failure.",
        "echo   The verified installation folder was kept so setup can be diagnosed.",
        'if exist "%WORK%" rmdir /s /q "%WORK%"',
        "pause",
        "exit /b 1",
        "",
        ":failed",
        "echo   Decompilation or reassembly was refused. No incomplete tree is presented as complete.",
        'if exist "%WORK%" rmdir /s /q "%WORK%"',
        "",
        ":refused",
        "pause",
        "exit /b 1",
        "",
    ))
    return "\r\n".join(lines)


def build(
    release_dir: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
    *,
    out_path: str | os.PathLike[str] | None = None,
) -> Path:
    folder = Path(release_dir)
    if not folder.is_dir():
        raise DecompilerError(f"release directory does not exist: {folder}")
    windows, optional = inspect_manifest(manifest_path)

    required = [
        "machinesoul.py",
        f"{PREFIX}-MANIFEST.png",
        f"{PREFIX}-REASSEMBLER.png",
        *(item["name"] for item in windows["capsules"]),
        *(item["name"] for item in optional["capsules"]),
    ]
    for name in required:
        if not (folder / name).is_file():
            raise DecompilerError(f"required final release asset is missing: {name}")

    output = Path(out_path) if out_path is not None else folder / OUTPUT_NAME
    if output.parent.resolve() != folder.resolve() or output.name != OUTPUT_NAME:
        raise DecompilerError("decompiler output must use its published name beside the assets")
    text = _batch_text(windows, optional)
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
    parser.add_argument("--release-dir", default=str(DEFAULT_RELEASE_DIR))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args(argv)
    try:
        output = build(args.release_dir, args.manifest)
    except DecompilerError as error:
        parser.exit(1, f"researchB decompiler failed: {error}\n")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
