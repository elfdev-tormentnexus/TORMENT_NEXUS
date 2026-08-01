# Patch C — shipped, and the optimisation it still needs

Updated 2026-08-01. Every number measured against the live shelf, through the
same code path the assistant uses, not a synthetic benchmark.

## Status

Patch C is **live on the researchC release** and verified end to end from the
shipped artifacts: decode, reassemble, apply, import, 75,048 vectors, semantic
search returning results with no pause warning. 1,397 tests pass.

| | patch B | patch C |
|---|---:|---:|
| Vectors | 15,000 | 75,000 |
| Shelf text reachable | 11.0% | 51.6% |
| Body chunks, not openings | 0.1% | 77.4% |
| MITRE ATT&CK part01 | ~1 vector | 6,306 |
| Quarantined (over 512 tokens) | 106 | 4,724 (6.3%) |
| **Warm semantic query** | ~0.5s | **0.073s** |

Query cost was the last problem and is now fixed: 4.42s per warm query when
the larger field first worked, 0.073s after four measured optimisations. The
first query after a start pays ~5s to build the in-memory field.

## Two bugs found while shipping it, both worth remembering

**The scan limit.** `_semantic` refuses outright once the eligible set passes
the scan limit -- it does not score a subset. Raising `EMBED_GLOBAL_CEILING`
to 75,000 while `MAX_EXPLICIT_VECTOR_SCAN` was 20,000 would have shipped a
field that *silently disabled semantic search entirely*. The comment three
lines above the constant said so. A test caught it after the first upload and
before anyone installed it. The ordering between the two numbers is now
asserted, not assumed.

**`_cosine` is not cosine.** It is a bare dot product that takes both sides
being unit length as given, because the embedding server normalises what it
returns. The first vectorised implementation computed a true cosine -- more
correct in isolation, and silently disagreeing with every score the loop had
ever produced. Caught by comparing the two paths directly: the difference was
3.17, which is impossible for a real cosine and was the tell. Now 6.5e-07.

The general lesson, which cost real time twice tonight: **a verification
suite that checks whether you built the thing correctly will not tell you
that you built the wrong thing.** Every integrity check passed on patch B
while it was 89% empty.

## Where the 2.58s goes

Measured at 75,000 vectors on the live shelf:

| Cost | Time | Addressed? |
|---|---:|---|
| Target CTE, window functions over 122,129 chunks, **per query** | ~1.5s | no |
| Loading 75,000 rows including full `text` to return 5 | ~0.7s | no |
| Building and sorting 75,000 Python tuples | ~0.3s | **yes** (argpartition) |
| numpy scoring | 0.1s | **yes** (was 3.98s) |

Scoring is now the smallest item. The arithmetic was never the problem.

## The optimisation: done

All three steps below were implemented, measured and shipped. Query cost went
from 4.42s to 0.073s per warm query, measured through the path the assistant
uses on a fresh install of the patch.

| Step | Warm query | What it was |
|---|---:|---|
| baseline | 4.42s | Python loop, full sort, every row's text read |
| top-N without sorting the rest | 2.58s | argpartition |
| fetch full records only for rows returned | 1.71s | two-phase query |
| hold the scored vectors in memory | **0.073s** | generation-token cache |

The first semantic query after a start still pays ~5s to build the cache.

Three of the four wins were not about the arithmetic -- that was already a
matrix product after the numpy change. They were about not doing work whose
result is thrown away: sorting 75,000 rows to read five, reading the text of
75,000 rows to return five, and re-reading 115 MB of coordinates per question.

**The cache needed an exact change token and the obvious ones do not work.**
`PRAGMA data_version` is unchanged on a freshly opened connection, and
`_connect` opens one per call, so it never sees another process's commit --
verified rather than assumed. A content signature over the vectors costs
0.29s, most of what the cache saves, and cannot separate a same-size rewrite
from no write at all. So writers announce it: one `library_meta` row read in
50 microseconds, bumped at every vector and membership change, including from
the importer's separate process. Two tests hold it: the cache reloads when the
generation moves, and embedding a row moves it.

## Also outstanding

- **`library status` is slow.** `_embedding_state()` runs the target CTE with
  a dozen correlated subqueries and took **over 120 seconds** at a 75,000
  target while a writer was active. The semantic path no longer pays this, but
  status still does. It is the same shape of problem and the same fix applies.
- **4,724 chunks (6.3%) are quarantined** -- over 512 tokens even at a
  1,000-byte bound, concentrated in ATT&CK JSON and kernel schema bodies.
  Lexically searchable, semantically absent. Disclosed on the release page.
  Nine times patch B's rate, because patch C embeds bodies and bodies are
  denser than headers.
- **`icon_anim` is whitelisted for release but untracked in git**, so a
  release test fails on any clean checkout. Predates all of this.

## Environment notes that cost time

- **Close Sable before embedding.** Its worker claims the pass lease.
- **`--log-disable` on any bulk embedding server.** The default verbosity
  wrote **25.8 GB in 50 minutes** at 35 vec/s and filled the disk to 99%,
  which killed the server mid-run. The DB survived intact (`quick_check: ok`)
  because SQLite's writes are transactional.
- **The CUDA runtime is at `llama.cpp/runtime/desktop-cuda-12.4-b9637/`**, not
  the default build, which is CPU-only. GPU embedding ran at 35 vec/s against
  ~5 on CPU. Backend delta measured at 4.57e-05 cosine, ~44x below the
  quantisation step, so mixing CPU- and GPU-computed vectors is invisible in
  the shipped field.
- **Any stall detector must tolerate `waiting-for-retry`**, or it aborts a run
  that is still converging. This killed two runs.
