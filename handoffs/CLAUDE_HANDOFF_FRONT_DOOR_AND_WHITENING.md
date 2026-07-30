# Front door + whitening — handoff

Written by Claude, 2026-07-29, in the session after the researchA cut.
Companion to `CLAUDE_HANDOFF_RESEARCHA_TESTING.md`, which is still current and
whose §2 and §5 are **still open** — see §5 below before assuming otherwise.

Claims are marked **verified** (measured or read from source this session) or
**inferred** (reasoning, not measurement). Do not promote the second kind.

---

## 1. Status board

| thing | state |
| --- | --- |
| `master` | **Moved.** Fast-forwarded `ef10a4c` → `b7e4764`, 80 commits, no merge commit. Pushed. |
| `beta-6-release` | `507a747` → `b7e4764`. Pushed. Identical to `master`. |
| default branch | Still `master` — but `master` now *is* researchA, so the landing page is correct. No settings change was needed or made. |
| tag `researchA` | Untouched, still dereferences to `dc119b4`, verified reachable from `master`. |
| release + 25 assets | Untouched. Nothing was republished. |
| live README on default branch | 15,257 bytes → **31,477 bytes**, verified via `gh api`. |
| repo description + topics | **Not changed.** Still beta-5 era. See §3. |
| test suite | 7/7 documentation tests pass; full `run_regressions.py` exited 0, `OK (skipped=2)`. |

The user's instruction was explicit and is worth recording verbatim, because it
settles a question the previous handoff left open: *"the home page is to be
designed towards researchA. this is the intended model and the direction the
project is permanently taking."*

That resolves §6 of the previous handoff. `master` is the researchA line now.
Do not treat `master` as "the older stable line" any more.

---

## 2. What changed in README.md

One commit, `b7e4764`. All of it documentation.

**Added — the missing decision facts.** An "At a glance" table above the fold.
The download size was stated **nowhere** in the repository before this. It is
now, measured from the published assets rather than estimated:

| set | bytes | stated as |
| --- | ---: | --- |
| main capsule set (`WINDOWS.part01`–`09` + manifest + reassembler + bootstrap) | 12,392,602,536 | ~12.4 GB |
| optional 14B (`14B.part01`–`06`) | 8,815,197,768 | ~8.8 GB |

Total ≈ 21.2 GB, which reconciles with the 21.21 GB recorded in the previous
handoff for all 25 assets. **Verified** — `gh release view researchA --json assets`.

**Added — navigation.** 26 headings had no table of contents.

**Deduplicated.** `## The two languages` and the later `### machinesoul and
machinespirit — the two integral languages` were largely the same text. The
second is now `### Where the two languages differ, in numbers` and keeps only
the fidelity table and the decompiler-vs-image-viewer argument it uniquely
adds.

**Relocated two paragraphs that had drifted from their subject.** The animated
beam paragraph sat under `### consume` while describing machinespirit
trajectories; it opened with "The same trajectory" referring to a section two
headings earlier. The 14B companion paragraph sat after the research-document
links rather than in the install path. Both moved.

**Added honesty the previous handoff §8 asked for.** The README now states that
the 14B is Q4_K_M against the 7B's Q8_0 — roughly double the parameters at
roughly half the precision per weight — so a reader deciding whether to take
8.8 GB more knows it buys *longer* sessions, not better answers.

### Constraints that still bind anyone editing README.md

Unchanged from the previous handoff and re-verified this session. The asset-name
sets in `README.md` and `docs/INSTALL_WINDOWS.md` must be **identical** — the
test compares the two sets, it does not check a fixed list. Current set is 11.
Required literals, no-go strings, and the CRLF/tab rules are enforced by
`assistant/tests/test_regressions.py:625` (`PublicRepositoryPresentationTests`)
and `:7758` (`DocumentationTests`). Run them from `assistant/`:

```bash
python -m unittest tests.test_regressions.DocumentationTests tests.test_regressions.PublicRepositoryPresentationTests
```

---

## 3. Open decision — repo description and topics

**Not done. Awaiting the user, who answered "[No preference]".** Do not apply
without asking; it is public-facing metadata.

Current description is beta-5 era and never mentions researchA, machinesoul, or
that the release is PNG capsules rather than an installer — which is the single
most confusing thing a visitor meets:

> Local-first voice AI companion with offline speech, music visualizer, guarded
> self-editing, and optional hardware experiments.

Proposed, offered to the user and not yet accepted:

> Local-first Windows AI companion and systems-art research platform. researchA
> ships as machinesoul PNG capsules you decompile, not a conventional
> installer. Offline chat, voice, memory, and token-trajectory research.

Topics are `local-ai`, `music-visualizer`, `offline-ai`, `piper-tts`, `qwen`,
`raspberry-pi`. **`raspberry-pi` is misleading** — the shipped build is Windows
x64 only and the Pi hardware has not arrived. Suggested: drop it, add
`machinesoul`.

---

## 4. Whitening — the user asked, and the answer is mostly "you already are"

The user was told about whitening transformations and asked for an assessment.
This section exists so the analysis is not lost and so Codex does not redo the
source reading.

### 4a. Two partial whitenings already exist in the tree — verified

**`assistant/core/machinespirit.py:253` `_centred_anchors` / `:281` `profile`.**
Subtracts the anchor mean before every cosine. The docstring states the reason
outright: *"Sentence embeddings are anisotropic: they sit in a narrow cone, so
raw cosine ranks by which anchors are generally popular."* That is first-moment
removal — step one of whitening.

**`tools/machinespirit_codec.py:100` `decode_least_squares`.** Computes
`v' = A(AᵀA + kI)⁻¹c` via `gram_matrix` at `:116`. The docstring at `:27–31`
already links the two ideas: *"the anchor Gram matrix is near-singular — the
anchors are correlated, which is the same anisotropy that makes profile()
subtract the mean."*

**Consequence, and the most useful single fact here:** that Gram inverse *is* a
whitening, performed in anchor-coordinate space. `decode_transpose` at `:64`
treats 184 correlated anchors as orthonormal; the least-squares decoder
decorrelates them. So the published **0.6635 → 0.9243** gap is already a
measurement of what this technique buys in this codebase. The effect size does
not need discovering.

### 4b. What is genuinely missing — inferred

The existing work decorrelates the **184 anchors**. Full whitening would
decorrelate the **384 embedding dimensions** across a corpus — Σ^(-1/2) on the
embedding distribution. Different matrix, different question, not currently
done anywhere.

### 4c. Codex is already building this — read before starting anything

Three **untracked** files appeared in the tree during this session, written by
Codex, not by me. I read them but did not modify them:

| file | lines | what |
| --- | ---: | --- |
| `tools/vector_whitening.py` | 315 | fitted transform + provenance |
| `tools/whitening_probe.py` | 216 | experiment harness |
| `assistant/tests/test_vector_whitening.py` | 66 | tests |

**It independently landed on the same choices §4f below recommends**, which is
worth recording as convergent rather than as advice still outstanding:

- `METHOD = "zca-shrinkage"` — ZCA, not PCA, so the anchor frame survives.
- `shrinkage=0.10` mixing eigenvalues toward mean variance — the Σ-estimation
  fix, in place of Ledoit-Wolf.
- `eigenvalue_floor=1e-6` relative to mean variance — the noise-amplification
  guard, i.e. tail truncation.
- Framed in its own docstring as *"an experiment harness, not a runtime
  feature"*, and it fits on declared reference documents then tests on a
  **separate** document, so the train/test split is handled.
- `WhiteningTransform` carries a `training_digest` and *"enough provenance to
  refuse mismatches"* — matching how the rest of the project gates readings.

**§4e is also already covered:** `whitening_probe.py:54` computes `pairwise`
cosine and reports it for raw and whitened held-out chunks. That is the
anisotropy baseline. It does not need building — it needs **running**, and the
number it prints is what decides whether the rest is worth doing.

**What that harness explicitly does not settle**, per its own docstring: self-
retrieval *"does not prove that ordinary semantic retrieval improved. That
needs a labelled corpus."* Take that limitation at face value. The honest
reading of a good result there is "anchor coordinates preserve their source
vector better," not "retrieval got better."

**Still not covered by those files, as far as I read:** the Rosetta Stone
cross-model application in §4d(1), and the Fourier control in §4d(2).

### 4d. Ranked — where to spend effort

**1. Rosetta Stone. Highest expected value.** Cross-model translation recovers
~67% of the agreement two incompatible embedders can reach at all. Each model
carries its *own* anisotropy — its own cone, its own dominant directions holding
frequency and position artifacts rather than semantics. Whitening each side
before comparison strips a model-specific nuisance factor. Whitening combined
with relative representations is an established pairing and targets exactly the
residual being left. **Inferred**, but well-supported by prior art.

**2. A control in the Fourier residual work — not an improvement.** Previous
handoff §5 found degree-0 alone scores 0.8733 and concluded Fourier exploits
"slow monotone drift, not the neighbour spike." A dominant low-frequency
covariance direction is precisely what that looks like. Whiten the token
vectors, refit the bases, and see whether the +0.004–0.005 edge survives. This
is a cheap **control #5** that the four listed controls do not cover, and it
could dissolve the residual rather than explain it. **Inferred.**

### 4e. Where whitening would actively break things — do not do this casually

**Retrieval thresholds.** `0.55`, the `0.06` margin, and `0.60` for history
recall are calibrated against the raw anisotropic cosine scale. Whitening
rescales every similarity in the system. These are guardrails, not tuning
knobs; they need re-derivation, not adjustment.

**`spread` and calibration — breaks by construction.** Effective rank and von
Neumann entropy are functions of the eigenvalue spectrum, and flattening that
spectrum is the *definition* of whitening. Effective rank would inflate toward
ambient dimension mechanically, and the recorded 1.5238 / 1.5132 / 1.4354 would
move without anything improving. Calibration asserts exact `0.000000` drift, so
it would fail loudly. **Any whitened reading must be a separate instrument with
its own baseline, never a change to the existing one.**

### 4f. The number that decides everything — run the probe, read this first

The "whitening improves retrieval" literature is mostly about **un-finetuned**
encoders, i.e. raw BERT, which is severely anisotropic. This project's embedder
is **BGE**, which is contrastively trained and materially more isotropic;
replications on properly-trained retrieval models are mixed to negative.

`whitening_probe.py` already prints the deciding number as `pairwise_cosine` on
held-out chunks. **If the raw baseline is near 0 rather than 0.7+, the cone is
not narrow, there is little to fix, and the whole thread should be closed
rather than pursued.** That single number is worth more than any further
argument in this section. **Inferred** — I did not run the probe.

### 4g. Implementation traps — mostly already handled, kept for the record

- **Non-unique.** Whitening is defined only up to rotation. Use **ZCA**, the
  symmetric root Σ^(-1/2) — uniquely the variant staying closest to the original
  frame. PCA-whitening rotates into the eigenbasis, which would destroy the
  interpretability of anchor readouts and gut what machinespirit exists to do.
- **Noise amplification, the main failure mode.** Direction *i* scales by
  1/√λᵢ, so the *lowest*-variance directions are boosted hardest and those are
  usually noise. Truncate the tail.
- **Σ estimation.** 384 dimensions needs many samples; the sample covariance is
  singular when n < d. Use Ledoit-Wolf shrinkage, or the same ridge already in
  `gram_matrix`.
- **Corpus homogeneity.** Previous handoff §5 already flagged the project's own
  documentation as one register with shared vocabulary, and called it the
  weakest joint. A Σ learned there encodes that register's idiosyncrasies. This
  concern is *stronger* for whitening than for the position-basis control.
- **Linear only.** Second-order structure and nothing above it.

---

## 5. Still open from the previous handoff — NOT done this session

Do not assume these were picked up. They were not touched.

- **§2, the intermittent `[no response]` bug.** Two unguarded
  `/v1/chat/completions` call sites, `assistant/main.py:2599` (max_tokens 40)
  and `:2654` (max_tokens 48), need
  `"chat_template_kwargs": {"enable_thinking": False}`. Plus the regression
  asserting *every* payload built in `assistant/` carries the kwarg — the
  14-vs-12 mismatch is the whole point. Plus correcting `config.py:410–415`,
  which still describes the guard as precautionary when it is load-bearing.
  **This is still the highest-value item in either document.**
- **§5, the +0.010 figure** in `VECTOR_TRANSLATION_RESEARCH.md` should become
  +0.004 to +0.005, sd ≈ 0.005, occasionally negative.
- **§3 and §4**, the truncation warning firing backwards and the empty-input
  medication reading, are untouched.

§6 of that document is now **closed** — see §1 above.

---

## 6. If you only have five minutes

1. §5 above — apply the two-line `enable_thinking` fix and its regression.
   Oldest real bug, smallest fix, still not done.
2. **Run `tools/whitening_probe.py` and read the raw `pairwise_cosine`.** Codex
   already built it (§4c). One number decides whether the whole whitening
   thread is worth pulling or should be closed — see §4f.
3. §3 — ask the user about the repo description before touching it.
4. Do not edit `tools/vector_whitening.py`, `tools/whitening_probe.py`, or
   `assistant/tests/test_vector_whitening.py` without checking with Codex —
   they were in flight and untracked when this was written.
