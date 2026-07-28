"""Build the Beta 6 documentation patch that the reassembler applies.

`docs/` is inside the Windows package, so any documentation corrected after
the 13 GB archive was built is stale in that archive even when the release
page is right. Rebuilding 12 GB to fix a markdown file is a bad trade, so the
corrected documents ship as a small separate asset instead.

The patch deliberately touches documentation only. It never replaces code,
launchers, models, or anything the release manifest hashes -- the installed
package must stay byte-identical to the archive whose SHA-256 is published.
Keeping that line sharp is the whole reason this is a separate tool with an
explicit file list rather than a diff of everything that changed.
"""

import hashlib
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
VERSION = "v0.2.0-beta.6"
PATCH = os.path.join(DIST, f"TORMENT_NEXUS-{VERSION}-docs-patch.zip")

# Source path -> path inside the extracted install. The archive contains one
# top-level TORMENT_NEXUS folder, so every entry is written under it and the
# patch extracts over the same directory the ZIP produced.
FILES = {
    "CHANGELOG.md": "TORMENT_NEXUS/CHANGELOG.md",
    os.path.join("docs", "RELEASE_NOTES_v0.2.0-beta.6.md"):
        "TORMENT_NEXUS/docs/RELEASE_NOTES_v0.2.0-beta.6.md",
}

MARKER = "TORMENT_NEXUS/docs/BETA6_DOCS_PATCH.txt"


def build():
    if not os.path.isdir(DIST):
        raise SystemExit(f"missing {DIST}")

    missing = [s for s in FILES if not os.path.isfile(os.path.join(ROOT, s))]
    if missing:
        raise SystemExit("missing source files: " + ", ".join(missing))

    lines = [
        f"TORMENT_NEXUS {VERSION} documentation patch",
        "",
        "The Windows archive was built before these documents were",
        "corrected, so the copies inside it were out of date. This patch",
        "replaced them. Documentation only -- no code, launcher, or model",
        "file was touched, and the installed package still matches the",
        "published archive checksum.",
        "",
        "Replaced:",
    ]
    lines += [f"  {dest}" for dest in sorted(FILES.values())]
    lines.append("")

    # Deterministic timestamps: a rebuilt patch with identical inputs should
    # produce an identical file, so its published SHA-256 stays meaningful.
    fixed = (2026, 7, 28, 0, 0, 0)

    with zipfile.ZipFile(PATCH, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, dest in sorted(FILES.items()):
            with open(os.path.join(ROOT, source), "rb") as handle:
                data = handle.read()
            info = zipfile.ZipInfo(dest, date_time=fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

        info = zipfile.ZipInfo(MARKER, date_time=fixed)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, "\n".join(lines).encode("utf-8"))

    with open(PATCH, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest().upper()

    print(f"wrote {PATCH}")
    print(f"  {os.path.getsize(PATCH)} bytes")
    print(f"  SHA-256 {digest}")
    return PATCH


if __name__ == "__main__":
    build()
