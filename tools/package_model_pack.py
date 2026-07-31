"""
Build and verify the versioned full-maintenance model pack.

The optional 14B GGUF is too large for one GitHub Release asset. This tool
accepts only the exact reviewed artifact, splits it below GitHub's asset
limit, proves that the parts reconstruct the expected SHA-256, and generates
an installer, manifest, checksums, and provenance/readme record.

Normal build:

    python tools/package_model_pack.py

Verify an existing output without reading the source GGUF:

    python tools/package_model_pack.py --verify-only

Existing output is never overwritten unless --force is explicit. Even then,
only the one exact versioned output directory can be replaced.
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_ROOT = os.path.join(ROOT, "dist", "modelpacks")
RELEASE_VERSION = "researchC"
MANIFEST_FORMAT = 1

# GitHub rejects release assets over 2 GiB. Keep the same conservative margin
# as package_release.py.
MAX_ASSET_BYTES = 2 * 1024**3 - 64 * 1024**2
CHUNK = 8 * 1024**2

_SAFE_PACK_ID = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SAFE_MODEL_NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\.gguf\Z")
_SHA256 = re.compile(r"\A[0-9A-F]{64}\Z")


class ModelPackError(RuntimeError):
    """The pack cannot be built or verified safely."""


@dataclass(frozen=True)
class ModelPackSpec:
    pack_id: str
    model_name: str
    size_bytes: int
    sha256: str
    artifact_repository: str
    artifact_revision: str
    derivative_repository: str
    declared_license: str

    @property
    def asset_stem(self):
        return f"TORMENT_NEXUS-{RELEASE_VERSION}-{self.pack_id}"

    @property
    def installer_name(self):
        return f"INSTALL_{self.asset_stem}.bat"

    @property
    def manifest_name(self):
        return f"{self.asset_stem}-MANIFEST.json"

    @property
    def checksums_name(self):
        return f"{self.asset_stem}-SHA256SUMS.txt"

    @property
    def readme_name(self):
        return f"{self.asset_stem}-README.txt"


FULL_MAINTENANCE_14B = ModelPackSpec(
    pack_id="full-maintenance-14b",
    model_name="Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf",
    size_bytes=8_988_111_200,
    sha256="E89A7AE4E2B456BF33C75CFF35664751DF20FF273E551D7CF7640AA9E84D3B79",
    artifact_repository=(
        "https://huggingface.co/bartowski/"
        "Qwen2.5-Coder-14B-Instruct-abliterated-GGUF"
    ),
    artifact_revision="91e7d17796389c79de80776bbd947afa81c1e34d",
    derivative_repository=(
        "https://huggingface.co/huihui-ai/"
        "Qwen2.5-Coder-14B-Instruct-abliterated"
    ),
    declared_license="apache-2.0",
)
DEFAULT_MODEL_PATH = os.path.join(ROOT, "models", FULL_MAINTENANCE_14B.model_name)


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _validate_spec(spec):
    if not _SAFE_PACK_ID.fullmatch(spec.pack_id):
        raise ModelPackError(f"unsafe pack id: {spec.pack_id!r}")
    if not _SAFE_MODEL_NAME.fullmatch(spec.model_name):
        raise ModelPackError(f"unsafe model filename: {spec.model_name!r}")
    if not isinstance(spec.size_bytes, int) or spec.size_bytes <= 0:
        raise ModelPackError("expected model size must be a positive integer")
    if not _SHA256.fullmatch(spec.sha256):
        raise ModelPackError("expected model SHA-256 must be 64 uppercase hex digits")
    if not spec.artifact_repository.startswith("https://huggingface.co/"):
        raise ModelPackError("artifact repository must be a Hugging Face HTTPS URL")
    if not re.fullmatch(r"[0-9a-f]{40}", spec.artifact_revision):
        raise ModelPackError("artifact revision must be a complete 40-digit commit")
    if not spec.derivative_repository.startswith("https://huggingface.co/"):
        raise ModelPackError("derivative repository must be a Hugging Face HTTPS URL")


def _is_reparse_point(path):
    try:
        attributes = os.stat(path, follow_symlinks=False).st_file_attributes
    except (AttributeError, OSError):
        return os.path.islink(path)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & flag)


def _validate_source(model_path, spec):
    _validate_spec(spec)
    path = os.path.abspath(model_path)
    if not os.path.isfile(path):
        raise ModelPackError(f"model file does not exist: {path}")
    if os.path.islink(path) or _is_reparse_point(path):
        raise ModelPackError("refusing a symlink or reparse-point model source")
    if os.path.basename(path) != spec.model_name:
        raise ModelPackError(
            "wrong model filename; expected exactly "
            f"{spec.model_name!r}, got {os.path.basename(path)!r}"
        )

    size = os.path.getsize(path)
    if size != spec.size_bytes:
        raise ModelPackError(
            f"wrong model size: expected {spec.size_bytes}, got {size}"
        )

    digest = _hash_file(path)
    if digest != spec.sha256:
        raise ModelPackError(
            "wrong model SHA-256: expected "
            f"{spec.sha256}, got {digest}"
        )
    return path


def _output_dir(output_root, spec):
    root = os.path.realpath(os.path.abspath(output_root))
    target = os.path.realpath(os.path.join(root, spec.asset_stem))
    if os.path.dirname(target) != root:
        raise ModelPackError("versioned output must be a direct child of output root")
    return root, target


def _part_names(spec, total, max_asset_bytes):
    if not isinstance(max_asset_bytes, int) or max_asset_bytes <= 0:
        raise ModelPackError("maximum asset size must be a positive integer")
    count = max(1, math.ceil(total / max_asset_bytes))
    if count > 99:
        raise ModelPackError("model would require more than 99 numbered parts")
    return tuple(
        f"{spec.asset_stem}.part{index:02d}"
        for index in range(1, count + 1)
    )


def _installer(spec, parts):
    """Return a fail-closed installer for the one exact reviewed GGUF."""
    checks = "\n\n".join(
        f'if not exist "%HERE%{name}" (\n'
        f"    echo   Missing {name}\n"
        "    echo   Download every numbered part into this folder first.\n"
        "    pause\n"
        "    exit /b 1\n"
        ")"
        for name in parts
    )
    joined = "+".join(f'"%HERE%{name}"' for name in parts)

    return f"""@echo off
setlocal EnableExtensions DisableDelayedExpansion
title TORMENT_NEXUS {RELEASE_VERSION} - full-maintenance 14B
set "HERE=%~dp0"
set "TARGET=%HERE%models\\{spec.model_name}"
set "TEMPFILE=%HERE%{spec.asset_stem}.joining"
set "EXPECTED={spec.sha256}"

echo.
echo   TORMENT_NEXUS {RELEASE_VERSION} optional full-maintenance model
echo   {spec.model_name}
echo.
echo   This is an abliterated model. Read MODELS.md and SAFETY.md first.
echo.

{checks}

if not exist "%HERE%models\\" (
    echo   Put this installer and every part inside the extracted
    echo   TORMENT_NEXUS folder that contains start_assistant.bat.
    pause
    exit /b 1
)

if not exist "%TARGET%" goto target_available
set "ACTUAL="
for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -NonInteractive -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath $env:TARGET).Hash"`) do set "ACTUAL=%%H"
if /i "%ACTUAL%"=="%EXPECTED%" goto already_installed
echo.
echo   A DIFFERENT FILE ALREADY EXISTS:
echo   %TARGET%
echo   It was not overwritten. Move or inspect it, then try again.
pause
exit /b 1

:already_installed
echo   The exact verified model is already installed.
exit /b 0

:target_available

if exist "%TEMPFILE%" del /q "%TEMPFILE%" >nul 2>&1

echo   [1/3] Joining {len(parts)} parts...
copy /b {joined} "%TEMPFILE%" >nul
if errorlevel 1 (
    echo   Could not join the parts. Is there enough disk space?
    if exist "%TEMPFILE%" del /q "%TEMPFILE%" >nul 2>&1
    pause
    exit /b 1
)

echo   [2/3] Verifying the complete model...
set "ACTUAL="
for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -NonInteractive -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath $env:TEMPFILE).Hash"`) do set "ACTUAL=%%H"
if /i not "%ACTUAL%"=="%EXPECTED%" (
    echo.
    echo   CHECKSUM MISMATCH - the download is damaged or incomplete.
    echo   expected %EXPECTED%
    echo   got      %ACTUAL%
    echo   No model was installed.
    del /q "%TEMPFILE%" >nul 2>&1
    pause
    exit /b 1
)

echo   [3/3] Installing without overwriting an existing model...
move "%TEMPFILE%" "%TARGET%" >nul
if errorlevel 1 (
    echo   The verified model could not be moved into models\\.
    pause
    exit /b 1
)

echo.
echo   Done. The exact reviewed model is installed.
echo   You may delete the numbered parts after a successful launch.
echo.
pause
"""


def _readme(spec, parts):
    part_lines = "\n".join(f"  {name}" for name in parts)
    return f"""TORMENT_NEXUS {RELEASE_VERSION} - OPTIONAL FULL-MAINTENANCE 14B

This asset set installs one exact optional abliterated model:

  {spec.model_name}
  {spec.size_bytes} bytes
  SHA-256 {spec.sha256}

Download the installer, manifest, checksum file, this README, and EVERY part:

{part_lines}

Put them in the extracted TORMENT_NEXUS folder containing
start_assistant.bat, then run:

  {spec.installer_name}

The installer refuses missing/corrupt parts and refuses to overwrite a
different existing model. After installation, use
start_full_maintenance_coder.bat and type its exact confirmation phrase only
if you intend to grant that maintenance profile.

BEHAVIOR WARNING

This model was modified to reduce learned refusal behavior. It can generate
harmful, illegal, insecure, explicit, biased, manipulative, or false material
confidently. Abliteration does not make it more truthful and does not grant it
authority. Read SAFETY.md, MODELS.md, RIGHTS.md, and THIRD_PARTY_NOTICES.md.

PROVENANCE RECORD

Exact GGUF repository:
  {spec.artifact_repository}
Observed revision:
  {spec.artifact_revision}
Named derivative repository:
  {spec.derivative_repository}
Uploader-declared license:
  {spec.declared_license}

Those repositories display the named license. This records uploader metadata;
it is not an independent legal conclusion about every input to the derivative
chain. The matching hash proves byte identity, not safety, accuracy, or legal
permission.
"""


def _file_record(folder, name, kind):
    path = os.path.join(folder, name)
    return {
        "kind": kind,
        "name": name,
        "size_bytes": os.path.getsize(path),
        "sha256": _hash_file(path),
    }


def _write_text(path, text, *, newline=None):
    with open(path, "w", encoding="utf-8", newline=newline) as handle:
        handle.write(text)


def _expected_checksum_text(manifest, manifest_hash):
    rows = [
        (
            manifest["model"]["sha256"],
            manifest["model"]["filename"] + " (rejoined)",
        )
    ]
    rows.extend((item["sha256"], item["name"]) for item in manifest["files"])
    rows.append((manifest_hash, manifest["manifest_name"]))
    return "".join(f"{digest}  {name}\n" for digest, name in rows)


def _verify_folder(folder, spec, max_asset_bytes):
    _validate_spec(spec)
    if (
        not os.path.isdir(folder)
        or os.path.islink(folder)
        or _is_reparse_point(folder)
    ):
        raise ModelPackError(f"model-pack output does not exist: {folder}")

    try:
        entries = list(os.scandir(folder))
    except OSError as exc:
        raise ModelPackError(f"cannot inspect model-pack output: {exc}") from exc
    for entry in entries:
        if (
            entry.is_symlink()
            or _is_reparse_point(entry.path)
            or not entry.is_file(follow_symlinks=False)
        ):
            raise ModelPackError(
                "model-pack output contains a non-regular or reparse entry: "
                f"{entry.name}"
            )
    actual_names = {entry.name for entry in entries}

    manifest_path = os.path.join(folder, spec.manifest_name)
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ModelPackError(f"cannot read model-pack manifest: {exc}") from exc

    if manifest.get("format") != MANIFEST_FORMAT:
        raise ModelPackError("unsupported model-pack manifest format")
    if manifest.get("release_version") != RELEASE_VERSION:
        raise ModelPackError("manifest release version does not match this tool")
    if manifest.get("pack_id") != spec.pack_id:
        raise ModelPackError("manifest pack id does not match this tool")
    if manifest.get("asset_stem") != spec.asset_stem:
        raise ModelPackError("manifest asset stem does not match this tool")
    if manifest.get("manifest_name") != spec.manifest_name:
        raise ModelPackError("manifest filename record is wrong")
    if manifest.get("checksums_name") != spec.checksums_name:
        raise ModelPackError("manifest checksum filename record is wrong")

    expected_model = {
        "filename": spec.model_name,
        "size_bytes": spec.size_bytes,
        "sha256": spec.sha256,
    }
    if manifest.get("model") != expected_model:
        raise ModelPackError("manifest model identity is not the reviewed artifact")

    expected_provenance = {
        "artifact_repository": spec.artifact_repository,
        "artifact_revision": spec.artifact_revision,
        "derivative_repository": spec.derivative_repository,
        "declared_license": spec.declared_license,
        "license_status": "uploader-declared; not an independent legal conclusion",
    }
    if manifest.get("provenance") != expected_provenance:
        raise ModelPackError("manifest provenance record is incomplete or changed")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ModelPackError("manifest contains no files")

    names = []
    part_records = []
    for record in files:
        if not isinstance(record, dict):
            raise ModelPackError("invalid file record in manifest")
        name = record.get("name")
        if (
            not isinstance(name, str)
            or os.path.basename(name) != name
            or name in names
        ):
            raise ModelPackError("unsafe or duplicate filename in manifest")
        if record.get("kind") not in {"part", "installer", "readme"}:
            raise ModelPackError(f"invalid file kind for {name}")
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            raise ModelPackError(f"missing model-pack file: {name}")
        size = os.path.getsize(path)
        if size != record.get("size_bytes"):
            raise ModelPackError(f"size mismatch for {name}")
        digest = _hash_file(path)
        if digest != record.get("sha256"):
            raise ModelPackError(f"SHA-256 mismatch for {name}")
        names.append(name)
        if record["kind"] == "part":
            if size > max_asset_bytes:
                raise ModelPackError(f"GitHub-sized part is too large: {name}")
            part_records.append(record)

    expected_parts = list(_part_names(spec, spec.size_bytes, max_asset_bytes))
    actual_parts = [item["name"] for item in part_records]
    if actual_parts != expected_parts:
        raise ModelPackError("numbered part set is incomplete or out of order")

    if [item["name"] for item in files if item["kind"] == "installer"] != [
        spec.installer_name
    ]:
        raise ModelPackError("manifest must contain the one versioned installer")
    if [item["name"] for item in files if item["kind"] == "readme"] != [
        spec.readme_name
    ]:
        raise ModelPackError("manifest must contain the one versioned README")

    joined = hashlib.sha256()
    joined_size = 0
    for record in part_records:
        with open(os.path.join(folder, record["name"]), "rb") as handle:
            for block in iter(lambda: handle.read(CHUNK), b""):
                joined.update(block)
                joined_size += len(block)
    if joined_size != spec.size_bytes:
        raise ModelPackError("numbered parts reconstruct the wrong byte size")
    if joined.hexdigest().upper() != spec.sha256:
        raise ModelPackError("numbered parts do not reconstruct the reviewed model")

    manifest_hash = _hash_file(manifest_path)
    checksums_path = os.path.join(folder, spec.checksums_name)
    try:
        with open(checksums_path, encoding="utf-8") as handle:
            checksums = handle.read()
    except OSError as exc:
        raise ModelPackError(f"cannot read checksums: {exc}") from exc
    if checksums != _expected_checksum_text(manifest, manifest_hash):
        raise ModelPackError("checksum ledger does not match the verified files")

    expected_names = set(names) | {spec.manifest_name, spec.checksums_name}
    if actual_names != expected_names:
        raise ModelPackError(
            "model-pack folder contains missing or unexpected files: "
            f"{sorted(actual_names ^ expected_names)}"
        )

    return manifest


def verify_output(
    *,
    output_root=DIST_ROOT,
    spec=FULL_MAINTENANCE_14B,
    max_asset_bytes=MAX_ASSET_BYTES,
):
    root, folder = _output_dir(output_root, spec)
    del root
    return _verify_folder(folder, spec, max_asset_bytes)


def _remove_exact_output(target, output_root, spec):
    """Remove only the direct, exact generated target selected by --force."""
    real_root, expected = _output_dir(output_root, spec)
    real_target = os.path.realpath(target)
    if real_target != expected or os.path.dirname(real_target) != real_root:
        raise ModelPackError("refusing to remove an unexpected output path")
    if os.path.islink(target) or _is_reparse_point(target):
        raise ModelPackError("refusing to replace a symlink or reparse-point output")
    shutil.rmtree(target)


def build(
    model_path=DEFAULT_MODEL_PATH,
    *,
    output_root=DIST_ROOT,
    spec=FULL_MAINTENANCE_14B,
    max_asset_bytes=MAX_ASSET_BYTES,
    force=False,
):
    _validate_spec(spec)
    requested_root = os.path.abspath(output_root)
    if os.path.lexists(requested_root) and (
        os.path.islink(requested_root) or _is_reparse_point(requested_root)
    ):
        raise ModelPackError("refusing a symlink or reparse-point output root")
    output_root, target = _output_dir(output_root, spec)
    if os.path.lexists(output_root) and not os.path.isdir(output_root):
        raise ModelPackError("output root exists but is not a directory")
    if os.path.lexists(output_root) and (
        os.path.islink(output_root) or _is_reparse_point(output_root)
    ):
        raise ModelPackError("refusing a symlink or reparse-point output root")
    if os.path.lexists(target) and not force:
        raise ModelPackError(
            f"versioned output already exists: {target}; use --force to replace it"
        )
    if os.path.lexists(target) and not os.path.isdir(target):
        raise ModelPackError("versioned output exists but is not a directory")

    disk_probe = output_root
    while not os.path.exists(disk_probe):
        parent = os.path.dirname(disk_probe)
        if parent == disk_probe:
            raise ModelPackError("cannot resolve a disk for the output root")
        disk_probe = parent
    free = shutil.disk_usage(disk_probe).free
    reserve = max(16 * 1024**2, min(spec.size_bytes // 20, 256 * 1024**2))
    if free < spec.size_bytes + reserve:
        raise ModelPackError(
            "not enough free disk space to split the model safely: "
            f"need at least {spec.size_bytes + reserve} bytes, have {free}"
        )

    # Hashing the reviewed 14B file takes meaningful time. Cheap output and
    # free-space failures happen first; the existing good output is still
    # preserved until a complete replacement has passed verification.
    source = _validate_source(model_path, spec)
    os.makedirs(output_root, exist_ok=True)
    if os.path.islink(output_root) or _is_reparse_point(output_root):
        raise ModelPackError("refusing a symlink or reparse-point output root")
    parts = _part_names(spec, spec.size_bytes, max_asset_bytes)
    part_size = math.ceil(spec.size_bytes / len(parts))
    temporary = tempfile.mkdtemp(
        prefix=f".{spec.asset_stem}.building-",
        dir=output_root,
    )

    try:
        with open(source, "rb") as model:
            for part_name in parts:
                remaining = min(part_size, spec.size_bytes - model.tell())
                part_path = os.path.join(temporary, part_name)
                with open(part_path, "xb") as part:
                    while remaining:
                        block = model.read(min(CHUNK, remaining))
                        if not block:
                            raise ModelPackError("model ended while writing parts")
                        part.write(block)
                        remaining -= len(block)
            if model.read(1):
                raise ModelPackError("model changed size while writing parts")

        installer_path = os.path.join(temporary, spec.installer_name)
        _write_text(installer_path, _installer(spec, parts), newline="\r\n")
        readme_path = os.path.join(temporary, spec.readme_name)
        _write_text(readme_path, _readme(spec, parts))

        records = [
            _file_record(temporary, name, "part")
            for name in parts
        ]
        records.extend([
            _file_record(temporary, spec.installer_name, "installer"),
            _file_record(temporary, spec.readme_name, "readme"),
        ])
        manifest = {
            "format": MANIFEST_FORMAT,
            "release_version": RELEASE_VERSION,
            "pack_id": spec.pack_id,
            "asset_stem": spec.asset_stem,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "manifest_name": spec.manifest_name,
            "checksums_name": spec.checksums_name,
            "model": {
                "filename": spec.model_name,
                "size_bytes": spec.size_bytes,
                "sha256": spec.sha256,
            },
            "provenance": {
                "artifact_repository": spec.artifact_repository,
                "artifact_revision": spec.artifact_revision,
                "derivative_repository": spec.derivative_repository,
                "declared_license": spec.declared_license,
                "license_status": (
                    "uploader-declared; not an independent legal conclusion"
                ),
            },
            "files": records,
        }
        manifest_path = os.path.join(temporary, spec.manifest_name)
        _write_text(
            manifest_path,
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
        checksums_path = os.path.join(temporary, spec.checksums_name)
        _write_text(
            checksums_path,
            _expected_checksum_text(manifest, _hash_file(manifest_path)),
        )

        _verify_folder(temporary, spec, max_asset_bytes)

        if os.path.lexists(target):
            _remove_exact_output(target, output_root, spec)
        os.replace(temporary, target)
        temporary = None
        _verify_folder(target, spec, max_asset_bytes)
        return target
    finally:
        if temporary and os.path.isdir(temporary):
            shutil.rmtree(temporary)


def _print_verified(folder, manifest):
    print(f"Verified {manifest['asset_stem']}")
    print(f"  output: {folder}")
    print(f"  model:  {manifest['model']['filename']}")
    print(f"  bytes:  {manifest['model']['size_bytes']}")
    print(f"  sha256: {manifest['model']['sha256']}")
    print("  upload every file in this directory")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            f"Build or verify the exact versioned TORMENT_NEXUS "
            f"{RELEASE_VERSION} full-maintenance 14B model pack."
        ),
    )
    parser.add_argument(
        "model",
        nargs="?",
        default=DEFAULT_MODEL_PATH,
        help="path to the exact reviewed 14B GGUF",
    )
    parser.add_argument(
        "--output-root",
        default=DIST_ROOT,
        help="parent directory for the versioned model-pack folder",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace only the exact versioned output directory if it exists",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify the existing versioned output without reading the GGUF",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {RELEASE_VERSION}",
    )
    args = parser.parse_args(argv)

    try:
        if args.verify_only:
            manifest = verify_output(output_root=args.output_root)
            folder = _output_dir(args.output_root, FULL_MAINTENANCE_14B)[1]
        else:
            folder = build(
                args.model,
                output_root=args.output_root,
                force=args.force,
            )
            manifest = verify_output(output_root=args.output_root)
    except ModelPackError as exc:
        parser.exit(1, f"model pack failed: {exc}\n")

    _print_verified(folder, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
