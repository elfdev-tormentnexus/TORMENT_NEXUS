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

`scratchpad/pq_probe.py` implements the measurement — k-means per subspace,
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
- Does dimension **reordering** before encoding improve PNG's filters?
  Near-constant dimensions grouped together should predict better. Untested.
- Is per-dimension quantisation range better than global? Dimensions with
  narrow spread currently waste most of their 256 levels.
- Can retrieval run directly against the quantised form without
  dequantising? Integer cosine on uint8 would be faster, not just smaller.

## 7. What this is not

It is not a compression advance, not a novel format, and not a way for a
model to read meaning out of a picture. A projection to two dimensions is
lossy and one-way; nothing recovers text from the semantic-space image, and
the decoder correctly refuses it for lack of a container.

What it is: a measured account of where quantisation pays, where a pixel
container costs, and a format honest enough to declare itself in its own
metadata so anyone can check the claim.
