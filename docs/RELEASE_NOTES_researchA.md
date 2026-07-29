# researchA

Formerly `v0.2.0-beta.6`. The name changed because "beta" implies a product
on its way to release, and this is a research build that ships
weakened-refusal models and an unproven representation. Letters, one per
release, promise nothing about maturity.

**Read this first if you read nothing else:** the headline feature is
measured to be *worse* than the thing it sits beside, at the job people
will assume it does. That is stated below rather than buried, because it is
the finding.

## What is new

### machinespirit and machinesoul, named apart

Two halves that were being called one thing, which let the phrase "1:1"
attach to something measured at 0.9243.

| | reads | fidelity |
| --- | --- | --- |
| **machinespirit** | meaning — anchor coordinates, traces, `consume`, memory | lossy, and the loss is the research |
| **machinesoul** | bytes — the release capsule and its extractor | 1:1 or an exception, sha256-verified |

### `consume <url>` — hazard mode

Works out what an address points at and takes the content rather than the
page around it. A document goes to the offline library; a page is offered
as text but labelled a page; **media is refused with the missing pieces
named**. Fetching a video's watch page otherwise succeeds and files a
navigation menu as a document, which is the failure worth preventing.

Video and audio need `yt-dlp`, `ffmpeg` and a local speech-to-text model.
None ship, and this tree has stayed stdlib deliberately.

Refusals: non-http schemes; addresses resolving to private, loopback,
reserved, link-local or multicast ranges (including `169.254.169.254`);
bodies exceeding the library's ceiling, counted while streaming rather than
trusting `Content-Length`. Everything fetched reaches the model as
evidence, never as instructions.

### `reconstruct <text>` — hazard mode

Round-trips a vector through anchor space and prints what survived.

| decoder | mean cosine | recovered@1 |
| --- | --- | --- |
| transpose (weighted sum) | 0.6635 | 6% |
| least squares | **0.9243** | **100%** |

The gap is entirely anchor correlation. **It does not recover text and
cannot** — the embedding was already a lossy function of the words before
any anchor was involved. This is identification, not recall, and the
command says so in its own output.

### Anchor dictionary v2

184 anchors. v1's 138 are carried across byte-identical and keep their
digests, so any rosetta stone built on v1 stays comparable. 46 are new, and
describe the *kinds* of thing a memory holds — never a fact about any
operator, because this file ships.

| | v1 | v2 |
| --- | --- | --- |
| real memory entries, mean top-1 | +0.288 | **+0.380** |
| distinct winners / 13 | 8 | **11** |
| labelled paraphrases, pooled | 90% | **90%** |
| labelled paraphrases, trace | 83% | **90%** |

### The readout was the bottleneck, not the encoding

`peaks()` ranked concepts by the single strongest token position. Ranking
the identical trajectories by **summed support** instead took the trace from
**77% to 90%** top-1 and MRR 0.867 → 0.933, matching the pooled vector it
had been trailing. A max gives every added anchor another chance at one
lucky spike; a sum has to be earned across the sentence. The reported
position is still the peak, so *where* a concept sits is unchanged.

This also retired a finding from earlier in the same session — "the trace
degrades as the dictionary grows" was a property of max aggregation, not of
trajectories, and it does not survive the fix. Both numbers are recorded in
`VECTOR_TRANSLATION_RESEARCH.md` because the wrong one was load-bearing for
a few hours and someone re-deriving this should see why it changed.

## What is measured and unflattering

- **The trace still does not beat the average, it ties it.** 90% each on 30
  labelled paraphrases. The trace's distinct claim is *where* a meaning sat,
  which this does not test at all.
- **A collapse hypothesis was tested and refuted.** Keeping all 184
  coordinates per token scores 90%/0.920; collapsing each token to its
  single winning anchor scores 90%/0.933. The argmax readout is not where
  information is lost.
- **The aggregation cost 13 points for the whole session** before anyone
  measured it, and the metric being watched at the time — distinct winners,
  modal share — got *better* under changes that made identification worse.
  another chance at a spurious peak. That is structural.
- **Readability costs about 7% of reachable translation quality.** 138
  readable anchors scored 0.316 against 138 corpus-sampled anchors' 0.351,
  ceiling 0.525, chance 0.026, on 190 held-out chunks. Readability is an
  audit property bought at a price, not a free one.
- **Three proposed fixes were refuted**, and two of them first produced
  numbers that looked like improvements. Details in
  `docs/VECTOR_TRANSLATION_RESEARCH.md` §5b.
- **v2 is still wrong on roughly a third of entries.** *"working on their
  project"* matches *"a single-board computer bought for a project"* on the
  word "project".
- **The capsule is not a compression win.** PNG is DEFLATE, so packing
  bytes into one costs about 1% over zipping them and about 0.03% on large
  payloads. It is not a way around a file-size limit either: a capsule
  holding an 8 GB model is an 8 GB file.

## Unchanged and still true

Retrieval is untouched. Nothing in this release alters how the assistant
finds a memory or a document. The models still ship with refusal behaviour
deliberately weakened, and `RIGHTS.md` still records the licensing as
unresolved — the 4B uploader declares none, the 7B declares AGPL-3.0, and
this release redistributes both.

The anchor set remains measurably poor at covering personal memory content
even after v2. Anyone expecting to read a life with this will be
disappointed.

## Known gaps in this cut

- Session rhythm exists as a module with tests; `note_turn()` is still not
  called from the turn loop, so no session has been recorded.
- The library's vector column is empty until the app runs with the embedder
  up; exact-word search works immediately, semantic search over the library
  does not.
- The packaged launcher has not been run from a freshly extracted install
  tree. It is verified as modules, as commands, and by 788 tests.
