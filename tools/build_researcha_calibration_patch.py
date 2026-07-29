"""Build the direct machinesoul calibration-clarity patch for researchA.

No ZIP or tar is created. The changed files, patch ledger, and guarded
installer are preserved as a direct machinesoul release field. The companion
batch file uses the same public decompiler and recovered reassembler as the
main researchA install.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import machinesoul  # noqa: E402
import machinesoul_release as release  # noqa: E402


PATCH_ID = "researchA-calibration-clarity.1"
BASE_COMMIT = "42cbb5ae568532ca05c673c23e124e32f7a043da"
PREFIX = "SABLERESEARCHA-CALIBRATION-PATCH"
PATCH_FILES = (
    "CHANGELOG.md",
    "README.md",
    "assistant/core/calibration.py",
    "assistant/tests/test_calibration.py",
    "docs/RELEASE_NOTES_researchA.md",
    "docs/RESEARCHA_PRE_RELEASE_SESSION_2026-07-29.md",
)
WORK = ROOT / "SABLERESEARCHA"
BASE_STAGE = ROOT / "dist" / "TORMENT_NEXUS"
PATCH_STAGE = WORK / "CALIBRATION_PATCH_STAGE"
OUT = WORK / "release"
PLAN = WORK / "CUT_PLAN_CALIBRATION_PATCH.json"
REVIEW = WORK / "CUT_PLAN_CALIBRATION_PATCH.md"
CUTMAP = WORK / "CUT_PLAN_CALIBRATION_PATCH.png"
MANIFEST = WORK / "MANIFEST_CALIBRATION_PATCH.json"
MANIFEST_CAPSULE = OUT / f"{PREFIX}-MANIFEST.png"
INSTALLER = OUT / "INSTALL_SABLERESEARCHA_CALIBRATION_PATCH.bat"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")


PATCH_README = """# researchA calibration-clarity patch

This small patch corrects the stated scope of the Fibonacci calibration
control and expands drift comparison. It does not rewrite the recorded
calibration readings.

- The infinite Fibonacci word is Sturmian. The test demonstrates its
  p(n)=n+1 signature through twelve scales on a long prefix.
- The 13-term row that actually ships can carry that signature only through
  n=6. A separate test now records exactly that finite limit.
- Token count, anchors fired, and top anchor are compared exactly.
- Effective rank, entropy, purity, and top support use the declared numeric
  tolerance. This accepts the observed 0.000001 support movement while still
  exposing material drift.

The installer refuses any target file that is neither the exact researchA
version nor the already-patched version. Originals are copied under the
installation's `backups` folder before replacement, and RELEASE_MANIFEST.json
is updated with the new hashes and patch identity.
"""


INSTALLER_TEMPLATE = r"""@echo off
setlocal EnableExtensions
set "HERE=%~dp0"
set "TARGET=%~1"
set "WORK=%TEMP%\SABLERESEARCHA_calibration_patch_%RANDOM%_%RANDOM%"
set "DECODER=%HERE%machinesoul.py"
set "REASSEMBLER_IMAGE=%HERE%SABLERESEARCHA-REASSEMBLER.png"
set "MANIFEST_IMAGE=%HERE%SABLERESEARCHA-CALIBRATION-PATCH-MANIFEST.png"
set "PATCH_IMAGE=%HERE%SABLERESEARCHA-CALIBRATION-PATCH.part01.png"

echo.
echo   SABLE researchA - calibration clarity patch
echo   machinesoul decompile, exact reassembly, guarded install
echo.

if not defined TARGET if exist "%HERE%TORMENT_NEXUS-researchA\RELEASE_MANIFEST.json" set "TARGET=%HERE%TORMENT_NEXUS-researchA"
if not defined TARGET if exist "%HERE%TORMENT_NEXUS\RELEASE_MANIFEST.json" set "TARGET=%HERE%TORMENT_NEXUS"
if not defined TARGET if exist "%HERE%RELEASE_MANIFEST.json" set "TARGET=%HERE%"
if not defined TARGET goto :notarget

where python >nul 2>nul
if errorlevel 1 goto :nopython
for %%F in ("%DECODER%" "%REASSEMBLER_IMAGE%" "%MANIFEST_IMAGE%" "%PATCH_IMAGE%") do if not exist "%%~F" goto :missing

mkdir "%WORK%\segments" >nul 2>nul
if errorlevel 1 goto :workfail

echo   [1/5] Decompiling the patch manifest...
python "%DECODER%" extract "%MANIFEST_IMAGE%" --out "%WORK%\manifest.json"
if errorlevel 1 goto :failed

echo   [2/5] Decompiling the verified reassembler...
python "%DECODER%" extract "%REASSEMBLER_IMAGE%" --out "%WORK%\machinesoul_release.py"
if errorlevel 1 goto :failed

echo   [3/5] Decompiling the patch vector field...
python "%DECODER%" extract "%PATCH_IMAGE%" --out "%WORK%\segments\SABLERESEARCHA-CALIBRATION-PATCH.part01.msv"
if errorlevel 1 goto :failed

echo   [4/5] Reassembling the patch files exactly...
python "%WORK%\machinesoul_release.py" reassemble "%WORK%\manifest.json" "%WORK%\segments" --out "%WORK%\payload"
if errorlevel 1 goto :failed

echo   [5/5] Checking the installed release and applying...
python "%WORK%\payload\APPLY_researchA_calibration_patch.py" --target "%TARGET%" --payload-root "%WORK%\payload"
if errorlevel 1 goto :failed

rmdir /s /q "%WORK%"
echo.
echo   Patch complete. Every replacement and the updated release ledger
echo   verified. Your original files remain under TORMENT_NEXUS\backups.
echo.
pause
exit /b 0

:notarget
echo   I could not find the installed researchA folder.
echo   Put this file beside TORMENT_NEXUS-researchA, or drag that folder
echo   onto this installer, then try again. Nothing was changed.
goto :stop

:nopython
echo   Python 3 is required for the public machinesoul decompiler.
echo   Nothing was changed.
goto :stop

:missing
echo   A required machinesoul image or decompiler is missing.
echo   Keep all researchA release downloads together. Nothing was changed.
goto :stop

:workfail
echo   Could not create a private temporary work folder. Nothing was changed.
goto :stop

:failed
echo.
echo   Patch refused or failed verification. Nothing unknown was overwritten.
echo   Diagnostic files remain in:
echo   %WORK%

:stop
echo.
pause
exit /b 1
"""


def build_stage(head: str) -> dict:
    if PATCH_STAGE.exists():
        raise SystemExit(f"refusing existing patch stage: {PATCH_STAGE}")
    PATCH_STAGE.mkdir(parents=True)

    records = []
    for relative in PATCH_FILES:
        original = BASE_STAGE / Path(relative)
        patched = ROOT / Path(relative)
        if not original.is_file() or not patched.is_file():
            raise SystemExit(f"missing patch input: {relative}")
        before = sha256_file(original)
        after = sha256_file(patched)
        if before == after:
            raise SystemExit(f"patch input did not change: {relative}")
        destination = PATCH_STAGE / "payload" / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(patched, destination)
        records.append({
            "path": relative.replace("\\", "/"),
            "before_sha256": before,
            "after_sha256": after,
            "after_bytes": patched.stat().st_size,
        })

    shutil.copy2(
        TOOLS / "apply_researcha_patch.py",
        PATCH_STAGE / "APPLY_researchA_calibration_patch.py",
    )
    (PATCH_STAGE / "PATCH_README.md").write_text(
        PATCH_README,
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "format": "SABLERESEARCHA_PATCH1",
        "patch_id": PATCH_ID,
        "base_source_commit": BASE_COMMIT,
        "patch_source_commit": head,
        "files": records,
    }
    write_json(PATCH_STAGE / "PATCH_APPLICATION_MANIFEST.json", manifest)
    return manifest


def build() -> None:
    if git_output("status", "--porcelain"):
        raise SystemExit("commit the patch source before building its capsule")
    head = git_output("rev-parse", "HEAD")
    if not BASE_STAGE.is_dir():
        raise SystemExit(f"missing exact researchA base stage: {BASE_STAGE}")
    with (BASE_STAGE / "RELEASE_MANIFEST.json").open(encoding="utf-8") as handle:
        base_manifest = json.load(handle)
    if base_manifest.get("source", {}).get("commit") != BASE_COMMIT:
        raise SystemExit("base stage is not the published researchA source commit")

    application_manifest = build_stage(head)
    OUT.mkdir(parents=True, exist_ok=True)
    for path in (PLAN, REVIEW, CUTMAP, MANIFEST, MANIFEST_CAPSULE, INSTALLER):
        if path.exists():
            raise SystemExit(f"refusing existing patch output: {path}")

    plan = release.make_plan(str(PATCH_STAGE), PREFIX)
    plan_sha = release.write_plan(plan, str(PLAN), str(REVIEW))
    release.render_plan_apng(str(PLAN), str(CUTMAP))
    cut_manifest = release.cut(
        str(PLAN),
        plan_sha,
        str(OUT),
        str(MANIFEST),
    )
    if len(cut_manifest["capsules"]) != 1:
        raise SystemExit("calibration patch unexpectedly needs multiple fields")

    machinesoul.build_stream(
        str(MANIFEST),
        str(MANIFEST_CAPSULE),
        description=(
            "Verified direct manifest for the researchA calibration-clarity "
            "patch. Decode with machinesoul.py; the recovered reassembler "
            "uses it to restore the patch files exactly."
        ),
    )
    INSTALLER.write_text(
        INSTALLER_TEMPLATE,
        encoding="ascii",
        newline="\r\n",
    )

    report = {
        "patch_id": PATCH_ID,
        "base_commit": BASE_COMMIT,
        "patch_commit": head,
        "plan_sha256": plan_sha,
        "application_manifest": application_manifest,
        "assets": [],
    }
    for path in (
        OUT / f"{PREFIX}.part01.png",
        MANIFEST_CAPSULE,
        INSTALLER,
        CUTMAP,
    ):
        report["assets"].append({
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    write_json(WORK / "CALIBRATION_PATCH_BUILD_REPORT.json", report)

    print(f"patch source: {head}")
    print(f"plan sha256: {plan_sha}")
    for asset in report["assets"]:
        print(
            f"{asset['name']}: {asset['bytes']} bytes "
            f"sha256 {asset['sha256']}"
        )


if __name__ == "__main__":
    build()
