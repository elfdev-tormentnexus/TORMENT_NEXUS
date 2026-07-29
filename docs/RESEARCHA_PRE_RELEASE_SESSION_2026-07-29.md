# researchA pre-release session: evidence, refutations, and inheritance

This document preserves the results of the final researchA session on
2026-07-29. It is an evidence map, not a claim that every technique was
invented here. Each section distinguishes prior work, a local measurement,
an engineering result, and an open hypothesis.

The session moved the suite from 807 to 915 passing tests, with two expected
Windows link-permission skips. The relevant commit chain is `e466139`,
`5187c02`, `6c8f1b0`, `66dc69d`, `a119914`, `fe760c1`, and `221ece7`.

## 1. The quietest failure: correct code that nothing reaches

`assistant/core/session_rhythm.py` already had `note_turn()`, `record()`, and
`viewing_pace()`, with unit tests. No live turn called them. The module was
correct; the feature did not exist.

The repair connected typed and spoken turns at their shared seam, writes one
bounded timing record at shutdown only after a real exchange, and lets the
animated beam use measured median pauses after enough sessions exist. The
privacy denylist now excludes that timing history from releases.

Lasting rule: a tested module proves its internal behaviour, not its
reachability. Features need an end-to-end assertion at the production seam.
Other dormant modules should be audited by tracing entry points, not by
counting tests.

## 2. Six audit defects closed before packaging

The pre-cut audit found six concrete defects:

1. `consume` validated only the supplied URL and then followed redirects
   without repeating the private-address check. Every redirect hop is now
   resolved and validated, with a cap and explicit handling for relative and
   media redirects. DNS rebinding between validation and connection remains
   named rather than implied fixed.
2. The autonomous edit guard could miss reflection through `getattr` and
   nested call expressions. Reflection is now treated as capability.
3. `extract_stream()` truncated an existing output before validating the
   capsule, then deleted it on refusal. It now writes beside the target and
   replaces only after verification.
4. `build_stream()` could leave its partial capsule or frame spill after an
   interruption. Cleanup now runs from `finally`.
5. Backup restore accepted the first flattened-name match even when more than
   one source matched. Ambiguity now refuses.
6. `session_rhythm.json` was absent from both release privacy guards because
   nothing had previously written it. Both the path pattern and independent
   basename check now cover it.

The important inheritance is methodological: a failure that is invisible on
small or successful inputs is still a release failure. The stale published
decompiler illustrated the same point—it could open a small research capsule
while lacking the streaming path required for 1.797 GB release fields.

## 3. machinesoul and machinespirit became separate, integral languages

**machinesoul** is Sable's exact data-preservation language. Ordered
four-coordinate vectors map to PNG/APNG pixels. The inverse reconstructs the
preserved source exactly or refuses. It is the public boundary for researchA,
which is why the standalone streaming decompiler is required for installation.

**machinespirit** is Sable's measured memory language. It reads token
trajectories through a fixed anchor dictionary and exposes traces, trails,
spread, and calibration. It is lossy; measuring that loss is part of the
research.

The distinction prevents the 1:1 guarantee of preservation from being
attached to a memory representation measured at 0.9243 cosine. The two meet
in `SABLE_CALIBRATION1`: machinesoul preserves the calibration reference;
that reference checks whether machinespirit still reads the same.

Capsule descriptions remain caller-supplied, cleartext, opt-in metadata
outside the preservation digest. They make a directory navigable without
decompilation, but they are labels, not machinespirit inference and not an
integrity guarantee.

## 4. The trail is sufficient for the readout, not for the trajectory

The full trace stores every token against every anchor. `trail <text>` keeps,
for each anchor that wins at least one token, accumulated support, strongest
reading, and peak position. It reproduces `peaks(trace(...))` exactly at four
tested lengths.

For an 89-token example, the trajectory contains 34,176 values and the trail
contains 24: 1,424 times fewer, with the ratio improving as input grows. That
ratio is secondary. The central result is sufficiency for a declared
inference: the trail retains everything the current `peaks()` readout uses and
explicitly discards everything else.

Support is load-bearing. A maxima-only readout was the version measured at
77% top-1; summed support reached 90% and matched the pooled control. The
reported position remains the strongest token, so the claim stays “which
concept, and where,” not merely which concept.

This is a local representation and exact-equivalence result. “Sufficient
statistic” is established statistical language, not a term invented here.

## 5. A trajectory was measured as a cluster, not a curve

The session proposed compressing token trajectories with a spline or other
smooth position function. The proposal was refuted by its simplest control:
degree 0, the pooled vector replicated, already explains the path at 0.8733
mean cosine.

| Basis | Parameters per dimension | Mean cosine |
| --- | ---: | ---: |
| polynomial degree 0 | 1 | 0.8733 |
| polynomial degree 1 | 2 | 0.8777 |
| polynomial degree 2 | 3 | 0.8826 |
| polynomial degree 3 | 4 | 0.8857 |

Doubling storage from degree 0 to degree 1 buys only +0.0043. The independent
`spread` measurement agrees: effective rank was 1.694 over 39 tokens. The
token states are close mainly because they occupy a tight region around their
centroid, not because they trace a cheaply parameterised curve.

This does not refute compressed sensing. Curve fitting assumes smoothness;
the surviving compressed-sensing proposal exploits sparsity. The trail also
survives because it preserves discrete readout events rather than vector
shape.

## 6. The basis control prevented a false structural story

Sinusoids beat polynomials at every matched parameter count and reached
0.9522 against 0.9243 at 21 parameters per dimension. A matched-capacity
random basis reached 0.9419. Therefore most of the apparent basis advantage
is capacity rather than discovered trajectory structure; the residual
sinusoidal edge is about +0.010.

That residual is open. The bundled GGUF declares a BERT architecture with
learned absolute position embeddings, not RoPE. Published work finds
anisotropy in contextual and BERT sentence representations
([Ethayarajh, 2019](https://aclanthology.org/D19-1006/);
[Li et al., 2020](https://aclanthology.org/2020.emnlp-main.733/)) and reports
low-dimensional, low-frequency structure in learned BERT/ALBERT position
embeddings
([Wennberg and Henter, 2024](https://aclanthology.org/2024.repl4nlp-1.17/)).
Those results make a positional explanation plausible; they do not establish
that this +0.010 is position rather than attention, tokenisation, local
smoothness, or another confound.

Required next controls: matched-length unrelated texts, repeated
equal-token-multiset permutations, the learned position-embedding eigenbasis,
and a model with a genuinely different position mechanism.

## 7. Spread measures breadth over a narrow anisotropic range

`spread <text>` derives purity, participation ratio/effective rank, and von
Neumann entropy from the token Gram matrix. Growing one topic by 49% moved
effective rank +1.1%; adding topics at matched length moved it +12.6%.
Permutation leaves the result unchanged, as both mathematics and regression
require.

The unflattering result matters: effective rank remained about 1.1–1.8
against a ceiling equal to token count. It is a sensitive breadth dial over a
narrow range, not a count of ideas and not an account of order. The local
geometry is consistent with established anisotropy and representation
degeneration work, but the numerical range is specific to this model and
corpus.

## 8. Calibration gained controls in both directions

`SABLE_CALIBRATION1` fixes seven texts and records their readings beside a
quantization-bearing model name, pooling mode, and anchor digest. Three rows
form the scale:

- periodic: one phrase repeated;
- Fibonacci: two phrases ordered by a deterministic aperiodic word; and
- seeded random: the same phrase multiset in another order.

The infinite Fibonacci word is Sturmian. The finite release test does not
prove that theorem; it verifies the expected p(n)=n+1 subword signature on a
long prefix through twelve scales and shows the periodic and seeded-random
controls fail the same check. The 13-term corpus row itself can carry the
signature only through n=6, and the test records that counting limit.

Fibonacci and random share a phrase mix, so a permutation-invariant
instrument must read them alike: 1.5238 and 1.5132. Periodic changes the mix
and reads separately at 1.4354. One comparison catches accidental order
sensitivity; the other catches an instrument that stopped responding to
content.

Calibration reports drift. It never changes thresholds or widens tolerance to
make drift disappear, and it is not a cryptographic identity attestation for
the live server.

## 9. Rosetta Stone crosses a vector gap, with a measured ceiling

`tools/rosetta_stone.py` implements relative representations: incompatible
models describe vectors against the same ordered anchor decree rather than
comparing native coordinates. This method has prior art; the project's
contribution is its implementation, refusal semantics, and measurement on a
384-dimensional/768-dimensional pair.

Translated neighbour agreement was 0.370, against 0.549 native cross-model
agreement as the reachable ceiling and 0.056 chance—about 67% of what the two
models could agree on at all. Anchor-digest mismatch refuses. Model,
quantization, and pooling changes invalidate a measured half. It is a
portability experiment, not a universal stone and not a storage improvement.

## 10. Results deliberately left negative or open

- Retrieval remains pooled. Late interaction showed the same top-three
  membership on three probes, far too little evidence for its cost.
- The shadow log now gathers larger evidence without deciding; `observe()`
  returns `None` by construction and stores digests rather than text.
- Anchor-space retrieval is not promoted. Stage 2's labelled-corpus gate
  remains.
- The current anchors still misread roughly a third of real memory entries.
- The Fourier residual remains unexplained.
- DNS rebinding between address validation and connection remains a named
  boundary.
- The installed two-server launcher still requires an end-to-end packaged
  run; passing imports and unit tests do not substitute for it.

## 11. What should outlive the implementation

Three practices made the session durable:

1. **A control can overturn an attractive explanation.** Degree 0 refuted the
   spline proposal; a random basis prevented capacity from being called
   structure; matched phrase multisets checked permutation invariance.
2. **A refutation belongs beside the reasoning that produced it.** Removing
   the wrong idea would make the next person rediscover it without the
   decisive control.
3. **Reachability, privacy, and refusal are features of the whole path.** A
   correct unused module, a safe first URL followed by an unsafe redirect,
   or a small capsule opened by a buffered extractor are all partial truths
   that fail in production.

The inheritance is not that researchA proved a universal theory of vector
memory. It produced a set of measured representations, hard negative results,
and controls strong enough to say exactly where the evidence stops.
