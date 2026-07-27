"""
Finds imports where a standard-library (or third-party) module is being
pulled out of one of your local packages — e.g.

    from project import json          <-- wrong, json is stdlib
    import json                       <-- correct

This happens when an editor's auto-import resolves a bare module name
against a local package instead of the standard library.

Run from the assistant folder:   python scan_bad_imports.py
This only reports. It changes nothing.
"""

import os
import re
import sys


LOCAL_PACKAGES = {
    "commands", "core", "editing", "memory", "project", "ui", "voice", "web",
}

SKIP_DIRS = {"__pycache__", "logs", ".git", "backup", "change_plans", "venv", ".venv"}

# Names that must never come from a local package. Python 3.10+ exposes
# the authoritative stdlib list; fall back to a hand list below that.
try:
    EXTERNAL = set(sys.stdlib_module_names)
except AttributeError:
    EXTERNAL = {
        "json", "os", "re", "sys", "time", "math", "random", "shutil",
        "textwrap", "threading", "subprocess", "signal", "datetime",
        "pathlib", "typing", "collections", "itertools", "functools",
        "traceback", "logging", "argparse", "copy", "glob", "io", "csv",
        "sqlite3", "socket", "struct", "hashlib", "base64", "uuid",
        "tempfile", "difflib", "ast", "inspect", "platform", "py_compile",
        "compileall", "importlib", "pickle", "queue", "select", "string",
    }

# Third-party packages you actually use.
EXTERNAL |= {
    "requests", "numpy", "sounddevice", "sherpa_onnx", "piper",
    "flask", "yaml", "bs4", "PIL",
}

FROM_RE = re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\s+(.+)$")


def iter_py_files(root):
    self_name = os.path.basename(os.path.abspath(__file__))

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for name in filenames:
            if name.endswith(".py") and name != self_name:
                yield os.path.join(dirpath, name)


def main():
    root = os.path.dirname(os.path.abspath(__file__))

    problems = []
    local_imports = []

    for path in iter_py_files(root):
        rel = os.path.relpath(path, root)

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().split("\n")
        except Exception as e:
            print(f"[skip] {rel}: {e}")
            continue

        for i, line in enumerate(lines, start=1):
            m = FROM_RE.match(line)

            if not m:
                continue

            module = m.group(1)
            names = m.group(2)
            top = module.split(".")[0]

            if top not in LOCAL_PACKAGES:
                continue

            local_imports.append((rel, i, line.strip()))

            imported = [
                n.strip().split(" as ")[0].strip()
                for n in names.replace("(", "").replace(")", "").split(",")
            ]

            module_self = os.path.splitext(os.path.basename(rel))[0]

            for n in imported:
                if n in EXTERNAL:
                    problems.append((rel, i, line.strip(), n, "external"))
                elif n == module_self:
                    problems.append((rel, i, line.strip(), n, "self"))

    print("=" * 68)

    if problems:
        print(f"SUSPECT IMPORTS  ({len(problems)} found)")
        print("=" * 68)

        for rel, lineno, text, name, kind in problems:
            print(f"\n  {rel}:{lineno}")
            print(f"      {text}")

            if kind == "external":
                print(f"      -> '{name}' is a standard/third-party module.")
                print(f"         Replace this line with:  import {name}")
            else:
                print(f"      -> this module is importing ITSELF.")
                print(f"         Delete this line. Reference its own names directly.")
    else:
        print("No stdlib modules being imported from local packages. Clean.")

    print()
    print("=" * 68)
    print(f"All local-package imports ({len(local_imports)}) — eyeball these:")
    print("=" * 68)

    current = None

    for rel, lineno, text in sorted(local_imports):
        if rel != current:
            print(f"\n  {rel}")
            current = rel

        print(f"      {lineno:>4}: {text}")

    print()


if __name__ == "__main__":
    main()
