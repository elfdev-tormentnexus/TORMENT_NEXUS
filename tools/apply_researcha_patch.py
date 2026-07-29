"""Apply a direct machinesoul researchA patch after exact verification."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


FORMAT = "SABLERESEARCHA_PATCH1"
BLOCK = 1024 * 1024


class PatchError(RuntimeError):
    """The patch cannot be applied without risking an unknown install."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value: str) -> Path:
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if (
        not normalized
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or ":" in pure.parts[0]
    ):
        raise PatchError(f"unsafe patch path: {value!r}")
    return Path(*pure.parts)


def load_manifest(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PatchError(f"cannot read patch manifest: {error}") from error
    if document.get("format") != FORMAT:
        raise PatchError("not a researchA patch manifest")
    if not isinstance(document.get("files"), list) or not document["files"]:
        raise PatchError("patch manifest has no files")
    return document


def _atomic_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix="." + path.name + ".",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            json.dump(document, out, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


def _updated_release_manifest(
    path: Path,
    patch_manifest: dict,
) -> dict:
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PatchError(f"cannot read RELEASE_MANIFEST.json: {error}") from error

    records = {
        item.get("path"): item
        for item in release.get("files", [])
        if isinstance(item, dict)
    }
    for item in patch_manifest["files"]:
        record = records.get(item["path"])
        if record is None:
            raise PatchError(
                f"release manifest does not name patched file: {item['path']}"
            )
        record["bytes"] = item["after_bytes"]
        record["sha256"] = item["after_sha256"]

    patches = release.setdefault("patches", [])
    patches = [
        item for item in patches
        if item.get("id") != patch_manifest["patch_id"]
    ]
    patches.append({
        "id": patch_manifest["patch_id"],
        "source_commit": patch_manifest["patch_source_commit"],
        "applied_utc": datetime.now(timezone.utc).isoformat(),
    })
    release["patches"] = patches
    return release


def apply_patch(target: str, payload_root: str, manifest_path: str) -> str:
    target_root = Path(target).resolve()
    payload_root = Path(payload_root).resolve()
    manifest_path = Path(manifest_path).resolve()
    if not target_root.is_dir():
        raise PatchError(f"install folder does not exist: {target_root}")
    if not payload_root.is_dir():
        raise PatchError(f"decoded patch folder does not exist: {payload_root}")

    manifest = load_manifest(manifest_path)
    release_manifest = target_root / "RELEASE_MANIFEST.json"
    checks = []
    for item in manifest["files"]:
        relative = safe_relative(item["path"])
        installed = (target_root / relative).resolve()
        payload = (payload_root / "payload" / relative).resolve()
        if target_root not in installed.parents:
            raise PatchError(f"installed path escapes target: {item['path']}")
        if payload_root not in payload.parents:
            raise PatchError(f"payload path escapes patch: {item['path']}")
        if not payload.is_file():
            raise PatchError(f"patch payload is missing: {item['path']}")
        if sha256_file(payload) != item["after_sha256"]:
            raise PatchError(f"patch payload is damaged: {item['path']}")
        if not installed.is_file():
            raise PatchError(f"installed file is missing: {item['path']}")
        current = sha256_file(installed)
        if current == item["after_sha256"]:
            state = "patched"
        elif current == item["before_sha256"]:
            state = "original"
        else:
            raise PatchError(
                f"installed file has an unknown version: {item['path']}"
            )
        checks.append((item, installed, payload, state))

    pending = [check for check in checks if check[3] == "original"]
    if not pending:
        return "already applied"

    release = _updated_release_manifest(release_manifest, manifest)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = target_root / "backups" / (
        manifest["patch_id"].replace("/", "_") + "_" + stamp
    )
    backup_root.mkdir(parents=True, exist_ok=False)
    shutil.copy2(release_manifest, backup_root / "RELEASE_MANIFEST.json")
    for _, installed, _, state in checks:
        if state == "original":
            relative = installed.relative_to(target_root)
            backup = backup_root / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(installed, backup)

    changed = []
    try:
        for item, installed, payload, state in checks:
            if state != "original":
                continue
            temporary = installed.with_name(installed.name + ".researcha-patch.tmp")
            shutil.copyfile(payload, temporary)
            if sha256_file(temporary) != item["after_sha256"]:
                raise PatchError(f"copied patch differs: {item['path']}")
            os.replace(temporary, installed)
            changed.append((installed, backup_root / installed.relative_to(target_root)))
        for item, installed, _, _ in checks:
            if sha256_file(installed) != item["after_sha256"]:
                raise PatchError(
                    f"post-install verification failed: {item['path']}"
                )
        _atomic_json(release_manifest, release)
    except BaseException:
        for installed, backup in reversed(changed):
            shutil.copy2(backup, installed)
        shutil.copy2(backup_root / "RELEASE_MANIFEST.json", release_manifest)
        raise

    return f"applied; originals retained in {backup_root}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--payload-root", default=os.path.dirname(__file__))
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args(argv)
    manifest = args.manifest or os.path.join(
        args.payload_root,
        "PATCH_APPLICATION_MANIFEST.json",
    )
    try:
        result = apply_patch(args.target, args.payload_root, manifest)
    except PatchError as error:
        print(f"PATCH REFUSED: {error}")
        return 1
    print(f"PATCH VERIFIED: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
