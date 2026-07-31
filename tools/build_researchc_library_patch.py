"""Build the direct machinesoul offline-library patch for researchC.

Same shape as the researchB self-read patch: no ZIP or tar, the payload and
a guarded installer are preserved as a machinesoul release field and decoded
by the same public decompiler as the main researchC install.

Two things differ, both forced by what this patch carries.

The researchB patch declared every file by hand in a tuple, so a mistake
surfaced as a refusal rather than as a silently different patch. A corpus of
eighteen thousand files cannot be hand-declared, so the declaration moves up
one level: the root below is declared, every file under it is an "add", and
the build refuses if any staged file falls outside that root or if any of
them already exists in the approved base cut. The guarantee is unchanged --
this patch can still never overwrite something it did not write -- but it is
asserted over a subtree instead of a list.

The researchB builder also refused to run against a dirty working tree, so
that the recorded source commit described the shipped bytes. Here no shipped
byte comes from the repository: the corpus is vendored third-party material
that is deliberately untracked, and demanding it be committed would be
demanding the wrong thing. The gate is narrowed rather than dropped -- the
two tool files that define this patch must be committed, so the code that
built it is pinned -- and the payload itself is pinned by the plan SHA-256
that the cutter requires.
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


PATCH_ID = "researchC-library.1"
BASE_COMMIT = "a774140bdccce23aa39c0e562bb0685e7fab435e"
BASE_PLAN_SHA256 = (
    "b9e6a4c8f8156bf74dac0cff4ac0e9c930a390f697901ed09fac9f6a7c0c0c2c"
)
PREFIX = "SABLERESEARCHC-LIBRARY-PATCH"

# Declared, not inferred. Everything the patch installs must sit under this
# root, and everything under it is an "add".
PATCH_ROOT = "assistant/knowledge/user_library/security/"

# The tool files that define this patch. Committed before a build, so the
# build is reproducible from a named commit even though its payload is not
# in the repository.
PINNED_TOOLS = (
    "tools/build_researchc_library_patch.py",
    "tools/apply_researchc_patch.py",
)

WORK = ROOT.parent / "SABLERESEARCHC"
SOURCE = WORK / "stage-library"
BASE_MANIFEST = WORK / "MANIFEST_WINDOWS.json"
PATCH_STAGE = WORK / "LIBRARY_PATCH_STAGE"
OUT = WORK / "release-library"
PLAN = WORK / "CUT_PLAN_LIBRARY_PATCH.json"
REVIEW = WORK / "CUT_PLAN_LIBRARY_PATCH.md"
CUTMAP = WORK / "CUT_PLAN_LIBRARY_PATCH.png"
MANIFEST = WORK / "MANIFEST_LIBRARY_PATCH.json"
MANIFEST_CAPSULE = OUT / f"{PREFIX}-MANIFEST.png"
INSTALLER = OUT / "INSTALL_SABLERESEARCHC_LIBRARY_PATCH.bat"
APPLIER_NAME = "APPLY_researchC_library_patch.py"


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


PATCH_README = """# researchC offline library patch

This patch installs the offline reference library the assistant reads when
it is asked something the bundled director does not reliably know.

## Why

The shipped director is a 4B model. It is small enough to run on the target
hardware and small enough to be confidently wrong about specifics -- kernel
interfaces, detection-rule syntax, algorithm details, incident procedure.
Those are not gaps a larger prompt closes; they are gaps in the weights.

The library closes them from the outside. Retrieval puts the actual text in
front of the model before it answers, so the answer is grounded in a
document that can be cited and checked rather than in a recollection that
cannot. This is the same lever as the researchB self-read patch, pointed at
the world instead of at the source.

## What it installs

Reference corpora under `assistant/knowledge/user_library/security/`:

- Linux kernel documentation
- SigmaHQ detection rules
- TheAlgorithms/Python
- YARA rules
- rstacruz cheatsheets
- MITRE ATT&CK and D3FEND
- CISA and NIST incident-response and testing publications

Every corpus keeps its own licence file where upstream provides one.
`NOTICES.md` in that folder is the ledger, and it records one unresolved
gap rather than papering over it: the cheatsheets corpus carries no licence
declaration at all. Availability is not permission. It ships deliberately,
with the gap recorded, and it can be deleted on its own without affecting
anything else.

## What it does not change

Nothing. Every record in this patch is an "add", and the installer refuses
to write over a file it did not put there. No existing file is replaced, so
the installed release stays byte-identical to the published cut apart from
the new material and the ledger entries describing it.

## After installing

Run `library rebuild` once. The library walks `user_library` itself, so the
rebuild is what indexes the new corpora; until it runs they are on disk but
not searchable.
"""


INSTALLER_TEMPLATE = r"""@echo off
setlocal EnableExtensions
set "HERE=%~dp0"
set "TARGET=%~1"
set "WORK=%TEMP%\SABLERESEARCHC_library_patch_%RANDOM%_%RANDOM%"
set "DECODER=%HERE%machinesoul.py"
set "REASSEMBLER_IMAGE=%HERE%SABLERESEARCHC-REASSEMBLER.png"
set "MANIFEST_IMAGE=%HERE%SABLERESEARCHC-LIBRARY-PATCH-MANIFEST.png"
set "PATCH_IMAGE=%HERE%SABLERESEARCHC-LIBRARY-PATCH.part01.png"

echo.
echo   SABLE researchC - offline library patch
echo   machinesoul decompile, exact reassembly, guarded install
echo.
echo   This installs about 146 MB across 18,458 files and replaces nothing.
echo.

if not defined TARGET if exist "%HERE%TORMENT_NEXUS-researchC\RELEASE_MANIFEST.json" set "TARGET=%HERE%TORMENT_NEXUS-researchC"
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
REM from the work folder, so the decoder has to sit beside it.
copy /y "%DECODER%" "%WORK%\machinesoul.py" >nul
if errorlevel 1 goto :failed

echo   [3/5] Decompiling the patch vector field...
python "%DECODER%" extract "%PATCH_IMAGE%" --out "%WORK%\segments\SABLERESEARCHC-LIBRARY-PATCH.part01.msv"
if errorlevel 1 goto :failed

echo   [4/5] Reassembling the library exactly (this takes a minute)...
python "%WORK%\machinesoul_release.py" reassemble "%WORK%\manifest.json" "%WORK%\segments" --out "%WORK%\payload"
if errorlevel 1 goto :failed

echo   [5/5] Checking the installed release and applying...
python "%WORK%\payload\APPLY_researchC_library_patch.py" --target "%TARGET%" --payload-root "%WORK%\payload"
if errorlevel 1 goto :failed

rmdir /s /q "%WORK%"
echo.
echo   Patch complete. Every file was verified against the release ledger,
echo   and nothing existing was replaced.
echo.
echo   Now start the assistant and run:  library rebuild
echo   The corpora are on disk but not searchable until that runs.
echo.
pause
exit /b 0

:notarget
echo   I could not find the installed researchC folder.
echo   Put this file beside TORMENT_NEXUS-researchC, or drag that folder
echo   onto this installer, then try again. Nothing was changed.
goto :stop

:nopython
echo   Python 3 is required for the public machinesoul decompiler.
echo   Nothing was changed.
goto :stop

:missing
echo   A required machinesoul image or decompiler is missing.
echo   Keep all researchC release downloads together. Nothing was changed.
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


def staged_files() -> list[tuple[str, Path]]:
    """Every payload file, as (manifest path, source path), sorted."""
    found = []
    for path in SOURCE.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(SOURCE).as_posix()
        found.append((relative, path))
    found.sort(key=lambda item: item[0])
    return found


def build_stage(head: str, base_records: dict) -> dict:
    if PATCH_STAGE.exists():
        raise SystemExit(f"refusing existing patch stage: {PATCH_STAGE}")

    entries = staged_files()
    if not entries:
        raise SystemExit(f"no payload files under {SOURCE}")

    outside = [path for path, _ in entries if not path.startswith(PATCH_ROOT)]
    if outside:
        raise SystemExit(
            f"{len(outside)} staged file(s) fall outside the declared root "
            f"{PATCH_ROOT}, first: {outside[0]}"
        )

    collisions = [path for path, _ in entries if path in base_records]
    if collisions:
        raise SystemExit(
            f"{len(collisions)} staged file(s) already exist in the approved "
            f"base cut, first: {collisions[0]}"
        )

    PATCH_STAGE.mkdir(parents=True)
    records = []

    for relative, source in entries:
        destination = PATCH_STAGE / "payload" / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append({
            "path": relative,
            "action": "add",
            "before_sha256": None,
            "before_bytes": None,
            "after_sha256": sha256_file(destination),
            "after_bytes": destination.stat().st_size,
        })

    shutil.copy2(TOOLS / "apply_researchc_patch.py", PATCH_STAGE / APPLIER_NAME)
    (PATCH_STAGE / "PATCH_README.md").write_text(
        PATCH_README,
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "format": "SABLERESEARCHC_PATCH1",
        "patch_id": PATCH_ID,
        "base_source_commit": BASE_COMMIT,
        "patch_source_commit": head,
        "files": records,
    }
    write_json(PATCH_STAGE / "PATCH_APPLICATION_MANIFEST.json", manifest)
    return manifest


def build() -> None:
    dirty = git_output("status", "--porcelain", "--", *PINNED_TOOLS)
    if dirty:
        raise SystemExit(
            "commit the patch tooling before building its capsule:\n" + dirty
        )

    head = git_output("rev-parse", "HEAD")

    if not SOURCE.is_dir():
        raise SystemExit(f"missing staged library: {SOURCE}")
    if not BASE_MANIFEST.is_file():
        raise SystemExit(f"missing exact researchC manifest: {BASE_MANIFEST}")

    with BASE_MANIFEST.open(encoding="utf-8") as handle:
        base_manifest = json.load(handle)

    release._validate_manifest(base_manifest)

    if base_manifest.get("plan_sha256") != BASE_PLAN_SHA256:
        raise SystemExit("base manifest is not the approved researchC cut")

    base_records = {item["path"]: item for item in base_manifest["files"]}

    for path in (PLAN, REVIEW, CUTMAP, MANIFEST, MANIFEST_CAPSULE, INSTALLER):
        if path.exists():
            raise SystemExit(f"refusing existing patch output: {path}")

    application_manifest = build_stage(head, base_records)
    OUT.mkdir(parents=True, exist_ok=True)

    plan = release.make_plan(str(PATCH_STAGE), PREFIX)
    plan_sha = release.write_plan(plan, str(PLAN), str(REVIEW))
    release.render_plan_apng(str(PLAN), str(CUTMAP))
    cut_manifest = release.cut(str(PLAN), plan_sha, str(OUT), str(MANIFEST))

    if len(cut_manifest["capsules"]) != 1:
        raise SystemExit(
            f"library patch needs {len(cut_manifest['capsules'])} fields; "
            "the installer template decodes exactly one"
        )

    machinesoul.build_stream(
        str(MANIFEST),
        str(MANIFEST_CAPSULE),
        description=(
            "Verified direct manifest for the researchC offline library "
            "patch. Decode with machinesoul.py; the recovered reassembler "
            "uses it to restore the patch files exactly."
        ),
    )
    INSTALLER.write_text(INSTALLER_TEMPLATE, encoding="ascii", newline="\r\n")

    report = {
        "patch_id": PATCH_ID,
        "base_commit": BASE_COMMIT,
        "patch_commit": head,
        "plan_sha256": plan_sha,
        "declared_root": PATCH_ROOT,
        "added_files": len(application_manifest["files"]),
        "payload_bytes": sum(
            item["after_bytes"] for item in application_manifest["files"]
        ),
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

    write_json(WORK / "LIBRARY_PATCH_BUILD_REPORT.json", report)

    print(f"patch source: {head}")
    print(f"plan sha256: {plan_sha}")
    print(f"added files: {report['added_files']} under {PATCH_ROOT}")
    print(f"payload bytes: {report['payload_bytes']}")
    for asset in report["assets"]:
        print(
            f"{asset['name']}: {asset['bytes']} bytes "
            f"sha256 {asset['sha256']}"
        )


if __name__ == "__main__":
    build()
