<!-- Mirrored from the researchC release page addendum, 2026-08-01. -->

# What the three researchC patches measured

*Added 2026-08-01, after patch C. Patch A shipped a corpus, patch B shipped a
vector field that was wrong, and patch C shipped one that was not. Almost
everything below was found by measuring something that had already passed
every check that existed for it. It is recorded because the failures were more
informative than the fix.*

### 1. A verification suite cannot tell you that you built the wrong thing

Patch B shipped 15,000 embeddings. Every check passed: bytes verified against
the release ledger, digests matched, the codec round-tripped bit-identically,
the installer was idempotent, 1,381 tests were green. `library status`
reported `complete: True, coverage 100%`.

The artifact was **89% empty**. 14,979 of its 15,000 vectors were a document's
*opening chunk*, and it reached 11% of the shelf's text. It made document
headers searchable by meaning and was described as making the shelf
searchable by meaning.

Nothing in the system was capable of noticing. `library status` measures
whether the *target* was filled; nothing measured whether the target was worth
filling. The checks answered "did we build this correctly" perfectly, and
"did we build the right thing" not at all. **Those are different questions and
only one of them had instrumentation.**

### 2. Two independent mechanisms produced the same blindness

The selection was a per-source round robin under a global ceiling: every
source gets its first chunk before any source gets a second.

- The shelf has **17,320 sources** and the ceiling was **15,000**. Round one
  never completed, so the rounds collapsed to exactly one.
- Independently, a flat cap of 120 chunks per source excluded **46,941
  chunks** — 38.4% of the shelf, and nearly all of MITRE ATT&CK — no matter
  how the order was computed.

Either alone would have caused it. Fixing one would have looked like a fix and
changed almost nothing, which is the more useful half of this finding.

Fairness was also computed *per source*, so a corpus stored in thousands of
small files out-voted one stored in seven large ones. ATT&CK is 28.8% of the
shelf by chunk count and received about seven vectors. **The metric rewarded
file layout, not content.**

Patch C plans the selection against the whole corpus first — the discipline
the release cutter already used for capsules, applied one layer deeper — and
orders by *proportional depth*, so every source contributes the same fraction
of itself at any cut point.

| | patch B | patch C |
|---|---:|---:|
| Shelf text reachable | 11.0% | **51.6%** |
| Body chunks, not openings | 0.1% | **77.4%** |
| MITRE ATT&CK part01 | ~1 vector | **6,306** |

### 3. Token density is a property of the corpus, and it moved under us

`bge-small-en-v1.5` accepts 512 tokens. The shipped bound was 1,600 UTF-8
bytes, which is comfortably inside that window *for prose*. This shelf is YAML
device-tree schemas, Sigma and YARA rules and kernel documentation, where
identifiers and punctuation inflate tokens per byte. Tokenising a 400-row
sample against the live server: **15.5% of the target exceeded the window**
(p90 554, max 985). Since the embedding request is all-or-nothing, one
oversized row failed its whole batch, making the one-row-at-a-time fallback
the common path rather than the exception.

Tightening to 1,000 bytes put 98.8% inside the window. But the more
interesting number came later: patch B quarantined **0.7%** of its target as
unembeddable, and patch C quarantined **6.3%** — nine times the rate, from the
same shelf under the same bound.

The difference is that patch B embedded headers and patch C embeds bodies.
**A document's opening is systematically less token-dense than its middle**,
so the first patch's own failure to reach body text was also hiding how hard
the body text is to embed. Roughly 4,700 of the densest chunks remain
lexically searchable and semantically absent, and no byte bound fixes that —
a byte bound cannot guarantee a token bound.

### 4. Truncation that lands mid-word is not free

A byte offset lands wherever it lands, usually mid-word: `...creating a
spatially iso`. That fragment becomes subword tokens that mean nothing on
their own, and because this model mean-pools, they are averaged into the
vector beside the real content. Every truncated chunk carried a little noise
in its coordinates.

Backing the cut off to the last whitespace: across 1,375 truncated chunks,
**100% now end on a word boundary, at a mean cost of 6.4 characters.**

### 5. Two constants can be coupled without either one saying so

`_semantic` refuses outright once the eligible set passes the exact-scan
limit — it does not score a subset and present it as complete. So raising the
backfill ceiling above that limit does not degrade retrieval, it **switches it
off**.

Patch C's first upload raised the ceiling to 75,000 while the scan limit was
20,000. It would have shipped a field that silently disabled the feature it
existed to provide — strictly worse than patch B, which at least worked on
headers. A test caught it after upload and before any install. The ordering
between the two numbers is now asserted rather than assumed.

### 6. `_cosine` was not cosine

It is a bare dot product that takes both sides being unit length as given,
because the embedding server normalises what it returns. The first vectorised
rewrite computed a *true* cosine — more correct in isolation, and silently
disagreeing with every score the loop had ever produced.

It was caught by comparing the two implementations directly rather than by
either one looking wrong: the discrepancy was **3.17**, which is impossible
for a real cosine and was the tell. Corrected, the paths agree to 6.5e-07
across 8,000 real vectors with identical ranking.

### 7. The arithmetic was never the expensive part

Holding 75,000 vectors is only useful if querying them is fast. It was not:
**4.42s per warm query.** Four measured steps:

| | per warm query |
|---|---:|
| Python loop, full sort, every candidate's text read | 4.42s |
| Vectorised scoring (1,289× faster in isolation) + top-N without sorting the rest | 2.58s |
| Fetch full records only for the rows actually returned | 1.71s |
| Hold the scored vectors in memory | **0.073s** |

Only one of those four is an arithmetic optimisation, and by the end scoring
was the *smallest* line item. The rest was **not doing work whose result is
discarded**: sorting 75,000 rows to read five, reading the text of 75,000 rows
to return five, and re-reading 115 MB of coordinates for every question.

### 8. The obvious cache-invalidation tokens do not work here

Caching the field needs a change token, and two plausible ones fail:

- **`PRAGMA data_version`** is unchanged on a freshly opened connection, and
  the library opens one per call — so it never observes another process's
  commit. Verified experimentally rather than inferred from the documentation.
- **A content signature** over the vectors costs 0.29s, most of what the cache
  was meant to save, and still cannot separate a same-size rewrite from no
  write at all.

So the writers announce it instead: one `library_meta` row, read in ~50
microseconds, bumped wherever a vector or the target membership changes —
including from the importer's separate process, which would otherwise leave a
running assistant scoring against a population that had just been replaced. A
stale answer here would be indistinguishable from a correct one, which is the
only reason the machinery is justified.

### 9. Things that were measured rather than assumed

- **GPU and CPU embeddings can be mixed.** The vector identity records the
  model and the text policy but not the backend. Measured delta between the
  two: **4.57e-05** in cosine, about **44× below** the SABLEVEC1 quantisation
  step — invisible in the shipped artifact. GPU embedding ran at 35 vectors/s
  against ~5 on CPU.
- **Quantisation costs 0.999899** mean cosine against the original float32
  across all 75,000 vectors.
- **Bulk embedding needs `--log-disable`.** Default server verbosity is fine
  at one query a minute and catastrophic at thousands: it wrote **25.8 GB in
  50 minutes** and filled the disk, killing the run. The database survived
  intact — SQLite's writes are transactional — and the pass resumed from its
  last committed vector.

---

**What generalises.** Patch B was not built carelessly; it was built with more
verification than most things get, and every piece of that verification
passed. The failure was in what nobody thought to measure. If there is one
transferable result here it is that *coverage of the checks is not coverage of
the artifact*, and a system confident enough to report `complete: True` should
be asked, separately and by something else, complete at what.
