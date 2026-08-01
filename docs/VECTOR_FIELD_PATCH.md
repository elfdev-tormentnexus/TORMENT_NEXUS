# The researchC patches: corpus, then vector field

researchC ships two patches after the base cut. Both are one click, both are
verified byte-for-byte against the release ledger, and neither can overwrite
a file it did not write.

| Patch | Installs | Replaces |
|---|---|---|
| **A — offline library** | ~146 MB of reference corpora across 18,458 files | nothing |
| **B — vector field** | 15,000 precomputed embeddings | `assistant/knowledge/library.py` |

Patch A gives the assistant material a 4B director was never trained on.
Patch B makes that material *semantically* searchable without the installing
machine spending an hour of its own CPU deriving an answer that is already
known.

Install A first, run `library rebuild`, then install B.

---

## Why patch B replaces code, when patch A replaced nothing

A vector is only comparable to another vector if the same text reached the
same model. The library records that as a **vector identity** — the model's
SHA-256, its pooling mode, and the text policy — and refuses to mix two
identities in one cosine space. That is not bookkeeping. Two embedding
populations sharing a space fail silently: plausible numbers, meaningless
geometry.

The base cut's text policy was wrong for the shelf it shipped with, in two
separate ways. Both were found by measurement, not review.

### The window overflow

`bge-small-en-v1.5` accepts 512 tokens. The base policy bounded embed text at
1,600 UTF-8 bytes, which is comfortably inside 512 tokens **for prose**. The
shipped shelf is not prose. It is YAML device-tree schemas, Sigma and YARA
rules, and kernel documentation, where punctuation and identifiers inflate the
token-per-byte ratio.

Tokenizing a 400-row sample of the 15,000-row embed target against the live
server:

| Bound | Over 512 tokens | Max tokens | Mean tokens |
|---:|---:|---:|---:|
| 1,600 bytes | **15.5%** | 985 | 381.6 |
| 1,200 bytes | 4.0% | 875 | 349.8 |
| **1,000 bytes** | **1.2%** | 794 | 310.3 |
| 800 bytes | 0.5% | 668 | 262.2 |

The embedding request is all-or-nothing, so a single oversized row failed its
whole batch and the surviving rows were retried one at a time. At 15.5% almost
every 24-row batch contained one, which made the one-row-at-a-time fallback the
common path rather than the exception — a 24-row request costing 24 sequential
requests.

1,000 bytes was chosen rather than 800 because the gain below it is small and
the cost in retained context is not. Note that **no byte bound can guarantee a
token bound** — a base64 blob or a minified line tokenizes far denser than the
table suggests. The residual tail is left to the existing retry-and-quarantine
path, which drops a genuinely unembeddable row from the target and pulls in a
replacement from below the ceiling, so the field still reaches 15,000.

### The mid-word cut

A byte offset lands wherever it lands, and `text[:1000]` usually lands in the
middle of a word:

```text
before:  ...at a column boundary creating a spatially iso
after:   ...at a column boundary creating a spatially
```

That fragment is not free. `iso` becomes subword tokens that mean nothing on
their own, and because this model mean-pools, they are averaged into the
vector beside the real content. Every truncated chunk carried a little noise
in its coordinates.

The cut now backs off to the last whitespace. Measured across 1,375 truncated
chunks: **100% now end on a word boundary, at a mean cost of 6.4 characters**
(worst case 154). It only backs off while that retains at least 60% of the
clipped text, so material with no whitespace at all is still cut where the
bound falls rather than being gutted.

### Why that forces a replace

Both changes alter the text that reaches the model, so both change the vector
identity — from `…+utf8-1600` to `…+utf8-1000-word`. The field was built under
the new policy. An install still running the old one would compute a different
identity, and the two populations would not be comparable.

So `library.py` travels with the field as a declared `replace`, and the
importer **recomputes the identity from the installation it is running inside**
— the model file on disk and the truncation policy in the installed
`library.py` — and refuses outright if they disagree. The two halves are
mechanically inseparable. Shipping either alone is the exact silent failure
the identity string exists to prevent.

---

## What is actually in the field

- 15,000 embeddings, 384 dimensions, in the shelf's own `fair_rank` order
  (built-ins first, then user sources in round-robin rounds).
- Stored as **SABLEVEC1**: one vector per row, three dimensions per pixel
  through RGB, affine uint8 quantisation with a single scale and offset for
  the whole file.
- A gzipped sidecar carrying the vector identity, the dimensions, and one
  `content_hash` per row.

Quantisation is lossy and the cost is measured rather than assumed: **mean
cosine 0.99993 against the original float32, worst case 0.99992**.

Rows are keyed by `content_hash` — `sha256(title\nheading\ntext)` — not by
chunk id, because ids belong to whichever machine indexed the shelf. A chunk
that is not on your installation simply goes unfilled, and an existing vector
is never overwritten. The import is idempotent.

## What it does not require

Nothing. `library semantic on` controls the persistent *backfill* — whether
the assistant embeds new chunks in the background. It does not gate search.
Once the field is imported, semantic retrieval works immediately on a fresh
install, with no local embedding pass and no setting to change.

Lexical search continues to cover the whole shelf, including the ~107,000
chunks deliberately outside the 15,000-row ceiling.

## What it is not

It is not the whole shelf. The embed target is bounded at 15,000 by
`EMBED_GLOBAL_CEILING` on purpose: embedding all 122,129 chunks would produce
roughly 190 MB of vectors, most of which nothing would ever read. The field is
the top 15,000 by fair rank, and the remainder stays lexically searchable.

It is also not a claim that retrieval is *correct*. A retrieved passage is not
proof that it is current, complete, applicable, or correctly interpreted.
