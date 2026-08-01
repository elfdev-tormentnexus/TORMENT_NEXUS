"""Build the researchC vector-field patch: one click, add and replace.

Patch A shipped the corpus. This ships the semantic layer over it -- the
15,000 embeddings the maintainer already computed -- so a new install gets
semantic retrieval without spending an hour of its own CPU on a pass whose
answer is already known.

It is the researchB self-read patch's shape rather than patch A's, because
this one cannot be adds-only. The field is only interchangeable with locally
computed vectors if the text policy that produced it matches, and the policy
that shipped in the base cut is not the one these vectors were built under:
1,600 bytes cut mid-word, which put 15.5% of the target over the embedder's
512-token window and left a fragment in every truncated chunk. So library.py
is a declared "replace", carrying the tightened bound and the word-boundary
cut, and the field is an "add" beside it.

The two are deliberately inseparable. The importer recomputes the vector
identity from the installed library.py and refuses if it disagrees, so the
field physically cannot be applied to an install that did not take the code
change. Shipping either half alone would produce a cosine space with two
incompatible populations in it, which fails silently and is the exact
failure the identity string exists to prevent.
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


PATCH_ID = "researchC-vector-field.2"
BASE_COMMIT = "a774140bdccce23aa39c0e562bb0685e7fab435e"
BASE_PLAN_SHA256 = (
    "b9e6a4c8f8156bf74dac0cff4ac0e9c930a390f697901ed09fac9f6a7c0c0c2c"
)
PREFIX = "SABLERESEARCHC-VECTOR-PATCH2"

FIELD_DIR = "assistant/knowledge/vector_field"

PINNED_TOOLS = (
    "tools/build_researchc_vector_patch.py",
    "tools/export_researchc_vector_field.py",
    "tools/import_vector_field.py",
    "tools/apply_researchc_patch.py",
)

WORK = ROOT.parent / "SABLERESEARCHC"
STAGE_FIELD = WORK / "stage-vector-field"
BASE_MANIFEST = WORK / "MANIFEST_WINDOWS.json"
PATCH_STAGE = WORK / "VECTOR_PATCH2_STAGE"
OUT = WORK / "release-vector2"
PLAN = WORK / "CUT_PLAN_VECTOR_PATCH2.json"
REVIEW = WORK / "CUT_PLAN_VECTOR_PATCH2.md"
CUTMAP = WORK / "CUT_PLAN_VECTOR_PATCH2.png"
MANIFEST = WORK / "MANIFEST_VECTOR_PATCH2.json"
MANIFEST_CAPSULE = OUT / f"{PREFIX}-MANIFEST.png"
INSTALLER = OUT / "INSTALL_SABLERESEARCHC_VECTOR_PATCH2.bat"
APPLIER_NAME = "APPLY_researchC_vector_patch2.py"

# (installed path, action, source file)
PATCH_FILES = (
    (
        "assistant/knowledge/library.py",
        "replace",
        ROOT / "assistant" / "knowledge" / "library.py",
    ),
    (
        f"{FIELD_DIR}/SABLERESEARCHC-VECTOR-FIELD.png",
        "add",
        STAGE_FIELD / "SABLERESEARCHC-VECTOR-FIELD.png",
    ),
    (
        f"{FIELD_DIR}/VECTOR_FIELD_KEYS.json.gz",
        "add",
        STAGE_FIELD / "VECTOR_FIELD_KEYS.json.gz",
    ),
    (
        f"{FIELD_DIR}/import_vector_field.py",
        "add",
        TOOLS / "import_vector_field.py",
    ),
)


PATCH_README = """# researchC vector-field patch (patch C)

75,000 precomputed embeddings over the offline library, plus the selection
plan and text policy they were built under. It supersedes the earlier
vector-field patch, and it should be installed on a base researchC install
rather than on top of that one.

## What was wrong with the first attempt

The first vector patch shipped 15,000 embeddings chosen by a flat per-source
round robin under a global ceiling. The shelf has 17,320 sources and the
ceiling was 15,000, so **round one never completed**: every source got its
opening chunk and nothing got a second. 14,979 of the 15,000 vectors were a
document's first chunk, and 87% of the shelf's text had no vector at all.
A second mechanism did the same damage independently -- a flat cap of 120
chunks per source excluded 46,941 chunks, nearly all of MITRE ATT&CK, no
matter how the order was computed.

Neither failure was visible. `library status` reported complete, 100%
coverage, because it measures whether the target was filled and never
whether the target was worth filling.

## What this one does instead

Selection is planned against the whole corpus before any compute is spent,
the way the release cutter plans capsules. Every source still contributes its
opening chunk, but bounded at one; everything after that is ordered by
*proportional depth*, so each source contributes the same fraction of itself
at any cut point rather than the same absolute count. The per-source cap
scales with the budget instead of being a constant.

Measured against the shipped shelf:

| | first attempt | this patch |
|---|---:|---:|
| Vectors | 15,000 | 75,000 |
| Shelf text reachable | 11.0% | **51.6%** |
| Body chunks, not openings | 0.1% | **77.4%** |
| MITRE ATT&CK part01 | ~1 vector | **6,306** |

## What it still does not cover

About half the shelf's text has no vector, deliberately: the budget is
bounded because embedding all 122,129 chunks would produce roughly 190 MB of
vectors. Lexical search continues to cover the whole shelf, including
everything the semantic layer does not reach.

**4,724 chunks were quarantined** -- 6.3% of the target. These exceed the
embedder's 512-token window even after truncation, and they are concentrated
in the densest material: ATT&CK JSON bodies and kernel schema definitions.
They are lexically searchable and semantically absent. Each one that
quarantined pulled a replacement in from below the ceiling, so the field is
still exactly 75,000 vectors.

## Why it replaces library.py

Two reasons, and either alone would be sufficient.

The text policy: a vector only means something beside the exact bound that
produced it. The base cut bounded embed text at 1,600 UTF-8 bytes and cut
wherever that offset fell, which left a mid-word fragment in every truncated
chunk -- and a fragment like `configura` becomes subword tokens that mean
nothing, which mean pooling then averages into the vector. This ships a
1,000-byte bound that backs off to the last whitespace.

The ceiling: the field is 75,000 vectors and the base cut's ceiling is
15,000. Importing this field into an installation that still had the old
ceiling would work, and then the next background pass would retire every
vector outside that smaller target -- silently deleting 60,000 of them.

The importer recomputes the vector identity from the installed library.py and
refuses if it disagrees, so the field cannot be applied to an install that
did not take the code change.

## Order

Install the offline library patch first and run `library rebuild`, so the
chunks exist. Then this patch. The installer runs the import for you; it
keys on content hashes, fills only empty vectors, never overwrites one, and
is safe to run twice.
"""


INSTALLER_TEMPLATE = r"""@echo off
setlocal EnableExtensions
set "HERE=%~dp0"
set "TARGET=%~1"
set "WORK=%TEMP%\SABLERESEARCHC_vector_patch2_%RANDOM%_%RANDOM%"
set "DECODER=%HERE%machinesoul.py"
set "REASSEMBLER_IMAGE=%HERE%SABLERESEARCHC-REASSEMBLER.png"
set "MANIFEST_IMAGE=%HERE%SABLERESEARCHC-VECTOR-PATCH2-MANIFEST.png"
set "PATCH_IMAGE=%HERE%SABLERESEARCHC-VECTOR-PATCH2.part01.png"

echo.
echo   SABLE researchC - vector field patch
echo   machinesoul decompile, exact reassembly, guarded install
echo.
echo   This installs 75,000 precomputed embeddings and the selection
echo   plan they were chosen by. No local embedding pass is needed.
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

echo   [1/6] Decompiling the patch manifest...
python "%DECODER%" extract "%MANIFEST_IMAGE%" --out "%WORK%\manifest.json"
if errorlevel 1 goto :failed

echo   [2/6] Decompiling the verified reassembler...
python "%DECODER%" extract "%REASSEMBLER_IMAGE%" --out "%WORK%\machinesoul_release.py"
if errorlevel 1 goto :failed

REM The recovered reassembler does a bare "import machinesoul", and it runs
REM from the work folder, so the decoder has to sit beside it.
copy /y "%DECODER%" "%WORK%\machinesoul.py" >nul
if errorlevel 1 goto :failed

echo   [3/6] Decompiling the patch payload...
python "%DECODER%" extract "%PATCH_IMAGE%" --out "%WORK%\segments\SABLERESEARCHC-VECTOR-PATCH2.part01.msv"
if errorlevel 1 goto :failed

echo   [4/6] Reassembling the payload exactly...
python "%WORK%\machinesoul_release.py" reassemble "%WORK%\manifest.json" "%WORK%\segments" --out "%WORK%\payload"
if errorlevel 1 goto :failed

echo   [5/6] Checking the installed release and applying...
python "%WORK%\payload\APPLY_researchC_vector_patch2.py" --target "%TARGET%" --payload-root "%WORK%\payload"
if errorlevel 1 goto :failed

echo   [6/6] Importing the vector field into the library...
python "%TARGET%\assistant\knowledge\vector_field\import_vector_field.py" --target "%TARGET%"
if errorlevel 1 goto :importfailed

rmdir /s /q "%WORK%"
echo.
echo   Patch complete. The field was verified against the release ledger
echo   and imported under a matching vector identity.
echo.
pause
exit /b 0

:importfailed
rmdir /s /q "%WORK%"
echo.
echo   The files installed correctly, but the field was not imported.
echo   The usual cause is that the offline library patch is not installed
echo   yet, or "library rebuild" has not been run, so there are no chunks
echo   to attach vectors to.
echo.
echo   Install the library patch, start the assistant, run:  library rebuild
echo   Then run this installer again. It is safe to run more than once.
echo.
pause
exit /b 1

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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")


def build_stage(head: str, base_records: dict) -> dict:
    if PATCH_STAGE.exists():
        raise SystemExit(f"refusing existing patch stage: {PATCH_STAGE}")
    PATCH_STAGE.mkdir(parents=True)

    records = []
    for relative, action, source in PATCH_FILES:
        if not source.is_file():
            raise SystemExit(f"missing patch input: {source}")
        original = base_records.get(relative)

        if action == "replace":
            if original is None:
                raise SystemExit(
                    f"declared replace but the base cut lacks it: {relative}"
                )
            before = original["sha256"]
            after = sha256_file(source)
            if before == after:
                raise SystemExit(f"patch input did not change: {relative}")
            record = {
                "path": relative,
                "action": "replace",
                "before_sha256": before,
                "before_bytes": original["size"],
            }
        elif action == "add":
            if original is not None:
                raise SystemExit(
                    f"declared add but the base cut already has it: {relative}"
                )
            after = sha256_file(source)
            record = {
                "path": relative,
                "action": "add",
                "before_sha256": None,
                "before_bytes": None,
            }
        else:
            raise SystemExit(f"unknown action {action!r} for {relative}")

        record["after_sha256"] = after
        record["after_bytes"] = source.stat().st_size

        destination = PATCH_STAGE / "payload" / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(record)

    shutil.copy2(TOOLS / "apply_researchc_patch.py", PATCH_STAGE / APPLIER_NAME)
    (PATCH_STAGE / "PATCH_README.md").write_text(
        PATCH_README, encoding="utf-8", newline="\n"
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
            f"vector patch needs {len(cut_manifest['capsules'])} fields; "
            "the installer template decodes exactly one"
        )

    machinesoul.build_stream(
        str(MANIFEST),
        str(MANIFEST_CAPSULE),
        description=(
            "Verified direct manifest for the researchC vector-field patch. "
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
        "records": [
            {"path": item["path"], "action": item["action"]}
            for item in application_manifest["files"]
        ],
        "payload_bytes": sum(
            item["after_bytes"] for item in application_manifest["files"]
        ),
        "assets": [],
    }
    for path in (
        OUT / f"{PREFIX}.part01.png", MANIFEST_CAPSULE, INSTALLER, CUTMAP,
    ):
        report["assets"].append({
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    write_json(WORK / "VECTOR_PATCH2_BUILD_REPORT.json", report)

    print(f"patch source: {head}")
    print(f"plan sha256: {plan_sha}")
    print(f"payload bytes: {report['payload_bytes']}")
    for item in report["records"]:
        print(f"  {item['action']:<8} {item['path']}")
    for asset in report["assets"]:
        print(
            f"{asset['name']}: {asset['bytes']} bytes "
            f"sha256 {asset['sha256']}"
        )


if __name__ == "__main__":
    build()
