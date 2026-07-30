"""
Build a self-contained, fully offline copy of the assistant to hand to
someone else.

The output folder installs with one run of setup.bat and touches nothing
on the target machine: no system Python, no PATH, no registry. Everything
-- interpreter, wheels, model weights, llama.cpp binaries -- travels in
the package, because the whole point of this project is that it works with
no network.

Three things drive the design:

Bundled interpreter. This project runs on Python 3.14, which almost nobody
has yet, and offline wheels are built for one exact version. Rather than
demand the recipient install a specific Python, the package carries the
embeddable distribution matching the wheels.

Privacy by default. The source tree contains real conversation history,
extracted memories, and a generated API key. Those are excluded by an
explicit denylist, and `--verify` re-scans the finished package for them
rather than trusting that the copy did the right thing.

Nothing is guessed about what to include. Anything not named is left out,
so a new stray folder cannot silently end up in a package sent to someone
else.

    python tools/package_release.py                 build into dist/
    python tools/package_release.py --archive       ... and zip it
    python tools/package_release.py --split         cut the ZIP for GitHub
    python tools/package_release.py --verify-only   re-check an existing build
    python tools/package_release.py --skip-download reuse cached wheels/python
"""

import argparse
import fnmatch
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime, timezone

# Files that could not be copied because something held them open. The
# usual cause is a process still running out of dist/ -- the glitch
# animator started with the packaged interpreter will do it.
LOCKED = []

# This script lives in tools/, so the project root is one level up.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
PACKAGE_NAME = "TORMENT_NEXUS"
STAGE = os.path.join(DIST, PACKAGE_NAME)
CACHE = os.path.join(DIST, ".cache")
MANIFEST_NAME = "RELEASE_MANIFEST.json"
# Letters, not a semantic version. A build shipping weakened-refusal models
# and an unproven representation is not a "beta" in the ordinary sense, and
# v0.3 / v1.0 would promise an ordered maturity this does not have. One
# letter per release: researchA, researchB, and so on.
RELEASE_VERSION = "researchB"
ARCHIVE_STEM = f"{PACKAGE_NAME}-{RELEASE_VERSION}-windows-x64"
ARCHIVE_NAME = f"{ARCHIVE_STEM}.zip"

# GitHub rejects a release asset over 2 GiB. The margin covers the difference
# between the API's accounting and ours, and costs nothing.
MAX_ASSET_BYTES = 2 * 1024**3 - 64 * 1024**2

# This helper is generated from the actual number of split parts. A hand-made
# helper once knew about only two parts; a later part would then be silently
# omitted and leave every recipient with a corrupt archive.
REASSEMBLER_NAME = f"REASSEMBLE_{ARCHIVE_STEM}.bat"

# Documentation that ships inside the archive is frozen at build time, so a
# correction made afterwards is stale in every copy already zipped. The
# reassembler applies this small optional asset after it extracts. It is
# documentation only and never touches a manifest-hashed file, so the
# installed tree still matches the published archive checksum. Built by
# tools/build_docs_patch.py; absent is fine and the install continues.
DOCS_PATCH_NAME = f"{PACKAGE_NAME}-{RELEASE_VERSION}-docs-patch.zip"

# The opposite case, and the reason the two are separate assets. This one
# replaces assistant/main.py, which the manifest hashes, so applying it makes
# the installed tree diverge from the published archive on purpose. The
# reassembler therefore names it and explains it but never runs it: the
# choice is the operator's, and an unmentioned choice is not one. Built by
# tools/build_ask_guard_patch.py.
ASK_GUARD_PATCH_NAME = f"{PACKAGE_NAME}-{RELEASE_VERSION}-ask-guard-patch.zip"
ASK_GUARD_INSTALLER = "INSTALL_ASK_GUARD_PATCH.bat"
COMMAND_GUARD_PATCH_NAME = (
    f"{PACKAGE_NAME}-{RELEASE_VERSION}-command-guard-patch.zip"
)
COMMAND_GUARD_INSTALLER = "INSTALL_COMMAND_GUARD_PATCH.bat"

# Every hand-applied patch, in the order the reassembler names them. Each
# replaces a manifest-hashed file and is therefore never applied for the
# operator, only named.
MANUAL_PATCH_INSTALLERS = (
    ASK_GUARD_INSTALLER,
    COMMAND_GUARD_INSTALLER,
)

PYTHON_VERSION = "3.14.6"
EMBED_URL = (f"https://www.python.org/ftp/python/{PYTHON_VERSION}"
             f"/python-{PYTHON_VERSION}-embed-amd64.zip")
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
WHEEL_CACHE = os.path.join(
    CACHE,
    f"wheels-cp{PYTHON_VERSION.replace('.', '')}-win_amd64",
)
WHEEL_CACHE_MANIFEST = os.path.join(WHEEL_CACHE, "SHA256SUMS.json")

MODEL_ARTIFACTS = (
    {
        "role": "director",
        "identity": "Qwen3-4B-Abliterated-Q8_0",
        "path": "models/Qwen3-4B-abliterated-bf16_q8_0.gguf",
    },
    {
        "role": "autonomous-coder",
        "identity": "Qwen2.5-Coder-7B-Abliterated-Q8_0",
        "path": "models/Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf",
    },
    {
        "role": "semantic-embedding",
        "identity": "bge-small-en-v1.5-q8_0",
        "path": "models/embedding/bge-small-en-v1.5-q8_0.gguf",
    },
)

# Only these are copied. Everything else is left behind on purpose.
INCLUDE_DIRS = [
    ("assistant", "assistant"),
    ("icon_anim", "icon_anim"),
    ("llama.cpp/build/bin/Release", "llama.cpp/build/bin/Release"),
    ("models/voice/piper", "models/voice/piper"),
    ("models/voice/sherpa-onnx-moonshine-tiny-en-int8",
     "models/voice/sherpa-onnx-moonshine-tiny-en-int8"),
]

# Source code is packaged from Git's tracked-file inventory, not by walking
# the working directory.  A private runtime file can be intentionally ignored
# by Git (and therefore leave ``git status`` clean); recursively copying the
# directory would still publish it.  Runtime/vendor trees below are explicit
# release inputs and remain recursive because many of their generated binary
# files are not represented in this repository's index.
TRACKED_ONLY_DIRS = {"assistant"}

INCLUDE_FILES = [
    # The project's own documentation, not just the installer's README.
    # A package built for someone to review is missing its most useful
    # file if the front door is left behind.
    "README.md",
    "CHANGELOG.md",
    "docs/ARCHITECTURE.md",
    "docs/BETA_GUIDE.md",
    "docs/BRING_YOUR_OWN_GGUF.md",
    "docs/FIRST_RUN.md",
    "docs/INSTALL_WINDOWS.md",
    "docs/MACHINESOUL_RELEASE_CUT_METHOD.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/TESTING.md",
    "docs/TROUBLESHOOTING.md",
    "docs/WIFI_SENSING_EXPERIMENT.md",
    "docs/WIFI_SENSING_NEXT_STEP.md",
    "docs/AGENT_INTERFACE.md",
    "docs/CAPABILITIES_AND_LIMITS.md",
    "docs/SUPER_DEV_HAZARD.md",
    "docs/OFFLINE_KNOWLEDGE.md",
    "docs/RELEASE_NOTES_researchA.md",
    "docs/RESEARCHA_PRE_RELEASE_SESSION_2026-07-29.md",
    "docs/RESEARCHB_STAGING_PLAN.md",
    "docs/VECTOR_TRANSLATION_RESEARCH.md",
    "docs/VECTOR_PIXEL_RESEARCH.md",
    "docs/RESEARCH_GOALS.md",
    "docs/RESEARCH_ROADMAP.md",
    "docs/SEMANTIC_AND_AGENT_BRIDGES.md",
    "docs/SENSING_MODULE.md",
    "docs/TDECK_CUSTOM_FIRMWARE.md",
    "LICENSES/AGPL-3.0.txt",
    "LICENSES/BGE_SMALL_EN_V1.5_NOTICE.txt",
    "LICENSES/LLAMA_CPP_MIT.txt",
    "LICENSES/QWEN_APACHE-2.0.txt",
    "LICENSES/SILERO_VAD_MIT.txt",
    "setup/requirements.txt",
    "setup/requirements-voice.txt",
    "setup/requirements-hardware.txt",
    "setup/requirements-release-windows.txt",
    "start_assistant.bat",
    "start_assistant_hazard.bat",
    "start_super_dev_hazard.bat",
    "start_interface_mode.bat",
    "start_maintenance_coder.bat",
    "start_autonomous_self_heal.bat",
    "start_full_maintenance_coder.bat",
    "setup/test_assistant.bat",
    "tools/glitch_icon.py",
    "tools/machinesoul.py",
    "tools/machinesoul_release.py",
    "tools/make_interface_shortcut.py",
    "tools/package_model_pack.py",
    "tools/package_release.py",
    "tools/build_super_dev_icon.py",
    "tools/rosetta_stone.py",
    "tools/source_capsules.py",
    "tools/vector_beam.py",
    "tools/wifi_sense_collector.py",
    "tools/reassemble_release_parts.bat",
    "tools/start_glitch.bat",
    "tools/stop_glitch.bat",
    "assets/assistant_icon.ico",
    "assets/assistant_icon_animated.gif",
    "assets/assistant_icon_animated.png",
    "assets/assistant_icon_interface.ico",
    "assets/hazard_icon.ico",
    "assets/hazard_icon.png",
    # The README's header image. Without it the front page of a reconstructed
    # release is a broken image link.
    "assets/sable_field.png",
    # Super Dev Hazard's shortcut icon, and the script that regenerates it.
    # Shipping the icon without its builder leaves a shortcut that cannot be
    # rebuilt after a move.
    "assets/super_dev_icon.ico",
    "models/Qwen3-4B-abliterated-bf16_q8_0.gguf",
    "models/Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf",
    "models/embedding/bge-small-en-v1.5-q8_0.gguf",
    "models/voice/silero_vad.onnx",
]

# Disclosure and community files are release inputs once they exist, but a
# branch that has not introduced one yet should not fail solely because of a
# future-facing filename. All other INCLUDE_FILES are mandatory.
OPTIONAL_ROOT_DOCUMENTS = (
    "SAFETY.md",
    "PRIVACY.md",
    "MODELS.md",
    "MODEL_DISCLOSURE.md",
    "MODELS_AND_RISKS.md",
    "THIRD_PARTY_NOTICES.md",
    "NOTICES.md",
    "RIGHTS.md",
    "USER_RIGHTS.md",
    "PROJECT_RIGHTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "LICENSE",
    "LICENSE.md",
    "NOTICE",
)
_root_disclosure_names = {
    name for name in OPTIONAL_ROOT_DOCUMENTS
    if os.path.isfile(os.path.join(ROOT, name))
}
for _name in os.listdir(ROOT):
    _upper = _name.upper()
    if (
        os.path.isfile(os.path.join(ROOT, _name))
        and _name.lower().endswith((".md", ".txt"))
        and any(
            marker in _upper
            for marker in (
                "SAFETY",
                "PRIVACY",
                "MODEL",
                "NOTICE",
                "RIGHTS",
                "CONTRIBUT",
                "SECURITY",
            )
        )
    ):
        _root_disclosure_names.add(_name)
INCLUDE_FILES.extend(sorted(_root_disclosure_names))

# Never ship these. Checked again by --verify against the built package.
#
# The music library is excluded for a different reason than the rest: it
# is not private, it is someone else's copyright. Redistributing a music
# mix inside a package handed around to friends is the sender's call to
# make deliberately, not something a build script should do quietly. The
# folder still ships (empty) so the feature works on arrival.
DENY_PATTERNS = [
    "*/memory/conversation_history.txt*",
    "*/memory/memories.json*",
    # Window titles name documents, pages and conversations. This is at
    # least as revealing as the conversation history.
    "*/memory/activity_log.jsonl*",
    # Session timings. Text never enters this file, but when someone sits
    # down, how long they stay and how long they pause is behavioural data
    # about a person, and a fresh copy must start with no history rather
    # than inherit the build machine's. PRIVACY.md describes it as the
    # operator's own; shipping it would make that false.
    "*/memory/session_rhythm.json*",
    # A future external Wi-Fi research collector may write one aggregate
    # status record here. It belongs to the running installation, never a
    # shareable package.
    "*/wifi_sensing_status.json*",
    "*/memory/plan_*.txt",
    "*/memory/change_plans/*",
    "*/backups/*",
    "*/assistant/music/*",
    # Generated desktop links contain absolute paths for this particular PC.
    # They are regenerated locally by glitch_icon.py and are not portable.
    "icon_anim/shortcuts/*",
    "icon_anim/recovered/*",
    "icon_anim/.animator.lock",
    "*.model_api_key",
    ".model_api_key",
    "*.dev_passcode",
    ".dev_passcode",
    "*.tdeck_ble_pin",
    ".tdeck_ble_pin",
    "*.spotify_token",
    ".spotify_token",
    # The read-only agent interface's bearer token. One running install's
    # credential; shipping it would hand a recipient a live one.
    "*.agent_token",
    ".agent_token",
    # Owner-supplied cloud API keys for the opt-in escalation bridge --
    # billing credentials for external accounts.
    "*.anthropic_api_key",
    ".anthropic_api_key",
    "*.openai_api_key",
    ".openai_api_key",
    # Per-install acknowledgement and consent records. Shipping either one
    # could make a fresh copy inherit decisions made on the build machine.
    "*.safety_acknowledgement.json",
    ".safety_acknowledgement.json",
    "*.activity_consent.json",
    ".activity_consent.json",
    "*.tutorial_state.json",
    "*/memory/chosen_name.json",
    "*/logs/*",
    "*/cache/prompt/*",
    # Embedding vectors are derived from the operator's memories and
    # conversation history; they are as private as their sources.
    "*/cache/embeddings.json*",
    # Loudness measurements are keyed by absolute path, so the cache is a
    # list of the operator's music files and where they live -- the same
    # material assistant/music/* is excluded for.
    "*/cache/track_loudness.json*",
    # The offline knowledge engine may ship an empty schema and curated
    # project references, never the operator's imported documents or the
    # derived search database built from them.
    "*/knowledge/user/*",
    "*/knowledge/user_library/*",
    "*/knowledge/imports/*",
    "*/knowledge/uploads/*",
    "*/knowledge/cache/*",
    "*/knowledge/*.db*",
    "*/knowledge/*.sqlite*",
    "*__pycache__*",
    "*.pyc",
    "*.pyo",
    "*.bak",
    "*.backup",
    "*/.claude/*",
    "*.env",
    "*secrets*",
]

# These files are never valid in a handoff, regardless of where a future
# feature writes them. Keeping the basename list beside the deny patterns
# gives verify() a second independent check instead of trusting copy_tree().
PRIVATE_RUNTIME_BASENAMES = {
    ".model_api_key",
    ".dev_passcode",
    ".tdeck_ble_pin",
    ".spotify_token",
    ".agent_token",
    ".anthropic_api_key",
    ".openai_api_key",
    ".safety_acknowledgement.json",
    ".activity_consent.json",
    ".tutorial_state.json",
    # Derived from memories and conversation history, so private like them.
    "embeddings.json",
    # Keyed by absolute path, so it enumerates the operator's music library
    # and its location -- the same material assistant/music/* is kept out
    # of a release for.
    "track_loudness.json",
    # Window titles name documents, pages and conversations. The deny
    # comment above calls this at least as revealing as the conversation
    # history, and that file is in this set -- so this one belongs here too.
    "activity_log.jsonl",
    # When the operator sits down, how long they stay, and how long they
    # pause between turns. No text, which is exactly why it reads as
    # harmless until it is written down next to a date.
    "session_rhythm.json",
    "chosen_name.json",
    "conversation_history.txt",
    "memories.json",
    "wifi_sensing_status.json",
    "knowledge.db",
    "knowledge.sqlite",
    "knowledge.sqlite3",
    "library.db",
    "library.sqlite",
    "library.sqlite3",
}

# Unused alternate voices. The tuned pipeline only uses hfc_female, and
# these are 200MB of dead weight in an already large package.
SKIP_NAMES = [
    "en_GB-vctk-medium.onnx",
    "en_GB-vctk-medium.onnx.json",
    "en_US-lessac-medium.onnx",
    "en_US-lessac-medium.onnx.json",
    "en_US-libritts_r-medium.onnx",
    "en_US-libritts_r-medium.onnx.json",
]


def private_basename(name):
    """True for a personal runtime file, including its recovery variants.

    Exact matching missed the sidecars runtime code writes beside the real
    file -- memory_store recovers a malformed store to
    ``memories.json.<stamp>.invalid-shape``, which holds the original memory
    data and is caught by the deny patterns but was invisible to this second,
    supposedly independent check.
    """
    if name in PRIVATE_RUNTIME_BASENAMES:
        return True

    return any(
        name.startswith(private + ".")
        for private in PRIVATE_RUNTIME_BASENAMES
    )


def denied(relpath):
    posix = relpath.replace("\\", "/")
    return any(
        fnmatch.fnmatch(posix, pattern) or fnmatch.fnmatch(
            "/" + posix, pattern)
        for pattern in DENY_PATTERNS
    )


class ReleaseBuildError(RuntimeError):
    """A release invariant failed before a sendable artifact was produced."""


SOURCE_STATE = {
    "commit": "unknown",
    "dirty": True,
    "working_tree_sha256": None,
}


def _git(args):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _path_is_within(path, parent):
    """Return whether *path* resolves at or below *parent*."""
    try:
        path = os.path.normcase(os.path.realpath(path))
        parent = os.path.normcase(os.path.realpath(parent))
        return os.path.commonpath((path, parent)) == parent
    except ValueError:
        # Different Windows drives cannot overlap.
        return False


def _configured_private_paths():
    """Yield configured operator-owned knowledge paths without importing it."""
    for variable, kind in (
        ("TORMENT_NEXUS_KNOWLEDGE_DIR", "directory"),
        ("TORMENT_NEXUS_KNOWLEDGE_DB", "database"),
    ):
        raw = os.environ.get(variable, "").strip()
        if not raw:
            continue

        expanded = os.path.expanduser(os.path.expandvars(raw))
        # The knowledge library currently accepts relative paths.  Its
        # launchers run from the project root, while a developer can invoke
        # this packager from another working directory.  Check both plausible
        # resolutions so changing the invocation directory cannot turn a
        # refusal into a leak.
        candidates = {
            os.path.realpath(os.path.abspath(expanded)),
            os.path.realpath(os.path.join(ROOT, expanded)),
        }
        for path in sorted(candidates):
            yield variable, kind, path


def _validate_configured_private_paths():
    """Refuse a build whose custom knowledge storage overlaps its inputs."""
    include_dirs = [
        os.path.join(ROOT, rel.replace("/", os.sep))
        for rel, _ in INCLUDE_DIRS
    ]
    include_files = [
        os.path.join(ROOT, rel.replace("/", os.sep))
        for rel in INCLUDE_FILES
    ]

    for variable, kind, private_path in _configured_private_paths():
        if kind == "directory":
            overlap = any(
                _path_is_within(private_path, source)
                or _path_is_within(source, private_path)
                for source in include_dirs
            ) or any(
                _path_is_within(source, private_path)
                for source in include_files
            )
        else:
            overlap = any(
                _path_is_within(private_path, source)
                for source in include_dirs
            ) or any(
                os.path.normcase(os.path.realpath(source))
                == os.path.normcase(private_path)
                for source in include_files
            )

        if overlap:
            raise ReleaseBuildError(
                f"{variable} points {kind} storage inside the release "
                "input tree; move it outside the project or unset the "
                "variable before packaging"
            )


def _tracked_files_under(src_rel):
    """Return tracked files below *src_rel*, refusing unsafe fallbacks."""
    normalized_root = src_rel.replace("\\", "/").strip("/")
    result = _git([
        "ls-files",
        "--cached",
        "-z",
        "--",
        normalized_root,
    ])
    if result.returncode:
        detail = (result.stderr or "").strip().splitlines()
        suffix = f": {detail[0]}" if detail else ""
        raise ReleaseBuildError(
            "Git's tracked-file inventory is unavailable for "
            f"{normalized_root}; refusing to recursively copy private or "
            f"untracked files{suffix}"
        )

    tracked = [
        item.replace("\\", "/")
        for item in result.stdout.split("\0")
        if item
    ]
    if not tracked:
        raise ReleaseBuildError(
            f"Git returned no tracked files for {normalized_root}; "
            "refusing to use a recursive-copy fallback"
        )

    source_root = os.path.join(
        ROOT,
        normalized_root.replace("/", os.sep),
    )
    prefix = normalized_root + "/"
    for rel in sorted(set(tracked)):
        if not rel.startswith(prefix) or os.path.isabs(rel):
            raise ReleaseBuildError(
                f"Git returned an invalid tracked path for {normalized_root}"
            )

        full = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            raise ReleaseBuildError(
                f"tracked release input is missing or not a file: {rel}"
            )
        if os.path.islink(full) or not _path_is_within(full, source_root):
            raise ReleaseBuildError(
                f"tracked release input escapes through a link: {rel}"
            )

        yield rel, full


def _directory_source_files(src_rel):
    """Yield ``(repository-relative path, full path)`` for one input tree."""
    normalized_root = src_rel.replace("\\", "/").strip("/")
    src = os.path.join(ROOT, normalized_root.replace("/", os.sep))
    if not os.path.isdir(src):
        raise ReleaseBuildError(
            f"required directory is missing: {normalized_root}"
        )

    if normalized_root in TRACKED_ONLY_DIRS:
        yield from _tracked_files_under(normalized_root)
        return

    for folder, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            yield rel, full


def source_state():
    """Return a content-free identity for the source snapshot.

    The status text itself can name private, untracked files, so only its
    digest enters the manifest. A clean release records the commit and
    ``dirty: false``; an explicitly allowed development build records that it
    was dirty without publishing the paths that made it so.
    """
    commit_result = _git(["rev-parse", "HEAD"])
    status_result = _git([
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ])

    if commit_result.returncode or status_result.returncode:
        return {
            "commit": "unknown",
            "dirty": True,
            "working_tree_sha256": None,
        }

    status = status_result.stdout
    return {
        "commit": commit_result.stdout.strip(),
        "dirty": bool(status.strip()),
        "working_tree_sha256": hashlib.sha256(
            status.encode("utf-8")
        ).hexdigest(),
    }


def require_release_source(allow_dirty, report):
    state = source_state()

    if state["commit"] == "unknown" and not allow_dirty:
        raise ReleaseBuildError(
            "the source commit could not be identified; use a Git checkout "
            "or --allow-dirty for a clearly marked development build"
        )

    if state["dirty"] and not allow_dirty:
        raise ReleaseBuildError(
            "the working tree is not clean; commit or remove every intended "
            "source change before a final build, or use --allow-dirty only "
            "for a non-release development package"
        )

    label = state["commit"]
    if state["dirty"]:
        label += " (DIRTY development snapshot)"
    report.append(f"  source {label}")
    return state


def _included_source_files():
    """Yield every source file the whitelist would copy."""
    seen = set()
    _validate_configured_private_paths()

    for src_rel, _ in INCLUDE_DIRS:
        for rel, full in _directory_source_files(src_rel):
            name = os.path.basename(full)
            if denied(rel) or name in SKIP_NAMES:
                continue

            normalized = rel.replace("\\", "/")
            if normalized not in seen:
                seen.add(normalized)
                yield normalized, full

    for rel in INCLUDE_FILES:
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            raise ReleaseBuildError(f"required file is missing: {rel}")
        if denied(rel):
            raise ReleaseBuildError(
                f"required file is also denylisted: {rel}"
            )

        normalized = rel.replace("\\", "/")
        if normalized not in seen:
            seen.add(normalized)
            yield normalized, full


def input_snapshot():
    """Cheaply identify every release input before and after staging."""
    snapshot = {}

    for rel, full in _included_source_files():
        stat = os.stat(full)
        snapshot[rel] = (stat.st_size, stat.st_mtime_ns)

    return snapshot


def copy_tree(src, dst, report, src_rel=None):
    if not os.path.isdir(src):
        raise ReleaseBuildError(f"required directory is missing: {src}")

    copied = skipped = 0

    if src_rel is None:
        src_rel = os.path.relpath(src, ROOT).replace("\\", "/")

    for rel, full in _directory_source_files(src_rel):
        name = os.path.basename(full)
        if denied(rel) or name in SKIP_NAMES:
            skipped += 1
            continue

        target = os.path.join(dst, os.path.relpath(full, src))
        os.makedirs(os.path.dirname(target), exist_ok=True)

        # A locked file must never be silently omitted: that ships a
        # package missing pieces nobody notices until it fails on
        # someone else's machine. Retry briefly, then record it so the
        # build can refuse to continue.
        for attempt in range(3):
            try:
                shutil.copy2(full, target)
                copied += 1
                break
            except PermissionError:
                if attempt == 2:
                    LOCKED.append(rel)
                else:
                    time.sleep(0.4 * (attempt + 1))
            except OSError as error:
                LOCKED.append(f"{rel} ({error})")
                break

    return copied, skipped


def _rmtree_stubborn(path, attempts=6):
    """
    Delete a tree that Windows may still be holding.

    A just-written 3GB folder is routinely locked for a few seconds by
    antivirus or a lingering shell, and a plain rmtree turns that into a
    hard failure halfway through a long build.
    """
    import stat
    import time

    def clear_readonly(func, target, _):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    for attempt in range(attempts):
        try:
            shutil.rmtree(path, onexc=clear_readonly)
            return True
        except (PermissionError, OSError):
            if attempt == attempts - 1:
                raise
            time.sleep(1.5 * (attempt + 1))

    return False


def stage(report):
    # Validate the complete whitelist before removing a previously good stage.
    # A missing model or document is a failed build, never a warning buried in
    # several hundred copy lines.
    list(_included_source_files())

    if os.path.isdir(STAGE):
        _rmtree_stubborn(STAGE)
    os.makedirs(STAGE)

    total_copied = total_skipped = 0

    for src_rel, dst_rel in INCLUDE_DIRS:
        src = os.path.join(ROOT, src_rel.replace("/", os.sep))
        dst = os.path.join(STAGE, dst_rel.replace("/", os.sep))
        copied, skipped = copy_tree(src, dst, report, src_rel=src_rel)
        total_copied += copied
        total_skipped += skipped
        report.append(f"  {src_rel:52s} {copied:5d} files"
                      + (f"  ({skipped} withheld)" if skipped else ""))

    for rel in INCLUDE_FILES:
        src = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(src):
            raise ReleaseBuildError(f"required file is missing: {rel}")
        dst = os.path.join(STAGE, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        total_copied += 1

    # Empty working folders, so the recipient's TORMENT_NEXUS starts with a blank
    # history instead of inheriting someone else's -- and so the music
    # feature has somewhere to look on first run.
    for sub in ("logs", "cache/prompt", "music"):
        os.makedirs(os.path.join(STAGE, "assistant", sub.replace("/", os.sep)),
                    exist_ok=True)

    return total_copied, total_skipped


def fetch(url, dest, report, allow_download=True):
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        report.append(f"  cached  {os.path.basename(dest)}")
        return True

    if not allow_download:
        report.append(
            f"  MISSING cached download {os.path.basename(dest)}"
        )
        return False

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        with open(dest, "wb") as handle:
            handle.write(data)
        report.append(f"  fetched {os.path.basename(dest)} "
                      f"({len(data)/1e6:.1f} MB)")
        return True
    except Exception as error:
        report.append(f"  FAILED  {url}: {error}")
        return False


def bundle_python(report, skip_download=False):
    embed_zip = os.path.join(CACHE, os.path.basename(EMBED_URL))
    get_pip = os.path.join(CACHE, "get-pip.py")

    if not fetch(
        EMBED_URL,
        embed_zip,
        report,
        allow_download=not skip_download,
    ):
        return False
    if not fetch(
        GET_PIP_URL,
        get_pip,
        report,
        allow_download=not skip_download,
    ):
        return False

    target = os.path.join(STAGE, "python")
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(embed_zip) as archive:
        archive.extractall(target)

    # The embeddable build disables site-packages by default; without this
    # pip installs land somewhere the interpreter will not look.
    for name in os.listdir(target):
        if name.endswith("._pth"):
            path = os.path.join(target, name)
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            text = text.replace("#import site", "import site")
            if "import site" not in text:
                text += "\nimport site\n"
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            report.append(f"  enabled site in {name}")

    shutil.copy2(get_pip, os.path.join(target, "get-pip.py"))
    report.append(f"  embedded Python {PYTHON_VERSION} staged")
    return True


def _wheel_files(folder):
    return sorted(
        name for name in os.listdir(folder)
        if name.endswith((".whl", ".zip"))
        and os.path.isfile(os.path.join(folder, name))
    )


def _write_wheel_cache_manifest(folder):
    files = [
        {
            "name": name,
            "bytes": os.path.getsize(os.path.join(folder, name)),
            "sha256": _hash_file(os.path.join(folder, name)),
        }
        for name in _wheel_files(folder)
    ]
    payload = {
        "format": 1,
        "python": PYTHON_VERSION,
        "platform": "win_amd64",
        "files": files,
    }
    path = os.path.join(folder, os.path.basename(WHEEL_CACHE_MANIFEST))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _verify_wheel_cache(report):
    if not os.path.isdir(WHEEL_CACHE):
        report.append(f"  MISSING wheel cache {WHEEL_CACHE}")
        return False

    manifest = os.path.join(
        WHEEL_CACHE,
        os.path.basename(WHEEL_CACHE_MANIFEST),
    )
    try:
        with open(manifest, "r", encoding="utf-8") as source:
            payload = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        report.append(f"  invalid wheel cache manifest: {error}")
        return False

    entries = payload.get("files")
    if (
        payload.get("format") != 1
        or payload.get("python") != PYTHON_VERSION
        or payload.get("platform") != "win_amd64"
        or not isinstance(entries, list)
    ):
        report.append("  wheel cache manifest does not match this release")
        return False

    expected = set()
    for entry in entries:
        if not isinstance(entry, dict):
            report.append("  malformed wheel cache entry")
            return False
        name = entry.get("name")
        if (
            not isinstance(name, str)
            or name != os.path.basename(name)
            or not name.endswith((".whl", ".zip"))
        ):
            report.append(f"  unsafe wheel cache entry: {name!r}")
            return False

        path = os.path.join(WHEEL_CACHE, name)
        expected.add(name)
        if not os.path.isfile(path):
            report.append(f"  cached wheel is missing: {name}")
            return False
        if os.path.getsize(path) != entry.get("bytes"):
            report.append(f"  cached wheel size mismatch: {name}")
            return False
        if _hash_file(path) != entry.get("sha256"):
            report.append(f"  cached wheel hash mismatch: {name}")
            return False

    actual = set(_wheel_files(WHEEL_CACHE))
    if actual != expected or not actual:
        report.append("  wheel cache contents do not match its manifest")
        return False

    report.append(f"  verified cached wheels ({len(actual)} files)")
    return True


def _download_wheel_cache(report):
    os.makedirs(CACHE, exist_ok=True)
    temporary = tempfile.mkdtemp(prefix=".wheels-", dir=CACHE)

    reqs = [os.path.join(ROOT, "setup", "requirements-release-windows.txt")]

    command = [sys.executable, "-m", "pip", "download",
               "--dest", temporary,
               "--only-binary", ":all:",
               "--python-version", ".".join(PYTHON_VERSION.split(".")[:2]),
               "--platform", "win_amd64",
               "--implementation", "cp"]
    for req in reqs:
        command += ["-r", req]
    command += ["pip", "setuptools", "wheel"]

    try:
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            report.append("  pip download FAILED:")
            report.append("  " + result.stderr.strip()[-900:])
            return False

        if not _wheel_files(temporary):
            report.append("  pip download produced no wheels")
            return False

        _write_wheel_cache_manifest(temporary)
        if os.path.isdir(WHEEL_CACHE):
            _rmtree_stubborn(WHEEL_CACHE)
        os.replace(temporary, WHEEL_CACHE)
        temporary = None
        report.append("  refreshed the verified wheel cache")
        return True
    finally:
        if temporary and os.path.isdir(temporary):
            shutil.rmtree(temporary, ignore_errors=True)


def bundle_wheels(report, skip_download=False):
    wheels = os.path.join(STAGE, "wheels")
    os.makedirs(wheels, exist_ok=True)

    if not skip_download and not _download_wheel_cache(report):
        return False
    if not _verify_wheel_cache(report):
        if skip_download:
            report.append(
                "  --skip-download requires a complete verified wheel cache"
            )
        return False

    names = _wheel_files(WHEEL_CACHE)
    for name in names:
        shutil.copy2(
            os.path.join(WHEEL_CACHE, name),
            os.path.join(wheels, name),
        )

    count = len(names)
    size = sum(
        os.path.getsize(os.path.join(wheels, name))
        for name in names
    ) / 1e6
    report.append(f"  {count} wheels ({size:.0f} MB)")
    return True


RUNTIME_ARTIFACTS = (
    "assistant/.model_api_key",
    "assistant/.dev_passcode",
    "assistant/.tdeck_ble_pin",
    "assistant/.spotify_token",
    "assistant/.agent_token",
    "assistant/memory/conversation_history.txt",
    "assistant/memory/memories.json",
    # Its absence is what marks a fresh install. Shipping it would rob the
    # recipient of the first-run walkthrough entirely.
    "assistant/.tutorial_state.json",
    # Likewise: a recipient's copy should hold its own naming ceremony rather
    # than arrive already answering to this one's.
    "assistant/memory/chosen_name.json",
)


def sanitize(report):
    """
    Remove files the app creates the moment it is run.

    Building a clean package is not enough on its own. Test-running
    setup.bat inside the staged folder makes the assistant generate an API
    key and initialise its memory store, so a sensible build-test-send
    sequence would ship exactly the files the denylist exists to keep out.
    This is run at the end of every build, and can be run on its own after
    testing a package by hand.
    """
    removed = []

    manifest_path = os.path.join(STAGE, MANIFEST_NAME)
    if os.path.isfile(manifest_path):
        os.remove(manifest_path)
        removed.append(MANIFEST_NAME)

    for rel in RUNTIME_ARTIFACTS:
        path = os.path.join(STAGE, rel.replace("/", os.sep))
        if os.path.isfile(path):
            os.remove(path)
            removed.append(rel)

    for folder, dirs, files in os.walk(STAGE):
        for name in list(dirs):
            if name == "__pycache__":
                shutil.rmtree(os.path.join(folder, name), ignore_errors=True)
                dirs.remove(name)
                removed.append(os.path.relpath(
                    os.path.join(folder, name), STAGE))

        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, STAGE)
            if denied(rel):
                os.remove(full)
                removed.append(rel)

    if removed:
        report.append(f"  removed {len(removed)} runtime artifact(s)")
        for item in removed[:6]:
            report.append(f"    - {item}")
    else:
        report.append("  nothing to clean")

    return removed


def verify(report):
    """Re-scan the built package for anything personal that slipped in."""
    problems = []
    scanned = 0

    for folder, dirs, files in os.walk(STAGE):
        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, STAGE)
            scanned += 1

            if denied(rel):
                problems.append(f"denylisted file present: {rel}")

            if private_basename(name):
                problems.append(f"personal file present: {rel}")

    report.append(f"  scanned {scanned} files in the package")

    for label, path in (
        ("memory dir", os.path.join(STAGE, "assistant", "memory")),
    ):
        if os.path.isdir(path):
            leftovers = [n for n in os.listdir(path)
                         if n in ("memories.json", "conversation_history.txt")]
            if leftovers:
                problems.append(f"{label} still holds {leftovers}")

    _verify_release_launchers(report, problems)
    _verify_manifest(report, problems)

    return problems


def _verify_release_launchers(report, problems):
    """Ensure the handoff starts with its embedded interpreter, not the host."""
    expectations = {
        # Paths are package-relative, and the launchers keep the folders
        # they live in at source.
        "start_assistant.bat": "python\\python.exe",
        "start_assistant_hazard.bat": "start_assistant.bat",
        "start_super_dev_hazard.bat": "start_assistant_hazard.bat",
        "start_interface_mode.bat": "start_assistant.bat",
        "tools/start_glitch.bat": "..\\python\\pythonw.exe",
        "tools/stop_glitch.bat": "..\\python\\python.exe",
        "setup/test_assistant.bat": "python\\python.exe",
        "setup.bat": "setup\\requirements-release-windows.txt",
    }

    for name, required_text in expectations.items():
        path = os.path.join(STAGE, name)
        try:
            with open(path, "r", encoding="utf-8") as source:
                contents = source.read().lower()
        except OSError:
            problems.append(f"missing release launcher: {name}")
            continue

        if required_text.lower() not in contents:
            problems.append(
                f"release launcher does not use the self-contained setup: {name}"
            )

    report.append(f"  checked {len(expectations)} self-contained launchers")


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash_parts(paths):
    """Return the byte count and SHA-256 of a binary concatenation."""
    digest = hashlib.sha256()
    total = 0

    for path in paths:
        with open(path, "rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
                total += len(block)

    return total, digest.hexdigest()


def _write_reassembler(part_paths, target, archive_sha256):
    """Generate a batch helper for exactly these parts, with CRLF endings."""
    names = [os.path.basename(path) for path in part_paths]
    lines = [
        "@echo off",
        "setlocal",
        'set "HERE=%~dp0"',
        f'set "ZIP=%HERE%{ARCHIVE_NAME}"',
        f'set "EXPECTED={archive_sha256.upper()}"',
        "",
        "REM The closing quote matters. Without it the variable expands and the",
        "REM opening \"(\" is swallowed into the quoted filename, so cmd loses the",
        "REM start of the block and the script fails in a way that points nowhere",
        "REM near the actual line.",
    ]
    variables = []

    for number, name in enumerate(names, 1):
        variable = f"PART{number}"
        variables.append(variable)
        lines.extend((
            "",
            f'set "{variable}=%HERE%{name}"',
            f'if not exist "%{variable}%" (',
            f"    echo Missing {name} in this folder.",
            "    pause",
            "    exit /b 1",
            ")",
        ))

    copy_sources = "+".join(f'"%{variable}%"' for variable in variables)
    lines.extend((
        "",
        "echo Reassembling the complete beta package...",
        f'copy /b {copy_sources} "%ZIP%" >nul',
        "if errorlevel 1 (",
        f"    echo Could not create {ARCHIVE_NAME}.",
        "    pause",
        "    exit /b 1",
        ")",
        "",
        "echo.",
        "echo Verifying the complete archive...",
        'set "ACTUAL="',
        "for /f \"skip=1 tokens=* delims=\" %%H in ('certutil -hashfile \"%ZIP%\" SHA256') do (",
        '    if not defined ACTUAL set "ACTUAL=%%H"',
        ")",
        'set "ACTUAL=%ACTUAL: =%"',
        'if /i not "%ACTUAL%"=="%EXPECTED%" (',
        "    echo.",
        "    echo CHECKSUM MISMATCH - the joined ZIP is not this release.",
        "    echo Expected: %EXPECTED%",
        "    echo Actual:   %ACTUAL%",
        '    del "%ZIP%" >nul 2>&1',
        "    pause",
        "    exit /b 1",
        ")",
        "",
        "echo Verified: %ZIP%",
        "echo.",
        "",
        "REM %~dp0 ends with a backslash, which can escape the closing quote",
        "REM when handed to PowerShell and silently corrupt the path.",
        'set "ROOT=%HERE%"',
        'if "%ROOT:~-1%"=="\\" set "ROOT=%ROOT:~0,-1%"',
        "",
        'set "INSTALL=%ROOT%\\' + PACKAGE_NAME + '"',
        'if exist "%INSTALL%\\setup.bat" (',
        "    echo Existing folder found - keeping it and skipping extraction.",
        "    goto :apply_patch",
        ")",
        "",
        "echo Extracting the package. This takes a while at this size...",
        "powershell -NoProfile -ExecutionPolicy Bypass -Command "
        "\"Add-Type -AssemblyName System.IO.Compression.FileSystem; "
        "[System.IO.Compression.ZipFile]::ExtractToDirectory('%ZIP%', "
        "'%ROOT%')\"",
        "if errorlevel 1 (",
        "    echo.",
        "    echo Could not extract automatically. Right-click the ZIP and",
        "    echo choose Extract All, then run setup.bat inside it.",
        "    pause",
        "    exit /b 1",
        ")",
        "",
        ":apply_patch",
        f'set "DOCPATCH=%ROOT%\\{DOCS_PATCH_NAME}"',
        'if not exist "%DOCPATCH%" (',
        "    echo Documentation patch not present - skipping it.",
        "    goto :finished",
        ")",
        "",
        "echo Applying the documentation patch...",
        "powershell -NoProfile -ExecutionPolicy Bypass -Command "
        "\"Expand-Archive -LiteralPath '%DOCPATCH%' -DestinationPath "
        "'%ROOT%' -Force\"",
        "if errorlevel 1 (",
        "    echo.",
        "    echo The documentation patch did not apply. This is harmless:",
        "    echo only bundled documents are affected and the release page",
        "    echo always has the current versions.",
        ")",
        "",
        ":finished",
        "echo.",
        f"echo Done. Open the {PACKAGE_NAME} folder and run setup.bat.",
        "echo.",
        # The reassembler deliberately applies none of these. Each replaces a
        # manifest-hashed file, so running one is the operator's decision --
        # but a decision nobody is told about is not one, and this screen is
        # the last thing they read.
        #
        # Written as flat gotos rather than nested if/else blocks: a bare
        # "if exist" inside a parenthesised block is where cmd's parsing
        # turns fragile, and this file already carries one comment about a
        # swallowed quote costing an afternoon.
        'set "ANYPATCH="',
    ))

    for installer in MANUAL_PATCH_INSTALLERS:
        lines.append(
            f'if exist "%ROOT%\\{installer}" set "ANYPATCH=1"'
        )

    lines.extend((
        "if not defined ANYPATCH goto :nopatch",
        "echo Manual steps remain, and nothing else will prompt for them.",
        f"echo Move these into the {PACKAGE_NAME} folder, then run each",
        "echo installer:",
        "echo.",
    ))

    for installer in MANUAL_PATCH_INSTALLERS:
        lines.append(
            f'if exist "%ROOT%\\{installer}" echo     {installer}'
        )

    lines.extend((
        "echo.",
        "echo They are applied by hand because, unlike the documentation",
        "echo patch, they replace files the release manifest hashes.",
        "goto :patchdone",
        "",
        ":nopatch",
        "echo Optional patches on the release page correct two cases where",
        "echo this assistant described something it had not actually done.",
        "echo They are applied by hand and are safe to skip.",
        "",
        ":patchdone",
        "pause",
        "",
    ))

    # Batch files are intentionally CRLF even though repository source uses
    # LF. cmd.exe is forgiving, but this preserves the form Windows users
    # expect and keeps generated output distinct from source formatting.
    with open(target, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write("\n".join(lines))


def split(report):
    """Cut the release ZIP into upload-sized parts and prove they rejoin."""
    archive = os.path.join(DIST, ARCHIVE_NAME)
    if not os.path.isfile(archive):
        report.append(f"  MISSING archive  {archive}")
        return False

    archive_size = os.path.getsize(archive)
    archive_hash = _hash_file(archive)
    part_count = max(1, (archive_size + MAX_ASSET_BYTES - 1) // MAX_ASSET_BYTES)
    part_paths = [
        archive + f".part{number:02d}"
        for number in range(1, part_count + 1)
    ]
    reassembler = os.path.join(DIST, REASSEMBLER_NAME)
    expected_parts = {os.path.normcase(os.path.abspath(path)) for path in part_paths}

    # Produce and verify every new asset in a temporary sibling directory.
    # An interrupted write cannot damage the source ZIP or a previously
    # published set of parts.
    try:
        with tempfile.TemporaryDirectory(
            prefix=f".{PACKAGE_NAME}_split_", dir=DIST
        ) as temporary:
            temporary_parts = [
                os.path.join(temporary, os.path.basename(path))
                for path in part_paths
            ]
            with open(archive, "rb") as source:
                for target in temporary_parts:
                    remaining = MAX_ASSET_BYTES
                    with open(target, "wb") as part:
                        while remaining:
                            block = source.read(min(1024 * 1024, remaining))
                            if not block:
                                break
                            part.write(block)
                            remaining -= len(block)

            temporary_reassembler = os.path.join(temporary, REASSEMBLER_NAME)
            _write_reassembler(
                temporary_parts,
                temporary_reassembler,
                archive_hash,
            )

            joined_size, joined_hash = _hash_parts(temporary_parts)
            if joined_size != archive_size or joined_hash != archive_hash:
                report.append(
                    "  REFUSING TO SPLIT - generated parts do not rejoin "
                    "to the source archive."
                )
                return False

            stale_parts = sorted(glob.glob(archive + ".part*"))
            extras = [
                path for path in stale_parts
                if os.path.normcase(os.path.abspath(path)) not in expected_parts
            ]
            if any(not os.path.isfile(path) for path in extras):
                report.append(
                    "  REFUSING TO SPLIT - an unexpected non-file matches "
                    f"{archive}.part*"
                )
                return False

            # Only now replace the derived release assets. The source ZIP is
            # never moved or rewritten. Matching old parts are atomically
            # replaced; obsolete later parts are removed so they cannot be
            # uploaded accidentally beside the generated helper.
            for stale in extras:
                os.remove(stale)
            for source, target in zip(temporary_parts, part_paths):
                os.replace(source, target)
            os.replace(temporary_reassembler, reassembler)
    except OSError as error:
        report.append(f"  SPLIT FAILED: {error}")
        return False

    report.append(
        f"  split {os.path.basename(archive)} into {part_count} part(s) "
        f"of at most {MAX_ASSET_BYTES / 1024**3:.2f} GiB"
    )
    report.append(f"  generated {reassembler}")
    report.append("  verified: the numbered parts rejoin byte-for-byte")
    return True


def discard_stage(report):
    """Remove a rebuildable staged package only after its archive is present."""
    archive = os.path.join(DIST, ARCHIVE_NAME)
    if not os.path.isfile(archive):
        report.append(
            f"  REFUSING TO DISCARD STAGE - archive is missing: {archive}"
        )
        return False

    if not os.path.exists(STAGE):
        report.append("  staged package already absent")
        return True
    if not os.path.isdir(STAGE):
        report.append(
            f"  REFUSING TO DISCARD STAGE - not a directory: {STAGE}"
        )
        return False

    try:
        shutil.rmtree(STAGE)
    except OSError as error:
        report.append(f"  COULD NOT DISCARD STAGE: {error}")
        return False

    report.append(f"  discarded rebuildable staged package: {STAGE}")
    return True


def write_manifest(report, source=None):
    """Record every shipped file so a handoff can be checked later."""
    entries = []

    for folder, _, files in os.walk(STAGE):
        for name in sorted(files):
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, STAGE).replace("\\", "/")

            if rel == MANIFEST_NAME:
                continue

            entries.append({
                "path": rel,
                "bytes": os.path.getsize(full),
                "sha256": _hash_file(full),
            })

    by_path = {entry["path"]: entry for entry in entries}
    models = []
    for artifact in MODEL_ARTIFACTS:
        entry = by_path.get(artifact["path"])
        if not entry:
            raise ReleaseBuildError(
                f"required model is absent from the staged package: "
                f"{artifact['path']}"
            )
        models.append({
            **artifact,
            "bytes": entry["bytes"],
            "sha256": entry["sha256"],
        })

    source = dict(source or SOURCE_STATE)
    payload = {
        "format": 2,
        "package": PACKAGE_NAME,
        "release_version": RELEASE_VERSION,
        "archive": ARCHIVE_NAME,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "commit": source.get("commit", "unknown"),
            "dirty": bool(source.get("dirty", True)),
            "working_tree_sha256": source.get("working_tree_sha256"),
        },
        "models": models,
        "files": entries,
    }
    path = os.path.join(STAGE, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")

    report.append(f"  wrote {MANIFEST_NAME} ({len(entries)} file hashes)")


def _verify_manifest(report, problems):
    path = os.path.join(STAGE, MANIFEST_NAME)

    if not os.path.isfile(path):
        problems.append(f"missing {MANIFEST_NAME}")
        return

    try:
        with open(path, "r", encoding="utf-8") as source:
            payload = json.load(source)
        entries = payload.get("files")
        if payload.get("format") != 2 or not isinstance(entries, list):
            raise ValueError("unsupported manifest format")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        problems.append(f"invalid {MANIFEST_NAME}: {error}")
        return

    listed = set()
    for entry in entries:
        rel = entry.get("path") if isinstance(entry, dict) else None
        expected = entry.get("sha256") if isinstance(entry, dict) else None

        if not isinstance(rel, str) or not isinstance(expected, str):
            problems.append(f"invalid manifest entry: {entry!r}")
            continue

        normalized = os.path.normpath(rel)
        if os.path.isabs(normalized) or normalized.startswith(".." + os.sep):
            problems.append(f"unsafe manifest path: {rel}")
            continue

        full = os.path.join(STAGE, normalized)
        listed.add(rel.replace("\\", "/"))
        if not os.path.isfile(full):
            problems.append(f"manifest file missing: {rel}")
        elif _hash_file(full) != expected:
            problems.append(f"manifest hash mismatch: {rel}")

    actual = set()
    for folder, _, files in os.walk(STAGE):
        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, STAGE).replace("\\", "/")
            if rel != MANIFEST_NAME:
                actual.add(rel)

    for rel in sorted(actual - listed):
        problems.append(f"manifest missing file: {rel}")
    for rel in sorted(listed - actual):
        problems.append(f"manifest lists absent file: {rel}")

    if payload.get("package") != PACKAGE_NAME:
        problems.append("manifest package name does not match this build")
    if payload.get("release_version") != RELEASE_VERSION:
        problems.append("manifest release version does not match this build")
    if payload.get("archive") != ARCHIVE_NAME:
        problems.append("manifest archive name does not match this build")

    source = payload.get("source")
    if not isinstance(source, dict):
        problems.append("manifest source identity is missing")
    else:
        commit = source.get("commit")
        dirty = source.get("dirty")
        tree_hash = source.get("working_tree_sha256")
        if not isinstance(commit, str) or not commit:
            problems.append("manifest source commit is invalid")
        if not isinstance(dirty, bool):
            problems.append("manifest source dirty state is invalid")
        if tree_hash is not None and (
            not isinstance(tree_hash, str) or len(tree_hash) != 64
        ):
            problems.append("manifest working-tree fingerprint is invalid")
        report.append(
            f"  source identity: {commit or 'unknown'}"
            + (" (dirty development build)" if dirty else " (clean)")
        )

    model_entries = payload.get("models")
    expected_models = {
        artifact["path"]: artifact for artifact in MODEL_ARTIFACTS
    }
    found_models = {}
    if not isinstance(model_entries, list):
        problems.append("manifest model inventory is missing")
    else:
        for model in model_entries:
            if not isinstance(model, dict):
                problems.append(f"invalid model inventory entry: {model!r}")
                continue
            rel = model.get("path")
            if not isinstance(rel, str) or rel not in expected_models:
                problems.append(f"unexpected model inventory path: {rel!r}")
                continue
            found_models[rel] = model
            expected = expected_models[rel]
            listed_file = next(
                (
                    entry for entry in entries
                    if isinstance(entry, dict) and entry.get("path") == rel
                ),
                None,
            )
            if model.get("role") != expected["role"]:
                problems.append(f"model role mismatch: {rel}")
            if model.get("identity") != expected["identity"]:
                problems.append(f"model identity mismatch: {rel}")
            if not listed_file or model.get("sha256") != listed_file.get("sha256"):
                problems.append(f"model hash does not match file manifest: {rel}")
            if not listed_file or model.get("bytes") != listed_file.get("bytes"):
                problems.append(f"model size does not match file manifest: {rel}")

    for rel in sorted(set(expected_models) - set(found_models)):
        problems.append(f"manifest model inventory is missing: {rel}")

    report.append(
        f"  manifest checked: {len(listed)} listed, {len(actual)} present"
    )


def write_launcher(report):
    for name, body in (
        ("setup.bat", SETUP_BAT),
        ("make_shortcut.ps1", MAKE_SHORTCUT_PS1),
        ("verify_install.py", VERIFY_INSTALL_PY),
        ("README.txt", README),
    ):
        with open(os.path.join(STAGE, name), "w",
                  encoding="utf-8", newline="\r\n") as handle:
            handle.write(body)
        report.append(f"  wrote {name}")


SETUP_BAT = r"""@echo off
setlocal
title TORMENT_NEXUS setup

echo.
echo   TORMENT_NEXUS - offline install
echo   ==========================
echo.

cd /d "%~dp0"

set "PY=%~dp0python\python.exe"
if not exist "%PY%" (
    echo   ERROR: bundled Python missing. Extract the whole archive first.
    pause
    exit /b 1
)

echo   [1/4] Preparing the bundled Python...
if not exist "%~dp0python\Scripts\pip.exe" (
    REM --no-warn-script-location matters here too, not just on the install
    REM below. get-pip drops pip.exe into python\Scripts, and warning that
    REM the folder is not on PATH is exactly wrong for a self-contained
    REM handoff -- nothing here should be on PATH. A yellow WARNING is the
    REM first thing a new user sees, and it reads like something broke.
    "%PY%" "%~dp0python\get-pip.py" --no-index --find-links "%~dp0wheels" ^
        --quiet --no-warn-script-location
    if errorlevel 1 (
        echo   ERROR: could not set up pip.
        pause
        exit /b 1
    )
)

echo   [2/4] Installing packages from the bundled wheels...
"%PY%" -m pip install --no-index --find-links "%~dp0wheels" ^
    -r "%~dp0setup\requirements-release-windows.txt" ^
    --quiet --no-warn-script-location
if errorlevel 1 (
    echo   ERROR: package install failed.
    pause
    exit /b 1
)

echo   [3/4] Checking the install...
if not exist "%~dp0models\Qwen3-4B-abliterated-bf16_q8_0.gguf" (
    echo   ERROR: the Q8 director model is missing from this package.
    pause
    exit /b 1
)
if not exist "%~dp0models\Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf" (
    echo   ERROR: the 7B autonomous coder model is missing from this package.
    pause
    exit /b 1
)
if not exist "%~dp0models\embedding\bge-small-en-v1.5-q8_0.gguf" (
    echo   ERROR: the semantic embedding model is missing from this package.
    pause
    exit /b 1
)
"%PY%" "%~dp0verify_install.py"
if errorlevel 1 (
    echo   ERROR: the install did not come out working. See above.
    pause
    exit /b 1
)

echo   [4/4] Creating the desktop shortcut...
if defined TORMENT_NEXUS_SKIP_SHORTCUT goto :shortcut_done
REM %~dp0 ends with a backslash, which escapes the closing quote when
REM passed to PowerShell and silently corrupts the path. Strip it.
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1" -Root "%ROOT%"
if errorlevel 1 (
    echo.
    echo   Everything installed, but the desktop shortcut could not be
    echo   created. Launch it with start_assistant.bat in this folder.
    pause
    exit /b 0
)

:shortcut_done
echo.
if defined TORMENT_NEXUS_SKIP_SHORTCUT (
    echo   Done. Shortcut creation was intentionally skipped.
) else (
    echo   Done. 'TORMENT_NEXUS' is on your desktop.
)
echo.
echo   Everything lives in this folder and nothing else on your PC was
echo   changed - no system Python, no PATH, no registry. To uninstall,
echo   delete this folder and the desktop shortcut.
echo.
if defined TORMENT_NEXUS_NONINTERACTIVE exit /b 0
pause
"""


# Kept as its own file rather than inlined into the batch script: escaping
# a multi-line PowerShell command through cmd silently mangled it, and the
# batch then reported success for a shortcut that was never created.
MAKE_SHORTCUT_PS1 = r"""param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = "Stop"

# Defensive: a trailing backslash arriving from cmd can carry a stray
# quote with it, which CreateShortcut rejects with an error that names
# neither the path nor the reason.
$Root = $Root.Trim().TrimEnd('"').TrimEnd('\')

try {
    if (-not (Test-Path $Root)) {
        Write-Host "  install folder not found: $Root"
        exit 1
    }

    $desktop = [Environment]::GetFolderPath('Desktop')
    $path = Join-Path $desktop 'TORMENT_NEXUS.lnk'

    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = (Join-Path $Root 'start_assistant.bat')
    $link.WorkingDirectory = $Root
    $link.IconLocation = (Join-Path $Root 'assistant_icon.ico') + ',0'
    $link.Description = 'A private, offline AI companion'
    $link.Save()

    if (-not (Test-Path $path)) {
        Write-Host "  shortcut was not created"
        exit 1
    }

    Write-Host "  created: $path"
    exit 0
} catch {
    Write-Host ("  shortcut failed: " + $_.Exception.Message)
    exit 1
}
"""


# Runs inside the freshly built environment, so a package that installs
# but cannot actually import its own dependencies fails loudly at install
# time rather than the first time the recipient double-clicks it.
VERIFY_INSTALL_PY = r'''"""
Check the bundled environment really works.

This must reproduce how the launcher actually starts, not a convenient
approximation of it. An earlier version began with

    sys.path.insert(0, os.path.join(HERE, "assistant"))

which manufactured the one condition a real launch never has. The
embeddable interpreter does not put the script's folder on sys.path, so
every project import failed on the recipient's machine -- while this
check reported "verified", because it had quietly supplied the missing
entry itself. A verifier that arranges its own success is worse than no
verifier: it converts a caught bug into a shipped one.

So the check below runs main.py itself, in a separate process, exactly
the way start_assistant.bat runs it: same interpreter, same working
directory, no path help. --check-imports makes it exit after the imports
instead of starting a session.

Probing with `python -c "import core.config"` is NOT equivalent and was
briefly used here by mistake -- it fails even on a healthy install,
because main.py's own path bootstrap never runs. The check has to invoke
the same file the launcher does.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSISTANT = os.path.join(HERE, "assistant")

failures = []

for module in ("numpy", "requests", "sounddevice", "soundfile",
               "soundcard", "piper", "sherpa_onnx"):
    try:
        __import__(module)
    except Exception as error:
        failures.append(f"import {module}: {error}")

# The real test: run main.py the way the launcher does.
try:
    result = subprocess.run(
        [sys.executable, os.path.join(ASSISTANT, "main.py"), "--check-imports"],
        cwd=ASSISTANT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if "IMPORTS_OK" not in (result.stdout or ""):
        detail = (result.stderr or "").strip().splitlines()
        failures.append(
            "the launcher's own start-up fails: "
            + (detail[-1] if detail else "no output")
        )

    for line in (result.stdout or "").splitlines():
        if line.startswith("MISSING:"):
            failures.append(line.partition(":")[2].strip())
except Exception as error:
    failures.append(f"could not run the start-up check: {error}")

if failures:
    print("  install verification FAILED:")
    for item in failures:
        print("    - " + item)
    raise SystemExit(1)

print("  verified: dependencies import and model files are present")
'''

README = rf"""TORMENT_NEXUS {RELEASE_VERSION} - local-first research build
=========================================================

WHAT THIS IS
    A local-first AI companion and tool system that runs on your machine.
    Conversation, memory, and speech work locally after installation. Optional
    web search and hardware features need deliberate separate setup.

WHAT YOU NEED
    - 64-bit Windows
    - About 13 GB for this extracted folder
    - At least 16 GB of RAM for the Q8 director and 7B coder
    - A microphone only if you want to speak; typed input works without one

    The machinesoul capsules, decoded vector segments, and reconstructed
    folder can temporarily use about 40 GB together. You may delete the
    downloaded capsules and decoded segments after the installation works.

INSTALLING
    The {RELEASE_VERSION} one-step decompiler normally reconstructs this folder and
    runs setup.bat for you. If setup did not start after every capsule and
    file hash verified:

    1. Keep this whole TORMENT_NEXUS folder together. Setup needs the
       neighbouring assistant, models, and python folders.
    2. Run setup.bat.
    3. Launch "TORMENT_NEXUS" from your desktop.

    Setup takes a couple of minutes and needs no internet.

    If the desktop shortcut could not be created, double-click
    start_assistant.bat in this folder. If this folder is moved or renamed
    later, run setup.bat again to recreate the shortcut.

WHAT IT TOUCHES
    Nothing outside this folder, plus one desktop shortcut. It does not use
    or modify your system Python, PATH, or registry. Python itself is
    bundled inside the "python" folder here. To uninstall, delete this
    folder and the shortcut.

FIRST RUN
    The Q8 director loads into RAM and takes a moment on the first message.
    The bundled 7B coder is an on-demand separate profile, started through
    start_maintenance_coder.bat or start_autonomous_self_heal.bat. It can run
    through the bundled CPU server, though a configured CUDA runtime is faster.

    Type "tutorial" for the beginner-friendly walkthrough. Type "help" to
    see available commands or "explain <anything>" for one focused guide.

SOME THINGS TO TRY
    help              list every command
    health check      show what is working on this computer
    music library     list local tracks it can play offline
    audio mode        talk to it out loud
    sing daisy bell   ask politely

VOICE
    Speech and listening run locally. "audio mode" turns voice on and
    "text mode" turns it off. Type "audio mode" again whenever you want
    voice back. Typing still works when no microphone is available.

MUSIC AND VISUALIZER
    Open this TORMENT_NEXUS folder, then open assistant\music. Put your own
    MP3, WAV, FLAC, or OGG files there. Type "music library" or
    "play <part of the song name>". A successful start message is shown
    instead of spoken, so the voice does not cover the opening lyrics. The
    full-screen visualizer opens automatically for a local song.

    In music mode:
        Left/Right     change visualizer scene
        Space          play the next local song
        [ and ]        change local-song volume
        Ctrl+B         exit music mode

    Scenes rotate every 2 minutes 45 seconds. Colours change automatically
    every 20 seconds. Each scene reacts strongly to a different mix of bass,
    beat, melody, treble, stereo movement, and waveform detail. Space affects
    local music only, never Spotify or a browser.

    Local-library repeat is on by default. When one local song ends, the next
    filename starts, and the last returns to the first. "repeat music off"
    stops after the current song; "repeat music on" restores the loop.

TIME AND RETURNING
    TORMENT_NEXUS reads this computer's local clock during each reply. It
    knows the current date and time, how long this session has been open,
    and the gap since the previous completed conversation. This does not
    mean it watched, waited, thought, worked, or felt anything while closed.

LONG TEXT
    Long typed messages keep the newest text visible. Long answers appear
    one page at a time: Space, Enter, or Down advances; Up or Backspace goes
    back; Escape or Q closes the page view.

THE GLITCHING ICON (optional)
    tools\start_glitch.bat makes the desktop icon corrupt itself now and
    then. tools\stop_glitch.bat stops it and restores the normal icon. It is
    off unless you start it, and it does not survive a reboot.

UPDATING LATER
    Install a newer research build in a new folder instead of extracting it over this
    one. Keep this folder as a backup until the new version launches. Local
    songs are in assistant\music. Private conversation and memory files are
    under assistant\memory; never upload them in a public bug report.

UNINSTALLING
    Close TORMENT_NEXUS, delete this folder, and delete the desktop shortcut.

PRIVACY
    This package contains no conversation history, memories, developer
    passcode verifier, device pairing PIN, API key, or music from the person
    who sent it. TORMENT_NEXUS starts with a blank slate. The included
    RELEASE_MANIFEST.json records a SHA-256 hash for every shipped file.

THANKS
    sundog - voice recognition testing, and a good deal of the new-user
    experience and interface detail in the first ten minutes of this.
"""


def main():
    parser = argparse.ArgumentParser(description="Build a shareable package.")
    parser.add_argument("--archive", action="store_true",
                        help="zip the package when done")
    parser.add_argument("--split", action="store_true",
                        help="cut the archive into upload-sized parts, "
                             "generate the matching reassembler, and verify "
                             "they rejoin")
    parser.add_argument("--discard-stage", action="store_true",
                        help="with --split, remove the verified rebuildable "
                             "stage folder before making parts")
    parser.add_argument("--skip-download", action="store_true",
                        help="use only the verified cached Python downloads "
                             "and wheel set; fail if that cache is incomplete")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="permit an explicitly marked dirty development "
                             "snapshot; never use for a published release")
    parser.add_argument("--verify-only", action="store_true",
                        help="re-check an existing build")
    parser.add_argument("--sanitize", action="store_true",
                        help="strip runtime artifacts, then re-verify "
                             "(rebuild before making a final archive if "
                             "you test-ran setup.bat)")
    args = parser.parse_args()

    if args.split and (args.archive or args.verify_only or args.sanitize):
        parser.error("--split is a separate action; archive or verify first")
    if args.discard_stage and not args.split:
        parser.error("--discard-stage requires --split")
    if args.allow_dirty and (
        args.split or args.verify_only or args.sanitize
    ):
        parser.error("--allow-dirty applies only when building a new package")

    report = []

    if args.split:
        if args.discard_stage and not discard_stage(report):
            print("\n".join(report))
            return 1
        ok = split(report)
        print("\n".join(report))
        return 0 if ok else 1

    # Windows keeps DLLs from the running embedded interpreter open. A build
    # cannot safely replace dist/TORMENT_NEXUS while it is being run by that
    # same package; without this check shutil emits an opaque access-denied
    # traceback partway through staging.
    if not (args.verify_only or args.sanitize):
        try:
            running_from_stage = os.path.commonpath((
                os.path.realpath(sys.executable),
                os.path.realpath(STAGE),
            )) == os.path.realpath(STAGE)
        except ValueError:
            running_from_stage = False
        if running_from_stage:
            print("REFUSING TO REBUILD FROM THE PACKAGE BEING REPLACED.")
            print("Run tools\\package_release.py with Python outside "
                  "dist\\TORMENT_NEXUS, then try again.")
            return 1

    if args.verify_only or args.sanitize:
        if not os.path.isdir(STAGE):
            print("Nothing built yet.")
            return 1

        if args.sanitize:
            source = source_state()
            manifest_path = os.path.join(STAGE, MANIFEST_NAME)
            try:
                with open(manifest_path, "r", encoding="utf-8") as handle:
                    previous = json.load(handle).get("source")
                if isinstance(previous, dict):
                    source = previous
            except (OSError, AttributeError, json.JSONDecodeError):
                pass

            print("Sanitizing...")
            sanitize(report)
            write_manifest(report, source=source)
            print("\n".join(report))
            report.clear()
            print()

        print("Verifying...")
        problems = verify(report)
        print("\n".join(report))
        if problems:
            print("\nPROBLEMS:")
            for p in problems:
                print("  " + p)
            if not args.sanitize:
                print("\nRun with --sanitize to strip these, "
                      "then verify again.")
            return 1
        print("\nClean - safe to send.")
        return 0

    os.makedirs(CACHE, exist_ok=True)

    try:
        source_before = require_release_source(args.allow_dirty, report)
        inputs_before = input_snapshot()
    except (OSError, ReleaseBuildError) as error:
        print("REFUSING TO BUILD:")
        print(f"  {error}")
        return 1

    print("Checking source snapshot...")
    print("\n".join(report))
    report.clear()
    print()

    LOCKED.clear()
    print("Staging files...")
    try:
        copied, withheld = stage(report)
        inputs_after = input_snapshot()
        source_after = source_state()
    except (OSError, ReleaseBuildError) as error:
        print("\n".join(report))
        print("\nREFUSING TO SHIP:")
        print(f"  {error}")
        return 1

    print("\n".join(report))
    report.clear()
    print(f"  -> {copied} files copied, {withheld} withheld by the denylist\n")

    if inputs_before != inputs_after or source_before != source_after:
        print("REFUSING TO SHIP - release inputs changed while staging.")
        print("Stop other editors and build again from one frozen snapshot.")
        return 1

    global SOURCE_STATE
    SOURCE_STATE = source_before

    if LOCKED:
        print(f"REFUSING TO SHIP - {len(LOCKED)} file(s) were locked and "
              f"could not be copied:")
        for item in LOCKED[:10]:
            print("  " + item)
        print("\nSomething is running out of the project or dist folder.")
        print("Stop it and rebuild -- a package missing files would fail")
        print("on the recipient's machine instead of here.")
        return 1

    print("Bundling Python...")
    if not bundle_python(report, skip_download=args.skip_download):
        print("\n".join(report))
        return 1
    print("\n".join(report))
    report.clear()
    print()

    print("Downloading wheels...")
    if not bundle_wheels(report, skip_download=args.skip_download):
        print("\n".join(report))
        return 1
    print("\n".join(report))
    report.clear()
    print()

    print("Writing installer...")
    write_launcher(report)
    print("\n".join(report))
    report.clear()
    print()

    print("Sanitizing runtime artifacts...")
    sanitize(report)
    print("\n".join(report))
    report.clear()
    print()

    print("Writing release manifest...")
    try:
        write_manifest(report, source=source_before)
    except ReleaseBuildError as error:
        print("\n".join(report))
        print(f"\nREFUSING TO SHIP - {error}")
        return 1
    print("\n".join(report))
    report.clear()
    print()

    print("Verifying no personal data leaked...")
    problems = verify(report)
    print("\n".join(report))
    if problems:
        print("\nREFUSING TO SHIP - problems found:")
        for p in problems:
            print("  " + p)
        return 1
    print("  clean\n")

    size = sum(
        os.path.getsize(os.path.join(f, n))
        for f, _, files in os.walk(STAGE) for n in files
    )
    print(f"Package: {STAGE}")
    print(f"Size:    {size/1e9:.2f} GB")

    if args.archive:
        print("\nArchiving (this takes a while at this size)...")
        base = os.path.join(DIST, ARCHIVE_STEM)
        path = shutil.make_archive(base, "zip", DIST, PACKAGE_NAME)
        print(f"Archive: {path} ({os.path.getsize(path)/1e9:.2f} GB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
