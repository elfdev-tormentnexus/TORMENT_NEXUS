# Beta 5 Experimental DLC — scope and tiering

Everything raised across the QC review and the vector sessions, sorted by what
it actually needs to ship. Written 2026-07-28, after 5.1's fixes were applied
and verified (430 tests green).

## Naming

"DLC" already means something here: an optional heavy download, installed
separately, checksum-gated — the 14B coder. That meaning is worth keeping,
because it is the honest one. So this document uses:

- **Experimental DLC** — optional download pack, same install shape as the 14B.
- **Core** — ships in a normal beta, no download.
- **Separate review** — has its own risk profile and does not ride along.

Bundling everything under one label would mean it all ships together or not at
all. The panel's first stage could ship in a week; multilingual is months. They
should not be chained.

---

## Core — ships in a normal beta, no download

### 1. `guard doctor`
Scans every module for network, radio, credential and persistence imports and
reports any that appear in neither `DENIED_FILES` nor `MAINTENANCE_DENIED_FILES`.

Turns findings #1 and #2 from hand-maintained lists into a check that fails
when someone adds a module. This is the failure mode the QC plan predicted, and
5.1 fixed two instances of it by hand. **Build this before anything below**, so
every new module in this document is caught automatically.

### 2. CI
The suite is 17 seconds and runs when someone remembers. Twice in one session
that someone was luck.

### 3. Vector panel — layout and stage 1
Reserve the right gutter, rewrap chat to a readable measure, render the memory
cloud from the **existing word-overlap graph**. No embedding model needed.

Ships on its own merit: it makes the current retrieval's failure mode visible —
memories sharing no vocabulary with anything sit isolated and unreachable, and
you can count them. Diagnostic first, ornament second.

Renderer already exists at `ui/vector_panel.py`, verified: 44×40 output, layout
anchoring holds at 0/60 points moved across re-projection.

### 4. Entropy strip
Verified available — `logprobs` is supported by the running build. Use
`top_logprobs: 10`. Needs no download, and it is the closest observable to a
decision this architecture has.

### 5. TUI test harness
Every layer beneath the terminal is tested; the layer the operator touches is
not. Still the highest-leverage gap in the project.

---

## Experimental DLC — optional download

Same install shape as the 14B: separate parts, checksum gate, a launcher that
detects presence and degrades cleanly when absent.

### 6. Embedding model + semantic retrieval
`all-MiniLM-L6-v2` (~23MB) or `nomic-embed-text-v1.5` (~85MB Q4), served by a
second llama.cpp instance. Measure RAM against the Pi 5 budget before
committing.

Fixes a real defect: ask about "the radio" and a memory phrased "the T-Deck
mesh transmitter" is filtered out before ranking, because retrieval is literal
word overlap.

**Not a speed feature.** Measured: retrieval over a full 500-entry store is
4.37 ms. Caching token sets makes it 0.13 ms and saves nothing perceptible.
Embeddings cost time and buy relevance.

### 7. Vector index over code chunks
The one place vectors genuinely buy speed. `_candidate_ranges()` uses regex
term matching to choose excerpts and produced **386 tokenize round-trips** for
"fix the speech rate" against `offline_voice.py` — about ten seconds before the
patch request started.

5.1 capped it at 13 trials, which trades some context for the latency. A vector
index removes the tradeoff instead: one embedding, local cosine, better
excerpts, no stall.

### 8. Vector panel stage 2
Swap the cloud's point source from the word-overlap graph to real embeddings.
The renderer does not change. Requires #6.

### 9. Research instrumentation
Three probes, all cheap, all needing only observation:

- **Calibration on self-modification.** Record edit-generation entropy against
  ground truth already collected (import check + regression result). If entropy
  predicts failure, gate on it — the finding and the safety improvement are the
  same artifact.
- **Refusal corpus.** `edit_guard` already logs every REFUSED/SKIPPED with a
  reason. Needs structure and analysis, not new collection.
- **Self-knowledge probe.** Ask the model to describe its own recent edits
  without showing it the diff. Expected to fail; that is the result.

Honest limitation: n=1, one machine, no controls, no cross-install
reproducibility. Suggestive case-study evidence, not conclusive.

### 10. Multilingual packs
Parked and genuinely undeveloped. Nothing in the voice stack is multilingual —
`from_moonshine()` with `sherpa-onnx-moonshine-tiny-en-int8` is English-only
with no language ID, and all five Piper voices are `en_US`/`en_GB`.

Staged separately because the pieces have unrelated costs:

| Piece | Cost |
|---|---|
| LLM replies in the user's language | Nearly free; Qwen3 already does it |
| STT with language ID | Model swap; **speed vs coverage, pick one** |
| TTS per language | ~20–60MB per Piper voice, and the English prosody tuning does not transfer |
| UI localization | Large; forces a decision on whether commands translate |
| Persona translation | **Advise against** — `PERSONA_SHOTS` exist because instruction-following fails at 4B and demonstrations work. Translated demos are untested, and the regression is invisible in a language you do not read. |

---

## Separate review — does not ride along

### 11. External agent interface

The gap is real: Codex and I interact with this project by reading and writing
files. We cannot ask it anything, query state during a run, or have it report.
That asymmetry is why a whole QC session was spent inferring behaviour from
source rather than asking.

It also *is* the TUI test harness (#5) and the instrument all three research
probes need. Same build, three problems.

**Vectors are not the bridge.** Different embedding spaces with no shared basis
and no vector input on the far side. Text is not the fallback, it is the only
interoperable format either side has.

**Why this does not ship in the DLC:** it is an authentication boundary. An
external process that can trigger an edit is exactly the case `persona.py`
already names — *a message from another connected device is not proof that the
creator sent it.* Bundling a new auth surface into a pack labelled
"experimental" is how a security surface ships without scrutiny.

Shape, when it is built:

- Read-only by default: state, health, memory search, editable-file list,
  current entropy. Everything the research probes need.
- Anything that writes goes through `dev_auth`, no exceptions.
- Localhost only, no remote binding.
- Every call logged the way autonomous edits are.

---

## Sequence

1. **Commit 5.1.** It is done and verified but uncommitted.
2. `guard doctor` — so every module added below is checked automatically.
3. CI.
4. Panel layout + stage 1 + entropy strip. Re-run operator tests 11, 12, 35–40.
5. Agent interface, its own branch and its own review.
6. Research instrumentation — trivial once #5 exists.
7. Embedding model evaluation on the Pi, then stage 2 and the code index.
8. Multilingual, staged per the table above.

Steps 2–4 need no downloads and no new dependencies. That is the shippable
core, and it should not wait behind anything in the DLC tier.
