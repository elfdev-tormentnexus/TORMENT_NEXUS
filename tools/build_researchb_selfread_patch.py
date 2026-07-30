"""Build the direct machinesoul self-read patch for researchB.

No ZIP or tar is created. The changed files, the two new modules, the
patch ledger and a guarded installer are preserved as a direct
machinesoul release field, decoded by the same public decompiler as the
main researchB install.

Unlike the researchA calibration patch, this one *adds* files as well as
replacing them, so it declares an action per record and ships
`apply_researchb_patch.py` rather than the researchA applier.
"""

from __future__ import annotations

import hashlib
import json
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


PATCH_ID = "researchB-self-read.1"
BASE_COMMIT = "567d4a87edd874ecfac44cb9dcb45ed8fece60b0"
BASE_PLAN_SHA256 = (
    "629fcff32152b6547de63ea00c6f161bff2d97690c5b1332ed64ab4e4df395c0"
)
PREFIX = "SABLERESEARCHB-SELFREAD-PATCH"

# Action per file, declared here rather than inferred at build time, so a
# mistake shows up as a refusal instead of as a silently different patch.
PATCH_FILES = (
    ("assistant/core/source_awareness.py", "add"),
    ("assistant/tests/test_source_awareness.py", "add"),
    ("assistant/main.py", "replace"),
    ("assistant/editing/edit_guard.py", "replace"),
    ("assistant/commands/command_handlers.py", "replace"),
)

WORK = ROOT / "SABLERESEARCHB"
BASE_MANIFEST = WORK / "MANIFEST_WINDOWS.json"
PATCH_STAGE = WORK / "SELFREAD_PATCH_STAGE"
OUT = WORK / "release"
PLAN = WORK / "CUT_PLAN_SELFREAD_PATCH.json"
REVIEW = WORK / "CUT_PLAN_SELFREAD_PATCH.md"
CUTMAP = WORK / "CUT_PLAN_SELFREAD_PATCH.png"
MANIFEST = WORK / "MANIFEST_SELFREAD_PATCH.json"
MANIFEST_CAPSULE = OUT / f"{PREFIX}-MANIFEST.png"
INSTALLER = OUT / "INSTALL_SABLERESEARCHB_SELFREAD_PATCH.bat"


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


PATCH_README = """# researchB self-read patch

This patch lets the assistant read its own source, and tells it what it
is made of before it is asked.

## Why

Asked what it had done to improve the vector panel, the assistant
described tooltips that appear on hover. This is a terminal program. It
has no hover, and no such work existed.

Sampled three times on the same opening, one reply in three claimed
ownership of work that had not happened. The fork was one token wide --
" working" against " glad" -- and it fell five tokens into the reply.
Everything after that token was fluent and wrong.

Measured on the bundled director, the confabulated reply scored a
*lower* mean candidate entropy than an honest open-ended one, 0.104
against 0.152. Nothing downstream can detect the failure once it starts,
which leaves prevention as the only available lever.

## What it changes

- A new `core/source_awareness.py` reads the project's own files, reports
  the shape of the source, the recent unattended edits, and what the
  weights file declares about itself.
- That block is injected into every turn's runtime context before
  generation begins. Grounding the model chooses to fetch would arrive
  after the decision to claim; this arrives before it.
- Two commands: `self` shows exactly what the model was told, and
  `read <path>` shows any project file as the assistant reads it.

## What it does not change

Reading is not editing. Every file protected from rewriting stays
protected; this patch only widens what may be read, and adds its own
module to the protected list in the same change.

Credentials are excluded. Weight files are refused as a read path and
reported as a header instead -- architecture, depth, width and
quantisation are legible and true, while the tensor data is neither
readable here nor interpretable by the model if it were.

The installer refuses any target file that is neither the exact researchB
version nor the already-patched version, and refuses to add a file where
something unrecognised already sits. Originals are copied under the
installation's `backups` folder before replacement, and
RELEASE_MANIFEST.json is updated with the new hashes, the two added
files, and this patch's identity.
"""


INSTALLER_TEMPLATE = r"""@echo off
setlocal EnableExtensions
set "HERE=%~dp0"
set "TARGET=%~1"
set "WORK=%TEMP%\SABLERESEARCHB_selfread_patch_%RANDOM%_%RANDOM%"
set "DECODER=%HERE%machinesoul.py"
set "REASSEMBLER_IMAGE=%HERE%SABLERESEARCHB-REASSEMBLER.png"
set "MANIFEST_IMAGE=%HERE%SABLERESEARCHB-SELFREAD-PATCH-MANIFEST.png"
set "PATCH_IMAGE=%HERE%SABLERESEARCHB-SELFREAD-PATCH.part01.png"

echo.
echo   SABLE researchB - self-read patch
echo   machinesoul decompile, exact reassembly, guarded install
echo.

if not defined TARGET if exist "%HERE%TORMENT_NEXUS-researchB\RELEASE_MANIFEST.json" set "TARGET=%HERE%TORMENT_NEXUS-researchB"
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

REM The recovered reassembler does a bare "import machinesoul", and it runs
REM from the work folder, so the decoder has to sit beside it. Omitting this
REM is what makes the researchA calibration patch installer fail at step 4;
REM DECOMPILE_SABLE_researchB.bat has always done it.
copy /y "%DECODER%" "%WORK%\machinesoul.py" >nul
if errorlevel 1 goto :failed

echo   [3/5] Decompiling the patch vector field...
python "%DECODER%" extract "%PATCH_IMAGE%" --out "%WORK%\segments\SABLERESEARCHB-SELFREAD-PATCH.part01.msv"
if errorlevel 1 goto :failed

echo   [4/5] Reassembling the patch files exactly...
python "%WORK%\machinesoul_release.py" reassemble "%WORK%\manifest.json" "%WORK%\segments" --out "%WORK%\payload"
if errorlevel 1 goto :failed

echo   [5/5] Checking the installed release and applying...
python "%WORK%\payload\APPLY_researchB_self_read_patch.py" --target "%TARGET%" --payload-root "%WORK%\payload"
if errorlevel 1 goto :failed

rmdir /s /q "%WORK%"
echo.
echo   Patch complete. Every replacement and addition verified against the
echo   release ledger. Your original files remain under TORMENT_NEXUS\backups.
echo.
echo   Try "self" to see what it now knows about itself.
echo.
pause
exit /b 0

:notarget
echo   I could not find the installed researchB folder.
echo   Put this file beside TORMENT_NEXUS-researchB, or drag that folder
echo   onto this installer, then try again. Nothing was changed.
goto :stop

:nopython
echo   Python 3 is required for the public machinesoul decompiler.
echo   Nothing was changed.
goto :stop

:missing
echo   A required machinesoul image or decompiler is missing.
echo   Keep all researchB release downloads together. Nothing was changed.
goto :stop

:workfail
echo   Could not create a private temporary work folder. Nothing was changed.
goto :stop

:failed
echo.
echo   Patch refused or failed verification. Nothing unknown was overwritten,
echo   and nothing new was left behind. Diagnostic files remain in:
echo   %WORK%

:stop
echo.
pause
exit /b 1
"""


def build_stage(head: str, base_records: dict) -> dict:
    if PATCH_STAGE.exists():
        raise SystemExit(f"refusing existing patch stage: {PATCH_STAGE}")
    PATCH_STAGE.mkdir(parents=True)

    records = []

    for relative, action in PATCH_FILES:
        patched = ROOT / Path(relative)
        key = relative.replace("\\", "/")
        original = base_records.get(key)

        if not patched.is_file():
            raise SystemExit(f"missing patch input: {relative}")

        if action == "replace":
            if original is None:
                raise SystemExit(
                    f"declared replace but the base cut lacks it: {relative}"
                )
            before = original["sha256"]
            after = sha256_file(patched)
            if before == after:
                raise SystemExit(f"patch input did not change: {relative}")
            record = {
                "path": key,
                "action": "replace",
                "before_sha256": before,
                "before_bytes": original["size"],
            }
        elif action == "add":
            if original is not None:
                raise SystemExit(
                    f"declared add but the base cut already has it: {relative}"
                )
            after = sha256_file(patched)
            record = {
                "path": key,
                "action": "add",
                "before_sha256": None,
                "before_bytes": None,
            }
        else:
            raise SystemExit(f"unknown action {action!r} for {relative}")

        record["after_sha256"] = after
        record["after_bytes"] = patched.stat().st_size

        destination = PATCH_STAGE / "payload" / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(patched, destination)
        records.append(record)

    shutil.copy2(
        TOOLS / "apply_researchb_patch.py",
        PATCH_STAGE / "APPLY_researchB_self_read_patch.py",
    )
    (PATCH_STAGE / "PATCH_README.md").write_text(
        PATCH_README,
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "format": "SABLERESEARCHB_PATCH1",
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

    if not BASE_MANIFEST.is_file():
        raise SystemExit(f"missing exact researchB manifest: {BASE_MANIFEST}")

    with BASE_MANIFEST.open(encoding="utf-8") as handle:
        base_manifest = json.load(handle)

    release._validate_manifest(base_manifest)

    if base_manifest.get("plan_sha256") != BASE_PLAN_SHA256:
        raise SystemExit("base manifest is not the approved researchB cut")

    base_records = {item["path"]: item for item in base_manifest["files"]}
    application_manifest = build_stage(head, base_records)
    OUT.mkdir(parents=True, exist_ok=True)

    for path in (PLAN, REVIEW, CUTMAP, MANIFEST, MANIFEST_CAPSULE, INSTALLER):
        if path.exists():
            raise SystemExit(f"refusing existing patch output: {path}")

    plan = release.make_plan(str(PATCH_STAGE), PREFIX)
    plan_sha = release.write_plan(plan, str(PLAN), str(REVIEW))
    release.render_plan_apng(str(PLAN), str(CUTMAP))
    cut_manifest = release.cut(str(PLAN), plan_sha, str(OUT), str(MANIFEST))

    if len(cut_manifest["capsules"]) != 1:
        raise SystemExit(
            f"self-read patch needs {len(cut_manifest['capsules'])} fields; "
            "the installer template decodes exactly one"
        )

    machinesoul.build_stream(
        str(MANIFEST),
        str(MANIFEST_CAPSULE),
        description=(
            "Verified direct manifest for the researchB self-read patch. "
            "Decode with machinesoul.py; the recovered reassembler uses it "
            "to restore the patch files exactly."
        ),
    )
    INSTALLER.write_text(INSTALLER_TEMPLATE, encoding="ascii", newline="\r\n")

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

    write_json(WORK / "SELFREAD_PATCH_BUILD_REPORT.json", report)

    print(f"patch source: {head}")
    print(f"plan sha256: {plan_sha}")
    for record in application_manifest["files"]:
        print(f"  {record['action']:<8} {record['path']}")
    for asset in report["assets"]:
        print(
            f"{asset['name']}: {asset['bytes']} bytes "
            f"sha256 {asset['sha256']}"
        )


if __name__ == "__main__":
    build()
