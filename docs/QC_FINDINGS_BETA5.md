# Beta 5 QC findings — Part 1 (agent-executable)

Reviewed at commit `1b01c7b`, working tree carrying Codex's in-flight release
edits. **No fixes applied.** Codex is mid-release; every item below is written
so it can be applied as a patch once the release lands.

Baseline: `python assistant/run_regressions.py` → 411 tests, 16–19 s, green.

Files Codex currently has open are marked *provisional* where a finding touches
them (`core/config.py`, `tools/package_release.py`, `assistant/tests/`).

---

## Blocker — fix before 5.1 ships

### 1. The capability gate misses the Windows process launcher

`editing/edit_guard.py` `_SENSITIVE_CALLS` enumerates every POSIX spawn/exec
variant — `os.spawnl` through `os.spawnvpe`, `os.execv`, `os.execve` — and omits
`os.startfile`, which is the Windows equivalent and **is already used in this
codebase**:

- `hardware/setup_hardware.py:34` — `os.startfile("ms-settings:bluetooth")`
- `visualizer/spotify_control.py:157` — `os.startfile(uri)`

`os` is not in `_SENSITIVE_IMPORT_ROOTS`, so `import os` is always free. An
unattended edit to any allowlisted module can add `os.startfile(...)` and pass
`change_capability_problem()` cleanly. On the project's primary platform that is
process execution.

Also absent: `os.execl`, `os.execlp`, `os.execle`, `os.execlpe`, `os.execvp`,
`os.execvpe`, `os.posix_spawn`, and the import roots `runpy`, `pickle`,
`marshal`. Two more matter specifically to this project — neither is listed, so
any editable module may introduce them from nothing:

- **`serial`** — the LoRa/Meshtastic radio. Egress the guard does not model.
- **`sounddevice` / `pyaudio`** — microphone capture.

Fix is additive to two frozen sets. Low risk, high value, and the module's own
docstring is what claims this boundary holds.

---

## Should fix — batch into 5.1

### 2. The 14B maintenance profile edits a wider surface than its gate assumes

`editing/maintenance_engine.py:180` gates a repair on
`edit_guard.change_capability_problem()` alone. That check is a **delta**: it
blocks *newly added* capability and deliberately permits capability a module
already has. The autonomous 7B path has `AUTONOMOUS_ALLOWED_FILES` on top of it.
The maintenance path has no file allowlist at all — its surface is everything not
in `DENIED_FILES`.

So an unattended repair may modify, without adding a single import:

- `web/search_engine_searxng.py`, `search_engine_brave.py`, `search_engine.py` —
  already import `requests`; the URL they post to is editable.
- `memory/memory_store.py` — already writes files; what it persists is editable.

Three such edits run back to back and are reported only afterward. It is
human-*initiated* (`full self heal`) but not human-*reviewed*, and the session
fails closed on validation, so this is not a live leak. It is the same argument
`edit_guard.py` makes about `persona.py`: a constraint the constrained thing can
edit is decoration.

**Fix:** add a `MAINTENANCE_DENIED_FILES` set covering the network and
persistence modules, applied in `_try_apply` beside the capability check. Do not
widen `DENIED_FILES` — that would remove a legitimate human-reviewed edit path.

### 3. `validate_restart()` treats environment warnings as code defects

`self_heal_state.validate_restart()` requires `health_check.report()` to contain
`"Overall: healthy"` — which means **zero warnings across all seven checks**,
including:

- SearXNG reachable (`_search_health`, 5 s probe)
- voice model files present
- ≥ 1 GiB free disk
- model API responding *and* authenticated
- every stored memory still meeting current durability rules

If SearXNG simply is not running, `maintenance_engine.run_session()` sees
"unhealthy", hands the 14B a diagnostic about a **network service**, and asks it
to produce a **code edit** to repair it — up to three attempts, each backed up,
written, import-checked, and then rolled back when validation still fails. The
same marker silently destroys an earned 7B self-heal credit in
`self_heal_state.load()`.

**Fix:** split `health_check` into code-owned checks and environment checks. Only
the code-owned set (plus the regression run, which is already the real signal)
should drive the repair loop; environment warnings belong in the report as
context the model is told it cannot fix.

This one also makes the `health` command more useful to you directly.

### 4. `PRIVATE_RUNTIME_BASENAMES` has drifted from `DENY_PATTERNS`

*Provisional — `tools/package_release.py` is open in Codex's tree.*

The known finding is confirmed, and there is a second instance:

| File | `DENY_PATTERNS` | `PRIVATE_RUNTIME_BASENAMES` |
|---|---|---|
| `memory/activity_log.jsonl` | ✅ `*/memory/activity_log.jsonl*` | ❌ |
| `memories.json.<stamp>.invalid-shape` | ✅ `*/memory/memories.json*` | ❌ |

The second is written by `memory_store._load_memory_list()` when it recovers a
malformed store — a file containing the *original* memory data.

Nothing leaks today: `denied()` runs in `copy_tree()`, again in `clean()`, and
again in `verify()`. The gap is that the documented "second independent check"
is one layer thin precisely where the deny comment says window titles are "at
least as revealing as the conversation history" — and `conversation_history.txt`
*is* in the basename set.

**Fix structurally, not by hand.** Adding two strings re-opens the moment
someone adds a third. Add a regression test asserting that every
literal-filename deny pattern has basename coverage, and have `verify()` match
on stem-prefix so `<name>.<stamp>.<suffix>` recovery files are caught by the
basename check too.

### 5. Oversized-file edits fire one HTTP round-trip per candidate range

`editing/edit_generator.py:281` — `_budgeted_user_message()` loops over *every*
candidate range from `_candidate_ranges()` and calls `_count_tokens()` inside the
loop. That is a `POST /tokenize` with a 10 s timeout, per candidate. There is no
cap and no early exit, and `_render_excerpts()` re-renders the whole accumulated
set each iteration (O(n²) string work).

`_candidate_ranges()` emits a range per matching line for large nodes *and* a
range per matching line globally. A common term in `voice/offline_voice.py`
(2,841 lines) can mean well over a hundred sequential requests before one token
of the patch is generated. This is the largest performance defect I found and it
is user-visible as an apparent hang.

**Fix:** cap candidates to the top ~12 by score, and break once a trial exceeds
budget rather than continuing through the tail.

---

## Low — batch or skip

6. **`patch_engine.apply_edit()` does not reject an empty `find`.**
   `"".count("")` is `1`, so on a zero-byte file an empty find/replace writes
   arbitrary content. Not reachable today — `edit_generator` rejects
   `not find.strip()` first — but the project ships zero-byte `__init__.py`
   files that are editable, and this function's docstring says it repeats the
   uniqueness check "because this function is the one that decides what gets
   written." One line, consistent with the module's stated intent.

7. **`suggestion_engine._pending` is shared** between autonomous and human
   batches. An autonomous cycle overwrites the list a human's `do <n>` indexes
   into.

8. **Two full directory walks per `suggestion_engine.generate()`** —
   `_inventory()` and the validation step each rebuild the editable-file list.

9. **Unused imports:** `tools/glitch_icon.py` (`struct`),
   `tools/package_model_pack.py` (`sys`). Nothing else in ~40k lines.

10. **`voice/offline_voice.py` is 98.7 KB against `MAX_EDITABLE_BYTES =
    120_000`** — 82% of the cap, and the largest file in
    `AUTONOMOUS_ALLOWED_FILES`. When it crosses the line, edits to it start
    failing with a size error rather than anything that explains itself. Not a
    fix; something to know before it happens.

---

## Checked and clean — no action

Recorded so the next review does not re-derive them.

- **No bare `except:`** anywhere outside `tests/`. Every swallowed exception
  sampled (`llm_server`, `edit_intent`, `tdeck`, `main`, `audio_source`,
  `local_player`) is a deliberate best-effort cleanup with a stated reason.
- **Untrusted-input framing is present on every path the plan named** — web
  results, Wi-Fi records, fixed diagnostics, chosen-name material, runtime
  context, and `natural_command`.
- **T-Deck inbound is an authentication boundary, not just framing.**
  `_on_text` requires `packet["from"] == local_node_num`, suppresses its own
  echoed output, and dedupes by packet id. Malformed sender ids fail closed.
- **`persona.py` carries no capability grants.** The search rule is attached
  beside its data in `_runtime_context_prompt()`, and only when search context
  exists. Last session's regression is genuinely fixed.
- **Path containment holds.** `resolve()` (realpath + prefix check),
  `restore()` (basename only), and `_checked_existing_backup()` (basename +
  prefix match) — no traversal found.
- **`VALIDATION_TIMEOUT_SECONDS = 120` is comfortable.** Measured suite runtime
  is 16–19 s.

---

## Additive suggestions

Ordered by how much they'd actually change.

1. **`guard doctor` command.** Scans every module for network, persistence,
   credential, and radio imports and reports any that appear in neither
   `DENIED_FILES` nor a maintenance deny set. This turns findings #1 and #2 from
   hand-maintained lists into a check that fails when someone adds a module —
   which is the failure mode the review plan predicted. Cheapest thing here with
   real leverage.
2. **TUI coverage harness.** Still the strongest item, and unchanged by this
   review: every layer beneath the terminal is tested and the layer you touch is
   not. It is the difference between "everything beneath it is verified" and
   "it works."
3. **CI.** The suite is 19 seconds. There is no reason it runs only when someone
   remembers.
4. **Environment/code split in `health_check`** — falls out of #3 above and
   makes `health` more legible to you as well.

---

## Part 2 — operator tests

The thirty checks in `QC_REVIEW_PLAN.md` stand as written. This review adds four
that specifically probe the findings above, and one correction:

- **Correction to the plan:** test 25 (`start_autonomous_self_heal.bat`) exercises
  the **7B autonomous** path, which *is* allowlist-protected. Finding #2 is about
  the **14B `full self heal` command** under `start_full_maintenance_coder.bat` —
  a different profile with a different surface. Test both, separately.

- **31.** With SearXNG deliberately **stopped**, run `full self heal` on the 14B.
  Expected today: it reports unhealthy and attempts code repairs for a network
  service. Confirms finding #3. Safe — it rolls back.
- **32.** Run `health` with SearXNG stopped and note how many of the seven checks
  warn. That count is what currently blocks every self-heal path.
- **33.** After any `--split` release build, run the rejoin verification manually
  and confirm the checksum gate. Nothing forces this before upload.
- **34.** Trigger an edit against `voice/offline_voice.py` naming a common term
  (e.g. "volume"). Time it. Finding #5 predicts a long stall before the diff
  appears.

---

## Patch plan — Beta 5.1

**Blockers (ship as 5.1):** #1.

**Should fix (same patch, they are small and related):** #2, #3, #4, #5.

**Low (fold in if the patch is already open):** #6, #8, #9.

**Deferred:** #7, #10 — behavioural notes, not defects.

**Never in this patch:** all four additive suggestions. Separate branch.

Sequence, once Codex's release has landed and the tree is clean:

1. Re-run the baseline suite and re-record the commit — these findings describe
   `1b01c7b` plus uncommitted release work.
2. #1 and #4 first: both are additions to frozen sets with regression tests, and
   #4's test is what stops the drift recurring.
3. #3 before #2 — the health split changes what `maintenance_engine` consumes,
   so doing it first avoids editing that module twice.
4. #5 last; it is the only one touching a hot path, and it wants its own timing
   check (operator test 34) before and after.
