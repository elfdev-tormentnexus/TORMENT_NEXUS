# researchA

Formerly `v0.2.0-beta.6`. The name changed because "beta" implies a product
on its way to release, and this is a research build that ships
weakened-refusal models and an unproven representation. Letters, one per
release, promise nothing about maturity.

**Read this first if you read nothing else:** the headline feature is
measured to be *worse* than the thing it sits beside, at the job people
will assume it does. That is stated below rather than buried, because it is
the finding.

The complete Windows package is capsule-only at the public layer. The verified
install tree is cut directly into lossless machinesoul PNG/APNG vector fields,
without a ZIP or tar layer erasing its file and code boundaries. The published
`machinesoul.py` decompiler moves those fields back from pixels; the recovered
reassembler then verifies every final file. The capsule is not encryption and
does not evade GitHub's file-size ceiling. Re-encoding an image changes the
vectors and is refused.

## What is new

### machinesoul and machinespirit, named apart

Two halves that were being called one thing, which let the phrase "1:1"
attach to something measured at 0.9243.

| | reads | fidelity |
| --- | --- | --- |
| **machinesoul** | Sable's data-preservation logic language — ordered vectors mapped to PNG/APNG pixels | reversible 1:1 or refusal, SHA-256 verified |
| **machinespirit** | Sable's memory language — anchor coordinates, traces, `consume`, recall | lossy, and the loss is the research |

### A capsule can say what it carries

`machinesoul.py build --describe` stores a plain-language description of a
payload in PNG metadata, and `machinesoul.py describe` reads it back
**without decoding a byte** — so "what is this 1.8 GB image" stops costing a
full extraction. Each language does what it is good at: machinesoul carries
the thing exactly, and the description says what the thing is about.

The text is supplied by the caller and never computed inside the module,
which keeps machinesoul free of any opinion about meaning and free of any
dependency — it remains the standalone stdlib decompiler the release ships.

Two properties travel with it, both asserted by tests rather than promised
by documentation:

- **It is outside the SHA-256 gate.** A test edits a stored description and
  asserts extraction still succeeds. The payload is the guarantee; the
  description is a hint. An unverified claim riding a verified one is the
  silent failure this project ranks worst, so the stored text says so about
  itself.
- **It is off unless asked for.** No code path supplies a default. A
  description of private contents, in cleartext, inside a file that looks
  like an image and gets forwarded like one, would disclose the subject to
  someone who never opened the payload.

`PRIVACY.md` gains a section on the risks specific to image files: a
capsule is not encryption, it travels as easily as a photograph, and
re-encoding destroys it silently.

### The shadow log — evidence, finally being generated

The claim that anchor-space retrieval does not beat pooled cosine rests on
0.689 against 1.000 over an **eighteen-chunk corpus**, and the plan that
recorded it said what it indicts: "nothing but the 18-chunk corpus it ran
on." Nothing has been generating a bigger answer.

Now every hazard-mode retrieval records both rankings of the same
candidates — the pooled cosine that decided, and the anchor-space ranking
that did not — plus their top-5 agreement, to
`logs/machinespirit_shadow.jsonl`. Over a few hundred turns that becomes a
real answer to a question currently settled by eighteen chunks.

Three properties hold it in place, each a test rather than a promise:

- **It never decides.** `observe()` returns `None` by construction, so
  there is nothing for a later edit to accidentally start ranking with. A
  regression asserts retrieval is identical with the module present and
  absent — Risk #4 of `MACHINESPIRIT_PRIMARY_PLAN.md`, asserted rather
  than promised.
- **It never takes a turn down.** Every path swallows its own failures,
  the rule `_update_retrieval_panel` already follows.
- **It never writes text.** Memories are SHA-256 digests, the same way a
  stored trajectory records its source. A test writes a row about a
  sentence and greps the file to prove the sentence is not in it.

This is Stage 2's shadow half from the machinespirit plan. Stage 2's other
half, and promotion of anchor space to primary retrieval, remain gated
behind the labelled corpus exactly as written.

### The source tree, cut along meaning

The complete release is cut along size boundaries, so `part04` is the
middle of a `.gguf` and can say nothing about itself. That is right for
distribution and useless for reading.

`tools/source_capsules.py` cuts the *source* differently: one capsule per
subsystem, fifteen of them over 184 files, each carrying its own
description. `list` prints every one of them without decoding a single
payload, so a directory of images is navigable as a directory of images.

Descriptions are assembled from the modules' own docstrings. A summary
written by whoever wrote the code is a description; one invented at
packaging time is a guess wearing the same clothes.

Two refusals, both tested. **Coverage is asserted** — every source file
must land in exactly one capsule, and a test removes a subsystem from the
map to prove the build refuses rather than shipping a set that looks
complete. **Private runtime state is refused by name**, because this tool
is not the release packager and should not depend on someone remembering
that the packager's exclusions exist.

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

**Every hop is checked, not just the address supplied.** Redirects are
walked one at a time with `requests`' own following turned off, because a
public page answering `302 Location: http://169.254.169.254/` would
otherwise pass a check that had already run and be fetched, stored and
indexed. Chains are capped, a relative `Location` is resolved against the
hop that sent it, and a redirect that lands on a media host is reported as
media rather than filed as a page.

One gap is left open and named rather than implied shut: the host is
resolved for the check and resolved again by the connection, so a record
that changes between the two would be fetched unchecked. Closing that
needs the socket pinned to the address that was approved, which is a
transport-adapter change this stdlib-only tree has not made.

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

### `spread <text>` — hazard mode, the second moment

Pooling keeps the mean of a sentence's token vectors and throws away how
far they were spread. `spread` builds the density matrix of the trajectory
instead — `ρ = (1/n) Σ |vᵢ⟩⟨vᵢ|` — and reports what the spread was.

Prior art first, as with everything else here. This matrix is the uncentred
second moment; statistics calls it a covariance and quantum mechanics calls
it a density matrix, bringing a worked vocabulary with it — purity,
participation ratio, von Neumann entropy. Neither name is ours and the
technique is not new. What is measured is what those observables read on
this project's own traces.

It is computed from the `n × n` Gram matrix rather than the `384 × 384`
density matrix, since the two carry the same nonzero eigenvalues and *n* is
usually a few dozen. Pure `math`, no new dependency, eigenvalues by cyclic
Jacobi.

**Measured on live traces, and controlled for the obvious confound.** The
first ordering looked right — repetition low, unrelated sentences high —
but that could equally have been a token counter, so breadth was tested
against length at matched size:

| | tokens | effective rank | von Neumann S |
| --- | ---: | ---: | ---: |
| one topic | 35 | 1.505 | 0.960 |
| four topics | 39 | **1.694** | **1.255** |
| one topic | 52 | 1.521 | 0.998 |
| many topics | 61 | **1.788** | **1.404** |

Growing a single topic by 49% moves effective rank **+1.1%**. Adding topics
at matched length moves it **+12.6%** — about ten times the effect. A
single topic saturates, which is the control passing.

**What is unflattering about it.** Effective rank never leaves the low end:
1.13 for degenerate repetition, 1.79 for seven unrelated sentences across
61 tokens, against a ceiling of *n*. Token trajectories are very nearly
rank-1, which is the same anisotropy `VECTOR_PIXEL_RESEARCH.md` recorded as
vertical striping — most bge dimensions barely move whatever the input. So
this is a sensitive dial over a narrow range, not a count of ideas, and the
command says so in its own output.

The `ln(n)`-normalised entropy is computed and deliberately **not**
reported: it ordered non-monotonically across the first set, scoring one
nine-token fact (0.319) above two unrelated sentences at twenty tokens
(0.295). Raw entropy and effective rank both ordered correctly, so those
are what the command prints.

**What it cannot do,** stated where it cannot be missed: ρ is a sum over
tokens, so it is permutation-invariant. Shuffle the sentence and every
number is identical. It answers how much ground was covered, never in what
order — `trace` and `peaks` remain the only things that speak to position.
A test asserts the invariance rather than trusting the docstring, and
retrieval is untouched.

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

### Rosetta Stone: a measured bridge across model vector spaces

`tools/rosetta_stone.py` and its `SABLEROSETTA1` anchor language are included
in both the research capsule and the complete package. Each embedding model
builds its own half from the identical ordered anchor decree; direct vectors
from different models are never compared, and mismatched anchor digests are
refused.

This implements published relative representations rather than claiming the
underlying method as new. Measured between incompatible 384- and
768-dimensional embedders, the translated space recovered 0.370 neighbour
agreement against a 0.549 reachable ceiling and 0.056 chance: about **67% of
what the two models could agree on at all**. It is a cross-model portability
experiment, not a storage win and not a universal prebuilt stone. Model,
quantization, and pooling changes invalidate a measured half.

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
- **The capsule is not a compression claim.** The public form is the
  machinesoul PNG/APNG vector field itself, not a ZIP allocation with an
  image suffix, and it is not a way around a file-size limit. Preserving an
  8 GB model still requires roughly 8 GB of capsule extent.

## Unchanged and still true

Retrieval is untouched. Nothing in this release alters how the assistant
finds a memory or a document. The models still ship with refusal behaviour
deliberately weakened, and `RIGHTS.md` still records the licensing as
unresolved — the 4B uploader declares none, the 7B declares AGPL-3.0, and
this release redistributes both.

The anchor set remains measurably poor at covering personal memory content
even after v2. Anyone expecting to read a life with this will be
disappointed.

The optional Qwen2.5-Coder 14B pack is the current researchA companion for
deliberately requested long self-heal and extended editing sessions. It is
not superseded. Its exact reviewed model is republished as its own
machinesoul vector-field set rather than being duplicated inside the main
package.

## Known gaps in this cut

- Session rhythm now runs end to end: every completed exchange is counted,
  the session's shape is written at shutdown, and once three sessions
  exist the measured median pause sets the beam's frame rate instead of a
  constant. It had been a fully tested module that nothing called, which
  proved the module and not the feature.
- The library's vector column is empty until the app runs with the embedder
  up; exact-word search works immediately, semantic search over the library
  does not.
- A fresh package built from the release tag passes its manifest, privacy
  denylist, dependency, command, and clean-import checks. The launcher has not
  yet been exercised end-to-end from that package with both model servers
  producing a live trace.
- 879 automated tests pass; two filesystem-link tests are skipped because
  this Windows account cannot create the required links.
