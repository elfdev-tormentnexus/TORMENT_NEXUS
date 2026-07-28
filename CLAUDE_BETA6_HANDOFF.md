# Beta 6 handoff — Claude, 2026-07-28

Written at the operator's request when context ran short. This supersedes
`CODEX_BETA6_RECOVERY.md` on every point where they disagree: that note was
accurate when written, and three of its four blockers have since changed
state.

## State

```text
branch: beta-6-release          (created this session, NOT pushed)
HEAD:   378e26f                 Beta 6: honesty fixes, offline knowledge, ...
tests:  639 pass, 2 expected symlink skips, ~32s
disk:   53.20 GiB free on C:
```

Working tree is clean except `README_DRAFT_BETA5.md`, which is untracked
**on purpose** — the Beta 5 handoff marks it as not part of any release
unless the operator explicitly chooses it. Leave it alone.

### Blockers from the recovery note, rechecked

| Recovery note | Actual, verified this session |
|---|---|
| Git metadata read-only | **Writable.** Probe branch created and deleted. |
| GitHub auth invalid | **Valid.** `gh` 2.96.0, account `elfdev-tormentnexus`, scopes `gist, read:org, repo, workflow`. |
| ~9.5 GiB free, packaging blocked | **Cleared.** 53.20 GiB free. |
| `config.py` mixed line endings | **Fixed.** Normalised to LF, 838 CRs removed, content byte-identical. `git diff --check` is clean tree-wide. |

**`gh` is not on PATH in a plain PowerShell session.** It lives at
`C:\Program Files\GitHub CLI\gh.exe`. Call it by full path or the command
will look uninstalled when it is not.

## What remains, in order

Nothing below has been done. Do not describe any of it as done until it
actually succeeds.

### 1. Push the branch

```powershell
cd C:\Users\evely\Documents\AI_Project
git push -u origin beta-6-release
```

Remote is `https://github.com/elfdev-tormentnexus/TORMENT_NEXUS.git`, the
credential helper is `manager`, and the branch has no upstream yet. Note
this branch also carries the earlier unpushed 5.1 commits (`fe4cb72`
through `1abc836`), so the first push moves more than one commit.

### 2. Build and verify the archive

```powershell
.\setup\test_assistant.bat
python tools\package_release.py --archive --skip-download
python tools\package_release.py --verify-only
python tools\package_release.py --split
```

Beta 5 for reference: 289 files, 13.06 GB staged, 12,345,399,239 bytes
zipped, six parts. Budget ~35 GiB peak; there is 53 GiB.

**The packager includes only Git-tracked files under `assistant/`.** That
is a privacy safeguard, not an oversight — do not widen it. It is why the
commit above had to happen before packaging could.

### 3. Smoke test, then rebuild if the test dirtied anything

Extract to a disposable directory and run the documented smoke test. If
running it creates files (`setup.bat` generates an API key and memory
files), rebuild from the clean committed tree rather than shipping the
folder you tested in.

### 4. Prerelease, upload, verify, publish

Create as a **prerelease**, upload all parts, compare published sizes and
hashes against local, and only then publish. Put the full ZIP SHA-256 and
the required part filenames in the notes, and insert the final test count.
`docs/RELEASE_NOTES_v0.2.0-beta.6.md` is committed and needs those numbers.

The 14B DLC parts in `dist\modelpacks\` (8.37 GiB) were built previously
and preserved through this session's cleanup. They are separate assets.

## What this session changed, and why it matters

The operator asked me to read the model's own `conversation_history.txt`.
Five real bugs were in it. All are fixed; every guard was verified by
re-injecting the original bug and confirming the test fails.

1. **The assistant reported a conversation that never happened.**
   `PERSONA_SHOTS` reached the model as plain user/assistant turns
   immediately before the real ones — structurally the six most recent
   turns. It fused two into "last time we spoke, you were working on audio
   settings and then said you might scrap the whole thing", and returned a
   third verbatim as a reply to an unrelated question. Fixed with
   `PERSONA_SHOTS_BOUNDARY` (a system message at all three injection
   sites, so the prompt-cache digest stays in step) plus a rule that no
   shot may assert anything about the operator's project. The marker alone
   is not trusted: asking a 4B model to discount six visible turns is the
   reasoning that already failed here once.

2. **Unregistered input was answered as if performed.** "finish goals" →
   "I am done with the goals". "drop all" and "finish" → stage directions.
   `near_miss_command()` in `command_handlers.py` now answers these in
   Python. Deliberately narrow — a false positive turns chat into an error
   message, which is worse than a miss.

3. **"choose a name" never reached the ceremony.** It produced "Sable"
   with a confabulated reason ("the forest shadows I was built to
   navigate"). `core/chosen_name.py` never ran, no `chosen_name.json` was
   written, and **`sable` is on that module's own `_STOCK_NAMES` veto
   list** — the real ceremony would have rejected it. Now handled by
   `_PHRASE_HINTS`.

4. **History was trimmed with a raw character slice**, leaving the file
   beginning mid-record (`r: hello there again`). Now cuts on exchange
   boundaries, which `history_recall` and `TimeAwareness` both parse.

5. **Fabricated hardware readings** ("the Whisplay HAT is running at 72%
   brightness... 380 lux... 41°C"). Already fixed in `core_memory.txt` by
   an earlier session; I only **verified** it live through `/ask`.

### Then, at the operator's direction

- **Visualizer.** Acid lattice drew lines ~3× thinner than the braille
  raster and rendered as speckle — the same class of bug `grid.py:192`
  already documents. Datastream's horizon floated six rows above the
  bottom. Neon horizon's skyline is now the project's corruption idiom
  (torn slabs, dropped cells, overexposed fragments). All eight scenes
  gained a wall-clock anchor layer via the new `visualizer/anchor.py`;
  reactivity raised globally in `reactivity.py`.
- **Loudness matching.** `visualizer/loudness.py`. Measured on the real
  41-track library: **20.0 dB spread → 1.4 dB**, loudest normalised peak
  0.985 against a 0.985 ceiling, no clipping. Gated RMS, not ITU LUFS —
  K-weighting is the honest next step and is documented in the module.
- **Operator-set names.** `name is NAME` bypasses the stock-name veto,
  because that veto governs the *machine* naming itself, not a person
  naming their companion. The record stores `chosen_by: "operator"` and
  `prompt_block()` tells the model it did not choose it. The operator has
  chosen **Sable**; it is not yet set.
- **Interface mode.** `start_interface_mode.bat`, an inverted icon
  generated without Pillow (`tools/generate_interface_icon.py`), and a
  Desktop shortcut. Every agent-interface call now echoes into the chat
  area (`AGENT_WATCH`, default on).
- **Onboarding.** `tutorial.introduction()` now covers the whole system in
  prose, 202 lines.

## Still owed to the operator

1. **`dev help` and `tutorial` usability.** Explicitly requested and not
   done. They are flat lists that assume you know the vocabulary. The
   operator wants them in the introduction's prose voice — "what is this
   group of tools for, when would I reach for it, what order do I learn
   them in". The introduction is the model to follow.
2. **A cosmetic "thoughts" display.** Short fragments that phase in and
   corrupt out at the same rate as typed-character phase-in. **Source them
   from real internal state** — sub-threshold retrieval candidates, token
   entropy, activity observations — not invented text. Displaying
   fabricated reasoning would recreate the exact bug class this whole
   session was spent removing. The operator agreed with that reasoning.
3. **An unbounded idle guard.** `ui.py:2890` suppresses the idle
   observation, check-in and auto-close whenever `_engine.current_input`
   is non-empty. One stray character disables all three forever, which is
   why a 5.5-minute idle produced nothing. "Someone mid-sentence is
   present, however long they pause" is right for a minute and wrong for
   an hour. Not fixed — the operator was told and has not decided.

## Things that cost time here

- **`gh` is not on PATH.** See above.
- **PowerShell mangles heredocs.** Write commit messages to a file and use
  `git commit -F`. `@'...'@` here-strings lost their quotes in this shell.
- **`_matches_registered_syntax` reads `entry["usage"]`.** A `<` in the
  usage string means "requires an argument", so adding `is <name>` to the
  `name` command silently stopped bare `name` being recognised. The usage
  string is load-bearing; it now says `is NAME`.
- **The deny-pattern/basename invariant is enforced by a test.** Adding
  `*/cache/track_loudness.json*` to `DENY_PATTERNS` failed the suite until
  `track_loudness.json` was also added to `PRIVATE_RUNTIME_BASENAMES`.
  That guard is from a previous QC session and it works — do not route
  around it.
- **Anchor line width is the whole design.** `anchor.lines()` at
  `π · step` renders eight-pixel lines that close into a wall; at
  `1.15 · step` they are certain to be sampled and thinner than a cell.
  Below `0.38 · step` the sampling guarantee is lost entirely.

## Conventions this repo enforces

- **Stage explicit paths. Never `git add -A`.** Two agents work in this
  tree. The 95-file commit here was staged path by path.
- **Fixes are applied and individually verified, never described.**
- **A guard test that passes with the bug re-injected is worthless.**
  Inject it and confirm the test fails.
- **Line endings are LF.** Writing a file from Python on Windows without
  `newline="\n"` converts the whole file to CRLF.
- **`OPENBLAS_NUM_THREADS=1`** for anything touching numpy or librosa
  audio, or it hangs rather than erroring.
- Do not refactor for taste. The comments here carry hard-won reasoning.
