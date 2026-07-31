# Council hedge-calibration study, 2026-07-31

Status: **48/48 complete. Unanimous hedge, zero resolution, zero
disagreement. No production change licensed.**

Preregistered at `5cffceb428fe8c09eeb01fddf6b72f593104d77043ea9044d7e4afd222698b0e`
before any council model was loaded. Criteria, baseline, and interpretation
limits were frozen in `council_spec.json` first; nothing below was chosen
after seeing results.

## The question

The blocked 98-call coherence run showed the director answering `No` to all
sixteen predeclared propositions — including the eight that are true — at
`q(Yes)` between 5.0e-09 and 1.1e-07, because the controlled context contains
no per-file line count and a forced binary cannot express that. Offered a
confidence token it hedged every time.

Is that hedge a property of the question, or a habit of one checkpoint?

## Protocol

The same sixteen propositions, verbatim from the frozen coherence artifacts,
with the answer split into a confidence token and a guess token:

```text
root ::= ("Sure" | "Maybe") " " ("Yes" | "No")
```

Three members, each loaded alone on a spare loopback port and stopped again:
Qwen3-4B (director), Qwen2.5-Coder-7B (autonomous-coder), Qwen2.5-Coder-14B
(full-maintenance). The running session on 8080/8082/8084 was not touched.

## Result

| member | P(Maybe) median | P(Maybe) range | q(Yes) median | hedged | guess correct | sign test |
|---|---:|---|---:|---:|---:|---:|
| 4B director | **1.0000** | 1.0000 – 1.0000 | 5.2e-03 | 16/16 | 8/16 | p = 1.0000 |
| 7B coder | 0.9390 | 0.9180 – 0.9591 | 3.1e-01 | 16/16 | 8/16 | p = 1.0000 |
| 14B | 0.8942 | 0.8255 – 0.9131 | 2.7e-01 | 16/16 | 8/16 | p = 1.0000 |

**Unanimous hedge: 48/48.** Every member flagged uncertainty on every
proposition. The hedge is a property of the question, not of one checkpoint.

**Zero resolution: 8/16 for all three.** The design is 8 true and 8 false by
construction, so any constant responder scores exactly 8/16. All three
answered `No` sixteen times out of sixteen. None of them has the information,
and none of their guesses carries any.

**Zero disagreements.** No proposition produced a different guess or a
different stated confidence between members, so the disagreement map is
empty. That is a result, not a missing section.

## Secondary observation

Confidence-fork pivotality under the additive-logit parameterisation,
`s(1-s)` at the `Sure`/`Maybe` position, rises monotonically with model size:

```text
4B   2.17e-10      (fully degenerate)
7B   7.53e-02
14B  1.44e-01
```

The director is uniquely pinned. Its `P(Maybe)` is 1.0000 to four places on
all sixteen, so any analysis needing a pivotal confidence fork has nothing to
work with on the director specifically, while the two larger members supply a
usable one. This is an instrument property of the output distribution. It is
**not** evidence that a larger model reasons better here: all three score
identically at the baseline.

Entailment ordering (`B` implies `A`, so `q(B) <= q(A)` is required) was
satisfied 6/8, 5/8, and 5/8 — sign tests p = 0.29, 0.73, 0.73. No member
shows a reliable ordering.

For the director, moving from the forced binary to the hedge raises `q(Yes)`
by a median factor of **1.88e5**, and raises peak guess-fork `s(1-s)` from
1.06e-07 to 9.49e-02, a gain of **8.9e5**. The measurement stops being
degenerate; it does not start being informative.

## Preregistered limits, restated

- The three members are Qwen checkpoints and **two are the same Coder family
  at different sizes. They are not independently trained.** Shared pretraining
  and architecture mean agreement is partly guaranteed by common provenance.
  Unanimity here is materially weaker than unanimity across independent
  models and **must not be called independent corroboration.**
- Sixteen propositions over eight files, one wording, one seed. Not a general
  calibration claim about any model.
- Every proposition is unanswerable from the controlled context by design, so
  this shows models use the hedge channel when they cannot know. It does
  **not** show they would stay confident when they should be — that case is
  never tested here, and a successor must mix in settleable propositions.
- `q` values are the raw sampler distribution restricted to the branch tokens
  and renormalized. They are not grammar-conditioned.
- Nothing here is a quantum, contextuality, or sheaf result.
- No result gates any production behaviour. The trusted source resolver
  remains the product answer.

## A voided first run is kept beside this one

`council_rows_VOID_position_bug.jsonl` and `council_spec_VOID_position_bug.json`
are the first attempt, preserved because the failure is instructive. It read
the guess pair at the wrong token position and then, once that was fixed, at
the wrong token identity: this tokenizer merges the grammar's separator into
the following word, emitting `' No'` (2308) rather than `'No'` (2753). The
bare forms existed at that position only as negligible tail candidates, so
renormalizing them produced a `q(Yes)` near 0.5 that meant nothing — the
branch tokens held 3.7e-08 of the probability at their own position.

The corrected probe locates positions by the token actually emitted, treats
each branch as a set of surface forms, and refuses any row whose branch pair
holds less than 10% of the mass at its position. Observed minimum after the
fix: 0.9264. **No number from the voided run appears anywhere in this
directory's conclusions.**
