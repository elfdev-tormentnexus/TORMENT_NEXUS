# Handoff — QC review, 5.1 patch, and the experimental branch

Written 2026-07-28 at the end of the session that executed
`QC_REVIEW_PLAN.md`. For a fresh context picking up the work.

## State

- **Branch:** `beta-5.1-guardrail-and-latency` (not merged, not pushed)
- **Base:** `ef10a4c` — Codex's `v0.2.0-beta.5` release, already on GitHub
- **Suite:** 497 tests, green, ~20s
- **Untracked and not mine:** `CODEX_HANDOFF.md`, `README_DRAFT_BETA5.md`.
  Leave them alone.

| Commit | What |
|---|---|
| `fe4cb72` | The five 5.1 fixes plus tests |
| `6e1fc82` | Three plan docs, the panel renderer, the logprobs probe |
| `4676b95` | `guard doctor` plus tests |
| `8bd8f28` | Handoff to a fresh context |
| `b5f7947` | `offline_voice.py` and `stream_filter.py` off the unattended list |
| `9cdefda` | POSIX launchers pointed at the project root |
| `1b7f2cd` | CI: the suite on every push |
| `7feb0ef` | Panel gutter reserved, chat rewrapped |
| `edd33a9` | Two gitignore rules anchored |
| `da178cf` | Memory cloud rendered (stage 1) |
| `b9bdaad` | Entropy strip fed from logprobs |
| `6bea453` | Music cube bounced against its drawn size |
| `7b3507d` | Read-only agent interface |

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

From `BETA5_DLC_PLAN.md`. Steps 1–6 are done.

7. **Research instrumentation.** The three probes in `BETA5_DLC_PLAN.md` §9.
   Now genuinely cheap: the agent interface is the instrument they needed.
8. **TUI test harness.** Still the highest-leverage gap — every layer beneath
   the terminal is tested and the layer the operator touches is not.
9. Embeddings, then panel stage 2, then the code index. **Blocked on
   hardware:** the Pi 5 has not arrived, and the plan says to measure RAM
   against its budget before committing to a model.
10. Multilingual, staged per the table in the plan. Months, not days.

### Open, and owed a real answer

- **The streamed logprobs shape and cost are unverified.** The suite shuts
  the model server down when it finishes, so there was none running by the
  time the strip was built. `tools/probe_logprobs.py` established the
  *non-streaming* shape; the streamed one is assumed to match and the parser
  is written to survive it not matching. Start the app and re-probe before
  trusting the latency.
- **Operator tests 11, 12 and 35–38 have not been re-run.** The panel
  geometry is covered by nine regression tests and was eyeballed as a
  rendered frame, but nobody has driven it by hand.
- **The agent interface wants a proper review.** It landed here because it
  was asked for; `BETA5_DLC_PLAN.md` keeping it out of the DLC tier because
  it is an auth boundary has not stopped being right.
- **`guard doctor` still reports four**, unchanged and unresolved by design.

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
