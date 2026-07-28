# Beta 5 quality-control review — scope and execution plan

Written 2026-07-28 at the end of a long session, for a **fresh context** to
execute once Beta 5 is uploaded and neither agent is touching the project.

Do not start this in a nearly-full context. A partial audit reads as a
complete one and is worse than none.

## Preconditions

1. Beta 5 uploaded, tag pushed, Codex finished.
2. `git status` clean, no uncommitted work from either agent.
3. Full suite green as the baseline: `python assistant/run_regressions.py`.
4. Record the commit the review starts from. Findings are worthless without
   knowing which tree they describe.

## Part 1 — what an agent can check alone

Work subsystem by subsystem. For each, read every function, not just the ones
tests touch.

- `core/` — config, persona, dev_auth, llm_server, health_check, tutorial,
  system_awareness, time_awareness, chosen_name, stream_filter, file_utils
- `editing/` — the guardrails. Highest value, highest risk.
- `memory/` — extraction, logic, store, worker
- `commands/` — handlers and natural_command
- `voice/`, `visualizer/`, `project/`, `web/`, `hardware/`
- `tools/` — packaging and the collector

Specific things worth hunting, drawn from what this session already surfaced:

- **Docs contradicting code.** Two were found this session, and one was a
  false alarm; check rather than assume in both directions.
- **Guardrail completeness.** `edit_guard.DENIED_FILES` should be re-derived
  from first principles: does every module that authenticates, authorises,
  persists, or reaches the network appear? A new module added since the list
  was written is the failure mode.
- **`PRIVATE_RUNTIME_BASENAMES` vs `DENY_PATTERNS`.** The module documents the
  basename set as a *second independent check*. `activity_log.jsonl` is
  covered by pattern only, while the deny comment calls window titles "at
  least as revealing as the conversation history" — which *is* in the basename
  set. Either the comment or the coverage is wrong. **Known open finding.**
- **Untrusted-input paths.** Web results, activity log, Wi-Fi records, file
  contents, device messages. Each must be data, never instruction.
- **Error paths.** Bare `except`, swallowed failures, anything that fails
  *open* rather than closed.
- **Prompt assembly.** Anything permanently in `persona.py` that grants a
  capability belongs beside its data instead (see `search_rule`, and the
  Wi-Fi regression this session).
- **Dead code, unused imports, near-duplicate logic** worth consolidating.

Fix what is clearly broken. Optimise what is clearly slow. **Do not
refactor for taste** — this codebase's comments carry hard-won reasoning and
rewriting them loses it.

## Part 2 — tests the operator must run

An agent cannot drive a TUI, hear audio, see a visualizer, or move through a
room. These are yours. Each is written to be run in a few minutes.

### Voice
1. `voice status` — reports the microphone.
2. Speak a sentence. Was it transcribed correctly?
3. `audio mode`, ask anything. Does the reply *sound* right — inflection
   inside sentences, endings falling rather than rising?
4. Ask it to sing Daisy Bell. Does the intro play before the singing, and do
   held notes articulate rather than smear?
5. `text mode` silences replies; `audio mode` restores them.

### Music and visualizer
6. `play <song>` — does the visualizer open by itself?
7. Left/Right through all ten scenes. Any that render wrong, tear, or freeze?
8. Does colour change roughly every 20s, and the scene every ~2m45s?
9. Space skips to the next song; `[` and `]` change volume; Ctrl+B exits.
10. Let one song end. Does the next start automatically, and the last wrap to
    the first?

### The terminal itself
11. Type a message wider than the window. Does the newest text stay visible?
12. Trigger a long reply. Space/Enter/Down page forward, Up/Backspace back,
    Escape/Q closes, and it returns to the bottom of the conversation.
13. Arrow keys cycle the command list.
14. Escape cancels speech, music, and a long interaction.

### Identity and memory
15. `name` — does the ceremony run, and do the candidates look grounded rather
    than stock? `name keep`, then confirm the **header** changes and the
    window title does *not*.
16. Ask what it is called, and why. It should attribute the reason to a note
    rather than narrating having chosen it.
17. `name forget` restores TORMENT_NEXUS.
18. `activity`, `activity off`, `activity forget` — does each do what it says?
19. Tell it something memorable, restart, and ask. Then `forget <text>`.

### Time and continuity
20. Close it, wait a few hours, reopen. Does it register the gap naturally
    without turning every reply into a timestamp?
21. Leave it idle. Does the check-in arrive visually rather than spoken?

### The dangerous ones — supervised, on a branch, with backups
22. `dev mode`, then `suggest`. Are the three ideas grounded in real files?
23. `do 1` — preview only. Is the diff sane and within the 40-line cap?
24. Approve one. Confirm the backup exists and rollback works.
25. **Only if you want to:** run `start_autonomous_self_heal.bat` and watch a
    full unattended cycle. Confirm it applies at most one edit, validates, and
    rolls back cleanly on a forced failure.
26. Set a sub-goal, run it, and confirm output appears **only** in
    `workshop/` and nothing executable was written.

### Optional integrations
27. Web search with SearXNG running.
28. `spotify search` and playback.
29. T-Deck / Meshtastic / Raspberry Pi if connected.
30. The 14B DLC: download the parts, run the installer, confirm the checksum
    gate works and `start_full_maintenance_coder.bat` finds the model.

**Report back only what surprised you.** Anything that behaved as documented
needs no comment.

## Part 3 — the patch

After both parts, group findings into:

- **Blockers** — wrong behaviour, broken guardrail, privacy leak. Fix and
  release as Beta 5.1.
- **Should fix** — real but survivable. Batch into the next beta.
- **Additive** — new features. Separate branch, never mixed into a fix patch.

Known candidates already identified this session:

- **No automated coverage of the interactive terminal at all.** Every layer
  beneath it is tested; the layer the operator actually touches is not.
- **No CI.** The suite runs when somebody remembers.
- **Release split verification is manual.** `--split` now verifies the rejoin,
  but nothing forces it to run before an upload.
- **`activity_log.jsonl` basename gap** (above).
- The Wi-Fi collector's Windows path is a measured dead end; the plan lives in
  `WIFI_SENSING_NEXT_STEP.md` and `WIFI_SENSING_TRANSPORT.md`.
