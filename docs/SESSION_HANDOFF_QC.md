# Handoff — QC review, 5.1 patch, and the experimental branch

Written 2026-07-28 at the end of the session that executed
`QC_REVIEW_PLAN.md`. For a fresh context picking up the work.

## State

- **Branch:** `beta-5.1-guardrail-and-latency` (not merged, not pushed)
- **Base:** `ef10a4c` — Codex's `v0.2.0-beta.5` release, already on GitHub
- **Suite:** 436 tests, green, ~19s
- **Untracked and not mine:** `CODEX_HANDOFF.md`, `README_DRAFT_BETA5.md`.
  Leave them alone.

Three commits:

| Commit | What |
|---|---|
| `fe4cb72` | The five 5.1 fixes plus tests |
| `6e1fc82` | Three plan docs, the panel renderer, the logprobs probe |
| `4676b95` | `guard doctor` plus tests |

## What was done

Part 1 of `QC_REVIEW_PLAN.md` ran against `editing/`, the guardrails, the
untrusted-input paths, the error paths, and the release packaging. Findings
are in `QC_FINDINGS_BETA5.md`. **All five actionable ones are fixed and
individually verified**, not merely described.

Then, at the operator's direction, three planning documents for experimental
work: `VECTOR_PANEL_PLAN.md`, `BETA5_DLC_PLAN.md`, and the tiering that keeps
"DLC" meaning an optional heavy download.

## Decided — recognition and formulation are protected

The operator's call: protect the central elements. Applied.

- `voice/offline_voice.py` removed from `AUTONOMOUS_ALLOWED_FILES` and added
  to `MAINTENANCE_DENIED_FILES`. It holds the microphone, the recogniser and
  speech synthesis. The allowlist rationale ("presentation, voice") was true
  of how replies *sound* and false of the half that owns capture; both share
  one 98KB file.
- `core/stream_filter.py` added to `MAINTENANCE_DENIED_FILES`. It decides
  which model output the operator ever sees, and only the 7B tier had been
  excluded from it. An unreviewed change could suppress output and look
  exactly like the model having said less.

Both stay editable with a human reviewing the diff. The unattended surface is
now five files, none holding hardware or display capability.

**The follow-up worth doing:** split capture and recognition out of
`offline_voice.py` into their own protected module. That would let the prosody
tuning — genuinely a good self-improvement target — return to the unattended
list without dragging the microphone with it. Not done here because splitting
a 2,800-line file is a refactor, and this was a boundary decision.

`guard doctor` still reports four lower-stakes modules with the same shape:
`core/health_check.py`, `memory/memory_extractor.py`,
`visualizer/music_metadata.py`, `visualizer/local_player.py`. Unresolved by
design — each is a question, not a bug.

## Next, in order

From `BETA5_DLC_PLAN.md`. Steps 1–2 are done.

3. **CI.** The suite is 19 seconds and runs when someone remembers.
4. **Panel layout, alone.** Reserve the right gutter, rewrap chat, draw an
   *empty bordered panel*. No rendering. Re-run operator tests 11, 12 and
   35–38. This is the risky change — it touches chat wrap, the input line and
   the pager. `ui/vector_panel.py` already works standalone, so the renderer
   is not the risk; the geometry is.
5. Stage 1 cloud + entropy strip.
6. Agent interface — own branch, own review. It is an auth boundary.
7. Research instrumentation, then embeddings, then multilingual.

## Facts that cost real time to establish

Recorded so they are not re-derived.

**Environment**

- `edit_guard.PROJECT_ROOT` is the **`assistant/` folder**, not the repo root.
  All guard-relative paths are relative to it.
- The Bash tool's cwd persists across calls and *will* drift. Use absolute
  paths or `cd` explicitly every time.
- The console is cp1252. Printing block or braille characters needs
  `PYTHONIOENCODING=utf-8` or it raises `UnicodeEncodeError`.
- **The model server shuts down when the regression suite finishes.** Anything
  needing a live server must run while TORMENT itself is up.

**Measured, not guessed**

- Regression suite: 436 tests, 17–19s. `VALIDATION_TIMEOUT_SECONDS = 120` is
  comfortable.
- Memory retrieval over a full 500-entry store: **4.37 ms**. Caching token
  sets gives 0.13 ms — a 35x speedup that saves four milliseconds. **Retrieval
  is not a bottleneck.** Do not "optimise" it.
- `edit_generator._candidate_ranges` produced **386 candidate ranges** for
  "fix the speech rate" against `offline_voice.py`, each formerly one
  `/tokenize` round-trip. Now capped at 13.
- `logprobs` **is supported**. Use `top_logprobs: 10` — at 5 the observed
  spread was 0.39–0.87, at 10 it was 0.00–0.72.
- Entropy is **front-loaded**: two tokens scored 0.72 and 0.69, the remaining
  twelve fell to ≤0.03. Once a phrasing is committed the rest is near-forced.
- The sampled token is not the top candidate roughly a third of the time, and
  every instance coincided with high entropy.

**Architecture**

- Chat wraps to the **full terminal width** (`ui.py:2129`). At 220 columns
  that is a 216-character line. Reserving the gutter fixes a real readability
  defect as well as making room.
- `_braille_rows()` (`ui.py:1135`) is generic and packs 8 dots per cell, but
  emits a bare character — **one colour per cell**. Use half-blocks where
  colour carries data.
- `MAX_MEMORIES = 500`, so a 44×40 panel is never pixel-limited.
- "Maximized" is **not detectable** from a terminal. `GetConsoleWindow()`
  returns the hidden pseudo-console under Windows Terminal, which is what a
  `.bat` double-click opens. Gate on available cells; `ui.py:1625` already
  sets that precedent.
- STT is `from_moonshine()` with `sherpa-onnx-moonshine-tiny-en-int8` —
  **English-only, no language ID**. All five Piper voices are `en_US`/`en_GB`.
  Multilingual is a model swap, not a setting.

**Corrections made mid-session, so they are not repeated**

- Contrast stretching for the entropy strip is **not** needed at
  `top_logprobs: 10`. An earlier claim that it was, based on a 5-candidate
  sample, was wrong.
- The deny-pattern/basename invariant is **not uniform**. The deny list mixes
  privacy, copyright and portability motivations, and only the privacy subset
  needs the second check. `icon_anim/.animator.lock` is an explicit exemption.

## Working agreements

- Fixes are **applied and individually verified**, never just described.
- Do not refactor for taste. The comments in this codebase carry hard-won
  reasoning; rewriting them loses it.
- Additive features never mix into a fix patch.
- Report only what surprised you. Confirming documented behaviour wastes
  everyone's time.
