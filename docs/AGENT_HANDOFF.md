# Handoff to the next agent

Written by Claude at the end of a long session, for whoever picks this up
next. Read this before changing anything — several of the constraints
below look arbitrary and are not.

---

## What this is

**TORMENT_NEXUS** — a private AI companion that runs entirely offline on
the operator's own machine. Local model (llama.cpp + Qwen3-4B), local
speech synthesis and transcription, self-hosted search, persistent
memory, guarded self-editing, and a hardware bridge.

The operator is learning by directing rather than by typing. They are
sharp at product judgement, triage, and observation, and are explicit
about wanting **honesty over agreeableness**. Give them real assessments,
including unwelcome ones. They have never once punished a straight answer.

The project is also deliberately an art piece. `README_DIGITALBIOHAZARD.txt`
is part of the work.

---

## Current state

- **173 regression tests, all passing.** This is the gate. Run it before
  and after everything.
- Under **git** since 2026-07-26. Working tree was clean at handoff.
- The shareable package builds, installs, and verifies clean.

### Verified by tests, NOT by a human

Do not describe any of these as working. They are tested mechanisms with
no human ever having seen or heard the result:

| Thing | Status |
|---|---|
| Voice at 155 Hz carrier | never listened to |
| Daisy Bell stopping on Escape | real bug fixed on that path; original failure never reproduced |
| Persona not claiming feelings | prompt changed; model compliance unknown |
| Purple text corruption effect | verified frame-by-frame, never watched live |
| Goal engine | never run against a live model — what it *chooses* is unknown |
| Idle check-in | never actually fired |

---

## Layout

Root holds only `README.md`, `start_assistant.bat`, and folders.

```
assistant/     the application
  core/        config, persona, tutorial, llm_server, dev_auth
  commands/    command registry and handlers
  editing/     edit_guard, edit_engine, autonomous_engine, goal_engine
  voice/       offline_voice (TTS + vocoder + ASR)
  ui/          the animated terminal
  memory/      extraction and storage
  hardware/    T-Deck / Meshtastic bridge
  tests/       test_regressions.py — the gate
tools/         package_release.py, glitch_icon.py
setup/         requirements*.txt, installers, test_assistant.bat
docs/          this file, benchmarks, the biohazard readme
assets/        icons
workshop/      the goal engine's sandbox (gitignored)
```

`start_assistant.bat` stays at root: the desktop shortcut and the release
package both target it.

---

## Commands

```
setup\test_assistant.bat                      173 tests — run always
python tools/package_release.py --skip-download   rebuild the handoff
python tools/package_release.py --sanitize        after test-running setup.bat
```

---

## Constraints that are load-bearing

### Do not widen `edit_guard` without a reason as good as the ones in it

It denies `main.py`, `commands/command_handlers.py`, `core/config.py`,
`core/dev_auth.py`, `ui/ui.py`, `core/persona.py`, `editing/` and `tests/`.

The stated argument: *an editor that can rewrite the code asking for
approval makes approval theatre.* `persona.py` and `tests/` were added on
the same grounds — the persona holds its own honesty rules and goes into
every prompt, and a suite the subject can edit stops being evidence.

### The goal engine cannot execute, and cannot write outside `workshop/`

`editing/goal_engine.py`. That single property is the whole safety story.
Paths resolve via `realpath` and are re-checked against the workshop root;
only `.md/.txt/.json/.csv`; one action per run; capped per file, per goal,
and in total. It lives under `editing/` so it cannot widen its own limits.
Off unless `TORMENT_NEXUS_GOALS=1`.

If you extend it, do not add execution. That is a different and much
larger thing to be responsible for.

### The model is abliterated

`Qwen3-4B-Instruct-2507-Abliterated` — refusal behaviour surgically
removed. Architecture and chat template are stock, so nothing is broken,
but it is likely **more compliant than the persona asks for**. Relevant
any time push-back, self-restraint, or honest disagreement matters.

---

## Traps that have already cost hours

**Building a package, testing it, then sending it ships secrets.**
Running `setup.bat` makes the assistant generate its API key and
initialise its memory store *inside the staged package*. Always
`--sanitize` after a test-run. The verifier catches it; trust it when it
refuses.

**Pin OpenBLAS threads for any numpy/librosa work.**
`OPENBLAS_NUM_THREADS=1` (plus `OMP_`, `MKL_`, `NUMEXPR_`). On 16 cores it
exhausts memory and then **hangs rather than erroring** — it once ate a
20-minute call silently.

**A tiny allocation failing is not a corrupt model.**
Windows commit charge fills over days of uptime until a 2 MB allocation
fails and ONNX reports a wall of arena detail. Check
`Get-Counter '\Memory\Committed Bytes','\Memory\Commit Limit'` before
touching code. A reboot clears it.

**Explorer's icon cache is keyed on path, not contents.**
Rewriting an `.ico` in place is invisible to it, even after `ie4uinit`.
This is why `tools/glitch_icon.py` uses a separate file per frame.

**Don't let the icon animator rename desktop shortcuts.**
`TORMENT_NEXUS_GLITCH_LABEL` is off for a reason: renaming a `.lnk` ten times a
burst leaves ghost entries in the desktop view. Recovery quarantines,
never deletes — an earlier version deleted, and a shortcut went missing.

---

## Known next task

**Split the large source files.** `ui/ui.py` (2475 lines),
`voice/offline_voice.py` (2128), `main.py` (2004),
`commands/command_handlers.py` (1662).

This is a fair review criticism and genuinely worth doing. It was
deliberately *not* attempted in the same pass as shipping a new feature —
every import moves, `edit_guard`'s denylist is keyed on those exact paths,
and a half-finished split is worse than none.

Do it in its own session, one file at a time, with the 173 tests as the
gate after each. `command_handlers.py` splits most cleanly along its
existing command groups.

---

## Working with two agents

Both Claude and ChatGPT are editing this repo. Git is the defence:

- `git diff` before you start, to see what the other one changed
- Commit in coherent units with the reasoning in the message
- If something mysteriously stops working, suspect two independent fixes
  layered on the same bug — that usually presents as one of them silently
  not taking effect

Watch for overlap on the dev-mode gate, the persona wording, and
`_play_audio`.
