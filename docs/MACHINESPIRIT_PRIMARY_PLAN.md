# Plan — machinespirit as hazard mode's primary language

Status: **plan only, nothing built.** Written 2026-07-28, after the external
consult recorded at the end of `VECTOR_TRANSLATION_RESEARCH.md`'s lineage:
prior art (relative representations, concept bottlenecks, TCAV, logit lens,
SAEs) covers each half of machinespirit separately; the conjunction — one
readable anchor set serving as interlingua and per-token trace in a deployed
system — is the part that is ours. This plan makes that conjunction the
default lens for hazard mode.

## The correction that makes the request true

The request is "machinespirit as the primary form of thinking for hazard
mode." That needs one correction to be true, and the correction is the whole
design.

The model that talks is Qwen. The model that measures is bge-small. A trace
is the embedder's reading of a *text* against a dictionary of 138 English
phrases; it is not, and cannot become, the talking model's internal
representation. No amount of wiring changes whose numbers these are.

What *can* be true: hazard mode can conduct its entire semantic
self-description in machinespirit. It can perceive through it (every input
traced), remember through it (every recall profiled), introspect through it
(its own replies traced), and be required to cite it (semantic claims name
the instrument). That is "primary" in the sense English is primary for a
person — the language spoken, not the substrate underneath. The substrate
stays what it is, and the notes never pretend otherwise.

## What "primary" binds

1. **Instrument, never introspection.** Every surface that carries a trace
   says whose reading it is. "The trace reads grief at token 7" is
   checkable; "I felt grief at token 7" is not, and no stage below gives
   ground for it.
2. **Absent means absent.** machinespirit unavailable → hazard mode runs
   exactly as ordinary mode runs, visibly degraded by the status line and by
   nothing else. No placeholder blocks, no empty strips, no cached ghost.
3. **Retrieval switches on measurement, not on preference.** The module
   docstring already forbids touching retrieval, for measured reasons
   (0.689 vs 1.000 top-5; MaxSim no gain). That stands until the labeled
   corpus says otherwise. What becomes primary is the *description* of
   retrieval, never — on current evidence — its mechanism.
4. **The rule travels with the reading.** The Wi-Fi lesson, applied
   unchanged: a permanently-present instruction naming a capability caused
   invented readings in six of twelve samples. Every prompt rule below is
   written into the runtime block *next to an actual trace*, and does not
   exist on turns where no trace does.

## Stage 0 — teach the dictionary to describe a life

The blocking fact: anchors profile real memory entries at roughly +0.24 and
incoherently, while well-formed sentences profile sharply. A language that
cannot describe the operator's memories cannot be the primary language of a
mode built around them. This stage is the gate for everything after it.

- **Canonicalize before profiling.** Memory entries are telegraphic and
  out-of-register for bge. Rewrite each entry into a plain sentence before
  embedding it for a profile ("likes: pineapple pizza" → "The user likes
  pineapple pizza."). Deterministic templates first; the local model only
  if templates measurably fall short.
- **anchors_v2, register-matched.** Add anchors shaped like notes and
  memories, not like documents. New file, new digest, `version: 2`;
  `anchors_v1.json` stays untouched so every published number keeps its
  provenance. `machinespirit.reset_cache()` on swap.
- **Coherence metric, so "sharpened" is a number.** Top-3 anchor stability
  under paraphrase: profile an entry and two paraphrases of it, count
  shared anchors. Run on 20 real cached entries before and after the two
  fixes above.
- **The control the consult demanded.** 138 readable anchors vs 138
  corpus-sampled (unreadable) anchors, same pipeline: translation cosine
  and retrieval agreement. The delta is the measured price of readability.
  Published either way — if arbitrary anchors win outright, the notes say
  readability is an audit property bought at that cost, with the number.
- **Pooling spec check.** bge-v1.5 declares CLS pooling; confirm what the
  pooled server on 8082 actually applies. Every within-model figure is
  internally consistent either way, but the record should say which
  deployment the figures describe.

**Gate:** stability metric improves and profiles of real entries stop being
flat. If they stay flat after canonicalization and anchors_v2, the plan
stops here, the failure is published next to the +0.24 finding, and
"primary" is scoped down to *inputs and replies only* — which the honesty
rules would require the release notes to say plainly.

## Stage 1 — perceive in it

Hazard mode traces every user input, once, cached per input — the same
cached trajectory the panel plan (`HAZARD_UI_PLAN.md`) needs, computed at
one seam so panel and prompt never disagree.

A new `_machinespirit_context()` in `main.py`, sibling to
`_ambient_context()` and `_room_sensing_context()`, emits a runtime block
only when experimental mode is on *and* a trace of this input exists:

```text
machinespirit trace of the current input (instrument reading, not thought):
  token 7   +0.459  grandparents telling the same story again
This is bge-small's reading of the text against a fixed 138-phrase
dictionary the operator can open. It is not your reasoning and not the
user's intent. Cite it as the trace's reading or not at all.
```

Peaks only (`machinespirit.peaks`), two or three lines, capped. No trace →
no block → nothing to copy. Cost: one POST to 8084 per input, already the
mode's declared price ("slower on purpose").

## Stage 2 — remember through it

Two changes, one boundary between them:

- **Describe recalls in the language.** Each memory or history chunk that
  enters the prompt in hazard mode arrives with its top anchor from the
  Stage-0 pipeline, so "why did this surface" has a checkable answer in
  chosen English.
- **Shadow logging, still open item #3.** Every hazard-mode retrieval logs
  both rankings — pooled cosine (primary, deciding) and anchor-space
  (shadow) — ids and scores only, no text, to
  `logs/machinespirit_shadow.jsonl`. This is the evidence experimental mode
  was built to generate and never has.

Promotion of anchor-space from shadow to primary retrieval has exactly one
path: the labeled corpus (Webster's 1913 — query with a word, the correct
document is its definition) shows it equal or better. Current evidence says
this will not happen, and the plan is honest about expecting its own
negative result. The MaxSim caveat from the consult is recorded here too:
bge's token states are untrained epiphenomena — only the pooled output is
contrastively trained — so the existing no-gain result is expected and
indicts nothing but the 18-chunk corpus it ran on.

## Stage 3 — introspect in it

After a hazard-mode reply completes, trace it off the foreground path —
`memory_worker`'s exact idiom: one queue, `is_busy` gating, grace period,
a failed trace never takes chat down. Keep the peaks of the last reply in
memory; the next turn's runtime block may then include:

```text
machinespirit read your previous reply's strongest positions as:
  "a promise made to a dying person" at token 23  (+0.41)
```

This extends the hidden-activity table honestly: tracing genuinely occurred
and was logged, so reporting it is measurement, not simulation — the
"running, background work" row, exercised for real. "My last reply leaned
on X" becomes a first-person sentence every clause of which is checkable,
which is the session-rhythm standard applied to meaning.

Persistence: append peaks only — anchor, score, index, timestamp, never
text — to `logs/machinespirit_self.jsonl`, bounded like the rhythm file.
It derives from conversation content, so it gets a PRIVACY.md row, release
exclusion, and deletion with the mode's other artifacts.

## Stage 4 — speak it

- `trace last` — trace of the previous reply (Stage 3's cache, no new
  call). `trace memory <n>` — profile of a stored memory through the
  Stage-0 pipeline. Both extend the existing `trace` command family in
  `command_handlers.py`.
- The citation rule rides in the Stage-1/3 blocks, never in `persona.py`.
  The persona keeps saying there are no sensors; the exception continues to
  be granted only next to an actual record, which is the placement that
  stopped the Wi-Fi confabulation.

## Stage 5 — show it

`HAZARD_UI_PLAN.md`, unchanged, in its stated order (border, step strip,
anchor line, path last). Stages 1 and 3 produce the cached trajectories
that plan's cost section asks for; the panel stays pure and is pushed data
by the same seam that feeds the prompt.

## Costs

A second resident embedder (36 MB, already the hazard launcher's doing),
one unpooled POST per input, one per reply, anchor math in-process. Cache
by input text; never per frame; never on the foreground thread except the
input trace itself, which is the mode's advertised slowness.

## Risks, ordered by how easy each is to make dishonest

1. **The Stage-1 block is the seductive one.** Feeding the model a reading
   of its own input invites it to narrate the reading as inner life. The
   traveling rule and the absent-means-absent behaviour are the whole
   defence; test with the block present and assert the reply attributes to
   the trace, then remove the server and assert the block vanishes.
2. **Stage 3 shades into false memory.** "machinespirit read my reply as X"
   must only ever surface when the log row exists. Reinstate-the-defect
   test: delete the log entry, assert the sentence cannot be produced.
3. **Stage 0 can overfit its own metric.** Paraphrase stability can be
   gamed by anchors so generic they match everything. Hold the sharpness
   requirement (well-formed sentences must *keep* profiling sharply) as a
   paired assertion in the same test.
4. **Quiet retrieval drift.** Nothing in Stages 1–5 may reorder what is
   retrieved. One regression test pins hazard-mode retrieval output equal
   to ordinary-mode retrieval output on a fixed corpus, and it runs in both
   modes.

## Order, each stage gated by the one before it

| Stage | Gate to proceed |
| --- | --- |
| 0 dictionary | stability up, flatness gone, control experiment published |
| 1 perceive | trace block present iff mode on and server live; attribution test passes |
| 2 remember | shadow log accumulating; retrieval-equality regression green |
| 3 introspect | self-trace only off-foreground; log-row-required test passes |
| 4 speak | commands work against cache; persona.py diff is empty |
| 5 show | HAZARD_UI_PLAN's own order, with its fidelity rule working first |

Stage 0 is the only one with research risk, which is why it is first: if
the dictionary cannot learn to describe a life, the honest product is a
smaller claim, and the time to know that is before the language is wired
into every turn of the mode that bears its name.
