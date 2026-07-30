import os, sys
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
from core import source_awareness as sa

print("=== MANIFEST ===")
print(sa.manifest_text())
print()
print("=== PER-FILE GROUND TRUTH ===")
targets = [
    "assistant/ui/ui.py",
    "README.md",
    "assistant/main.py",
    "assistant/core/tutorial.py",
    "assistant/core/persona.py",
    "assistant/core/machinespirit.py",
    "assistant/core/machinespirit_shadow.py",
    "assistant/core/source_awareness.py",
    "assistant/core/power_guard.py",
    "docs/RESEARCHC_GOALS.md",
    "CHANGELOG.md",
    "assistant/core/config.py",
    "assistant/core/edit_guard.py",
]
root = sa.PROJECT_ROOT
NL = b"\n"
for t in targets:
    p = os.path.join(root, t.replace("/", os.sep))
    if os.path.isfile(p):
        with open(p, "rb") as h:
            raw = h.read()
        mlines = raw.count(NL) + 1
        print("%-45s EXISTS bytes=%-8d manifest_lines=%-7d newlines=%d" % (
            t, len(raw), mlines, raw.count(NL)))
    else:
        print("%-45s MISSING" % t)

print()
print("=== DIRECTORY GROUND TRUTH (manifest rules) ===")
entries = sa.inventory()
for area, (files, lines) in sa._shape(entries):
    print("%-30s files=%-5d lines=%d" % (area, files, lines))
print("TOTAL files=%d lines=%d" % (len(entries), sum(e["lines"] for e in entries)))

print()
print("=== assistant/core: every file on disk (all suffixes) ===")
core = os.path.join(root, "assistant", "core")
names = sorted(os.listdir(core))
print("count all entries:", len(names))
py = [n for n in names if n.endswith(".py")]
print("count .py:", len(py))
print(", ".join(py))
