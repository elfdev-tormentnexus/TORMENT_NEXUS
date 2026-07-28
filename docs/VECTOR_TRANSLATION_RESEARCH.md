# Cross-model vector translation and token trajectories

Companion to [Vector-to-pixel encoding](VECTOR_PIXEL_RESEARCH.md), which
covers containers and quantisation. This document covers two later
questions: whether two models that share no vector space can be made to
compare vectors at all, and whether the path a sentence traces before
pooling is worth keeping.

Everything below was measured on this machine against this stack on
2026-07-28. Where something was computed rather than run, or run at a scale
too small to carry a claim, it says so.

## Reproduction environment

| | |
| --- | --- |
| Embedder A | `bge-small-en-v1.5-q8_0.gguf`, 384 dims, mean pooling, `sha256:ec38e8da142596baa913124ae50550de284b6916bf59577ef2f0cb9660c2f514` |
| Embedder B | `nomic-embed-text-v1.5.Q8_0.gguf`, 768 dims, mean pooling, 146,146,432 bytes |
| Server | `llama-server` with `--embedding`, `-c 512`, `-ub 512`, `-ngl 0`, `-t 2` |
| Unpooled route | llama.cpp's native `/embeddings`; the OpenAI-compatible `/v1/embeddings` refuses `--pooling none` with HTTP 400 |
| Tools | `tools/rosetta_stone.py`, `tools/vector_beam.py` |

Changing the model, quantisation or pooling invalidates every figure here.

---

## 1. Prior art, stated first

Neither technique below is ours.

**Relative representations** — Moschella, Maiorca, Crisostomi, Ricciardi,
Locatello, Rodolà, *Relative representations enable zero-shot latent space
communication*, ICLR 2023. Represent each vector by its similarities to a
shared anchor set rather than by its own coordinates.

**Learned linear alignment** — the older alternative. Mikolov, Le, Sutskever
2013; Conneau, Lample, Ranzato, Denoyer, Jégou 2017 for the cross-lingual
case. Fits a map per model pair from paired data; works, but requires the
pairing and the fitting.

**Late interaction** — Khattab and Zaharia, *ColBERT*, SIGIR 2020. Keep
per-token vectors and score with MaxSim rather than comparing pooled
vectors.

The contribution here is measurement at one project's real scale, with
negative results kept.

---

## 2. Why a container cannot solve this

Dimension 7 in one model has no relationship to dimension 7 in another, and
equal dimensionality does not imply comparable meaning. Cosine between
vectors from two models is noise, not degraded signal.

A serialisation format transports numbers faithfully and says nothing about
what they mean, so writing two models' vectors into the same container
makes them equally readable and no more mutually intelligible. This was
worth establishing before building anything, because the container is the
intuitive place to look for a fix and it is the wrong place.

Related defect, recorded in the companion document: `SABLEVEC1` stores
`dims`, `count`, `scale`, `low` and `layout`, and no model identity. The
project's own runtime is stricter than its container — `model_identity()`
keys the embedding cache so a swapped embedder cannot silently leave old
geometry behind — so the container is the one place that discipline lapses.

---

## 3. Anchor translation, measured

`tools/rosetta_stone.py`. Both models embed an identical ordered anchor
list; every vector is re-expressed as its cosine to each anchor.

**Anchor set:** 122 general-domain texts, digest `b5421687348e956e`, plus a
16-entry project block under a separate digest so an outside agent holding
none of the project's material can use the core alone.

**Corpus:** ~180 paragraph chunks from six project documents, truncated to
800 characters so both models see identical inputs within the 512-token
context.

Top-10 neighbour agreement between the two models:

| | Agreement |
| --- | --- |
| chance | 0.056 |
| **translated into anchor space** | **0.370** |
| each model's native neighbours | 0.549 |

The third row is a ceiling, not a competitor: it is how much the two models
agree with each other at all, obtained by comparing their own neighbour
lists by index. No translation can exceed it.

**Result: translation recovers 67% of the achievable ceiling at 6.6×
chance.**

Within-model fidelity, Spearman correlation between absolute cosine and
relative cosine over all pairs:

| Model | Spearman |
| --- | --- |
| bge-small (384d) | +0.737 |
| nomic-embed (768d) | +0.667 |

Different dimensionality was chosen deliberately. Two 384-dim models could
be accused of accidental compatibility; 384 against 768 cannot be compared
at all without translation, so there is no baseline to confuse it with.

### Scale caution

An earlier run on a 20-chunk corpus at k=5 gave 0.610 translated against a
0.680 ceiling — 90% of ceiling, far rosier. With n=20, chance alone is
0.263. **The 20-chunk figure should not be quoted.** It is recorded here
only because the discrepancy is the point: small-corpus retrieval metrics
flatter themselves.

### What it costs

- Dimensionality becomes the anchor count.
- Anchors must span the domain of use; anchors drawn from one subject give
  a distorted account of another.
- It is an approximation, not an isomorphism. A third of the reachable
  agreement is lost.
- Quantising a relative representation is a second lossy step on top of the
  first, and the two have not been measured together.

### Refusal semantics

Two stones built on different anchor lists describe different coordinate
systems, and comparing them returns a plausible-looking similarity rather
than an error. `check_compatible` raises `AnchorMismatch` instead. The
guard was verified by reinstating the defect — replacing the digest
comparison with a permanently false condition — and confirming mismatched
stones then compare without complaint.

Anchor order is part of the coordinate system, and the digest is computed
over NUL-separated texts so that `["ab","c"]` and `["a","bc"]` cannot
collide.

---

## 4. Anchor profiles as a readout

Once a vector is in anchor space it is N numbers against named English
sentences, which is legible to a person, to the operator, and to any model
that can read — with no embedder and no shared weights.

Example, `bge-small`, project block enabled, mean-vector centred:

```text
"I keep thinking about something my grandmother said before she died."
  +0.478  grandparents telling the same story again
  +0.317  the moment before a difficult conversation
  +0.316  a promise made to a dying person
  +0.310  grief arriving months later
```

### Anisotropy, and a fix that was not one

Sentence embeddings occupy a narrow cone, so raw cosine scores cluster near
0.5 against everything and rank by which anchors are generally popular
rather than by subject.

The first correction attempted was standardising each vector's scores
across the anchors — subtract the mean, divide by the standard deviation.
**This cannot work, and it is worth recording because it looked like it
did.** Both operations are constants with respect to one vector's own
scores, so the transform is monotonic and the ranking is invariant. It
produced different-looking numbers in identical order.

The correction that does work subtracts the **mean anchor vector** from
both the target and each anchor before computing cosine, which changes the
geometry rather than the scale. Confirmed to reorder real cached vectors.

The regression test for this needed a case where the shared direction
genuinely dominates — an anchor carrying a large common component and
nothing specific. A naive three-anchor example ranks identically either
way and would have passed while testing nothing.

### Negative result: the anchor set does not span the memories

Well-formed sentences profile sharply, at +0.478 for the top anchor above.
Entries in the project's real embedding cache profile at roughly **+0.24
and incoherently**, with top anchors that do not cohere into a subject.

**The 122 general and 16 project anchors do not span what this assistant
actually remembers.** The anchor set is the artifact, and this one is built
for documents rather than for a life. Any state-reading built on the
current set would read noise.

### Privacy note

The embedding cache is keyed by SHA-256 of the text and stores no text, so
this describes memories it cannot read. That makes an opaque cache
inspectable, and it also makes an anchor profile a **shareable description
of a private memory's subject**. Both properties follow from the same
mechanism.

---

## 5. Token trajectories — `SABLE7` and machinespirit

Naming, since two things are involved and they version separately:
**`SABLE7` is the container** that stores an ordered per-token path.
**machinespirit is the representation** it carries — the trajectory read
against the anchor dictionary. A file is SABLE7; what the assistant does
with it is machinespirit. It is reachable from
`start_assistant_hazard.bat`, from `experimental mode`, and from
`trace <text>`.

`tools/vector_beam.py`. A sentence embedding is a mean over token vectors.
Before pooling, a sentence is an ordered sequence — a path — and pooling
collapses it to one point.

`SABLE7` names that ordered trajectory. It is deliberately not a revision
of `SABLE1` or `SABLEVEC1`: those carry an unordered payload and an
unordered set of vectors, and neither has a notion of sequence. For a
trajectory the order is the content, so it declares itself separately.

Measured on `"I keep thinking about something my grandmother said before
she died."`, bge-small with `--pooling none`:

| | |
| --- | --- |
| tokens | 14 |
| dims per token | 384 |
| consecutive-token cosine | 0.601 – 0.937, mean 0.814 |
| token-to-pooled cosine | 0.804 – 0.952, mean 0.905 |
| **cosine range pooling flattens** | **0.148** |
| path length, Σ(1−cos) between steps | 2.422 |

The path moves, unevenly, and the pooled point sits at varying distance
from the tokens it summarises.

### Containment

The mean is recoverable from the path; the path is not recoverable from the
mean. The trajectory is therefore strictly more information than what the
current format stores, at N times the size. A test guards this, because it
is the entire justification for keeping the path.

### The rendering is not the data

Each token's colour is a fixed seeded projection onto three axes, taken
after centring on the path mean. It is lossy and one-way: three numbers
cannot carry 384, and nothing recovers a token vector from its colour.
Centring before projection is required or every token renders nearly the
same colour and the beam looks flat when it is not. Brightness tracks each
token's cosine distance from the pooled point, so the tokens the stored
vector represents worst are the ones that burn.

To store a trajectory losslessly, `SABLEVEC1` already accepts N vectors.

### Negative result: late interaction did not pay here

The established use for token vectors is MaxSim — each query token takes
its best document token, then average (ColBERT). Compared against plain
pooled cosine over an 18-chunk corpus from `THE_STORY_OF_SABLE.md`:

| Query | Top-3 membership | Rank-1 |
| --- | --- | --- |
| "what is the assistant called and why" | identical | differs |
| "a checksum or verification that refused to proceed" | identical | same |
| "something the system got wrong about its own history" | identical | same |

**Identical top-3 membership on all three probes, one reordering at rank
1.** Three unlabelled queries is far too small to conclude the technique is
useless, and nowhere near enough to justify N× storage and N×M scoring
against thresholds as tight as a 0.55 minimum with a 0.06 margin.

**Nothing is wired into the retrieval path.** The beam is a rendering and a
measurement, not a change to how the assistant retrieves.

### Why not dynamic time warping

DTW is the classic way to compare two sequences of unequal length: it finds
the lowest-cost monotonic alignment by dynamic programming, at O(N×M) per
comparison against O(D) for a single pooled cosine.

It is probably the wrong tool here. DTW's monotonicity constraint assumes
that order must be preserved in the alignment, which is why it suits time
series. Sentences that mean similar things routinely reorder their content,
and DTW would penalise exactly that. MaxSim imposes no ordering constraint,
which is why the retrieval literature uses it — and MaxSim is what showed
no benefit above. Untested here.

---

## 6. Open questions

- Anchors drawn to span the assistant's actual memory content, since the
  present set demonstrably does not. This gates any state-reading work.
- Whether quantising a relative representation compounds the loss.
- How few anchors the translation survives.
- Whether project anchors help or distort when both agents hold the same
  material.
- Whether MaxSim pays on a labelled corpus large enough to measure, with
  ground truth rather than three probes.
- DTW over trajectories, if a use appears that genuinely needs order.

## 7. What this is not

It is not a new quantisation method, not a way for a model to read meaning
out of a picture, and not a technique that lets a larger model run on
smaller hardware. Model weights are already quantised by far more
sophisticated means than anything here — the bundled 14B uses `Q4_K` across
289 tensors with 49 promoted to `Q6_K` and 241 held at `F32`, with scales
stored per block. A single global scale and offset is strictly less than
that.

It is a measured account of where cross-model translation pays, where it
does not, and what a sentence discards when it becomes a point.
