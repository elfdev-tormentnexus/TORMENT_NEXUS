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

## 5b. Proposed fixes, and the ones that were refuted

The `+0.24` haze on real memory entries had four candidate explanations.
Measuring them cost less than arguing about them, and only one survived.
Recorded in full because the three failures are more useful than the
success: each looked correct, and two produced numbers that improved on
the metric being watched while making the system worse.

**A metric that rewarded disorder.** Centering each token on its own
trajectory's mean *appeared* to sharpen traces dramatically — distinct
winning anchors rose from 3 to 12, the modal anchor's share fell from 71%
to 14%, and the top hit on one probe improved from the generic
*"grandparents telling the same story again"* to the specific *"a promise
made to a dying person"*. Every visible sign said it worked.

Scored against 30 labelled paraphrases it collapses:

| centering | top-1 | top-3 | MRR | median rank |
| --- | --- | --- | --- | --- |
| anchor mean (current) | **83%** | 97% | 0.896 | 1 |
| + trajectory mean | 0% | 7% | 0.088 | 23 |
| + trajectory mean, whitened | 3% | 3% | 0.105 | 17 |
| pooled control | **90%** | 97% | 0.923 | 1 |

The mechanism is exact rather than mysterious. `tools/pooling_probe.py`
establishes that the pooled vector **is** the mean of the token vectors,
at cosine `1.000000` on every probe — so subtracting the trajectory mean
subtracts the sentence's topic, and the topic is usually the answer. What
looked like resolution was noise spread evenly across more anchors, and
range/distinct/modal is a proxy that cannot tell those apart.

**The pooled control winning was the honest headline, until §5e found the
cause and removed it.** 90% against 83% here; the trace reaches 90% once
`peaks()` ranks by summed support instead of by one strongest position. The
83% in the table above is the *old* ordering, kept because it is what the
centering variants were measured against.
This measures *which* concept, which is the question the average is better
at; the trace's only claim is *where*, which this does not test. But
"trajectories shadow retrieval" is now a measured 83-versus-90 rather than
an impression from one run.

**Corpus-mean centering: a no-op.** 0.131 against 0.127, identical distinct
and modal counts. The anchor mean and the memory-corpus mean point the same
way because the anisotropy belongs to the model, not to either corpus.

**Canonicalisation: refuted in both directions.** The premise was that
telegraphic entries sit out of register for a sentence embedder. This
project's entries are already plain sentences, so there was nothing to
rewrite — and *degrading* them into telegraphic form scores **higher**,
+0.324 against +0.288, winning 9 of 11 paired comparisons. A constant
subject prefix on every entry drags them all into one region; stripping the
grammar removes shared scaffolding.

**The survivor: coverage.** v1 had no anchors for what a stored memory is
about. Four unrelated entries all profiled strongest against the same
self-editing anchor; both hardware entries against the same voice-synthesis
one. The single concept v1 *did* hold — loneliness — scored +0.419 and was
right. `anchors_v2` adds 46 anchors describing kinds of memory (never a
fact about any operator; the file ships):

| | v1 (138) | v2 (184) |
| --- | --- | --- |
| memories, mean top-1 | +0.288 | **+0.380** |
| distinct winners / 13 | 8 | **11** |
| most-repeated winner | 4 | **2** |
| labels, pooled top-1 | 90% | **90%** |
| labels, trace top-1 | 83% | 77% → **90%** |

The trace figures are the old max ordering; §5e replaces them with 90%.
The pooled control holds exactly despite 33% more competitors. The trace
loses six points, and that is structural rather than noise: it takes a
**max across positions**, so each added anchor is another chance at a
spurious peak, while the mean has no max to inflate. *The trace degrades as
the dictionary grows; the pooled read does not.* Roughly a third of entries
are still wrong — *"working on their project"* matches *"a single-board
computer bought for a project"* on the word "project".


### Negative result: a trajectory is a cluster, not a curve

*Measured 2026-07-29, live traces, same stack as everything above.*

Fitting a function of token position to the path is the obvious way to keep
a trajectory cheaply, and it does not pay. The control that decides it is
degree 0 — which *is* the pooled vector, replicated.

| basis | params/dim | mean cosine | gain over degree 0 |
| --- | ---: | ---: | ---: |
| degree 0 (the pooled vector) | 384 | 0.8733 | — |
| degree 1, a straight line | 768 | 0.8777 | +0.0043 |
| degree 2, a parabola | 1,152 | 0.8826 | +0.0092 |
| degree 3 | 1,536 | 0.8857 | +0.0124 |

Doubling the storage buys **+0.4%** cosine. The vector already kept accounts
for roughly 87% of every token in the sentence, and knowing *where* a token
sits adds almost nothing at any low order. At degree 12 — three times the
storage — it reaches only 0.9225.

The reason is measurable and agrees with §4's anisotropy from a second
direction: `spread` reports an effective rank of **1.694 out of 39** for the
same text. A path confined to under two effective directions is a tight
cluster around its own mean, and a cluster is described by its centroid,
which is degree 0. Repetitive text is *more* clustered still — a
single-topic passage scores 0.9008 at degree 0 and gains less from every
added term.

This also refutes a proposal made in the same session, which is worth
recording because the reasoning sounded good: consecutive token vectors
are close, therefore the path is smooth, therefore a spline plus small
residuals should be cheap. Consecutive vectors *are* close — but because
everything sits near the centroid, not because the path traces a curve.

### A better basis, and the control that still kills it

Sinusoids are the right shape where polynomials are the wrong one, and they
measurably win. The matched-capacity **random basis** is what settles it.

| params/dim | polynomial | sinusoidal | random (control) |
| ---: | ---: | ---: | ---: |
| 5 | 0.8906 | 0.8920 | 0.8880 |
| 13 | 0.9186 | **0.9260** | 0.9133 |
| 21 | 0.9243 | **0.9522** | 0.9419 |

Sinusoids beat polynomials at every count, by a widening margin. But at 21
parameters a *random* basis beats polynomials outright, so most of what any
basis gains is capacity rather than structure discovered. Fourier's genuine
edge over random is about **+0.010**.

This is the same control §6 of `VECTOR_PIXEL_RESEARCH.md` used to kill
dimension reordering, and the same conclusion: information that survives an
arbitrary substitute was never stored in the thing being varied.

The economics fail regardless — 21 params/dim is 8,064 values against a raw
14,976, a 1.86× saving for 0.9522. The trail keeps **12 values** and
reproduces the readout exactly, because reproducing the reading and
reconstructing the vectors are different problems.

**Open, untested.** Fourier's residual +0.010 needs explaining. One plausible
hypothesis is **position structure rather than meaning**, but this run does
not distinguish positional embeddings, attention, tokenisation, or ordinary
local smoothness. The GGUF identifies the bundled embedder as `bert`, and
[BERT](https://aclanthology.org/N19-1423/) constructs each input from token,
segment, and learned absolute position embeddings — not RoPE — so calling a
rotary basis the correctly-shaped probe would overstate what architecture and
data establish.

The next controls are: unrelated texts at matched token length; equal token
multisets under several permutations; the learned position-embedding
eigenbasis if it can be recovered; and the same basis comparison across a
model with a genuinely different position mechanism. A recent BERT/ALBERT
study reports that learned absolute position embeddings occupy a
low-dimensional subspace dominated by low-frequency rotational components,
which makes the hypothesis worth testing but does not make this +0.010 its
measurement ([Wennberg and Henter, 2024](https://aclanthology.org/2024.repl4nlp-1.17/)).

### The name for what the trail is

A **sufficient statistic** — a function of the data carrying everything
relevant to a particular inference. That is why it reproduces `peaks()`
exactly rather than approximately, and why its compression ratio is beside
the point: sufficiency is about having identified the question, not about
size. Curve fitting failed because it was trying to be sufficient for
reconstructing the vectors, which nobody asked for.

The cluster finding itself is a local re-measurement of published work on
**anisotropy** and **representation degeneration**, not a claim to have
discovered either phenomenon. Ethayarajh found contextual representations in
every examined layer of ELMo, BERT, and GPT-2 to be anisotropic rather than
uniformly distributed by direction
([2019](https://aclanthology.org/D19-1006/)). Gao et al. used
*representation degeneration* for learned word embeddings collapsing into a
narrow cone in neural language generation
([ICLR 2019](https://openreview.net/forum?id=SkEYojRqtm)). Li et al. then
measured a non-smooth anisotropic BERT sentence space and linked that geometry
to poor direct semantic-similarity behaviour
([2020](https://aclanthology.org/2020.emnlp-main.733/)). Those papers support
the comparison; they do not predict this project's effective rank of 1.694,
its basis scores, or the trail result, which are measurements from this stack.

## 5c. What readability costs

The steelman against a human-readable anchor set: translation quality
depends on coverage, spread and cross-model stability, and readability is
invisible to all three. Corpus-sampled anchors match the data distribution
by construction and should do at least as well.

138 readable anchors against 138 sampled from held-out project prose, same
pipeline (`rosetta_stone.py measure --anchors`), 190 held-out chunks,
bge-small against nomic-embed-text-v1.5:

| anchors | top-5 agreement | of reachable |
| --- | --- | --- |
| readable (v1 decree) | 0.316 | 58% |
| corpus-sampled | **0.351** | **65%** |
| ceiling (native agreement) | 0.525 | — |
| chance | 0.026 | — |

**Readability costs about 7% of reachable translation quality**, roughly
2.3 standard errors on 950 neighbour slots. The steelman is correct and the
price is modest. Confound worth stating: sampled anchors average 91
characters against the readable set's 37, and length was not controlled.

Readability is therefore an **audit** property, not a representational one,
bought at a measured price. That is a defensible trade — the operator can
read the coordinate system before the data arrives — but it is a trade, and
earlier drafts implied it was free.

## 5d. Anchor coordinates as a codec

Encoding replaces a 384-dimensional vector with its cosine to each of 184
anchors. The anchors span at most 184 dimensions, so the discard is
guaranteed by the arithmetic; below 384 anchors this is lossy by
construction and no decoder recovers the orthogonal component.

| decoder | mean cosine | worst | recovered@1 | median rank |
| --- | --- | --- | --- | --- |
| transpose (weighted sum) | 0.6635 | 0.5818 | 6% | 9 |
| least squares (ridge) | **0.9243** | 0.8929 | **100%** | 1 |

The entire gap is anchor correlation — the same anisotropy that forces
`profile()` to subtract the mean makes the transpose decoder count popular
directions many times over. This had not been measured before, and it
matters: the obvious decoder is the one most people would write, and it
fails.

Where this is useful, and where it is not: **not for storage.** uint8 gives
4.00× at 1.000 retrieval fidelity; anchor coordinates give 2.09×
dimensional reduction at 0.9243. uint8 wins on both axes. The use is
portability across models, which uint8 does not have — the same conclusion
section 3 reached, now with a decode figure attached.

**None of this recovers text.** The embedding was already a lossy function
of the words before any anchor was involved; recovering wording from an
embedding needs a trained inverse model and is approximate even then. The
`reconstruct` command therefore reports identification, not recall, and
says so in its own output.

## 5e. The readout, not the encoding

Two hypotheses about where the trace loses to the average. One was tested
and refuted; the other was not a hypothesis at all until the refutation
pointed at it.

**Refuted: that collapsing each token to one anchor is the lossy step.**
Scored three readouts of the same trajectories on the same labelled probes:

| readout | top-1 | top-3 | MRR |
| --- | --- | --- | --- |
| all 184 coordinates kept | 90% | 93% | 0.920 |
| top-3 anchors per token | 83% | 93% | 0.888 |
| **top-1 anchor per token** | **90%** | **100%** | **0.933** |

Collapsing to the single winner is not worse than keeping everything — it is
marginally *better*, acting as a denoiser. And keeping everything lands
exactly on the pooled control's 90%, which makes sense once stated: summing
the whole coordinate field across tokens approximates reconstructing the
mean.

**The actual cost was aggregation.** The same argmax readout scores 77% when
anchors are ranked by their single strongest position and **90%** when
ranked by summed support across positions:

| `peaks()` ordering | top-1 | top-3 | MRR |
| --- | --- | --- | --- |
| max over positions (before) | 77% | 100% | 0.867 |
| sum over positions (after) | **90%** | 100% | **0.933** |

A max gives every additional anchor another chance at one lucky spike, and a
lucky spike cannot be told from a real one when only the best survives. A
sum has to be earned across the sentence. This is the same mechanism as the
v1→v2 degradation in §5b, and it means that degradation was never a property
of trajectories — it was a property of how they were being read. `peaks()`
now orders by support and still reports the peak position, because *where* a
concept sits is the claim the feature exists to make.

**What is still untested.** Every readout above answers *which sentence is
this*, and all of them answer it well. None of them test whether per-token
contextual detail survives, which is the trace's actual claim. That needs
the labelled corpus in §6 and does not have a scoreboard yet. A passing
sentence-identification test is not evidence for a localisation claim, and
should not be cited as one.

---

## 5a. A time axis that stays lossless

The obvious question about rendering a trajectory is why PNG rather than
video, since video is the medium built for sequences. The answer is that
MP4 in practice means H.264, and H.264 is lossy — worse than generically
so for this purpose, because 4:2:0 chroma subsampling stores colour at
quarter resolution and the colour is where the data lives. A payload would
be destroyed before the lossy quantiser reached it.

**APNG is the honest form of the same idea.** PNG frames plus a control
chunk: lossless, browser-native, byte-exact. No invention needed for the
container.

The invention is in the pacing. APNG frame duration is a real field and
nothing requires it to be uniform, so `tools/vector_beam.py animate` sets
each frame's delay from that step's cosine distance. The animation holds
where the trajectory turns and moves quickly where it does not, which makes
duration carry the step distance rather than merely enabling playback.

Measured on the fourteen-token sentence: 90 ms fastest frame, 610 ms
slowest, 4.4 s total. The longest hold falls on the token the anchor trace
reads as *"the moment before a difficult conversation"*.

A second, independent source sets the *rate* rather than the shape.
`assistant/core/session_rhythm.py` measures the operator's median pause
between exchanges across past sessions, and `viewing_pace()` converts it to
a duration multiplier bounded to 0.6×–1.8×. Pacing anything visual at a
fixed speed is a guess about the viewer; this one has been counted. It
requires three sessions before it moves at all and returns exactly 1.0 when
unmeasured, because an invented preference is worse than none.

**The time axis here is the token axis.** It is not the assistant's clock,
and the analogy should not be allowed to become an identity in a later
write-up.

### Capacity was never the constraint

Three separate attempts to find unused room all returned the same answer,
and it is worth recording as one finding rather than three:

| Attempt | Result |
| --- | --- |
| Use the alpha channel (4 bytes/px instead of 3) | **identical file size**, to the byte |
| Reorder dimensions so PNG filters predict better | within 0.9%; random ordering beat variance-sorting |
| Use video frames for a third axis | more frames = more bytes, and so does a taller image |

The medium does not create data. 25,728 payload bytes are 25,728 bytes in
one wide image, one tall image, or three hundred frames.

One actionable finding did come out of it: an image that declares RGBA and
pins alpha at 255 costs **21% more** than the same image as RGB. That is
real and unclaimed — see the open questions.

## 6. Open questions

- Anchors drawn to span the assistant's actual memory content, since the
  present set demonstrably does not. This gates any state-reading work.
- **Drop the unused alpha channel** from every RGBA image whose alpha is
  uniformly 255, for a flat 21% saving with no visual change. Blocked:
  `read_png` in `tools/vector_pixel_compiler.py` hard-requires colour type
  6, so an RGB re-encode is rejected by this project's own decoder. Fix the
  decoder with a test first. Attempted 2026-07-28, produced a mark the
  decoder refused, reverted.
- **A labelled retrieval corpus.** A dictionary supplies natural ground
  truth: query with a word, the correct document is its definition.
  Webster's 1913 Unabridged is public domain. Every negative result in this
  document is provisional without one, including the MaxSim result, which
  rests on three unlabelled probes.
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
