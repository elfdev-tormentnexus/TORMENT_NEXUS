# Handoff — cutting Research v1, 2026-07-28

Written at the end of a very long session, at the operator's request, for
whoever cuts the release. Supersedes `CLAUDE_HANDOFF_POST_BETA6.md` where
they disagree; that note is still correct about AVG, the checksum cycle, and
the gotchas, and you should read it too.

## State

```text
branch:   beta-6-release   pushed through 1d6424a
release:  v0.2.0-beta.6    PUBLISHED, 21 assets, untouched this session
tests:    721 pass, 2 expected skips   (was 644 at session start)
tree:     clean
```

Fifteen commits this session. Nothing shipped to the published release; all
work is on the branch, and the published assets were not re-uploaded or
modified.

### Commit order, for context

```text
d380284  README/install path, LICENSE, hero mark, pq_probe rescued, 3.6x
21517c2  rosetta stone, cross-model translation measured
946dc98  describe: vectors in readable anchors, centering fix
e4b2be2  reordering answered -- negative
3e2fcf3  the beam: per-token trajectories
16a24ae  SABLE7 container + translation research doc
1820361  experimental-mode flag, shadow-first
243dbeb  trace: locate meaning at a token
785f33e  hazard stripes + env-var mode start
407e2eb  machinespirit wired into the assistant
da55f69  outward docs + this handoff
5a8f6c2  bulk downloader: discover parts instead of assuming six
dae86b0  animated APNG beam, lossless time axis
1d6424a  session rhythm, and beam pacing from it
```

## What the release is meant to be

The operator's decision: **rename from `beta` to `research v1`**, because a
build shipping weakened-refusal models plus an unproven representation is
not a beta in the ordinary sense, and the version string should say so. Same
instinct that published the failed Wi-Fi result.

**Do the rename after confirming the feature works, not before.** The name
should describe something real.

## The headline feature: machinespirit

An embedding is a mean over token vectors. The mean says what a sentence is
about; it cannot say *where* a meaning appeared, because averaging destroys
that. machinespirit keeps the path and reads each token position against a
fixed English concept dictionary.

```text
trace I keep thinking about something my grandmother said before she died.
  token   7  +0.459  grandparents telling the same story again
  token  11  +0.421  a promise made to a dying person
```

`SABLE7` is the container; machinespirit is the representation. They version
separately and the docs keep them apart deliberately.

### Everything it touches

| Piece | Path |
| --- | --- |
| App-side reader | `assistant/core/machinespirit.py` |
| Anchor dictionary | `assistant/core/anchors_v1.json` (digest `b5421687348e956e`) |
| Config | `MACHINESPIRIT_URL` / `_KEY` in `assistant/core/config.py` |
| Commands | `experimental mode`, `trace <text>` in `command_handlers.py` |
| Launcher | `start_assistant_hazard.bat` + `assets/hazard_icon.ico` |
| Research tools | `tools/rosetta_stone.py`, `tools/vector_beam.py` |
| Session rhythm | `assistant/core/session_rhythm.py` |
| Documents | `docs/VECTOR_TRANSLATION_RESEARCH.md`, `docs/VECTOR_PIXEL_RESEARCH.md` |

### Landed after this handoff was first written

- **Bulk downloader fixed.** The operator wants it on every release from
  now on, which made a latent bug worth fixing first: the part list was
  `range(1, 7)` against a `part0{n}` template, and `build()` never checked
  for parts that exist but are *not* listed. The first release with a
  larger archive would have shipped a six-part downloader for a seven-part
  archive, verified every file it carried, reported success, and handed
  every recipient a corrupt archive. Parts are now discovered from `dist`,
  required to be consecutive from 1, and a stray part fails the build.
  **This matters directly for the cut you are about to make.**
- **Animated beam**, `tools/vector_beam.py animate`. APNG, lossless, one
  frame per token, frame duration proportional to that step's distance.
- **Session rhythm**, `assistant/core/session_rhythm.py`. Session duration,
  exchange counts, typical pause, and rank against past sessions. Feeds
  `viewing_pace()`, which sets the animation rate from measured behaviour
  instead of a constant. Not yet wired into the turn loop — the module and
  its 25 tests exist; nothing calls `note_turn()` yet.

### The constraint that breaks naive implementations

**llama.cpp fixes pooling at server launch.** A per-token trajectory cannot
come from the pooled embedder on 8082. It needs a *second* instance of the
same model started with `--pooling none`, which the hazard launcher starts
on 8084. This is cheap — bge-small is 36 MB — but it is not optional, and
anything that assumes one server will silently get a single pooled point
where a path was requested.

Also: the unpooled route is llama.cpp's own `/embeddings`. The
OpenAI-compatible `/v1/embeddings` refuses `pooling=none` with HTTP 400.

## Before you cut

1. **Verify the launcher end to end on a real extracted tree.** It has been
   verified as a module and as commands, but the packaged launcher has not
   been run from an installed copy.
2. **Confirm `anchors_v1.json` actually lands in the package.** The packager
   copies tracked files under `assistant/` with no extension filter, so it
   should — but if it does not, machinespirit fails at runtime with no
   dictionary, and that is a silent feature death rather than a crash.
3. `start_assistant_hazard.bat` and both hazard icons are already added to
   the packager's explicit root list in `tools/package_release.py`. A
   launcher missing from that list does not ship and nothing warns you.
4. **Re-check AVG's Web Shield before any upload.** It has re-enabled itself
   once already. Sample `(Get-NetAdapterStatistics | Measure-Object
   SentBytes -Sum).Sum` 20–30s apart; a literal zero delta with a live
   connection is the AV path, not a broken uploader. Two prior sessions were
   lost rewriting a working uploader.
5. **The checksum cycle has a required order** and renaming the version
   re-enters it from the top: finalise notes → rebuild patch → record its
   digest → rebuild downloader → record its digest → stop.

## What is honest about this feature, and must stay in the release notes

The temptation will be to describe machinespirit as an improvement. It is
not, in the way people will assume, and the project's whole posture depends
on not overclaiming here.

- **Retrieval is unchanged.** Late interaction (ColBERT-style MaxSim) over
  trajectories retrieved the *same documents* as plain pooled cosine on the
  only test run. Trajectories shadow retrieval; they do not replace it.
- **Anchor space is worse for storage**, not better: 0.689 top-5 agreement
  against uint8 absolute's perfect **1.000**. The rosetta stone buys
  portability across models, not compression.
- **The gain is a capability, not a margin.** The trace locates a concept at
  a token, which the averaged vector cannot do *at all*. That is the claim,
  and it is enough.
- **The anchor set does not span the assistant's own memories.** Real cached
  entries profile at roughly +0.24 and incoherently, while well-formed
  sentences profile sharply. The dictionary is built for documents, not for
  a life. Anyone expecting to read Sable's memory with this will be
  disappointed, and the notes should say so.

## Measurements worth keeping accurate

| Claim | Number |
| --- | --- |
| Quantisation, float32 → uint8 | exactly **4.00×** |
| Round-trip cosine error | 6.91e-05, **868×** under the 0.06 retrieval margin |
| uint8 retrieval fidelity | **1.000** top-5 agreement with float32 |
| Embedding cache, JSON → uint8 | **35.2×** (906,109 → 25,728 bytes) |
| SABLEVEC1 vs zlib'd float32 | **3.59×** |
| Cross-model translation | 0.370 vs 0.549 ceiling, 0.056 chance — **67% of reachable** |
| Trajectory independence from the mean | **98.6%** |
| PNG alpha channel | gains **nothing**; RGBA-with-pinned-alpha costs **21%** |

## The honesty rule this session converged on

Worth carrying forward, because it settled several arguments and will
settle more. The line is **not** whether the assistant says "I". It is
whether the fact underneath is real and checkable.

- "Six hours, the longest session I have a record of" — first person, warm,
  and every clause verifiable against `session_rhythm.json`. Fine.
- "I felt every minute of that" — verifiable against nothing. Not fine, and
  no module here gives ground for it.

The same rule resolved the hidden-activity question. `time_awareness.py`
says the assistant "cannot claim to have watched, waited, thought, or felt
anything" during a gap — correct for the *closed* case, where nothing ran.
But when the assistant is **running and the library worker is rebuilding an
index**, activity genuinely occurred and was logged. Reporting it is
measurement, not simulation. The blanket phrasing forbids a true statement
by accident.

Three states, and only the third has anything to report:

| State | Hidden activity? |
| --- | --- |
| Closed | No. Clock only. |
| Running, idle, nothing queued | No. |
| Running, background work | **Yes, and logged.** |

Unbuilt: wiring the worker's completed jobs into something the assistant
can mention. The operator wants this.

## Still open

1. **Cache conversion to uint8** — 35×, zero measured retrieval cost,
   proven twice by different methods. Clearest win available. Touches a
   privacy-sensitive derived cache the release builder excludes, so it wants
   its own change and its own tests.
2. **Alpha fix** — dropping the unused alpha channel saves 21% on every
   RGBA image. **Blocked**: `read_png` in `tools/vector_pixel_compiler.py`
   hard-requires colour type 6. I tried this, produced a mark our own
   decoder rejected, and reverted it. Fix the decoder first, with a test,
   then re-encode.
3. **Shadow retrieval logging** — experimental mode is meant to generate the
   evidence that would justify it. The flag and commands exist; nothing logs
   comparisons yet.
4. **A labelled retrieval corpus.** The operator's idea, and it is the right
   one: a dictionary gives natural labels — query with a word, the correct
   document is its definition. Webster's 1913 Unabridged is public domain on
   Gutenberg. This is the missing piece that would settle whether
   trajectories help retrieval, which every negative result above is
   provisional without.
5. QC findings 3, 4, 6, 7 — GitHub settings and the published release body.
   Cannot be done from the repository.
6. **Model licensing** before any wider audience. `RIGHTS.md` records it as
   unresolved: the 4B uploader declares no licence, the 7B declares
   AGPL-3.0, and the release redistributes both.

## Two near-misses this session, recorded because the pattern matters

Both were caught by verification, neither shipped.

- A centering fix that **could not have worked**: standardising each
  vector's scores across anchors is monotonic, so it reorders nothing. It
  produced different-looking numbers in identical order and looked correct.
  The real fix subtracts the mean anchor *vector*, changing geometry rather
  than scale.
- A re-encoded `sable_mark.png` that **our own decoder rejects**. The 21%
  saving was real and the payload verified byte-identical, but `read_png`
  requires RGBA. Restored from git.

The project's standard held both times: apply, then verify individually,
then check the guard still fails with the defect reinstated. Keep doing
that, especially during a release.
