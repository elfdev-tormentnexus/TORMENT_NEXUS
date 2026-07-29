"""Capsule the source tree one subsystem at a time, each saying what it is.

The complete release already ships as machinesoul, but as nine capsules cut
along size boundaries: part04 is the middle of a `.gguf` and can say nothing
about itself. That is correct for distribution and useless for reading.

This cuts the *source* along meaning instead. One capsule per subsystem,
each carrying a description in its metadata, so a directory of images is
navigable without extracting any of them:

    python tools/source_capsules.py build --out dist/source
    python tools/source_capsules.py list dist/source/SOURCE_MANIFEST.json
    python tools/source_capsules.py verify dist/source/SOURCE_MANIFEST.json

Both languages doing the job each is actually good at. machinesoul carries
the bytes and reconstructs them exactly or refuses. The description says
what the bytes are about, and is never mistaken for them -- it sits outside
the SHA-256 gate, which `machinesoul.read_description` states in the stored
text itself.

The description is built from the modules' own docstrings rather than
generated. A summary that was written by whoever wrote the code is a
description; one invented at packaging time is a guess wearing the same
clothes.

Coverage is asserted, not assumed: every source file must land in exactly
one capsule or the build refuses. A subsystem map that silently dropped a
module would produce a set of capsules that looked complete and was not,
which is the failure this project treats as worst.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import machinesoul


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ordered, explicit, and reviewable. A glob would quietly absorb whatever
# appeared next to it; this refuses instead and makes someone look.
SUBSYSTEMS = (
    ("assistant-core", "assistant/core"),
    ("assistant-commands", "assistant/commands"),
    ("assistant-editing", "assistant/editing"),
    ("assistant-memory", "assistant/memory"),
    ("assistant-knowledge", "assistant/knowledge"),
    ("assistant-ui", "assistant/ui"),
    ("assistant-voice", "assistant/voice"),
    ("assistant-visualizer", "assistant/visualizer"),
    ("assistant-web", "assistant/web"),
    ("assistant-hardware", "assistant/hardware"),
    ("assistant-project", "assistant/project"),
    ("assistant-tests", "assistant/tests"),
    ("tools", "tools"),
    ("docs", "docs"),
)

# Files directly under assistant/ rather than in one of its packages.
LOOSE = ("assistant-root", "assistant")

SKIP_DIRS = {"__pycache__", ".git", "backups", "logs", "change_plans",
             "user_library", "builtin", "music", "cache"}

SOURCE_SUFFIXES = {".py", ".md", ".json", ".txt", ".bat", ".ps1"}

# Private runtime state lives under assistant/memory/ beside the source.
# The release packager excludes it by deny pattern and basename; this tool
# is not the packager, so it carries its own refusal rather than trusting
# someone to remember.
NEVER_CAPSULE = {
    "memories.json", "conversation_history.txt", "activity_log.jsonl",
    "session_rhythm.json", "chosen_name.json", "embeddings.json",
    "track_loudness.json", "wifi_sensing_status.json",
}


class SourceCapsuleError(RuntimeError):
    """The capsule set would not describe the tree it claims to."""


def _is_source(name):
    if name in NEVER_CAPSULE:
        return False
    return os.path.splitext(name)[1].lower() in SOURCE_SUFFIXES


def _walk(relative, recurse=True):
    """Source files under a directory, repo-relative, sorted."""
    base = os.path.join(ROOT, relative.replace("/", os.sep))
    if not os.path.isdir(base):
        return []

    found = []
    for current, folders, names in os.walk(base):
        folders[:] = sorted(d for d in folders if d not in SKIP_DIRS)
        if not recurse:
            folders[:] = []
        for name in sorted(names):
            if not _is_source(name):
                continue
            full = os.path.join(current, name)
            found.append(os.path.relpath(full, ROOT).replace("\\", "/"))
    return sorted(found)


def _docstring_summary(path):
    """The first sentence of a module's own docstring, or nothing.

    Deliberately not a parse: reading the first triple-quoted block with
    string handling keeps this dependency-free and is enough for a summary
    line. A file whose docstring cannot be found simply contributes none.
    """
    try:
        with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
            text = handle.read(4000)
    except (OSError, UnicodeDecodeError):
        return None

    for quote in ('"""', "'''"):
        start = text.find(quote)
        if start == -1 or text[:start].strip().startswith("import"):
            continue
        end = text.find(quote, start + 3)
        if end == -1:
            continue
        body = text[start + 3:end].strip()
        first = body.split("\n\n")[0].replace("\n", " ").strip()
        return first[:200] or None
    return None


def describe(name, paths):
    """What this subsystem is, in the words of the code inside it."""
    total = sum(os.path.getsize(os.path.join(ROOT, p)) for p in paths)
    lines = [f"{name}: {len(paths)} files, {total:,} bytes.", ""]

    for path in paths:
        if not path.endswith(".py"):
            continue
        summary = _docstring_summary(path)
        if summary:
            lines.append(f"  {os.path.basename(path)} -- {summary}")

    return "\n".join(lines)


def _digest_of(paths):
    """One digest over the subsystem's contents, path names included.

    Names are hashed alongside bytes because a rename with no edit is still
    a change to what the capsule carries.
    """
    running = hashlib.sha256()
    for path in paths:
        running.update(path.encode("utf-8"))
        with open(os.path.join(ROOT, path), "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                running.update(block)
    return running.hexdigest()


def plan():
    """Which files go in which capsule, with coverage asserted."""
    groups = []
    claimed = {}

    for name, relative in SUBSYSTEMS:
        paths = _walk(relative)
        if not paths:
            continue
        for path in paths:
            if path in claimed:
                raise SourceCapsuleError(
                    f"{path} is claimed by both {claimed[path]} and {name}")
            claimed[path] = name
        groups.append((name, relative, paths))

    loose_name, loose_root = LOOSE
    loose = [p for p in _walk(loose_root, recurse=False) if p not in claimed]
    if loose:
        for path in loose:
            claimed[path] = loose_name
        groups.append((loose_name, loose_root, loose))

    # Every source file under the covered roots must be in exactly one
    # capsule. Anything left over means the map is stale.
    everything = set()
    for relative in ("assistant", "tools", "docs"):
        everything.update(_walk(relative))

    missed = sorted(everything - set(claimed))
    if missed:
        listed = "\n".join(f"  {p}" for p in missed[:20])
        raise SourceCapsuleError(
            f"{len(missed)} source files are in no capsule:\n{listed}\n\n"
            "Add a subsystem for them rather than shipping a set that looks "
            "complete and is not.")

    return groups


def build(out_dir):
    """Write one capsule per subsystem, plus a manifest that verifies them."""
    os.makedirs(out_dir, exist_ok=True)
    groups = plan()
    entries = []

    for name, relative, paths in groups:
        capsule = os.path.join(out_dir, f"SOURCE-{name}.png")
        payload = machinesoul.tar_paths(paths, ROOT)
        machinesoul.build(payload, capsule, frames=4,
                          description=describe(name, paths))
        entries.append({
            "name": name,
            "root": relative,
            "files": len(paths),
            "paths": paths,
            "bytes": len(payload),
            "source_sha256": _digest_of(paths),
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "capsule": os.path.basename(capsule),
            "capsule_sha256": machinesoul._sha256_of_file(capsule).hex(),
        })
        print(f"  {name:24} {len(paths):3d} files  "
              f"{os.path.getsize(capsule):>9,} bytes")

    manifest_path = os.path.join(out_dir, "SOURCE_MANIFEST.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump({"format": "MACHINESOUL_SOURCE1", "capsules": entries},
                  handle, indent=1, sort_keys=True)
    return manifest_path


def verify(manifest_path):
    """Extract every capsule and compare it to what the manifest claims."""
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    folder = os.path.dirname(os.path.abspath(manifest_path))
    problems = []

    for entry in manifest["capsules"]:
        capsule = os.path.join(folder, entry["capsule"])
        try:
            payload, meta = machinesoul.extract(capsule)
        except machinesoul.CapsuleError as error:
            problems.append(f"{entry['name']}: {error}")
            continue

        if meta["sha256"] != entry["payload_sha256"]:
            problems.append(f"{entry['name']}: payload digest differs")
            continue
        print(f"  {entry['name']:24} sha256 verified  {len(payload):>9,} bytes")

    if problems:
        raise SourceCapsuleError("\n".join(problems))
    return len(manifest["capsules"])


def cmd_build(args):
    print(f"capsuling source into {args.out}")
    path = build(args.out)
    print(f"\nmanifest: {path}")
    return 0


def cmd_verify(args):
    try:
        count = verify(args.manifest)
    except SourceCapsuleError as error:
        print(f"refused: {error}")
        return 1
    print(f"\n{count} capsules verified")
    return 0


def cmd_list(args):
    """What the set contains, read from metadata without decoding it."""
    with open(args.manifest, encoding="utf-8") as handle:
        manifest = json.load(handle)
    folder = os.path.dirname(os.path.abspath(args.manifest))

    for entry in manifest["capsules"]:
        described = machinesoul.read_description(
            os.path.join(folder, entry["capsule"]))
        print(f"== {entry['capsule']}")
        print(described or "  (no description)")
        print()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="write one capsule per subsystem")
    b.add_argument("--out", required=True)
    b.set_defaults(func=cmd_build)

    v = sub.add_parser("verify", help="extract every capsule and check it")
    v.add_argument("manifest")
    v.set_defaults(func=cmd_verify)

    l = sub.add_parser("list", help="read every description without decoding")
    l.add_argument("manifest")
    l.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
