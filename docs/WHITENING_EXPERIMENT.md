# Whitening experiment — anisotropy is not a licence to change retrieval

This document records the 2026-07-29 whitening experiment prompted by an
external suggestion.  Whitening is a standard linear transformation, not a
new researchA claim: for a reference mean `mu` and covariance `Sigma`, a
transformed vector is `Sigma^(-1/2) (x - mu)`.  Its purpose here was to test
whether the measured narrow embedding cone was removable nuisance geometry
or useful signal.

## What was implemented

`tools/vector_whitening.py` introduces `SABLEWHITE1`, an opt-in regularised
ZCA transform.  It is deliberately outside the ordinary memory and
machinespirit paths.  A transform records and hashes:

- the source-vector digest and sample count;
- dimension, shrinkage and eigenvalue floor;
- model and pooling metadata supplied by the caller; and
- the exact mean and symmetric transform matrix.

The transform refuses malformed/non-finite matrices, wrong dimensions,
tampered digests, or compatibility metadata that differs from the recorded
model/reference identity.  It never overwrites raw vectors.  Every
vector being compared — anchors, queries and candidates — must receive the
same model-bound transform before an L2-normalised cosine is meaningful.

Regularisation is mandatory for this project.  The BGE space has 384
dimensions while the declared public fit corpus has fewer independent samples
than that.  An ordinary inverse covariance would contain zero-variance
directions and turn noise into arbitrarily large coordinates.  Shrinkage
moves eigenvalues toward the average variance; the floor is a second refusal
against nearly-null directions.

`tools/whitening_probe.py` then fits only on named public documentation and
evaluates a separate held-out public document.  It reports geometry and
least-squares anchor reconstruction.  It explicitly does **not** claim a
retrieval improvement: that requires a labelled relevance corpus, which the
project does not yet have.

## Baseline

Before the experiment, the complete suite ran clean at **925 passing tests,
2 expected skips**.  The skips are Windows link-permission tests unavailable
to this account.

## Live measurements

All figures below came from the local `bge-small-en-v1.5-q8_0` mean-pooled
server.  The tested model identity was
`sha256:ec38e8da142596baa913124ae50550de284b6916bf59577ef2f0cb9660c2f514:pooling:mean`.

The main fit used 212 public chunks from:

- `docs/THE_STORY_OF_SABLE.md`
- `docs/VECTOR_TRANSLATION_RESEARCH.md`
- `docs/VECTOR_PIXEL_RESEARCH.md`
- `docs/SEMANTIC_AND_AGENT_BRIDGES.md`
- `docs/CAPABILITIES_AND_LIMITS.md`

It evaluated 34 held-out chunks from
`docs/RESEARCHA_PRE_RELEASE_SESSION_2026-07-29.md`.

| shrinkage | raw mean reconstruction cosine | whitened | raw / whitened recovered@1 |
| ---: | ---: | ---: | --- |
| 0.02 | 0.9157 | 0.9015 | 100% / 100% |
| 0.10 | 0.9157 | 0.8201 | 100% / 100% |
| 0.30 | 0.9157 | 0.7726 | 100% / 100% |
| 0.60 | 0.9157 | 0.7622 | 100% / 100% |

Whitening did do what its mathematics predicts: held-out mean pairwise cosine
fell from `+0.5462` to approximately `+0.012` through `+0.020`, so the common
direction was substantially removed.  That is a geometry result, not an
application result.

The least aggressive setting, 0.02, was then checked on two independent
held-out documents:

| test document | raw cosine | whitened cosine | change |
| --- | ---: | ---: | ---: |
| `ARCHITECTURE.md` (20 chunks) | 0.9026 | 0.9072 | +0.0046 |
| `RELEASE_NOTES_researchA.md` (48 chunks) | 0.9125 | 0.9041 | -0.0084 |

Both preserved 100% self-retrieval at rank one.  That ceiling makes the
metric insensitive, while the sign change shows no stable held-out gain.

An earlier deliberately under-sampled fit — only 18 chunks — reduced held-out
reconstruction from 0.9026 to 0.8335 at shrinkage 0.10.  This is why a
reference-corpus digest, shrinkage declaration and held-out evaluation are
load-bearing rather than bookkeeping.

## Decision

**Do not change ordinary retrieval, machinespirit profiles, calibration, or
the published researchA capsule.  No release patch is warranted.**

Whitening unquestionably changes the covariance geometry, but the current
measurements do not establish a consistent practical benefit.  Installing it
as a default would change every score and calibration reading by construction
while risking loss of anchor reconstruction.  The release must not treat
flatter geometry as better semantics.

This also does not overturn the earlier trajectory experiment in
`VECTOR_TRANSLATION_RESEARCH.md`: subtracting each trajectory's own mean,
then whitening, scored only 3% top-1 on the labelled paraphrase set because
the trajectory mean is the sentence topic.  Corpus whitening is a different
operation, but that result is a warning against applying either transform to
token paths without a separately measured task.

## What would justify reconsideration

Build the labelled retrieval corpus already named in
`docs/MACHINESPIRIT_PRIMARY_PLAN.md`, then freeze a public train/validation
split before tuning shrinkage.  Compare raw, mean-centred, diagonal scaling,
and regularised ZCA whitening on the same held-out relevance labels.  Bind the
winning transform to model identity, quantisation, pooling, anchor digest and
fit-corpus digest; generate a separate calibration record rather than
rewriting the existing one.
