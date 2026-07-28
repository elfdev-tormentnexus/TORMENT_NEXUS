# Vector-to-pixel encoding — measurements and format

Scope: two encodings that both put data in pixels and are otherwise
unrelated. One stores arbitrary bytes. The other stores embedding
coordinates. They were built in the same session and it would be easy to
describe them as one idea; they are not, and their measured answers point in
opposite directions.

Everything below is measured on this machine against this stack. Numbers are
reproducible with the tools named. Where something was not run, it says so.

Embedding model for every vector measurement:
`bge-small-en-v1.5-q8_0`, mean pooling, identity
`sha256:ec38e8da142596baa913124ae50550de284b6916bf59577ef2f0cb9660c2f514`.
Changing the model, quantisation or pooling invalidates the numbers.

---

## 1. Prior art, stated first

Nothing here is novel and it is worth saying so before the measurements
rather than after. Bytes in raster order is what a bitmap is. Data-bearing
images cover QR codes, PNG steganography, PaperBak and optar for print, and
a long line of archival work. Splitting a vector into subspaces and storing
centroid indices is product quantisation, described by Jégou, Douze and
Schmid in 2011 and shipped in FAISS since.

The contribution of this document is not a technique. It is a set of
measurements at this project's actual scale, with the win attributed to the
part that earns it.

---

## 2. Arbitrary bytes to pixels — a loss

`tools/vector_pixel_compiler.py`. Bytes go into RGB channels in raster
order under a declared container, and come back byte-identical or the
checksum reports failure.

Measured on `docs/THE_STORY_OF_SABLE.md`, 5,385 bytes of Markdown:

| Form | Bytes | Against zlib |
| --- | --- | --- |
| Source text | 5,385 | — |
| zlib level 9 | 2,566 | 100% |
| Pixel-compiled PNG | 3,384 | **131.9%** |

**The pixel layer costs +818 bytes, or +32%, and buys nothing
functional.** All of the size reduction is zlib; PNG then adds a container
back. If the goal is to make a file smaller, this is strictly worse than
compressing it.

It has exactly one honest use: **transport through channels that carry
images but not files.** A README, a release page, a social card, a chat that
strips attachments. That is reach, not efficiency, and it should never be
described as compression.

### Container format: SABLE1

Three bytes per pixel through RGB, alpha held at 255, raster order.

```text
magic    6 bytes   "SABLE1"
version  1 byte
flags    1 byte    bit 0 set when payload is zlib compressed
length   4 bytes   big-endian, payload bytes as stored
crc32    4 bytes   big-endian, over the payload as stored
payload  length bytes
padding  deterministic filler to the end of the final row
```

Padding is derived from byte position rather than randomness, so identical
input produces an identical file and rebuilds can be compared.

The decoder **searches for the magic** rather than requiring it at offset
zero. Pinning it to the first pixel forces the payload into the top-left
corner and dictates the composition of any image sharing the frame. Since
the header carries its own length and CRC32, a false match on six bytes
fails the checksum rather than returning junk.

**Known fragility:** the payload survives file copies, not re-encodings. A
screenshot, a transcoding host, or a platform that recompresses destroys it
silently while the image still looks identical. Treat one file as canonical
and do not assume copies carry it.

---

## 3. Embedding coordinates to pixels — a win, with the credit placed correctly

`tools/vector_pixel_codec.py`. One vector per row, three dimensions per
pixel through RGB, affine uint8 quantisation with a single scale and offset
recorded in the PNG's own metadata.

Measured on 43 chunks of the same document, embedded live:

| Form | Bytes | Of raw |
| --- | --- | --- |
| float32 raw | 66,048 | 100% |
| float32 + zlib | 61,541 | 93.2% |
| **uint8 quantised, raw** | **16,512** | **25.0%** |
| uint8 quantised + zlib | 13,818 | 20.9% |
| Quantised PNG | 17,152 | 26.0% |

Fidelity after the full round trip: **mean cosine 0.999929, worst 0.999921**,
mean error 7.15e-05. Effectively lossless for retrieval.

### Where the win actually comes from

**Quantisation, entirely — exactly 4.00×.** Not the pixels. The pixel
container costs **+3.9%** over raw quantised bytes and **+24.1%** over
zlib'd quantised bytes.

But one line separates this from section 2 and must not be lost:
**zlib barely touches float32 at all — 93.2%.** Float mantissas are
high-entropy, so the "just compress it instead" answer that defeats
byte-to-pixel *fails here*. Against the naive baseline of storing floats,
the quantised form is a genuine 4× improvement that costs 7e-05 of cosine.

### Against zlib, stated directly

"How does it do against just compressing it" is the first question anyone
asks, and the table above answers it only by division. Stated outright,
against the realistic baseline of zlib'd float32:

| Form | vs float32 + zlib |
| --- | --- |
| quantised + zlib | 4.45× |
| quantised, raw bytes | 3.73× |
| **quantised PNG (SABLEVEC1)** | **3.59×** |

So the shipped artifact is **3.6× smaller than zlib'd float32** — a real
end-to-end number against the obvious alternative. Note where it sits in that
table, though: the PNG is the *weakest* of the three quantised forms, not the
strongest. The 3.6× is earned by quantisation and partly given back by the
container. Both readings are the same finding from opposite ends.

So the correct claim is narrow and defensible:

> Embedding sets are wastefully stored as float32. Quantising to uint8 costs
> almost nothing measurable and saves 4×. Putting the result in a PNG costs a
> further 4% and buys a viewable, self-describing, portable artifact.

Anything broader than that is overselling.

### Container format: SABLEVEC1

Header lives in a PNG `tEXt` chunk as JSON, not in pixel order, because a
decoder needs it before it can interpret anything:

```json
{"magic": "SABLEVEC1", "dims": 384, "count": 43,
 "scale": <float>, "low": <float>,
 "layout": "one vector per row, three dims per pixel via RGB"}
```

Quantisation is affine over the whole file — one scale and offset, not per
row — so any decoded vector is directly comparable to any other without
unpacking a per-row table.

### The image is legible as data

Reading across a row is one text chunk's coordinates. Reading down a column
is how one dimension varies across the corpus. The rendered result shows
strong vertical striping: specific `bge-small` dimensions sit near-constant
regardless of input, and the discriminating signal is narrower than 384
dimensions implies.

That is not an artifact of the encoding. It also explains two numbers above:
near-constant columns are what PNG's row filters were built to collapse, and
dimensions that never move do not need 32 bits to say so.

---

## 4. Product quantisation — economics computed, experiment NOT run

The natural next step, and the one where "vectors describing vectors"
becomes literal: split each vector into M sub-vectors, learn K centroids per
subspace, store each vector as M indices. The codebook is the decompiler and
the codebook is itself vectors.

Cost has a fixed part and a per-vector part, and that decides everything:

```text
codebook   = K * D * 4 bytes     fixed, independent of M
per vector = M bytes             at K <= 256, one byte per index
```

At K=256, D=384 the codebook alone is **393,216 bytes** before a single
vector is stored. Crossover, where the toll is finally repaid:

| K | Codebook | Beats float32 above | Beats uint8 above |
| --- | --- | --- | --- |
| 16 | 24,576 | ~16 vectors | ~65 vectors |
| 64 | 98,304 | ~64 vectors | ~262 vectors |
| 256 | 393,216 | ~257 vectors | ~1,046 vectors |

*(computed, M=8; arithmetic only, no experiment behind these)*

**This corpus is 110 vectors** — 67 in `assistant/cache/embeddings.json`
plus 43 from the story. At that scale PQ with a useful codebook is expected
to lose badly to plain uint8, and the technique only becomes interesting
above roughly a thousand vectors.

`tools/pq_probe.py` implements the measurement — k-means per subspace,
size and mean-cosine at several (M, K) settings. **It was written and never
executed.** No recall numbers exist. Do not cite any until it runs.

---

## 5. Actionable finding, unbuilt

`assistant/cache/embeddings.json` currently holds **67 vectors of 384
dimensions in 906 KB**, as JSON floats. JSON is the worst case: a float that
occupies 4 bytes binary is commonly 12–20 bytes as text.

Quantising that cache to uint8 with a stored scale is plausibly an
order-of-magnitude reduction at ~7e-05 cosine error, with no visual
component and no new format. This is the only genuine performance result the
whole line of work produced, and it arrived as a side effect of an
aesthetic question.

Not implemented. It touches a privacy-sensitive derived cache that the
release builder deliberately excludes, so it wants its own change with its
own tests.

---

## 6. Open questions

- Does PQ recall hold at this project's realistic ceiling? Run the probe
  once the corpus passes ~1,000 vectors.
- ~~Does dimension **reordering** before encoding improve PNG's filters?~~
  **Answered 2026-07-28: no.** Real SABLEVEC1 PNGs over the 67-vector cache,
  natural order 26,872 bytes; sorted by variance 26,841 (99.88%); sorted by
  mean 26,638 (99.13%); random control 26,851 (99.92%). Everything inside
  0.9%, and random beats variance-sorting. The permutation round-trips
  identically, which is the point: information that survives arbitrary
  rearrangement was never stored in the arrangement. Row index is insertion
  order and column index is the model's emission order — both arbitrary, so
  neither can carry meaning, and PNG's filters have no real adjacency to
  exploit. The layout is a rendering, not a structure.
- The **alpha channel is unused** — pinned at 255, so the container carries
  3 bytes per pixel where 4 are available. That is a genuine 33% capacity
  increase and the only literal extra dimension on offer here, unlike
  rearrangement. Untested, and fragile: premultiplication in some image
  pipelines mangles alpha silently.
- Is per-dimension quantisation range better than global? Dimensions with
  narrow spread currently waste most of their 256 levels.
- Can retrieval run directly against the quantised form without
  dequantising? Integer cosine on uint8 would be faster, not just smaller.

## 6a. The header does not record which model produced the vectors

`SABLEVEC1` stores `dims`, `count`, `scale`, `low` and `layout` — everything
needed to reconstruct the numbers, and nothing that says what they mean. The
top of this document warns that changing the model, quantisation or pooling
invalidates every figure here, but the container itself cannot express that
warning, so a file carries no evidence of its own origin.

That is tolerable while one process writes and reads its own cache. It
becomes a real defect the moment a file is exchanged, because a receiver has
no way to detect that the vectors came from a different embedder and cosine
against its own vectors is meaningless rather than merely degraded — it
fails silently, which is the failure mode this project treats as worst.

Minimum fix: carry `model`, `pooling` and the embedder's file digest in the
same `tEXt` JSON, and have the decoder refuse a mismatch rather than warn.
Not implemented.

## 7. Anchor sets — a rosetta stone between two models' spaces

The question this line of work keeps circling: two agents built on different
embedders cannot share vectors, because dimension 7 in one model has no
relationship to dimension 7 in another. Same dimensionality does not imply
same meaning. Cosine between vectors from different models is not degraded
signal, it is noise. **A container format cannot fix this** — SABLEVEC1
transports numbers faithfully and says nothing about what they mean, so
shipping a file between two models makes their vectors equally readable and
no more mutually intelligible than before.

There is a technique that does address it, and it is published rather than
ours. **Relative representations** (Moschella et al., *Relative
representations enable zero-shot latent space communication*, ICLR 2023).
The idea:

1. Fix an ordered set of **anchor texts**, shared by both agents.
2. Each model embeds the anchors in its own private space.
3. Any vector is then re-expressed as its similarities to those anchors —
   `[cos(v, a1), cos(v, a2), ... cos(v, aN)]` — instead of its own
   coordinates.

Both models now describe meaning in a coordinate system defined by *content
they both saw*, not by axes neither can explain to the other. The rosetta
stone analogy is exact rather than decorative: the stone worked because the
same decree appeared in three scripts, and the anchors are the same texts in
two vector languages.

The older alternative is a **learned linear map** — Procrustes alignment on
paired embeddings (Mikolov et al. 2013; Conneau et al. 2017 for the
cross-lingual case). It works, but it must be fitted per model pair and
needs paired data. Relative representations need no fitting, which is what
makes them interesting for agents that meet without prior arrangement.

### What it would cost, honestly

- Dimensionality becomes N, the anchor count. The published work uses
  hundreds; too few anchors and distinct meanings collapse together.
- Anchors must span the domain they will be used on. Anchors drawn from one
  subject give a distorted account of another.
- It is an approximation, not an isomorphism. Expect retrieval quality below
  each model's native performance — the gain is that cross-model comparison
  becomes possible at all, not that it becomes free.
- Quantising a relative representation is a second lossy step on top of the
  first, and the two have not been measured together.

### What the container would need

Section 6a's fix is a precondition, not a separate task. A relative-
representation file is meaningless without knowing what it is relative *to*,
so the header must carry:

```json
{"magic": "SABLEVEC1", "space": "relative",
 "anchors": "<sha256 of the ordered anchor texts>", "count_anchors": <N>,
 "model": "<embedder id>", "pooling": "mean"}
```

A decoder should refuse to compare two files whose `anchors` digests differ,
rather than returning a number that looks like a similarity.

### Measured, 2026-07-28

Implemented in `tools/rosetta_stone.py` and run against two genuinely
incompatible spaces: `bge-small-en-v1.5-q8_0` at **384 dims** and
`nomic-embed-text-v1.5` Q8_0 at **768 dims**, both mean-pooled, served
side by side on separate ports. 122 core anchors, digest `b5421687348e956e`.

Different dimensionality is deliberate. Two 384-dim models could be accused
of accidental compatibility; 384 against 768 cannot be compared at all
without translation, so there is no baseline to be confused with.

Corpus of ~180 paragraph chunks from six project documents, top-10
neighbour agreement between the two models:

| | Agreement |
| --- | --- |
| chance | 0.056 |
| **translated into anchor space** | **0.370** |
| each model's native neighbours | 0.549 |

The last row is the ceiling, not a competitor: it is how much the two models
agree with each other *at all*, measured by comparing their own neighbour
lists by index. No translation can beat it.

So translation recovers **67% of the achievable ceiling at 6.6× chance.**
Within-model fidelity — does the relative form preserve each model's own
structure — is Spearman **+0.737** for bge and **+0.667** for nomic.

**It works, and it is not free.** A third of what the models could agree on
is lost in translation, and each model's own neighbour structure is only
about three-quarters preserved. That is the honest shape of the result: good
enough to make cross-model comparison possible where it was impossible, not
good enough to pretend the two spaces have become one.

One caution against overreading these numbers. An earlier run on a 20-chunk
corpus gave 0.610 against a 0.680 ceiling — 90% of the ceiling, far rosier —
because with n=20 chance alone is 0.263. The larger corpus is the honest
figure and the small one should not be quoted.

Not yet measured: whether quantising a relative representation compounds the
loss, how few anchors it survives, and whether project anchors help or
distort when both agents hold the same material.

## 8. What this is not

It is not a compression advance, not a novel format, and not a way for a
model to read meaning out of a picture. A projection to two dimensions is
lossy and one-way; nothing recovers text from the semantic-space image, and
the decoder correctly refuses it for lack of a container.

What it is: a measured account of where quantisation pays, where a pixel
container costs, and a format honest enough to declare itself in its own
metadata so anyone can check the claim.
