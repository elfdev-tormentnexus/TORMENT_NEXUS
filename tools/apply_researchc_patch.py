"""Apply a direct machinesoul researchC patch after exact verification.

Unchanged from the researchB applier apart from the format discriminator:
the capability this needs -- a patch that may **add** files the base cut
never contained -- was already built and proven there. The library patch
is the extreme case of it, adding thousands of files and replacing none,
which is why the add path is guarded as tightly as it is below.

Adding is the broader capability, so it is narrowed everywhere it can be:

  * The action is declared per file in the manifest, not inferred from
    what happens to be on disk. A record that says "replace" can never
    create a file, and a record that says "add" can never silently
    overwrite one that exists with unknown content.
  * An "add" whose target already exists is refused unless that file is
    already byte-identical to the patched result, which is the
    already-applied case and the only benign one.
  * Rollback removes what it created, including any directory it had to
    make, so a failed patch leaves no partial module behind for Python to
    import on the next start.

Everything else is inherited: paths are checked for traversal before use,
originals are copied under the installation's backups folder, every write
is verified by digest afterwards, and any failure restores the whole set
before raising.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


FORMAT = "SABLERESEARCHC_PATCH1"
BLOCK = 1024 * 1024
ADD = "add"
REPLACE = "replace"


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
        raise PatchError("not a researchC patch manifest")
    if not isinstance(document.get("files"), list) or not document["files"]:
        raise PatchError("patch manifest has no files")
    for item in document["files"]:
        action = item.get("action")
        if action not in {ADD, REPLACE}:
            raise PatchError(
                f"patch record declares no usable action: {item.get('path')!r}"
            )
        if action == REPLACE and not item.get("before_sha256"):
            raise PatchError(
                f"replace record has no prior digest: {item.get('path')!r}"
            )
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


def _updated_release_manifest(path: Path, patch_manifest: dict) -> dict:
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PatchError(f"cannot read RELEASE_MANIFEST.json: {error}") from error

    entries = release.setdefault("files", [])
    records = {
        item.get("path"): item
        for item in entries
        if isinstance(item, dict)
    }

    for item in patch_manifest["files"]:
        record = records.get(item["path"])

        if item["action"] == REPLACE:
            if record is None:
                raise PatchError(
                    f"release manifest does not name patched file: {item['path']}"
                )
        elif record is None:
            # The ledger has to grow, or a file this patch installed would
            # be invisible to every later verification of the install.
            record = {"path": item["path"]}
            entries.append(record)
            records[item["path"]] = record

        record["bytes"] = item["after_bytes"]
        record["sha256"] = item["after_sha256"]

    patches = [
        item for item in release.get("patches", [])
        if item.get("id") != patch_manifest["patch_id"]
    ]
    patches.append({
        "id": patch_manifest["patch_id"],
        "source_commit": patch_manifest["patch_source_commit"],
        "applied_utc": datetime.now(timezone.utc).isoformat(),
    })
    release["patches"] = patches
    return release


def _plan(manifest: dict, target_root: Path, payload_root: Path) -> list:
    """Decide each file's state before a single byte is written."""
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

        if not installed.exists():
            if item["action"] != ADD:
                raise PatchError(f"installed file is missing: {item['path']}")
            state = "create"
        else:
            if not installed.is_file():
                raise PatchError(f"install path is not a file: {item['path']}")

            current = sha256_file(installed)

            if current == item["after_sha256"]:
                state = "patched"
            elif item["action"] == REPLACE and current == item["before_sha256"]:
                state = "original"
            else:
                # An "add" landing on an unrecognised file is the case
                # worth refusing loudest: the install already contains
                # something at that path that this patch did not write.
                raise PatchError(
                    f"installed file has an unknown version: {item['path']}"
                )

        checks.append((item, installed, payload, state))

    return checks


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
    checks = _plan(manifest, target_root, payload_root)
    pending = [check for check in checks if check[3] in {"original", "create"}]

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
            backup = backup_root / installed.relative_to(target_root)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(installed, backup)

    replaced = []
    created = []
    made_directories = []

    try:
        for item, installed, payload, state in checks:
            if state == "patched":
                continue

            if state == "create":
                folder = installed.parent
                if not folder.exists():
                    folder.mkdir(parents=True, exist_ok=True)
                    made_directories.append(folder)

            temporary = installed.with_name(
                installed.name + ".researchc-patch.tmp"
            )
            shutil.copyfile(payload, temporary)

            if sha256_file(temporary) != item["after_sha256"]:
                raise PatchError(f"copied patch differs: {item['path']}")

            os.replace(temporary, installed)

            if state == "create":
                created.append(installed)
            else:
                replaced.append((
                    installed,
                    backup_root / installed.relative_to(target_root),
                ))

        for item, installed, _, _ in checks:
            if sha256_file(installed) != item["after_sha256"]:
                raise PatchError(
                    f"post-install verification failed: {item['path']}"
                )

        _atomic_json(release_manifest, release)
    except BaseException:
        for installed, backup in reversed(replaced):
            shutil.copy2(backup, installed)
        for installed in reversed(created):
            try:
                installed.unlink()
            except OSError:
                pass
        for folder in reversed(made_directories):
            try:
                folder.rmdir()
            except OSError:
                # Not empty, so something else is using it. Leaving it is
                # correct; removing it would not be.
                pass
        shutil.copy2(backup_root / "RELEASE_MANIFEST.json", release_manifest)
        raise

    added = len(created)
    changed = len(replaced)
    return (
        f"applied; {changed} replaced, {added} added; "
        f"originals retained in {backup_root}"
    )


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
