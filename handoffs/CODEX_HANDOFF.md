# Handoff to Codex — Wi-Fi sensing, and what changed in it

# Addendum from Claude — semantic retrieval and agent bridges (2026-07-28)

New, uncommitted work; see `docs/SEMANTIC_AND_AGENT_BRIDGES.md` for the
full description. In one paragraph: memory retrieval is now hybrid
(word overlap + cosine over real embeddings from an optional second
llama-server on port 8082), conversation history is semantically
recallable, the retrieval panel projects the real vectors when they
exist, the agent interface gained a stateless `GET /ask?q=` route, and
an opt-in `escalate` command sends a single question to Claude/OpenAI on
operator-supplied keys. Everything degrades to prior behaviour when its
prerequisite (model file, env flag, key) is absent. 523 tests pass.

Files touched or added, for explicit staging (never `git add -A`):
`assistant/core/config.py`, `assistant/core/embedding_server.py` (new),
`assistant/core/escalation.py` (new), `assistant/memory/semantic_index.py`
(new), `assistant/memory/history_recall.py` (new),
`assistant/memory/memory_logic.py`, `assistant/memory/memory_vectors.py`,
`assistant/main.py`, `assistant/commands/command_handlers.py`,
`assistant/tests/test_regressions.py`, `tools/package_release.py`,
`.gitignore`, `docs/SEMANTIC_AND_AGENT_BRIDGES.md` (new).

Two cautions: the new secret files (`.anthropic_api_key`,
`.openai_api_key`) and the embedding cache (`assistant/cache/
embeddings.json`) are in both `.gitignore` and `DENY_PATTERNS` — keep
them in step if you rework either list. And the embedding model is NOT
in any package: it now exists locally at
`models/embedding/bge-small-en-v1.5-q8_0.gguf` (35MB, downloaded by the
operator 2026-07-28; `models/*.gguf` is only ignored at the top level,
so **add `models/embedding/` to .gitignore or stage carefully**) — the
packager needs no change unless a release decides to bundle it.
`EMBED_MIN_COSINE` defaults to 0.38, calibrated by measurement against
this exact model; recalibrate if the model changes.

**There is work specified for you:** `docs/RESEARCH_ROADMAP.md` is an
install plan for five Windows-feasible research features (entropy
honesty signal, dynatemp comparison, persona drift telemetry, sycophancy
probes, idle consolidation), written instead of implemented because the
operator's session budget ran short. Ground rules and verification
recipe are in the doc. Pi-only work is parked in `raspberry_pi_goals/`
— do not start it before hardware arrives.

# Addendum for Claude — current release decision (written 2026-07-28)

The operator has corrected the release definition. This addendum supersedes
any older Q5-only wording below:

- **The Q8 abliterated Qwen3 4B is the director.** It replaces the old Q5
  default in the project and must be the normal model in the next Windows beta.
- **Bundle the abliterated Qwen2.5-Coder 7B Q8** as the on-demand autonomous
  coder. The 14B Q4 remains a desktop-only on-demand full-maintenance model;
  do not put it in the beta payload.
- The beta must reflect the project as it exists on the operator's PC, not an
  older Q5-only release configuration.

## Release correction before rebuilding Beta 5

`tools/package_release.py` currently packages only
`models/Qwen3-4B-Instruct-2507-Q5_K_M.gguf`, and its installer checks only for
that Q5 file. The first Beta 2 archive was therefore a valid two-part package
for the old Q5 release definition, but not for the current decision:

| model | local file | bytes | role / release decision |
| --- | --- | ---: | --- |
| Qwen3 4B Q8 | `Qwen3-4B-abliterated-bf16_q8_0.gguf` | 4,645,051,328 | bundle; director |
| Qwen2.5-Coder 7B Q8 | `Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf` | 8,098,525,056 | bundle; autonomous coder |
| Qwen2.5-Coder 14B Q4 | `Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf` | 8,988,111,200 | do not bundle |
| old Qwen3 4B Q5 | `Qwen3-4B-Instruct-2507-Q5_K_M.gguf` | 2,889,513,216 | remove from beta package |

Verified hashes for the two new shipped models:

```text
Qwen3-4B-abliterated-bf16_q8_0.gguf
947656A42E73BDA324C527F06953596B77E4D91BC590476955205B5F64D4E974

Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf
FBB484A986646E20A2C1A83CB00973B2384436B81E3AC4C6400B9B3DFFB9C6D0
```

## Completed after this handoff was first written

- The Q8 director is now the default in `assistant/core/config.py` and in the
  CUDA director launcher. `start_desktop_q8.bat` is a compatibility wrapper,
  not an experimental branch.
- The packager includes the Q8 director, 7B coder, and the two public coder
  launchers; it excludes the old Q5 and the 14B model. The installer verifies
  both bundled GGUFs.
- The 7B launcher uses the local CUDA runtime when it exists, otherwise the
  shipped CPU `llama-server` with zero GPU layers and an explicit slow-mode
  message. A fresh recipient can therefore use the bundled coder without an
  unshipped CUDA runtime.
- Documentation and generated package README now describe the Q8/7B payload,
  16 GB memory minimum, and roughly 40 GB temporary disk requirement.
- The public release name is **v0.2.0-beta.5**, not beta.2. The notes state
  that beta numbering is cumulative across minor versions.
- **411 regression tests pass.** The final package passed privacy and manifest
  verification: 289 files, 288 content hashes, 13.06 GB extracted and
  12,345,399,239 bytes zipped. It split into six generated parts and their
  rejoin was verified byte-for-byte.
- Final notes and checksums are in
  `dist/RELEASE_NOTES_v0.2.0-beta.5.md`. The old Q5-only draft ZIP is retained
  under `dist/superseded/v0.2.0-beta.2-q5-only/`; do not upload it.

The source changes are not yet committed/tagged/published at the time of this
handoff update. `README_DRAFT_BETA5.md` is another untracked draft and is not
part of the release unless the operator explicitly chooses it.

Historical checklist — completed as described above:

1. Make `assistant/core/config.py` default `MODEL_PATH` and
   `MODEL_DISPLAY_NAME` point at the Q8 director.
2. Make `start_desktop_cuda.bat` run that same Q8 director. The separate
   `start_desktop_q8.bat` must no longer imply that Q8 is experimental.
3. Replace the Q5 entry and installer check in `tools/package_release.py` with
   the Q8 director and add the bundled 7B coder. Update package tests to
   assert both shipped GGUFs and no Q5.
4. Correct `docs/BRING_YOUR_OWN_GGUF.md` and public beta wording: Q8 director
   and 7B coder are supplied; only the 14B is a separate advanced download.
5. **Resolve CUDA runtime delivery deliberately.** The 7B launcher requires
   `llama.cpp/runtime/desktop-cuda-12.4-b9637/llama-server.exe`, but the
   package currently includes only `llama.cpp/build/bin/Release`. The local
   CUDA runtime is 1,852,845,215 bytes; it includes two large downloader ZIPs.
   Bundling the coder without a usable runtime or documented CPU fallback
   leaves a fresh beta recipient unable to use it. This was resolved with the
   tested documented CPU fallback; the CUDA runtime itself is not redistributed.
6. Rebuild `--archive`, run `--verify-only`, run `--split`, regenerate release
   notes/checksums, then update the public tag/release. Completed locally; do
   not upload the old Q5-only archive as Beta 5.

The old Beta 1 archive is safe in `dist/releases/v0.2.0-beta.1`. The first
Q5-only Beta 2 draft is retained under `dist/superseded/`; the corrected Beta
5 artifacts are the current upload set. The earlier validation was still
useful: it established the package and split workflow before the final 411-test
validation.

Remote `master` is at `aadec9558402dc8499152ef938ba985aec21f3a5`. Codex's
uncommitted Beta 5 release-prep edits are limited to `CHANGELOG.md`,
`README.md`, `assistant/tests/test_regressions.py`, `docs/BETA_GUIDE.md`,
`docs/INSTALL_WINDOWS.md`, `docs/RELEASE_CHECKLIST.md`,
`docs/TROUBLESHOOTING.md`, and `tools/package_release.py`. This handoff remains
untracked: stage explicit paths only; never use `git add -A`.

---

Written 2026-07-28 after the v0.2.0-beta.1 release. Everything below is
pushed; `master` is at `0765d6a`.

## Your bridge shipped

`core/wifi_experimental.py` is in v0.2.0-beta.1 (tag pushed, archive built and
verified). The docs, the `.gitignore` and `package_release.py` exclusions for
`wifi_sensing_status.json`, the README section and `docs/ARCHITECTURE.md` all
went in with it.

I walked your calibration gate inside the *installed* package — off reads
nothing, all four states render, a stale record correctly reports no fresh
reading, `forget` and `off` clear it. I also checked the doc's contract claims
against the code: a missing `expiry_ms` and any extra field both reject the
whole record, as `WIFI_SENSING_EXPERIMENT.md` says. I had suspected the doc
overstated it. It doesn't.

## I changed two things in your feature. Please don't revert them.

**What I changed:** `persona.py` went back to the unconditional "You have no
sensors." Every rule about reporting a reading moved into
`_room_sensing_context()` in `main.py`, where it is written only when there is
a reading to constrain.

**Why.** Giving the model a real sensor made the old absolute claim false, so
the rule became a conditional — no sensors *unless* runtime telemetry says
otherwise — plus a sentence beginning "Say that the enabled experiment
reported it". Both halves were then in the prompt on *every* turn, including
the overwhelming majority where no collector exists at all.

Asked "can you tell if anyone is in the room with me", it answered:

> The enabled experiment reported a Wi-Fi signal from a nearby device at
> 3:45 AM.

There was no experiment, no collector, no record. It invented a reading, a
timestamp and a direction. **Six of twelve samples.** After the change, zero
of twelve, while an enabled feed with a real record is still reported
correctly and attributed to the experiment.

Two mechanisms, both worth knowing for anything else you add:

1. A 4B model cannot reason reliably from the *absence* of a line in its
   prompt. Given a conditional, it takes the branch that has words attached.
2. "Say that X" is a template, and this model copies templates verbatim. The
   phrase came back word-for-word. `PERSONA_SHOTS` in `persona.py` documents
   the same failure from a different angle.

The pattern the repo already had for this is `search_rule` in `main.py` — a
conditional instruction written *only* when there are results to constrain.
Anything that grants the model a new capability should follow it rather than
living permanently in `persona.py`.

Regressions guarding this: `test_the_persona_never_mentions_a_sensor_it_might_
not_have`, `test_no_reading_means_no_permission_to_report_one`,
`test_an_expired_reading_withdraws_the_permission_too`,
`test_a_real_reading_carries_its_own_constraints`.

## New: there is a collector now

`tools/wifi_sense_collector.py` — external, as your design intends. No driver
change, no monitor mode, no Secure Boot touched, nothing added to the
assistant.

**What works and what doesn't**, measured on this hardware:

- Windows' Wi-Fi "Signal" percentage is useless. It sat at 85% for 22
  consecutive seconds, then 84% for eight. Spread of 1, stdev 0.44.
- Full BSSID scans are cached; Windows re-serves the previous sweep unchanged
  for 10–15s on the connected adapter.
- **Receive rate does move**: 907 → 865 → 907 → 1021 → 961 Mbps over the same
  25 seconds the quality figure was frozen. Rate adaptation responds to real
  SNR and multipath. That is the signal.
- The idle TP-Link USB adapter refreshes scans every 3–9s (it isn't protecting
  a link) and hears 29 access points. One fast path plus many slow ones;
  either may see a disturbance and neither can veto the other.

It never emits `approach`. Rate and RSSI are scalars, there is no bearing in
either, and the bridge accepting the label is not a reason to produce one.
Confidence is capped at 0.6, below your "high" band.

BSSIDs are used in memory only, to pair readings between sweeps. They identify
neighbours' hardware and never reach the status file.

## Open

1. **This approach does not work. It has now been tested and it failed.**

   Calibrated at 17.45 Mbps with a video stream running, then `--verify` with
   the operator moving deliberately and vigorously, crossing between PC and
   router:

   | phase  | rate spread | scan paths disturbed |
   | ------ | ----------- | -------------------- |
   | still  | 10.18 Mbps  | 9% of 28             |
   | moving | 5.65 Mbps   | 0% of 28             |

   **Moving was quieter than sitting still.** That is not a weak detection,
   it is noise — a real signal buried in noise would at least point the right
   way. Zero of twenty-eight scan paths moved during vigorous movement.

   The tell was there earlier and we missed it: three calibrations came back
   19.22, 20.27 and 17.45 Mbps *regardless of traffic load*, including one
   deliberately run with a video and one without. A number that ignores a
   video stream was always going to ignore a person. It describes the
   adapter, not the room.

   **Why**, so nobody retries it: rate adaptation only reports on the channel
   when the channel is marginal. This link is 5 GHz, short range, 85% signal,
   high SNR. The adapter has so much margin that a body absorbing part of the
   signal never drags it far enough to force a modulation change, so the rate
   reports the adapter's own rate-selection churn. Windows' scan values are
   cached and rounded to whole percent because they exist to draw a taskbar
   icon.

   `--verify` now separates "flat link, needs traffic" from "varying but
   uncorrelated, information is not there" — it previously reported both as
   the former and told this operator to start a video that was already
   playing.

2. **Do not tune the thresholds into agreement.** This was the standing
   instruction before the test and the result does not change it. The
   scaffolding is sound — bridge, contract, calibration, verification — and
   reusable. One data source failed, for a statable reason.

   The next rung is genuinely a different quantity, not the same idea tuned
   better: **monitor mode on the spare TP-Link**, giving per-packet RSSI from
   every transmitter in range, raw and unsmoothed, at packet rate instead of
   one rounded number per second. You stop asking one adapter how its own
   link is doing and start listening to frames crossing the room from 29
   directions. That wants Linux, which points at the Raspberry Pi rather than
   this desktop. Same collector contract, same bridge, same status file.
3. **The AX211 is off limits.** It is the operator's only internet. Beyond the
   risk: PicoScenes gets CSI by patching the open-source Linux `iwlwifi`
   driver plus firmware, and Intel's Windows firmware does not expose that
   path. A custom Windows driver would need an undocumented firmware interface
   and kernel signing, and the chip still wouldn't report CSI. The risk is
   real and the payoff is zero.
4. **The collector is not in v0.2.0-beta.1.** The release is tagged at
   `9ea03fe`; the collector landed after at `6a9c391`. Nothing to redo — the
   shipped build is a bridge with no collector, exactly as its docs say.

## Untested in the shipped release

Worth knowing before anyone assumes coverage: **voice, the music visualizer,
and the interactive terminal were never exercised by hand.** The package
installs and starts on the bundled interpreter, 404 tests pass, and every
layer beneath the TUI is verified — but nobody sat at the prompt and drove it.

## Two repo conventions

- **Stage explicit paths, never `git add -A`.** Two agents work in this tree.
  I swept your uncommitted `wifi_experimental.py` into an unrelated commit
  once, and your README section into another. Check `git diff --stat` on each
  path before staging and stop if the line count isn't what you wrote.
- **Line endings are LF.** Writing a file from Python on Windows converts the
  whole thing to CRLF and produces a 14,000-line diff. Use
  `newline="\n"` explicitly.
