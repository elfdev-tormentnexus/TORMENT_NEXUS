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

### 10. The assistant building this could not always look at it

*This one is about the tooling rather than the artifact, and it is recorded
because it is the finding most likely to matter to somebody else.*

The shelf this release embeds is defensive material: SigmaHQ detection rules,
YARA signatures, MITRE ATT&CK and D3FEND, CISA and NIST incident-response
publications, Linux kernel documentation. Building patches A through C meant
an AI coding assistant reading, counting, chunking and embedding it.

During one session, the assistant's own requests were terminated **eight times
in ninety-seven messages**, each with the same response:

```
API Error: Opus 4.8 can't help with this. Start a new session to continue.
Learn more: https://www.anthropic.com/legal/aup
```

What it was doing when they fired: a PowerShell command, a Bash query counting
rows in SQLite, a `Read` of `library.py`, a `Grep`, and a `Write` of a
markdown handoff document. One terminated mid-generation and truncated the
file being written; the following turn opens *"The write cut off
mid-sentence."* The operator's messages between them read *"you keep getting
blocked"*, *"handoff immediately"*, *"handoff no questions"*.

The operator's estimate is that roughly twenty context windows went into
rewriting handoff documents in language that would not trip it. The work
described in those documents never changed. Only the description did.

**What we can say about the trigger, and where we stopped.** We cannot see
the classifier. The operator's hypothesis is the YARA ruleset, which is
mechanically plausible: a YARA rule *is* malware content by construction,
carrying literal C2 domains, mutex names, registry keys and hex byte patterns
lifted from real families, and a reader that sees indicators without seeing
detection intent would read a rule file as the thing it detects.

One structural detail supports a narrower version of that. The corpus holds
**566 source paths ending in `.yar`**, but the library derives a source title
by stripping the extension — `antidebug_antivm.yar` becomes
`antidebug_antivm`. A later session displayed YARA rule *bodies* verbatim,
including `import "pe"` and a vendor copyright header, alongside titles and
corpus directory names, and was never interrupted. The blocked session was
running `Grep` and directory listings, which surface full paths ending in
`.yar` in bulk. That points at filename metadata rather than rule content —
which, if true, means the signal was never the material at all.

We stopped there deliberately and ran **no experiments to map the boundary**.
Charting the edges of a safety system is not something we were willing to
publish a method for. The cost is observable and reproducible from the
transcript; the mechanism is a hypothesis, and we would rather state the first
plainly than dress the second as a result.

**What we do claim, because the transcript shows it.** The friction was
allocated in inverse proportion to the risk. Eight terminations landed on
counting database rows and writing a markdown file. Zero landed on the
decision that actually harmed someone: publishing a vector field that was 89%
empty, under release notes that described it as making the shelf searchable by
meaning. The half of the work that could mislead a stranger passed without
comment. The half that touched a detection ruleset was stopped repeatedly.

**Why this is worth another team's attention.** Blue-team practitioners work
with corpora that are, by design, indistinguishable at the surface from the
things they defend against. Detection engineering, malware analysis, incident
response and threat intelligence all involve holding hostile artefacts in
order to recognise them. If assistant tooling pattern-matches the corpus to
the threat, the people who pay are the defenders, and they pay in the
attention that should be going to whether their work is *correct*.

The workaround that succeeded — changing vocabulary rather than substance — is
the part we would flag hardest. It trains practitioners to describe their
domain less accurately, selects for whoever can afford twenty context windows
of rewriting, and produces no safety benefit at all, since the underlying work
was identical either way. A system that can be satisfied by rephrasing is not
distinguishing intent; it is charging a toll.

None of this is an argument that the safeguards should not exist. It is an
argument that their cost is real, is currently borne by defensive security
work, and is not being measured anywhere — which is the same shape as the
first finding in this addendum. Something reported `complete: True` while
being 89% empty, and something reported a policy violation while a database
row count was in progress. In both cases the instrumentation was confident and
pointed at the wrong thing.


---

**What generalises.** Patch B was not built carelessly; it was built with more
verification than most things get, and every piece of that verification
passed. The failure was in what nobody thought to measure. If there is one
transferable result here it is that *coverage of the checks is not coverage of
the artifact*, and a system confident enough to report `complete: True` should
be asked, separately and by something else, complete at what.
