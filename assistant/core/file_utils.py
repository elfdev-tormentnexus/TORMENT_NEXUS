import os
import json
import shutil
import tempfile
from datetime import datetime


# ============================================================
# FILE HELPERS
# ============================================================

def ensure_file(path, default=""):
    folder = os.path.dirname(path)

    if folder:
        os.makedirs(folder, exist_ok=True)

    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(default)


def load_text(path):
    ensure_file(path)

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def append_file(path, text):
    ensure_file(path)

    with open(path, "a", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


def save_text(path, text):
    """Atomic overwrite, for callers that periodically rewrite (not append) a file."""
    ensure_file(path)

    folder = os.path.dirname(path) or "."
    fd, temp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, path)

    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def save_json(path, data):
    """
    Write via a temp file + os.replace() so a crash or power loss
    mid-write leaves either the old file or the new one intact, never
    a truncated one. This is the assistant's persistent memory --
    losing it to an interrupted write is exactly the kind of thing
    that shouldn't happen unattended on a device with no one watching.
    """
    ensure_file(path)

    folder = os.path.dirname(path) or "."
    fd, temp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, path)

    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def load_json(path):
    """
    On corruption, the old behaviour silently returned [] -- which,
    for a memory file, means the assistant's entire memory quietly
    resets with no trace of what happened. Instead, preserve the
    unreadable file alongside the fresh empty one and say so, so a
    corrupt file is at least recoverable-by-hand instead of just gone.
    """
    ensure_file(path, "[]")

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        corrupt_path = path + f".{stamp}.corrupt"

        try:
            shutil.copy2(path, corrupt_path)
        except Exception:
            corrupt_path = None

        reset_error = None

        try:
            save_json(path, [])
        except Exception as reset_problem:
            reset_error = reset_problem

        where = f" A copy was saved to {corrupt_path}." if corrupt_path else ""
        reset = (
            " The live store was reset to an empty list."
            if reset_error is None
            else f" The live store could not be reset: {reset_error}."
        )
        print(f"[file_utils] WARNING: {path} is corrupt ({e}); starting empty.{where}")
        print(f"[file_utils]{reset}")

        return []

# ============================================================
# DEVELOPER FILE TOOLS
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PathError(Exception):
    """A user-supplied path escaped the project root."""


def safe_join(base, relative_path):
    """
    Join relative_path onto base, refusing anything that would escape
    it. Plain os.path.join(base, relative_path) doesn't protect
    against this: a ".." can walk back out, and if relative_path is
    itself absolute, os.path.join silently discards `base` entirely
    and returns the absolute path as-is.
    """
    if not relative_path or not relative_path.strip():
        raise PathError("No file given.")

    candidate = relative_path.strip().replace("\\", os.sep).replace("/", os.sep)

    if os.path.isabs(candidate):
        raise PathError("Absolute paths are not allowed.")

    base = os.path.realpath(base)
    full = os.path.realpath(os.path.join(base, candidate))
    base_cmp = os.path.normcase(base)
    full_cmp = os.path.normcase(full)

    if not full_cmp.startswith(base_cmp + os.sep) and full_cmp != base_cmp:
        raise PathError("That path is outside the project.")

    return full


def list_files(folder=""):
    """List useful project files, skipping huge folders."""

    target = safe_join(PROJECT_ROOT, folder) if folder else PROJECT_ROOT

    if not os.path.exists(target):
        return []

    ignored = {
        ".git",
        "__pycache__",
        "node_modules",
        "build",
        "bin",
        "obj",
        "dist",
        ".venv",
    }

    results = []

    for root, dirs, files in os.walk(target):

        # remove ignored folders from traversal
        dirs[:] = [
            d for d in dirs
            if d not in ignored
        ]

        for file in files:
            if file.endswith((
                ".py",
                ".json",
                ".bat",
                ".md",
                ".txt"
            )):
                full_path = os.path.join(root, file)
                relative = os.path.relpath(
                    full_path,
                    PROJECT_ROOT
                )
                results.append(relative)

    return results


def backup_file(path):
    """Create a timestamped backup copy without overwriting older backups."""

    try:
        source = safe_join(PROJECT_ROOT, path)
    except PathError:
        return None

    if not os.path.exists(source):
        return None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = source + f".{stamp}.backup"

    shutil.copy2(source, backup)

    return os.path.relpath(backup, PROJECT_ROOT)
