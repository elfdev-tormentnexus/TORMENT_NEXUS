# Deferred to a Beta 6 patch

Found while auditing the release page against what actually shipped,
2026-07-28. Neither item blocks the Beta 6 upload: the release page is
correct, and the package works. Both need a rebuilt package to fix, which
is why they are here instead of in the release.

## 1. `start_interface_mode.bat` is tracked but not packaged — SHIPPING AS AN ADD-ON

**Resolved for Beta 6 as an optional add-on.**
`tools/build_interface_mode_dlc.py` builds a 3 KB payload plus an installer
with the payload's SHA-256 baked in, in the same shape as the 14B model pack.
Verified against a real extracted install: checksum checked, launcher, icon
and documentation placed, desktop shortcut created, exit 0.

It stays deliberately *outside* the documentation patch. That patch claims the
installed tree still matches the published archive checksum, which is only
true because it touches documentation and nothing else; adding a launcher to
it would quietly break that guarantee. A separate add-on the operator chooses
keeps both statements true.

The packaging question below is still open for the next release: decide
whether interface mode belongs in the base staged tree.



The launcher is in the repository and is **not** in the archive. The five
launchers that do ship are `setup.bat`, `start_assistant.bat`,
`start_autonomous_self_heal.bat`, `start_full_maintenance_coder.bat` and
`start_maintenance_coder.bat`.

The packager stages `assistant/`, `icon_anim/`,
`llama.cpp/build/bin/Release/` and `models/voice/`, so a launcher sitting at
the repository root is outside the staged set. Interface mode is therefore
unavailable to anyone installing Beta 6, and the release notes deliberately
do not mention it.

Decide first whether interface mode is meant to ship at all. If it is, the
fix is in the packager's staging list, not a file move — and it needs the
`AGENT_WATCH` behaviour and the generated icon to travel with it.

## 2. In-package documentation is a stale snapshot — SHIPPING A FIX

**Resolved for Beta 6 by an auto-applied patch.** `tools/build_docs_patch.py`
builds `TORMENT_NEXUS-v0.2.0-beta.6-docs-patch.zip`, and the reassembler now
extracts the package and applies it automatically. The patch replaces
documentation only, so the installed tree still matches the published archive
checksum, and a missing patch file is skipped rather than treated as an error.

The underlying ordering problem is still worth fixing properly next release —
finalise packaged documentation *before* building — and the release gate now
says so explicitly. What follows is the original finding.



`docs/` **is** part of the package: 19 files, including
`RELEASE_NOTES_v0.2.0-beta.6.md`. The archive was built from `97711ca`, so
the shipped copies predate the release-day corrections. Inside the package:

- the release notes still read `verified at release` instead of the real
  639/2 count, and still list optional 14B asset filenames that do not
  exist;
- `CHANGELOG.md` also still reads `verified at release`;
- `CHANGELOG.md` does not mention the offline knowledge library, the
  visualizer and loudness work, or the conversation honesty fixes.

The published release page is correct and says outright that it is
authoritative, so an online reader is fine. A reader working purely offline
from the extracted folder is not.

The real lesson is ordering: documentation that ships inside the package has
to be final *before* the package is built. The release gate in the notes
implies this but does not say it, because until this release nobody had
noticed `docs/` was packaged at all. Add an explicit step.
