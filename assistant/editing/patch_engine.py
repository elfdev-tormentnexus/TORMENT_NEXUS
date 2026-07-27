# ============================================================
# PATCH ENGINE
#
# Responsible only for transforming text.
# It never reads or writes files.
# ============================================================

import difflib


def insert_at_top(original_text, new_text):
    """Inserts new_text at the top of a file."""
    return new_text.rstrip() + "\n\n" + original_text


def replace_text(original_text, old, new):
    """Replace one block of text with another."""
    return original_text.replace(old, new, 1)


def apply_edit(original_text, find, replace):
    """
    Apply a find/replace, refusing anything ambiguous.

    Returns (new_text, error). Exactly one is None. The uniqueness
    check is repeated here even though the generator already ran it,
    because this function is the one that decides what gets written.
    """
    count = original_text.count(find)

    if count == 0:
        return None, "The text to replace is no longer in the file."

    if count > 1:
        return None, f"The text to replace appears {count} times; refusing to guess."

    return original_text.replace(find, replace, 1), None


def make_diff(original_text, new_text, filename="file"):
    """Unified diff, so the user sees the change rather than a description."""
    diff = difflib.unified_diff(
        original_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"{filename} (current)",
        tofile=f"{filename} (proposed)",
        n=3,
    )

    return "".join(diff)


def diff_stats(original_text, new_text):
    """(added, removed) line counts."""
    added = removed = 0

    for line in difflib.unified_diff(
        original_text.splitlines(),
        new_text.splitlines(),
        lineterm="",
        n=0,
    ):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1

    return added, removed
