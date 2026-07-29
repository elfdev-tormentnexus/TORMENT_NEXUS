# Handoff to Sol — researchA, from the audit to the cut

Written by Claude, 2026-07-29. Everything below is committed and pushed.

**State:** `origin/beta-6-release` is at the head of this branch. Tree clean.
**915 tests pass, 2 expected skips** (was 807 at your `9cc9d11`).

Your cut maps were correct and I verified them independently before
touching anything — coverage exact across all 363 files, no gaps or
overlaps, no capsule over the 1.797 GB ceiling, every in-file cut
vector-aligned, and the plan hashes matching `sha256` of the exact JSON
bytes the cutter compares. The 332-byte gap between `sum(data_size)` and
`total_size` is inter-entry alignment padding (126 gaps in part01, 46 in
part09) and is not double counting.

Then I patched the source, which invalidated the Windows half. Read
§1 before anything else.

---

## 1. What your plans stand or fall on now

| artifact | state |
| --- | --- |
| `CUT_PLAN_14B` `93646759…` | **Still valid.** One `.gguf`, untouched by source patches. |
| `CUT_PLAN_WINDOWS` `36ee7005…` | **Invalid.** Source changed under it. |
| `dist/TORMENT_NEXUS` | **Stale.** Built from `6494565`. |
| `capsule/SABLE_researchA_research.png` | **Stale.** It carries `ARCHITECTURE.md` and the release notes, both edited. |
| `extractor/machinesoul.py` | **Was already stale before I started — see §2.** |
| `SHA256SUMS.txt`, `CAPSULE_CONTENTS.txt` | Regenerate last, after every asset above is final. |

`SABLERESEARCHA/UPLOAD.md` is rewritten as the full capsule-only runbook in
the correct order. The old one predated the pivot and would have published
a release whose own body named six assets while the upload command attached
three.

## 2. The one item that is not bookkeeping

`SABLERESEARCHA/extractor/machinesoul.py` was pinned at commit `5ee852e`,
**three behind**, and that copy has **no `extract_stream` and no
`_chunks_of`**. It is the buffered-only version.

It reads the 143 KB research capsule perfectly, which is exactly why the
staleness was invisible. It would try to load each **1.797 GB release part
entirely into memory** — the failure your own commit `6494565` exists to
prevent, shipped as the tool `RELEASE_BODY.md` tells recipients to
download.

Every release part is an ordinary `MACHINESOUL1` capsule (the cutter builds
each through `machinesoul.build_stream()`; `MACHINESOUL_RELEASE1` names the
plan and manifest, not the pixels), so the published `machinesoul.py` is
the right tool for every asset — **once it is the current one.** Copy it
fresh and regenerate `SHA256SUMS.txt`.

## 3. Audit findings, all fixed (`e466139`)

I ran a full read-only audit before patching. Six real defects:

- **`consume` redirect SSRF.** The private-address refusal ran once against
  the supplied URL, then followed redirects unchecked; `fetch()` re-requested
  the *original* address with redirects enabled. A public page answering
  `302 Location: http://169.254.169.254/` was fetched, stored and indexed.
  `MAX_REDIRECTS` was defined and referenced nowhere. Every hop is now
  validated, chains capped, relative `Location` resolved against its own hop,
  media-host redirects reported as media. +10 tests.
  The DNS re-resolution gap that remains is **named in the notes** rather
  than implied shut.
- **Reflection bypass in the autonomous capability gate.** `getattr` and
  family were unlisted, and `_call_name` returns `""` for a call whose callee
  is a call, so `getattr(os, "sys" + "tem")(...)` added process capability
  invisibly.
- **`extract_stream` destroyed an existing file on refusal** — it truncated
  `--out` before validating a byte, then deleted it, while saying nothing
  was kept. True of the payload, false of the file. Writes beside and renames
  now.
- **`build_stream` leaked** a partial capsule and frame spill on interrupt.
- **`restore()` ambiguity** — it took whichever file the walk reached first
  when a flattened backup name matched more than one.
- **`session_rhythm.json` was in neither `.gitignore` nor `DENY_PATTERNS`.**
  It went unlisted for as long as nothing wrote it. Now covered by the deny
  pattern *and* the independent basename check.

Two doc corrections: `ARCHITECTURE.md` claimed session rhythm supplied the
animation pace (nothing called it), and the release notes claimed the
address refusal covered redirects (it did not).

## 3b. Second round — launchers, tutorials, calibration

**Launchers renamed to what they are.** `TORMENT_NEXUS_INTERLINKED` (the
read-only agent interface) and `TORMENT_NEXUS_HAZARD`. Window titles,
banners and desktop shortcut names follow, and `make_interface_shortcut.py`
gained `--hazard` and `--both` — the hazard launcher had an icon but no way
to put it on a desktop.

**Each launcher has its own walkthrough.** Hazard eight sections,
interlinked five, in the structure and voice of the ordinary tour.
Progress is stored **per mode**, so finishing one never marks another seen,
and a pre-mode state file migrates into `ordinary` rather than resetting
anyone. One thing to watch if you touch it: lesson sets must resolve at
**call time**. The first version froze them in a dict at import, so
anything rebinding `LESSONS` was silently ignored while looking correct.
The existing vanished-command regression caught it.

**`calibrate` and `SABLE_CALIBRATION1`.** Seven fixed texts with readings
recorded under a named model, quantization, pooling and anchor digest.
Nothing previously detected any of those changing and moving every
published figure at once. Three rows are controls, one a **Fibonacci word**
ordering — Sturmian, exactly n+1 subwords at every length, asserted by
`is_sturmian()` and a test rather than cited. Fibonacci and random share a
phrase mix and differ only in order, so they must read alike: 1.5238
against 1.5132, permutation invariance shown on live data.

**Note for the rebuild:** `assistant/core/calibration_v1.json` and its
capsule are recorded against this machine's embedding model. They are
source, not runtime state, and should ship. If the bundled model ever
differs from the one named in the record, `calibrate` will correctly report
drift on every row — re-record rather than widen the tolerance.

## 4. Features added

**Session rhythm, wired end to end.** It was a fully tested module that
nothing called — `note_turn()`, `record()` and `viewing_pace()` were all
correct and all unreachable. Now counted at the one seam both the typed and
spoken loops pass through, written once at shutdown for sessions holding at
least one exchange, surfaced in the runtime prompt as counted facts, and
`vector_beam`'s `--pace` finally asks `viewing_pace()` for the measured
multiplier its help text always claimed came from there.

**`spread <text>`** — the density matrix of a trajectory's tokens: purity,
participation ratio, von Neumann entropy. Computed from the `n × n` Gram
matrix rather than the `384 × 384` second moment since they share every
nonzero eigenvalue; cyclic Jacobi written out to keep the module pure
`math`. Measured on live traces **with the length control**: growing one
topic 49% moves effective rank +1.1%, adding topics at matched length moves
it +12.6%. Permutation-invariant, and a test asserts that rather than the
docstring claiming it.

**`trail <text>`** — the same reading as `trace`, bounded by the dictionary
instead of the input. 89 tokens → 24 values against 34,176 (**1,424×**, and
the ratio improves with length). A test asserts it reproduces `peaks()`
*exactly* at four lengths. **Do not "simplify" it to store only maxima** —
that is the 77% version; summed support is what reaches 90%, and there is a
test guarding it.

**Shadow log** — Stage 2's shadow half. Every hazard-mode retrieval records
both rankings plus top-5 agreement, so the "anchor space doesn't retrieve
better" claim stops resting on eighteen chunks. `observe()` returns `None`
by construction; a regression asserts retrieval is identical with the module
present and absent (Risk #4, as a test). Digests only, never text.

**Capsule descriptions** — `build --describe` / `describe`, read without
decoding. Opt-in, never automatic, and **outside the SHA gate** — a test
edits a stored description and asserts extraction still succeeds.

**`tools/source_capsules.py`** — the source tree cut along meaning rather
than size. 15 capsules over 184 files, each describing itself from its
modules' own docstrings. Coverage asserted: a test removes a subsystem and
proves the build refuses.

**`PRIVACY.md`** gained a section on risks specific to image files: a
capsule looks like an image and is forwarded like one, it is not
encryption, its description is cleartext, re-encoding destroys it silently.

## 5. Research findings

**A token trajectory is a cluster, not a curve.** Measured on live traces:
a polynomial in *t* buys **+0.0043** mean cosine over the pooled vector at
twice the storage, +0.0092 at three times. Degree 0 *is* the pooled vector
and already scores 0.8733. Fitting curves to trajectories is refuted.

This agrees with `spread`: effective rank **1.694** out of 39 for the same
text. A path confined to under two effective directions is a blob, and a
blob is described by its centroid.

**Consequence:** the trail works *because* it records discrete events
rather than shape. Compressed sensing remains viable — it exploits
sparsity, not smoothness, and the 1-sparse-per-token result is untouched.

**A sinusoidal basis beats a polynomial one** at every parameter count —
0.9522 against 0.9243 at 21 params/dim. But the matched-capacity **random
control** reaches 0.9419, beating polynomials outright, so most of any
basis's gain is parameter count rather than structure found. Fourier's
genuine edge over random is about +0.010.

**Open hypothesis, untested:** that residual edge may be
positional-encoding structure rather than meaning. If so it should be
subtracted from traces, not modelled. Test: whether the edge is similar
across unrelated texts of equal length.

**The right name for the trail is a sufficient statistic** — it carries
everything relevant to the `peaks()` readout, which is why it reproduces it
exactly and why the compression ratio is beside the point. The cluster
finding is a re-measurement of published **anisotropy / representation
degeneration** work; verify citations before they enter the notes.

**Now written down** in `docs/VECTOR_TRANSLATION_RESEARCH.md` §5b, next to
the other refuted fixes: the polynomial refutation with its degree-0
control, the three-basis comparison, the positional-encoding hypothesis,
and the sufficient-statistic framing. Anisotropy citations were left out on
purpose — the substance is confirmed on this stack, the papers were
recalled rather than checked, and that document does not carry references
it has not verified. Add them once someone has.

## 6. Deliberately not done

- **Stage 2's other half** (describing recalls in anchor space) and any
  promotion of anchor space to primary retrieval. Still gated behind the
  labelled corpus exactly as `MACHINESPIRIT_PRIMARY_PLAN.md` says.
- **A machinespirit profile inside capsule metadata.** The description
  hook exists and takes caller-supplied text; wiring an anchor profile into
  it would need the pooled server at packaging time.

## 7. Guardrails not to widen

- `observe()` in `machinespirit_shadow` returns `None` **by design**. There
  is deliberately no value for anything to start ranking with.
- The trail stores support *and* peak. Support is load-bearing.
- The capsule description is opt-in and unverified. Both properties are
  tested; neither is decoration.
- `machinesoul.py` must stay stdlib and standalone — it ships as the
  published decompiler. The description text is passed *in*; the module
  holds no opinion about meaning, which is the line separating it from
  machinespirit.
- Retrieval is untouched, and a regression pins it.
- Tutorial lesson sets resolve at call time, never through a frozen map.
- `calibrate` reports drift; it never adjusts anything to make drift go
  away. If a row moves, the instrument moved.
- Compressed sensing remains the one surviving compression candidate —
  it exploits sparsity rather than smoothness, so nothing measured this
  session touches it.

## 8. Order for the cut

1. commit nothing — the tree is clean and pushed at `6c8f1b0`
2. `python tools/package_release.py` — rebuild the 13 GB stage
3. rebuild the research capsule (docs changed)
4. **refresh `extractor/machinesoul.py`** (§2)
5. replan Windows, render the map, review it, approve the new hash
6. cut both, reassemble, verify
7. regenerate `SHA256SUMS.txt` and `CAPSULE_CONTENTS.txt` last
8. upload **every** asset `RELEASE_BODY.md` names — that mismatch is what
   made the old runbook wrong

Full commands in `SABLERESEARCHA/UPLOAD.md`.
