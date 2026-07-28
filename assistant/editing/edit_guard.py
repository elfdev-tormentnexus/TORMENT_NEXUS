"""
Safety rails for self-editing.

Everything that touches disk goes through here. The rules:

- Some files are off limits. An edit engine that can rewrite its own
  safety checks has no safety checks.
- Nothing is written unless it parses. A file that fails to import
  means the assistant will not start next launch, and you would be
  repairing it by hand without the assistant's help.
- Backups are timestamped. The old code wrote to "<file>.backup" and
  overwrote it every time, so two edits in a row destroyed the
  original.
- Writes are atomic. Write a temp file, then replace. A crash midway
  through a direct write leaves the real file truncated.
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime


PROJECT_ROOT = os.path.realpath(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

BACKUP_FOLDER = os.path.join(PROJECT_ROOT, "backups")

MAX_EDITABLE_BYTES = 120_000


# Files the engine may never modify.
#
# editing/  -- these modules ARE the safety system
# core/config.py -- holds the paths and the model location; a bad
#                   edit here breaks startup before anything can
#                   report the problem
# main.py, commands/command_handlers.py -- these hold the
#                   confirm/approve dispatch and the DEV_MODE gate
#                   that decide whether a proposed edit requires a
#                   human to say yes. If the editor can rewrite the
#                   code that asks for approval, the approval step
#                   is theater, not a safety rail.
# core/dev_auth.py, ui/ui.py -- these verify and mask the owner passcode.
#                   Once the UI handles credentials it is an authentication
#                   boundary, not an unattended presentation surface.
DENIED_PREFIXES = (
    "editing" + os.sep,
    "backups" + os.sep,
    "tests" + os.sep,
    "__pycache__" + os.sep,
    ".git" + os.sep,
)

#
# core/persona.py -- the honesty rules, the refusal guidance, and the
#                   character live here, and this text is injected into
#                   every single prompt. It is the same argument as
#                   main.py above: an editor able to soften the rule that
#                   says "do not claim feelings you do not have" can talk
#                   its way past a human skimming a diff, and the rule
#                   stops being a constraint.
# tests/          -- the suite is the evidence that a change was safe.
#                   An editor that can weaken a test can make any change
#                   pass, which turns the proof into a formality. The
#                   project's own README says a green suite does not
#                   prove a change correct; that is only true while the
#                   suite is written by someone other than the thing
#                   being tested.
#
# core/chosen_name.py -- the validator in here is the only thing standing
#                   between a grounded name and a stock one, and it is also
#                   what keeps the operator's stored text out of the answer.
#                   An editor able to relax its own naming rules can name
#                   itself anything, which is the same argument as persona.py:
#                   a constraint the constrained thing can edit is decoration.
DENIED_FILES = (
    os.path.join("core", "chosen_name.py"),
    os.path.join("core", "config.py"),
    os.path.join("core", "dev_auth.py"),
    os.path.join("core", "file_utils.py"),
    os.path.join("core", "llm_server.py"),
    os.path.join("core", "persona.py"),
    "main.py",
    os.path.join("commands", "command_handlers.py"),
    os.path.join("commands", "natural_command.py"),
    os.path.join("project", "project_builder.py"),
    os.path.join("ui", "ui.py"),
    os.path.join("voice", "setup_voice.py"),
)

# Unattended edits get a deliberately smaller surface than changes a human
# previews and confirms. These modules can improve presentation, relevance,
# and read-only project understanding without rewriting startup,
# authentication, command authorization, persistence, or network boundaries.
#
# voice/offline_voice.py was here on a "presentation, voice" rationale, which
# is true of the half that decides how replies sound and false of the half
# that owns the microphone and the recogniser. Both live in one 98KB file, so
# the whole thing came along. The capability gate cannot help: it blocks a
# module gaining sounddevice and cannot block a module that already has it
# from changing what it does with captured audio.
#
# Removed rather than split, because splitting a 2,800-line file is a
# refactor and this is a boundary decision. Splitting capture and recognition
# into their own protected module would let the prosody tuning return here,
# which is the outcome worth having.
AUTONOMOUS_ALLOWED_FILES = (
    os.path.join("voice", "session.py"),
    os.path.join("memory", "extraction_rules.py"),
    os.path.join("memory", "memory_logic.py"),
    os.path.join("project", "project_analyzer.py"),
    os.path.join("project", "project_mapper.py"),
)

# The full-maintenance profile edits a much wider surface than an unattended
# 7B cycle, gated only by change_capability_problem(). That gate is a delta:
# it blocks capability a patch ADDS and deliberately permits capability a
# module already has. For most modules that is the right trade. For these it
# is not -- each already holds the capability that matters, so a repair could
# re-point where data goes without adding a single import, unattended, and be
# reported only after three edits have landed.
#
# This is the same argument DENIED_FILES makes about persona.py. These stay
# editable through the human preview-and-confirm path, which is the point:
# the restriction is on nobody reviewing, not on the file.
MAINTENANCE_DENIED_FILES = (
    # Network egress. The URL is data, and data is editable.
    os.path.join("web", "search_engine.py"),
    os.path.join("web", "search_engine_brave.py"),
    os.path.join("web", "search_engine_searxng.py"),
    os.path.join("web", "search_intent.py"),
    # Radio egress and device credentials.
    os.path.join("hardware", "tdeck.py"),
    os.path.join("hardware", "setup_hardware.py"),
    # OAuth token handling plus network.
    os.path.join("visualizer", "spotify_control.py"),
    # Everything that persists what the operator said or did.
    os.path.join("memory", "memory_store.py"),
    os.path.join("memory", "memory_worker.py"),
    os.path.join("core", "system_awareness.py"),
    os.path.join("core", "wifi_experimental.py"),
    # The last gate between what the model generated and what the operator
    # reads. It decides which spans are hidden and when to hang up on a
    # hallucinated turn marker. An unreviewed change here could suppress
    # output without anything else noticing -- the same argument persona.py
    # gets, one layer further down the pipe.
    os.path.join("core", "stream_filter.py"),
    # Capture, recognition and speech synthesis. Off the unattended list
    # entirely; this keeps it off the unreviewed 14B path as well.
    os.path.join("voice", "offline_voice.py"),
)

_SENSITIVE_IMPORT_ROOTS = {
    "aiohttp",
    "ctypes",
    "httpx",
    "importlib",
    # Dynamic code loading. pickle and marshal both execute on load, so
    # they are code execution wearing a serialisation costume.
    "marshal",
    "multiprocessing",
    "pathlib",
    "pickle",
    "requests",
    "runpy",
    # This project has a radio and a microphone. A module that gains
    # pyserial gains LoRa/mesh egress; one that gains an audio capture
    # library gains the room. Neither is process or network capability in
    # the usual sense, and both were invisible to this check before.
    "pyaudio",
    "serial",
    "shutil",
    "socket",
    "sounddevice",
    "subprocess",
    "tarfile",
    "tempfile",
    "urllib",
    "webbrowser",
    "zipfile",
}

_SENSITIVE_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "open",
    # The exec family, complete. Listing only execv/execve left every
    # other spelling of the same operation unguarded.
    "os.execl",
    "os.execle",
    "os.execlp",
    "os.execlpe",
    "os.execv",
    "os.execve",
    "os.execvp",
    "os.execvpe",
    "os.open",
    "os.popen",
    "os.posix_spawn",
    "os.posix_spawnp",
    "os.remove",
    "os.removedirs",
    "os.rename",
    "os.renames",
    "os.replace",
    "os.rmdir",
    "os.spawnl",
    "os.spawnle",
    "os.spawnlp",
    "os.spawnlpe",
    "os.spawnv",
    "os.spawnve",
    "os.spawnvp",
    "os.spawnvpe",
    # os.startfile is the Windows process/document launcher and this is a
    # Windows-first project that already calls it in two places. Every POSIX
    # spawn and exec variant was listed while the one that actually runs here
    # was not.
    "os.startfile",
    "os.system",
    "os.truncate",
    "os.unlink",
    "pathlib.Path.rename",
    "pathlib.Path.replace",
    "pathlib.Path.rmdir",
    "pathlib.Path.unlink",
    "pathlib.Path.write_bytes",
    "pathlib.Path.write_text",
    "shutil.copy",
    "shutil.copy2",
    "shutil.copyfile",
    "shutil.move",
    "shutil.rmtree",
}

_SENSITIVE_CALL_PREFIXES = (
    "aiohttp.",
    "ctypes.",
    "httpx.",
    "requests.",
    "socket.",
    "subprocess.",
    "tarfile.",
    "urllib.",
    "webbrowser.",
    "zipfile.",
)


class GuardError(Exception):
    """Refused for a safety reason, with an explanation for the user."""


def _policy_key(path):
    """Case-insensitive, platform-independent key for protection rules."""
    return os.path.normpath(path).replace("\\", "/").casefold()


def resolve(relative_path):
    """
    Turn a user-supplied path into an absolute one inside the project,
    or raise. Rejects anything that escapes the project directory.
    """
    if not relative_path or not relative_path.strip():
        raise GuardError("No file given.")

    candidate = relative_path.strip().replace("\\", os.sep).replace("/", os.sep)

    if os.path.isabs(candidate):
        raise GuardError("Absolute paths are not allowed. Use a path inside the project.")

    # realpath also resolves symlinks/junctions. A path can look as if
    # it is inside the project lexically while actually pointing out
    # of it through one of those filesystem links.
    full = os.path.realpath(os.path.join(PROJECT_ROOT, candidate))
    root_cmp = os.path.normcase(PROJECT_ROOT)
    full_cmp = os.path.normcase(full)

    # normpath collapses "..", so compare after normalising.
    if not full_cmp.startswith(root_cmp + os.sep) and full_cmp != root_cmp:
        raise GuardError("That path is outside the project.")

    rel = os.path.relpath(full, PROJECT_ROOT)
    rel_cmp = _policy_key(rel)

    for prefix in DENIED_PREFIXES:
        if rel_cmp.startswith(_policy_key(prefix)):
            raise GuardError(
                f"{rel} is protected.\n"
                "The editing modules and backups cannot be edited by the "
                "editor itself."
            )

    if rel_cmp in {_policy_key(path) for path in DENIED_FILES}:
        raise GuardError(
            f"{rel} is protected.\n"
            "It controls safety-sensitive runtime, command, or output "
            "boundaries and cannot be rewritten automatically."
        )

    return full


def list_editable_files():
    """
    Every .py file the editor could actually be pointed at right now --
    i.e. everything resolve() wouldn't refuse. Used to ground suggestion
    generation in files that exist and aren't denylisted, instead of
    letting the model invent or propose an untouchable target.
    """
    out = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [
            d for d in dirs
            if d not in ("__pycache__", "logs", ".git", "backups", "change_plans")
        ]

        for f in files:
            if not f.endswith(".py"):
                continue

            rel = os.path.relpath(os.path.join(root, f), PROJECT_ROOT).replace("\\", "/")

            try:
                resolve(rel)
            except GuardError:
                continue

            out.append(rel)

    return sorted(out)


def list_autonomous_files():
    """Files an unattended cycle may consider, grounded to the live project."""
    editable = set(list_editable_files())
    return sorted(
        path.replace("\\", "/")
        for path in AUTONOMOUS_ALLOWED_FILES
        if path.replace("\\", "/") in editable
    )


def _import_aliases(tree):
    aliases = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                aliases[item.asname or item.name] = (
                    f"{node.module}.{item.name}"
                )

    return aliases


def _call_name(node, aliases):
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)

    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value, aliases)
        return f"{parent}.{node.attr}" if parent else node.attr

    return ""


def _capabilities(tree):
    aliases = _import_aliases(tree)
    imports = Counter()
    calls = Counter()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                root = item.name.split(".")[0]
                if root in _SENSITIVE_IMPORT_ROOTS:
                    imports[root] += 1
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in _SENSITIVE_IMPORT_ROOTS:
                imports[root] += 1
        elif isinstance(node, ast.Call):
            name = _call_name(node.func, aliases)

            if (
                name in _SENSITIVE_CALLS
                or name.endswith((".write_text", ".write_bytes", ".unlink"))
                or name.startswith(_SENSITIVE_CALL_PREFIXES)
            ):
                calls[name] += 1

    return imports, calls


def change_capability_problem(relative_path, original, updated):
    """Explain whether a patch adds a protected runtime capability.

    Both autonomous repair profiles may retain capabilities already present in
    an editable module, but neither may introduce process, network, dynamic
    code, or additional filesystem capability.  The normal 7B cycle adds a
    smaller file allowlist on top of this shared boundary; the explicit 14B
    repair session uses the wider human-editable surface but keeps this rule.
    """
    try:
        old_tree = ast.parse(original, filename=relative_path)
        new_tree = ast.parse(updated, filename=relative_path)
    except SyntaxError as error:
        return f"syntax check failed at line {error.lineno}: {error.msg}"

    old_imports, old_calls = _capabilities(old_tree)
    new_imports, new_calls = _capabilities(new_tree)

    added_imports = sorted(
        name
        for name, count in new_imports.items()
        if count > old_imports[name]
    )
    added_calls = sorted(
        name
        for name, count in new_calls.items()
        if count > old_calls[name]
    )

    if added_imports:
        return (
            "the patch adds a protected system/network import: "
            + ", ".join(added_imports)
        )

    if added_calls:
        return (
            "the patch adds a protected system/network operation: "
            + ", ".join(added_calls)
        )

    return None


def maintenance_change_problem(relative_path, original, updated):
    """Explain why an unattended full-maintenance repair is out of bounds."""
    normalized = _policy_key(relative_path)
    denied_here = {_policy_key(path) for path in MAINTENANCE_DENIED_FILES}

    if normalized in denied_here:
        return (
            f"{relative_path} reaches the network, a radio, or stored personal "
            "data; it can only be changed through a human-reviewed edit"
        )

    return change_capability_problem(relative_path, original, updated)


def autonomous_change_problem(relative_path, original, updated):
    """Explain why a normal unattended edit is outside its safety budget."""
    normalized = _policy_key(relative_path)
    allowed = {_policy_key(path) for path in AUTONOMOUS_ALLOWED_FILES}

    if normalized not in allowed:
        return (
            f"{relative_path} requires a human-reviewed edit; unattended "
            "cycles cannot modify that module"
        )

    return change_capability_problem(relative_path, original, updated)


def locate(name):
    """
    Turn whatever the model said into a real project path.

    The classifier routinely answers "ui.py" when the file is at
    "ui/ui.py". Failing on that is pointless when there is exactly one
    file with that name. Ambiguity is reported rather than guessed at.
    """
    if not name or not name.strip():
        raise GuardError("No file given.")

    cleaned = name.strip().replace("\\", "/").lstrip("./")

    # Already correct?
    direct = os.path.normpath(os.path.join(PROJECT_ROOT, cleaned))

    if os.path.isfile(direct):
        return os.path.relpath(direct, PROJECT_ROOT).replace("\\", "/")

    basename = os.path.basename(cleaned)
    matches = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [
            d for d in dirs
            if d not in ("__pycache__", "logs", ".git", "backups", "change_plans")
        ]

        for f in files:
            if f == basename:
                rel = os.path.relpath(os.path.join(root, f), PROJECT_ROOT)
                matches.append(rel.replace("\\", "/"))

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        listed = "\n".join(f"  {m}" for m in sorted(matches))
        raise GuardError(
            f"There is more than one file called {basename}:\n{listed}\n\n"
            "Say which one you mean."
        )

    raise GuardError(f"No file called {basename} in the project.")


def read(relative_path):
    full = resolve(relative_path)

    if not os.path.exists(full):
        raise GuardError(f"File not found: {relative_path}")

    size = os.path.getsize(full)

    if size > MAX_EDITABLE_BYTES:
        raise GuardError(
            f"{relative_path} is {size:,} bytes, over the "
            f"{MAX_EDITABLE_BYTES:,} limit for automated edits."
        )

    with open(full, "r", encoding="utf-8") as f:
        return f.read()


def check_syntax(content, filename="<edit>"):
    """
    None if the content parses, otherwise a human-readable error.
    Non-Python files pass without checking.
    """
    if not filename.lower().endswith(".py"):
        return None

    try:
        ast.parse(content, filename=filename)
        return None
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"
    except Exception as e:
        return str(e)


def backup(relative_path):
    """Timestamped copy. Returns the backup's path relative to the project."""
    full = resolve(relative_path)

    os.makedirs(BACKUP_FOLDER, exist_ok=True)

    flat = relative_path.replace("\\", "_").replace("/", "_")

    # Microsecond precision makes a same-second collision unlikely, but
    # "unlikely" is exactly what let two edits in a row destroy a
    # backup before (see the module docstring). The counter suffix
    # closes the window outright instead of just narrowing it.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(BACKUP_FOLDER, f"{flat}.{stamp}.bak")

    counter = 1
    while os.path.exists(dest):
        dest = os.path.join(BACKUP_FOLDER, f"{flat}.{stamp}_{counter}.bak")
        counter += 1

    shutil.copy2(full, dest)

    return os.path.relpath(dest, PROJECT_ROOT)


def _checked_existing_backup(relative_path, backup_path):
    """Validate a pre-created backup before a transactional replacement.

    Full-maintenance sessions persist their rollback record before changing a
    file.  Letting them supply that already-created backup closes the small
    crash window between making a backup and recording it, without allowing a
    caller to point ``write`` at an arbitrary path.
    """
    if not isinstance(backup_path, str) or not backup_path.strip():
        raise GuardError("A transactional write needs a real backup path.")

    name = os.path.basename(backup_path)
    expected_prefix = (
        relative_path.replace("\\", "_").replace("/", "_") + "."
    ).casefold()

    if not name.casefold().startswith(expected_prefix) or not name.endswith(".bak"):
        raise GuardError("The supplied backup does not belong to this file.")

    source = os.path.join(BACKUP_FOLDER, name)
    if not os.path.isfile(source):
        raise GuardError("The supplied transactional backup is missing.")

    return os.path.relpath(source, PROJECT_ROOT)


def write(relative_path, content, backup_path=None):
    """
    Validate, back up, then replace atomically.

    ``backup_path`` is only for trusted transaction orchestration.  When it
    is supplied, it must be an existing backup made for this exact file; the
    usual public path still creates its own timestamped backup.  Raises
    GuardError before touching the target if the content will not parse.
    """
    full = resolve(relative_path)

    problem = check_syntax(content, os.path.basename(full))

    if problem:
        raise GuardError(f"Refusing to write: the result has a syntax error.\n{problem}")

    if backup_path is None:
        backup_path = backup(relative_path) if os.path.exists(full) else None
    else:
        backup_path = _checked_existing_backup(relative_path, backup_path)

    folder = os.path.dirname(full)

    fd, temp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, full)

    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    return backup_path


def module_name(relative_path):
    """'ui/ui.py' -> 'ui.ui'. None if it is not an importable module."""
    if not relative_path.lower().endswith(".py"):
        return None

    stem = relative_path[:-3].replace("\\", "/").strip("/")

    if stem.endswith("/__init__"):
        stem = stem[: -len("/__init__")]

    return stem.replace("/", ".")


def import_check(relative_path, timeout=45):
    """
    Actually import the module in a fresh subprocess.

    check_syntax() only proves the file parses. A file can parse
    perfectly and still explode on import -- a NameError at module
    level, a bad import, a typo in a decorator. That failure would
    only surface on the next launch, by which point the assistant is
    dead and cannot help fix itself.

    Returns None if it imports, otherwise the error output.
    """
    module = module_name(relative_path)

    if not module:
        return None

    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Importing {module} hung for more than {timeout}s."
    except Exception as e:
        return f"Could not run the import check: {e}"

    if result.returncode == 0:
        return None

    err = (result.stderr or result.stdout or "").strip()

    # The last few lines carry the actual error; the traceback above
    # is mostly our own harness.
    lines = [l for l in err.splitlines() if l.strip()]

    return "\n".join(lines[-6:]) if lines else "Import failed with no output."


# ============================================================
# ROLLBACK
# ============================================================

def list_backups(relative_path=None):
    """Newest first. Optionally filtered to one file."""
    if not os.path.isdir(BACKUP_FOLDER):
        return []

    flat = relative_path.replace("\\", "_").replace("/", "_") if relative_path else None

    out = []

    for name in os.listdir(BACKUP_FOLDER):
        if not name.endswith(".bak"):
            continue

        if flat and not name.startswith(flat + "."):
            continue

        out.append(name)

    return sorted(out, reverse=True)


def restore(backup_name):
    """
    Put a backup back. The current file is itself backed up first, so
    a rollback is undoable too.
    """
    source = os.path.join(BACKUP_FOLDER, os.path.basename(backup_name))

    if not os.path.exists(source):
        raise GuardError(f"No such backup: {backup_name}")

    # "core_config.py.20260726_143208.bak" -> "core/config.py"
    stem = os.path.basename(backup_name)
    parts = stem.split(".")

    if len(parts) < 3:
        raise GuardError(f"Unrecognised backup name: {backup_name}")

    flat = ".".join(parts[:-2])
    target = flat.replace("_", os.sep, flat.count("_"))

    # The flattening is lossy, so find the real file by matching the
    # tail rather than trusting the reconstruction.
    guess = None

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ("backups", "__pycache__", ".git")]

        for name in files:
            candidate = os.path.relpath(os.path.join(root, name), PROJECT_ROOT)

            if candidate.replace("\\", "_").replace("/", "_") == flat:
                guess = candidate
                break

        if guess:
            break

    if not guess:
        raise GuardError(
            f"Could not work out which file {backup_name} belongs to."
        )

    with open(source, "r", encoding="utf-8") as f:
        content = f.read()

    write(guess, content)

    return guess
