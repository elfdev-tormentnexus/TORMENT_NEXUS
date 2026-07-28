"""
Re-derives the protection lists from what modules actually do.

`DENIED_FILES` and `MAINTENANCE_DENIED_FILES` are hand-maintained, and a
hand-maintained list drifts. The QC review found two entries missing --
`os.startfile` from the capability gate and `activity_log.jsonl` from the
release basename set -- and both had the same shape: a module or a file added
after the list was written, and nobody went back.

So this asks the opposite question. Instead of "is this file on the list",
it walks every module, works out which capabilities it holds, and reports the
ones that reach the network, a radio, or the microphone without appearing in
either protection list.

It answers a question, it does not enforce one. A finding here is a prompt to
decide, not evidence of a bug -- some modules legitimately hold a capability
and legitimately stay repairable.

This module lives in `editing/`, so it is itself unwritable by any model-driven
edit. A checker the checked thing can edit is decoration.
"""

import ast
import os

from editing import edit_guard


# Grouped by what an unreviewed change to the module could actually do,
# rather than by which standard library package it happens to be.
CAPABILITY_GROUPS = {
    "network": {
        "aiohttp", "httpx", "requests", "socket", "urllib", "ftplib",
        "smtplib", "telnetlib", "websockets",
    },
    "radio": {"serial", "meshtastic", "bluetooth", "bleak"},
    "capture": {"sounddevice", "pyaudio", "cv2", "mss"},
}

# Reported but never treated as needing protection on their own. Almost every
# module touches the filesystem; saying so about all of them is noise.
ADVISORY_GROUPS = {
    "process": {"subprocess", "ctypes", "multiprocessing"},
    "dynamic": {"importlib", "marshal", "pickle", "runpy"},
}


def _module_capabilities(path):
    """Which capability groups a single file holds, by its imports."""
    try:
        with open(path, "r", encoding="utf-8") as source:
            tree = ast.parse(source.read(), filename=path)
    except (OSError, SyntaxError):
        return set(), set()

    roots = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                roots.add(item.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])

    held = {
        name for name, group in CAPABILITY_GROUPS.items()
        if roots & group
    }
    advisory = {
        name for name, group in ADVISORY_GROUPS.items()
        if roots & group
    }

    return held, advisory


def _protection(relative_path):
    """How a module is currently protected, if at all."""
    key = edit_guard._policy_key(relative_path)

    for prefix in edit_guard.DENIED_PREFIXES:
        if key.startswith(edit_guard._policy_key(prefix)):
            return "denied (prefix)"

    if key in {edit_guard._policy_key(p) for p in edit_guard.DENIED_FILES}:
        return "denied"

    if key in {
        edit_guard._policy_key(p)
        for p in edit_guard.MAINTENANCE_DENIED_FILES
    }:
        return "maintenance-denied"

    return ""


def audit():
    """Return (findings, surveyed). A finding is an unprotected capability."""
    findings = []
    surveyed = 0

    for folder, dirs, files in os.walk(edit_guard.PROJECT_ROOT):
        dirs[:] = [
            d for d in dirs
            if d not in ("__pycache__", "logs", ".git", "backups", "cache")
        ]

        for name in sorted(files):
            if not name.endswith(".py"):
                continue

            full = os.path.join(folder, name)
            relative = os.path.relpath(full, edit_guard.PROJECT_ROOT)
            relative = relative.replace("\\", "/")
            surveyed += 1

            held, advisory = _module_capabilities(full)

            if not held:
                continue

            protection = _protection(relative)

            if protection:
                continue

            findings.append({
                "file": relative,
                "capabilities": sorted(held),
                "advisory": sorted(advisory),
            })

    return findings, surveyed


def report():
    """A human-readable audit of protection coverage."""
    findings, surveyed = audit()

    lines = [
        "GUARD DOCTOR",
        "=" * 58,
        f"Surveyed {surveyed} modules under {edit_guard.PROJECT_ROOT}",
        "",
    ]

    if not findings:
        lines.append(
            "Every module reaching the network, a radio, or the microphone "
            "appears in a protection list."
        )
        return "\n".join(lines)

    lines.append(
        f"{len(findings)} module(s) hold a reach-out capability and appear in "
        "neither DENIED_FILES nor MAINTENANCE_DENIED_FILES:"
    )
    lines.append("")

    for finding in findings:
        detail = ", ".join(finding["capabilities"])
        if finding["advisory"]:
            detail += f"  (also {', '.join(finding['advisory'])})"
        lines.append(f"  {finding['file']}")
        lines.append(f"      {detail}")

    lines.extend([
        "",
        "This is a prompt to decide, not a bug report. A module may hold a",
        "capability and still be a legitimate repair target -- the question",
        "is whether an unreviewed change to it is acceptable.",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
