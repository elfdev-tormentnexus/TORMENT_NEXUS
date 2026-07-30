# CLAUDE NEW WINDOW HANDOFF — start here

**You are the next Claude window on TORMENT_NEXUS. This file is addressed to
you.** It replaces the version written at the end of the researchB build
session; that Claude's two jobs are now done, and this records what was
decided, what was found along the way, and what is still open.

Older files in this directory are historical session notes, not instructions.
This is the current one.

**The operator's next request is already known: an in-depth, every-single-
function audit and full test pass over the entire project.** Read §5 before
starting it, and read §6 before proposing anything at all.

The tree is **green and committed**: `master` is at `44684ab`, 1,022 tests,
`OK (skipped=2)`. Nothing is half-applied. **Not pushed** — the operator has
not asked.

---

## 1. What the last session did

Both jobs from the previous handoff are complete.

### The researchA → researchB rename (release blocker — cleared)

`RELEASE_VERSION` is `researchB` in `tools/package_release.py:65` and
`tools/package_model_pack.py:36`. Verified propagation to all five derived
names: archive, reassembler, docs patch, ask-guard patch, command-guard patch,
and the model-pack asset stem. `'researchA' in package_release.README` is now
`False`.

Beyond what the previous handoff listed, two more strings named the version
and were missed by its sweep:

- `tools/package_model_pack.py:2` — the module docstring. **Reworded, not
  converted.** An f-string docstring is not a docstring: `__doc__` becomes
  `None`. Several tools in this repo do `argparse.ArgumentParser(
  description=__doc__.splitlines()[0])`, so converting one would be a
  latent `AttributeError`. `package_model_pack` does not do that today, but
  the rule matters for the next tool.
- `tools/package_model_pack.py:665` — the argparse description, an ordinary
  f-string.

Four version pins repointed at researchB, not weakened:
`test_package_model_pack` ×2, `test_regressions.ReleaseModelContractTests
.test_release_artifacts_are_stably_versioned`.

### `COMBINED_FORMAT` — the judgement call, resolved

`tools/machinesoul_release.py:41` stays `"SABLERESEARCHA_MANIFEST1"`. The
previous handoff could not resolve whether it names the format or the
release. The published manifest on disk settles it:

```
SABLERESEARCHA/COMBINED_MANIFEST.json
  format:     "SABLERESEARCHA_MANIFEST1"      <- the format
  components.windows.format: "MACHINESOUL_RELEASE1"
  components.windows.prefix: "SABLERESEARCHA-WINDOWS"   <- the release
```

It occupies the same `"format"` slot as `MACHINESOUL_RELEASE1`, both ending in
a version digit; `_load_reassembly_manifest()` at `:1037` compares it for
equality to decide whether a manifest is readable at all; and the release
identity lives in a separate `prefix` field the operator supplies with
`--prefix` at cut time. So researchB capsules inherit no researchA marker
from it, and changing it would strand ~21 GB of published assets. Reasoning
is written at the definition and in `docs/MACHINESOUL_RELEASE_CUT_METHOD.md`.

**Do not revisit this without reading both call sites first.**

### Package whitelist

Added to `INCLUDE_FILES`: `assets/sable_field.png`,
`assets/super_dev_icon.ico`, `tools/build_super_dev_icon.py`, and
`docs/RESEARCHB_STAGING_PLAN.md`. `assistant/core/provenance.py` needed no
entry — `assistant/` ships via `INCLUDE_DIRS` with `TRACKED_ONLY_DIRS`, and it
is committed.

New test `test_every_whitelisted_file_actually_exists` fails in fifty seconds
if a whitelist entry is absent. The builder already raised on this, but only
once a long build was underway. Model/voice payloads are excluded from the
check because they are documented external downloads.

### Receipts on the answer path

`knowledge/library.prompt_context_with_citations()` returns
`(text, citations)`. `prompt_context()` still returns a plain string and
delegates, so every existing caller is unchanged.

The pairing happens inside the library on purpose: the size cap drops whole
records, and a caller re-running the search to build its own citation list
would sometimes cite a document the model never saw.

`main.py` holds the citations at `build_messages`, and
`_record_conversation_turn()` finishes the receipt once the answer exists.
`receipt` (dev_only=False, group "knowledge") renders the last one.

The reply is recorded as **one INFERRED claim**. It is not split into observed
and inferred parts. Splitting properly needs quote-matching against the
excerpts; a wrong `OBSERVED` label lends a file's authority to something the
model supplied, which is worse than no label. **This is the obvious next
feature and it is deliberately not done — do it carefully or not at all.**

---

## 2. Bugs found while doing the above

- **The T-Deck bridge records a failed generation as a turn**
  (`main.py:2330`, `reply = "I could not complete that request: ..."`). That
  would have produced a receipt citing the documents retrieved for a question
  that was never answered. Cleared in `run_generation`'s `except` branch. The
  test for it was verified to fail without the guard.
- **`_citation()` falls back to UNVERIFIED, never CLEAN**, when a row has no
  trust in its stored metadata. Rows shelved before trust-at-ingest have none,
  and reading a missing field as clean would let the oldest, least-examined
  documents present themselves as the most trustworthy.

---

## 3. Two mistakes made and corrected — read this, it will save you

### Tests wrote fabricated exchanges into the operator's real memory

Calling `main._record_conversation_turn()` directly in a test appends to
`assistant/memory/conversation_history.txt` and queues it for embedding. Ten
invented exchanges reached the real file before it was caught.

**`conversation_history.txt` is gitignored** (`.gitignore:42`), so
`git status` will never show you this. It was caught by file mtime. The file
was restored to 217 lines; a backup of the polluted version is in the session
scratchpad.

`tests/test_provenance.AnswerPathReceiptTests` now patches `mem.append_history`,
`history_recall.refresh` and `memory_worker.submit`, restores `session_turns`,
and carries `test_this_test_class_does_not_write_to_real_memory`, which
compares the real file's bytes before and after. **If you add a test that
touches the answer path, extend that class rather than writing a new one.**

### A scripted file rewrite flipped the whole file to CRLF

`pathlib.write_text(read_text())` — the ordinary "edit, test, restore"
pattern — converted `assistant/main.py` from LF to CRLF, turning a 95-line
diff into 3,816 insertions. The text compared equal, so the round-trip check
passed.

Repo files are LF; the machine is Windows; there is **no `.gitattributes`**,
so nothing normalises this. Rewrite repo files in binary mode
(`open(p,'rb')` / `open(p,'wb')`), and **check `git diff --stat` after any
scripted rewrite** — a diff far larger than the edit means endings flipped.
`b.replace(b'\r\n', b'\n')` puts it back.

---

## 4. Still open

### The beginner-docs rename — deliberately NOT done, and why

`test_regressions.DocumentationTests.test_beginner_docs_point_at_the_current_release`
still reads `current = "researchA"`. The previous handoff instructed flipping
it. That instruction was not followed, for three reasons the previous Claude
did not have in view:

1. **Part counts are outputs of the cut, not inputs.** The docs name
   `SABLERESEARCHA-WINDOWS.part01` … `part09` and `-14B.part01` … `part06`
   explicitly. researchB's tree has grown, so those counts will likely differ,
   and they cannot be known before stage 5.
2. **The calibration patch must be removed, not renamed.**
   `2a844f0 Add the researchA calibration clarity patch` is in master's
   history, so researchB ships that fix built in and publishes no calibration
   patch. `INSTALL_SABLERESEARCHA_CALIBRATION_PATCH.bat` and its two capsules
   should disappear from the beginner docs entirely.
3. **Flipping now would make the docs lie.** They would tell a user to select
   a GitHub release that does not exist. researchA is what is downloadable
   today, so `current = "researchA"` is currently *correct*.

Scope if you do it: **93 prose references + 49 asset-name references across 17
files.** Highest counts are `README.md` (22 + 11), `docs/INSTALL_WINDOWS.md`
(13 + 15), `docs/RELEASE_CHECKLIST.md` (5 + 18), `docs/TROUBLESHOOTING.md`
(8 + 5), `MODELS.md` (10 + 0).

Also coupled: `test_beginner_install_path_names_every_release_asset` pins the
exact asset set and the `SABLERESEARCHA-[A-Za-z0-9.-]+\.png` regex, and
requires README and INSTALL_WINDOWS to name identical sets.

**This belongs to stage 5. The operator was told and has not redirected.**

### Must NOT be renamed — historical record

Unchanged from the previous handoff, and still correct:
`docs/RELEASE_NOTES_researchA.md`,
`docs/RESEARCHA_PRE_RELEASE_SESSION_2026-07-29.md`, `CHANGELOG.md` entries,
`tools/apply_researcha_patch.py`,
`tools/build_researcha_calibration_patch.py`,
`assistant/tests/test_researcha_patch.py`,
`assistant/memory/core_memory.txt`, and the local gitignored `SABLERESEARCHA/`
cut directory.

### Known-open, not blocking

- **`machinespirit.available()` returns True while every call 401s.** It
  probes `/health`, which needs no auth. Cost an hour on 2026-07-29: a stale
  `sable-anchor-field-check` server squatting on 8084 made every
  `trajectory()` return a bare `None`. Make it exercise an authorised
  endpoint. Carried over unfixed from two handoffs now.
- **No `.gitattributes`**; `git diff --check` reports ~3,670 CRLF findings.
  Noise, but see §3 — it is also a live foot-gun.
- **README trace figures are slightly stale**: live gives `+0.456 / +0.420`
  where the README says `+0.459 / +0.421`. Left alone deliberately: correcting
  a published number to another number nobody re-measured is not an
  improvement. Re-measure before editing.
- `docs/RESEARCHB_STAGING_PLAN.md` stages 1, 3, 4, 5 are still blank, and
  stage 2 has only 2.1. Stage 0 and 2.1 are recorded, with an explicit note of
  which figures were re-measured and which were transcribed.

---

## 5. The audit the operator is about to ask for

They asked, mid-session, for "an in-depth, every single function, full suite
of tests and audit the entire torment nexus project."

Before starting, know the shape of what you are auditing:

- **1,022 tests, ~50 s**, via `.\setup\test_assistant.bat` or
  `python run_regressions.py` from `assistant/`. **Set
  `OPENBLAS_NUM_THREADS=1`** or numpy/librosa paths hang instead of erroring.
- The suite is the safety boundary, not a certification —
  `docs/TESTING.md` says so, and it is right.
- **Do not publish a fixed test count into any document.** The staging plan's
  hardcoded `975` was already stale twice; it now records the invariant
  ("no failures, 2 skips") instead.
- Working directory persists between Bash and PowerShell calls in this
  harness. The test runner needs `cd assistant`; after that, `git` commands
  will resolve against `assistant/` until you `cd` back. This caused two
  confusing results in the last session.

Things worth pointing the audit at, based on what surfaced incidentally:

- `prompt_context` is called **twice per turn** — once in
  `_runtime_context_prompt` (`main.py:1134`) and once in `build_messages`
  (`main.py:1287`). Only the second one now yields citations. 6.2 ms each, so
  it is not a performance problem, but it is a duplicated retrieval and the
  two could in principle disagree.
- No test asserted that whitelisted release files exist until last session.
  Look for the same shape elsewhere: lists of filenames that nothing checks.
- `machinespirit.available()` (above) is a liveness check that does not check
  liveness. Other `available()` / `configured()` probes may share the flaw.

---

## 6. The pacing rule — read this before proposing more work

Unchanged, and it is about the operator's health rather than process. They
worked to the point of getting sick during the researchA cut. In their words:

> "dont let me argue for patches, let me take a break before doing any
> patchwork. thats the idea"

**The cut-off is after a push, not before.** Pre-release feature work in the
same session is welcome — keep landing it until they are happy. The moment to
push back is once an update has shipped and they start arguing for patches on
top.

Say the concern once, then respect the answer. They have overruled it
deliberately and been right every time.

---

## 7. If you only have five minutes

1. The tree is green at `44684ab` and **unpushed**. Ask before pushing.
2. Do not sed `researchA` out of the tree. §4 says what must stay, and the
   beginner-docs flip belongs to stage 5, not to today.
3. If you write a test that touches the answer path, extend
   `AnswerPathReceiptTests` — it is isolated. A fresh one will write into the
   operator's real conversation history, and git will not tell you.
