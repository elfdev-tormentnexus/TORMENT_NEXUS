# CODEX — cutting researchB. Start here.

**You are picking up from a Claude session that ended at its time limit on
2026-07-30.** Everything below is committed and pushed to `master`. The tree
is green: **1,060 tests, no failures, 2 skips.**

The operator wants researchB uploaded today. This file is what stands between
you and that. Read §1 and §2 before touching anything.

---

## 1. The honest state: researchB is NOT ready to upload

The tree is in good shape. That is a different claim from ready, and the
difference is entirely unrun verification rather than unfinished code.

| what | state |
| --- | --- |
| The 8 audit findings | all implemented, tested, verified |
| Suite | 1,060 pass / 2 skip |
| Naming | flipped to researchB across 18 documents |
| Staging plan stages 1, 3, 4, 5 | **never run** |
| Stage 2 | 2.1 of 2.6 |
| **5.3 — decompile every capsule on a clean directory** | **not done** |
| **5.4 — install from the decompiled tree** | **not done** |
| researchB cut itself | **never cut** |
| A download path for researchB | **does not exist** — see §4 |

**5.3 and 5.4 are the release.** Everything else is preparation. Uploading
without them means publishing 12+ GB of capsules nobody has confirmed
reassemble. `docs/RESEARCHB_STAGING_PLAN.md` is the plan; it asks for stages
1–4 green and recorded before stage 5, and it says explicitly that stages 2
through 5 should not run on the same day. That instruction exists because the
researchA cut made the operator ill. **Read §7 before deciding to compress it.**

## 2. Run the suite like this

```
set OPENBLAS_NUM_THREADS=1
python assistant/run_regressions.py
```

Without `OPENBLAS_NUM_THREADS=1`, numpy/librosa paths hang instead of erroring.
~50 seconds. **Do not publish a fixed test count into any document** — the
staging plan's hardcoded number went stale twice; it records the invariant
("no failures, 2 skips") instead.

Working directory persists between tool calls in these harnesses. The runner
wants the repo root; `cd assistant` will silently make later `git` commands
resolve against `assistant/`. That cost the last two sessions time.

## 3. What changed today, and why you care

Eight audit findings, all in `docs/AUDIT_2026-07-30.md` with evidence and
resolutions. The ones that affect a cut:

- **`machinespirit.diagnose()` used to report `ready: True` with no servers
  running.** Fixed. It now reads `embedding_server.is_alive()` instead of a
  config check, and `available()` probes an authenticated `/v1/models` rather
  than the unauthenticated `/health`. If you verify machinespirit during
  staging and it says a server is down, believe it now.
- **The suite used to leave a real `llama-server` running after every run.**
  Fixed. If you find a stray one, it is not from the suite.
- **`.gitattributes` now pins `*.py` and `*.md` to LF.** 26 files were
  normalised and 3 UTF-8 BOMs stripped in `e48ecd5`, which is listed in
  `.git-blame-ignore-revs`. `*.json` and `*.bat` are deliberately NOT pinned —
  `anchors_v1/v2.json` are CRLF and carry the digests published figures
  reproduce against, and two launchers are CRLF where cmd.exe is fussy. The
  reasons are written into `.gitattributes` itself.
- **`TORMENT_NEXUS.bat`** is new: one menu, four modes, dispatching to the
  existing wrappers. It ships in `INCLUDE_FILES`. It also offers to stop
  llama-servers left over from a previous session, matched on the install path.
- **The prompt budget now sheds retrieved documents** when it cannot fit them,
  instead of raising an error blaming the operator's message.

## 4. The download path — a real gap, and a decision already made

**researchA ships no downloader.** It is capsules plus
`DECOMPILE_SABLE_researchA.bat`, and the user fetches ~12.4 GB by hand from
the release page.

`tools/build_bulk_downloader.py` exists but is a **Beta 6 artifact** — zip
parts, a different distribution shape, pinned to `v0.2.0-beta.6`. Do not
"update" it and assume that solves researchB. The same applies to
`build_ask_guard_patch`, `build_command_guard_patch`, `build_docs_patch` and
`build_interface_mode_dlc`: all are post-hoc patch builders for an archive
that already shipped, and renaming their `VERSION` would make them stop
describing the thing they built.

**The operator has decided researchB should get a small fetcher asset.** Their
words: *"i think it should have a smaller fetcher asset."* The design
constraints they and the last session settled on:

- **Not an `.exe`.** An unsigned executable that downloads gigabytes is a
  textbook AV false positive. A `.bat` calling `curl.exe` (Windows 10 1803+)
  avoids it entirely, which is what the Beta 6 downloader did.
- **Resume and verify.** `curl -C -` matters at gigabytes on a connection that
  drops, and every part must be checked against its SHA-256 after transfer,
  with an already-valid file skipped. The Beta 6 tool is a good model for the
  *mechanism* even though it is the wrong artifact.
- **Generate it, do not hand-write it.** The Beta 6 tool reads the asset list
  and digests from the files actually built. A hand-made helper in this
  project once knew about two parts when there were more, and every recipient
  got a corrupt archive.
- **Watch AVG.** This machine's AVG HTTPS scanning silently pins large
  transfers at 0 B/s while small requests succeed. It has cost real hours.
  Whatever you build, measure throughput before blaming the code.

## 5. Naming — what is already done, and the one thing left

Flipped to researchB today, in `912b58b`: 139 references across 18 documents
that describe the shipping product.

**Must never be flipped**, and were not: `CHANGELOG.md`,
`docs/RELEASE_NOTES_researchA.md`, `docs/RESEARCHA_PRE_RELEASE_SESSION_*`,
`docs/WHITENING_EXPERIMENT.md`, `docs/RESEARCHB_STAGING_PLAN.md`'s researchA
baselines, `tools/apply_researcha_patch.py`,
`tools/build_researcha_calibration_patch.py`,
`assistant/tests/test_researcha_patch.py`,
`assistant/memory/core_memory.txt`, and the gitignored `SABLERESEARCHA/` cut
directory. Those record what happened.

**`SABLERESEARCHA_MANIFEST1` must never change.** It names the capsule
*format*, not a release. It sits in the same `format` slot as
`MACHINESOUL_RELEASE1`, `_load_reassembly_manifest()` compares it for equality
to decide whether a manifest is readable at all, and the release identity
lives in a separate `prefix` field supplied with `--prefix` at cut time.
Changing it strands ~21 GB of published researchA assets.

**The one thing left: part counts.** Both beginner documents now say
`SABLERESEARCHB-WINDOWS.partNN.png` and `SABLERESEARCHB-14B.partNN.png`,
deliberately. How many parts exist is an output of the cut. After you cut:

1. Count the parts the cut actually produced.
2. Replace `partNN` with the real last part in `README.md` and
   `docs/INSTALL_WINDOWS.md`.
3. `test_beginner_install_path_names_every_release_asset` pins the set and
   requires both documents to name **identical** sets. Update it with them.

The calibration patch is already removed from the beginner docs rather than
renamed — `2a844f0` is an ancestor of master and edits `calibration.py`
itself, so researchB ships that fix built in and publishes no patch. A test
now asserts no beginner document names one.

## 6. Still not done, beyond the cut itself

- **Public docs do not describe today's changes.** The launcher menu, the new
  desktop icon, the prompt-budget shedding, and the machinespirit probe fix
  are all unmentioned in README / INSTALL_WINDOWS / ARCHITECTURE / CHANGELOG.
  The naming is right; the content is a release behind.
- **`CHANGELOG.md` has no researchB entry.**
- **Stages 1–4 of the staging plan**, with their numbers recorded in the table
  at the bottom of that document. An empty row means a stage was not run, and
  that is a fine state to leave it in — but not before publishing.

## 7. The pacing rule — this is about the operator's health

They worked to the point of getting sick during the researchA cut. In their
own words, carried through three handoffs now:

> "dont let me argue for patches, let me take a break before doing any
> patchwork. thats the idea"

The cut-off is **after a push, not before**. Pre-release work in the same
session is welcome. The moment to push back is once something has shipped and
they start arguing for patches on top of it.

They said today they want researchB uploaded today, and they have been at this
for five hours. Both things are true at once. Say the concern once — that 5.3
and 5.4 are the release and skipping them means publishing something nobody
has confirmed reassembles — then respect the answer. They have overruled this
deliberately before and been right every time.

## 8. Traps that cost the last sessions time

- **`assistant/memory/conversation_history.txt` is gitignored.** Tests that
  call `main._record_conversation_turn()` write into the operator's real
  memory and `git status` stays clean. Ten fabricated exchanges reached it
  before anyone noticed. If you add a test touching the answer path, extend
  `tests/test_provenance.AnswerPathReceiptTests` — it is isolated and carries
  a test that asserts it does not write to the real file.
- **Scripted file rewrites.** Use binary mode (`open(p,'rb')` / `'wb'`). This
  is safer now that `.gitattributes` exists, but check `git diff --stat` after
  any scripted rewrite: a diff far larger than the edit means endings flipped.
- **`machinespirit` needs both embedding servers.** 8084 unpooled supplies the
  path, 8082 pooled embeds the anchor dictionary. The hazard launcher starts
  8084; the app starts 8082.
