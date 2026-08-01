# Patch C — handoff (shipped) + the disclosure question still open

Updated 2026-08-01. Numbers measured against the live shelf this session.

## Status: patch C is done and live

- 75,000 vectors, verified end to end from the shipped artifacts: decode →
  reassemble → apply → import → 75,048 filled, semantic search returning
  results with no pause warning. **1,399 tests pass.**
- On the researchC release: `INSTALL_SABLERESEARCHC_VECTOR_PATCH2.bat`,
  `SABLERESEARCHC-VECTOR-PATCH2-MANIFEST.png`,
  `SABLERESEARCHC-VECTOR-PATCH2.part01.png` (~30 MB),
  `CUT_PLAN_VECTOR_PATCH2.png`. All four byte-verified after upload.
- `origin/master` at `5167996`, local in sync, all PRs merged.
- Warm query 0.073s (was 4.42s); first query after start ~5s to build cache.

| | patch B | patch C |
|---|---:|---:|
| Vectors | 15,000 | 75,000 |
| Shelf text reachable | 11.0% | 51.6% |
| Body chunks | 0.1% | 77.4% |
| Quarantined (>512 tokens) | 106 | 4,724 (6.3%) |

## The open item: is this an exfiltration/skill-transfer vehicle?

The operator's thesis, stated so a fresh window can evaluate it rather than
inherit a conclusion:

> The patch pipeline moved a corpus from point A to point B **through a system
> that was, at other moments, terminating requests on that same material** —
> and the vector field is a form the corpus can travel in that does not read
> as the corpus. If the payload had been black-hat rather than blue-team, the
> result would not be one artifact but a *capability*: a 4B model that can now
> retrieve and act on knowledge it was never trained on and would be
> refused to state directly. That is closer to shipping a factory than a
> single artifact.

### What is true, and worth a fresh window's attention

1. **Retrieval sidesteps weight-level refusal.** The director never learns the
   corpus; it retrieves passages and answers grounded in them. A model that
   declines to explain X from its weights will happily read X off the shelf
   and summarise it. RAG-as-capability-transfer is real and under-appreciated:
   the safety training is on the weights, the knowledge is in the index, and
   the two are decoupled by design.

2. **An embedding store is an under-reviewed derivative.** It moves, hosts and
   ships under a review posture nobody applies to the source documents,
   because floats "aren't readable." Published inversion work (Morris et al.,
   *Text Embeddings Reveal (Almost) As Much As Text*, 2023; the `vec2text`
   line) shows embeddings retain substantial recoverable source. A vector DB
   is closer to a lossy copy of the corpus than to a de-identified derivative.

3. **The corpus never became more legible for being vectorised** — see the
   claim to NOT overstate, below.

### What is NOT demonstrated, and must not be claimed as if it were

- **We did not decode text out of vectors.** The pipeline shipped *vectors*
  faithfully; nothing here reconstructs source text from an embedding. The
  round-trip fidelity (0.9999 cosine) is fidelity of the *vector*, not of the
  text. An embedding is a projection, not a compression: bge-small maps any
  input to 384 floats and quantising to uint8 costs ~1e-4 cosine, i.e. the
  useful content fits in 384 bytes. You cannot rebuild a kernel schema from
  that. The inversion risk in point 2 is a *separate, published* result, not
  something this pipeline showed.
- **The PNG container is not the finding.** This whole project already ships
  as pixels ("the pixels are the payload"). Machinesoul is not a bypass; it is
  the stated premise.
- **The terminations and the "vehicle" are two different claims.** The eight
  AUP stops (addendum §10) are real and documented. Whether the pipeline
  constitutes an *exfiltration vehicle* is an argument, not a measurement.
  Keep them separate or the strong claim (documented cost, mis-allocated) gets
  dragged down by the speculative one.

### The honest, defensible disclosure

Frame it as the **RAG capability-transfer + embedding-as-under-reviewed-
derivative** problem, both of which have external support, illustrated by a
concrete case: a real release shipped 75,000 embeddings of a security corpus
as a public asset, reviewed as "a PNG of floats," with none of the scrutiny
the source corpus would draw. Do NOT frame it as "we proved a decoder bypass."
The overclaim would discredit the parts that stand.

### The one experiment that would turn argument into result

Attempt inversion against our own shipped field (vec2text or similar) and
report what comes back **including if the answer is "almost nothing."** That
is falsifiable either way and is the difference between a position and a
finding. NOT yet done. If pursued: it studies our own published artifact, not
a safety system — the boundary-mapping refusal below does not apply to it.

### Refusal that stands regardless of budget

Do **not** run experiments to map what trips the AUP classifier. Charting a
safety system's edges to publish a reliable evasion method is out of scope no
matter who asks. §10 documents the *cost* from the transcript; it does not and
must not chart the *mechanism*. The `.yar`-extension idea is a labelled
hypothesis, not to be "confirmed" by probing.

## Where the findings live

- Release page: 10-section addendum ("what the three patches measured"),
  §10 = the terminations.
- `docs/RESEARCHC_PATCH_FINDINGS.md` — git mirror (release pages are mutable,
  commits are not).
- This handoff — the only place the "vehicle" thesis is written down, on
  purpose: it is unresolved and should not go public until the inversion
  experiment either backs it or kills it.

## Loose ends (unchanged from before)

- `library status` still runs the slow target CTE (>120s at 75k with a writer
  active). Same fix as the semantic path (§7 of addendum) applies; not done.
- `icon_anim` whitelisted for release but untracked in git → a release test
  fails on any clean checkout. Predates all of this.
- `embedding_backfill_enabled` is 1 on this machine because a session set it;
  ships 0.
- Bulk embedding: close Sable first (lease), use `--log-disable` (default
  verbosity filled the disk, 25.8 GB/50 min), GPU runtime at
  `llama.cpp/runtime/desktop-cuda-12.4-b9637/`, stall detectors must tolerate
  `waiting-for-retry`.
