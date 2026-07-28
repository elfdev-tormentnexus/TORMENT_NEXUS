# TORMENT_NEXUS handoff

Updated by Codex: 2026-07-28 (America/Toronto).

## Start here

```text
C:\Users\evely\Documents\AI_Project
https://github.com/elfdev-tormentnexus/TORMENT_NEXUS
```

```text
branch: master
HEAD:   33f9364
remote: origin/master matches HEAD (0 ahead, 0 behind)
```

Nothing from the current continuation has been committed or pushed. The
worktree intentionally contains 26 modified tracked files and 8 untracked
source/launcher files. Inspect `git status` rather than assuming it is clean.

```text
33f9364  Plan the two singing features for the next session
ff9d37f  Add maintainer handoff for the next session
a79d013  Document what the last three commits added
a6454df  Let it notice the room                  (system awareness)
```

Run the suite before trusting any of it:

```powershell
cd C:\Users\evely\Documents\AI_Project\assistant
python -m unittest tests.test_regressions
```

Expect **346 tests, OK, about 15 seconds**.

## Current Codex continuation — read this first

This is the authoritative summary of the entire uncommitted continuation
session. The older sections below preserve useful background, copyright
decisions, and release traps, but this section overrides any conflicting
historical claim.

### Verification and repository state

- Run the complete suite from `assistant/` with
  `OPENBLAS_NUM_THREADS=1`: `python -m unittest tests.test_regressions`.
  It most recently passed **346 tests in about 15 seconds**. `git diff --check`
  is clean. No `llama-server` process is intentionally left running after the
  desktop smoke tests.
- Do not commit, package, or upload any GGUF weights, the isolated desktop CUDA
  runtime, caches, logs, memories, music, credentials, or pairing state. The
  current work is not part of the published Beta 3 archive or its visualizer
  patch.
- The user has correctly kept the model layout flat; no new subfolders are
  required:

  ```text
  models/
    Qwen3-4B-Instruct-2507-Q5_K_M.gguf                 2,889,513,216 bytes
    Qwen3-4B-abliterated-bf16_q8_0.gguf                4,645,051,328 bytes
    Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf    8,098,525,056 bytes
    Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf 8,988,111,200 bytes
  ```

  The 7B SHA-256 is
  `fbb484a986646e20a2c1a83cb00973b2384436b81e3ac4c6400b9b3dffb9c6d0`.
  The 14B SHA-256 is
  `e89a7ae4e2b456bf33c75cff35664751df20ff273e551d7cf7640aa9e84d3b79`.

### Music visualizer, bass detection, and terminal presentation

- `assistant/visualizer/audio_source.py` now detects low-end events with
  adaptive spectral flux rather than simple rising bass. It uses cached FFT
  masks, a 35–180 Hz kick band, 30 Hz–8 kHz onset analysis, a 1.5-second
  adaptive history, a 115 ms beat refractory interval, and time-based
  envelopes/gain release. New features are `sub_bass`, `kick`, and `onset`.
  Mid/high leakage is presence-gated, and the first kick after silence can
  trigger correctly.
- Added `assistant/visualizer/y2k_player.py`: the new default **aqua player**
  scene, a terminal-braille black-glass/chrome player with dual oscilloscope,
  orbital spectrum, gel equalizer, stereo markers, and beat bloom.
- Rebuilt `assistant/visualizer/datastream.py` as a layered falling-code
  curtain with curved strands, foreground/background depth, a spectrum-shaped
  low horizon, treble-driven speed, and a short beat scan fault rather than
  persistent static.
- Added `assistant/visualizer/acid_lattice.py`: an original acid-green
  triangular lattice with bass-pulled jagged void/horizon, scan lines, and
  onset-only fracture bursts. It is influenced by the supplied music-video
  language, not copied footage or frames.
- `assistant/visualizer/reactivity.py` has profiles for aqua player and acid
  lattice and a retuned datastream profile. `assistant/ui/ui.py` now exposes
  ten scenes in this order: aqua player, radial tunnel, spectrum cathedral,
  orbital reactor, corrupt cube, neon horizon, plasma flow, datastream rain,
  wormhole, acid lattice. Music mode renders at 25 FPS; normal chat remains at
  the lower redraw rate. Local playback still opens music mode automatically.
- `ui.py` also adds strictly canvas-only corruption: a typed character has a
  0.20-second phase-in, while sparse 0.18-second fragments appear only in
  blank gutters or separator chrome every 1.6–3.8 seconds. The input buffer
  and chat history are never changed; both effects are cleared in music mode.

### Voice, Daisy Bell, and reusable song groundwork

- `assistant/voice/offline_voice.py` now applies the same restrained digital
  finish to ordinary speech and singing: chromatic carrier snapping suppresses
  within-syllable pitch glide/vibrato, phrase-level steps remain intentional,
  and `_digital_voice_texture` adds modest time-aligned quantisation, edge,
  and soft drive without delay, echo, chorus, resampling, or a second signal.
  Speech uses a lower edge than singing (0.022 vs 0.035) to retain consonants.
- Normal speech now passes its carrier pitch, formant shift, cadence,
  flattening, and stable sentence-specific chromatic pitch bias explicitly.
  The current defaults reduce cadence strength from 0.88 to 0.35 and raise the
  speech carrier from 155 to 168 Hz. This remains a generic offline Piper
  treatment, not a cloned actor or reference-audio voice.
- Added immutable `Song` and generalized the Daisy-only cache, build,
  accompaniment, mixing, and playback path. `sing_daisy_bell()` remains a
  backward-compatible wrapper around `sing(DAISY_SONG, ...)`.
- `voice_training/analyze_current_voice.py` now prefers `soundfile`, accepts
  optional `--ffmpeg` fallback, renders the active chunked speech chain, and
  uses low-memory RMS excerpt selection for long references.
- `assistant/voice/README.md`, `docs/SINGING_PLAN.md`, and related user docs
  describe the treatment and the song refactor. The supplied dialogue/Daisy
  references were used only as listening/measurement targets; no reference
  recording or voice model is shipped.

### Desktop model roles and guarded self-editing

The existing Qwen3 4B Q5 companion was already an abliterated Instruct build.
Do not treat refusal behavior as an authority boundary. Trusted Python roles,
protected paths/capabilities, exact patches, backups, fixed checks, regression
tests, and rollback decide what any model may do.

- `start_assistant.bat` is unchanged and remains the CPU/Pi-compatible Q5
  default. Do not replace or move that Q5 model.
- `start_desktop_cuda.bat` runs Q5 as **director** with CUDA full offload,
  8K context, alias `desktop-companion`, and its own prompt cache. It owns
  conversation, goals/subgoals, `modify plan`, and `approve plan`.
- `start_desktop_q8.bat` runs the 4B Q8 as a separate experimental **director**
  profile with its own alias/cache. It does not replace Q5 or change Pi scope.
- `start_maintenance_coder.bat` runs the moved abliterated 7B Q8 as
  **autonomous-coder** with 16 GPU layers, 4K context, flash attention, Q8 KV
  cache, alias `maintenance-coder`, and a separate cache. It does not run an
  automatic edit on startup by default.
- `start_autonomous_self_heal.bat` is an explicit wrapper permitting one
  bounded startup repair cycle with that same 7B profile.
- `start_full_maintenance_coder.bat` runs the abliterated-Instruct 14B Q4 as
  **full-maintenance** with 20 GPU layers, 4K context, flash attention, Q8 KV
  cache, and a separate alias/cache. It is an on-demand maintenance model, not
  the normal conversation model.
- Exit one profile before launching another. `llm_server.py` checks the live
  server alias and refuses accidental reuse of another profile. `config.py`
  validates `director`, `autonomous-coder`, and `full-maintenance`; an unknown
  explicit role fails closed to `restricted`.

Role workflow:

1. Director: `modify plan <file> <change>`, then `approve plan`.
2. Exit the director; start the 7B coder (or 14B when appropriate).
3. Coder: `preview plan`, inspect the diff, then `confirm edit`.

Only the 7B can run the normal guarded autonomous cycle/observed serial mode.
It remains capped at one normal edit, or three watched edits, with a 40-line
cap, a small allowlist, syntax/import checks, backups, and no newly added
process/network/dynamic-code/filesystem capability. Earned restart credit is
bound to the 7B actor role; another profile may validate it but cannot spend
it, and legacy/unbound markers fail closed.

`assistant/editing/maintenance_engine.py` is a new protected 14B transaction.
Developer-mode `full self heal` first runs the fixed health/regression check;
only a failing result is passed as bounded diagnostic data to the model. It
allows at most three edits of 120 changed lines each, persists its rollback
record before every replacement, uses normal path/capability/syntax/import
guards, and re-runs the fixed checks after each edit. A non-green/no-safe
session rolls back all session edits in reverse. A lingering active transaction
is recovered before normal UI work on the next startup; an unreadable marker
is retained and reported rather than silently discarded. The model never
selects shell commands or alters the safety modules.

Measured on this RTX 4060 desktop only: 4B Q8 was about 48 generated tokens/s;
the moved 7B Q8 was about 17.7 generated tokens/s with about 2.3 GiB VRAM free;
the 14B Q4 was about 8.5 prompt tokens/s and 12.2 generated tokens/s with about
2.6 GiB free. Do not treat these as Raspberry Pi estimates.

### Documentation, tests, and remaining work

- Updated `README.md`, `docs/FIRST_RUN.md`, `docs/BETA_GUIDE.md`,
  `docs/TESTING.md`, `assistant/core/tutorial.py`, and `CHANGELOG.md` for the
  ten-scene visualizer, automatic local-music presentation, visual QA, voice
  behavior, and model-profile work. `docs/BRING_YOUR_OWN_GGUF.md` is the
  current source-of-truth for local model locations, launchers, overrides,
  role separation, and the 14B checksum.
- Tests cover synthetic kick vs midrange false bass, silence-to-kick onset,
  sustained-bass non-retriggering, all scene render/reactivity paths, resize,
  terminal-corruption safety/music exclusion, voice carrier/digital texture,
  generic Daisy arrangement, model role routing, 7B restart-credit ownership,
  14B transaction/recovery, and server profile aliases.
- Still intentionally incomplete: Come Josephine is not playable (only the
  reusable `Song` groundwork exists); `sing what you want` is not implemented;
  Daisy Bell has not been faithfully aligned to the supplied Max Mathews
  reference for tempo/key/intro timing; response latency has been diagnosed
  but not changed; activity-awareness first-run consent remains a user choice;
  the 4B Q8 remains experimental; no Pi 16 GB/coder-model deployment plan has
  been implemented.
- For any future latency work, add private phase timing first. Current likely
  contributors are the single-slot server, background memory extraction,
  full-reply-before-speech behavior, prompt ordering, and occasional intent
  classification. Do not claim latency is fixed.

## What exists now that did not before

**Local-library repeat** (`1eaa1f4`, written by Codex, verified here). Repeat
is on at launch, follows the filename order `music library` prints, wraps last
to first. `repeat music [on|off]`. A transport lock serialises play, skip, stop
and auto-advance; a generation counter means a manual stop invalidates a
pending transition instead of letting a stale watcher start the next song.

**Eight visualizer scenes** (`92b21f7`). The original four plus `neon horizon`
(perspective wireframe ground, banded sun, spectrum-cut skyline), `plasma flow`
(metaballs), `datastream rain` (glyph columns, beat-driven corruption) and
`wormhole` (projected starfield). Each has its own entry in
`visualizer/reactivity.py`. Adding a scene means three places: that profile
table, `ui._MUSIC_SCENES`, and `ui._make_music_scene()`. Two guard tests exist
because both of the silent failures are easy: a scene listed with no factory
branch, and a scene with no profile (which still runs, on the radial tunnel's
profile, and simply stops responding to what it was built around).

**Voice delivery** (`0fd8ba2`). Tuned against fourteen minutes of reference
dialogue. Within-phrase inflection 0.71 to 2.35 semitones, phrase-to-phrase
pitch 0.18 to 2.21, sentence fall 0.83 to 1.17, 8 kHz spectral share -17 to
-23 dB. Each sentence takes a pitch offset derived from a hash of its own
text, so it varies between sentences and is fixed for any one sentence.
Tunable without editing code:

```text
TORMENT_NEXUS_CADENCE_DEPTH          3.80   inflection depth
TORMENT_NEXUS_CADENCE_FALL           0.60   sentence declination
TORMENT_NEXUS_CADENCE_LIFT           2.20   ceiling on upward steps
TORMENT_NEXUS_PHRASE_PITCH_SPREAD    2.30   between-sentence variation
TORMENT_NEXUS_TILT_DB_OCTAVE         3.4    high-frequency rolloff
TORMENT_NEXUS_PAUSE_SECONDS          0.52   pause after a sentence
```

**Audio-reactive voice face** (`0fd8ba2`). The envelope is taken from the
speech buffer before playback and handed to the UI whole with a timestamp, so
the renderer interpolates at its own frame rate. Smoothing is per second, not
per frame. Constants live at the top of `ui/ui.py` (`SPEECH_ATTACK_RATE`,
`SPEECH_RELEASE_RATE`, `SPEECH_REACH_*`).

**System awareness** (`a6454df`). `core/system_awareness.py` samples the
foreground application and window title, idle time, CPU, memory and power
every 20 seconds, through `ctypes` only. Persists to
`assistant/memory/activity_log.jsonl` as a change log, 14-day retention.
Commands: `activity`, `activity on|off`, `activity forget`. Wired into the
model context beside the clock, and into a two-stage idle wait: a remark
partway into a silence, then the existing "still there?" check.

**Tutorial introduction** (`a6454df`). `core/tutorial.introduction()` — a
written, not generated, self-description that opens the walkthrough.

## Historical request snapshot (superseded by current continuation)

These original bullets are retained only for background. Their completion
status is stale; use the current-continuation section above for what is still
open and what groundwork now exists.

1. **`sing what you want`** — not started. Not designed beyond a note below.
2. **Come Josephine in My Flying Machine** — not started. This is the oldest
   outstanding request. 1910, public domain (Fred Fisher / Alfred Bryan). The
   user wants **parody lyrics** rewritten as a TORMENT_NEXUS joke, in the
   spirit of the improvised Daisy Bell continuation.
3. **First-run consent for activity awareness** — open decision, see below.
4. **CHANGELOG and docs** for the voice and awareness work — the CHANGELOG's
   Unreleased section covers the scenes but not the voice or awareness.

### The copyright constraint, so it is not relitigated

The user first asked for "You Belong to Me". That is the 1952 Pee Wee King /
Redd Stewart / Chilton Price composition, protected in the US until roughly
2047; their file is a 2014 Courtnee Draper cover. They then proposed keeping
the melody and substituting parody lyrics. That does not clear it: the melody
is the protected part, new words over it make a derivative work, and parody
gets latitude when it comments on the original rather than using it as a
vehicle. They accepted this and chose Come Josephine instead. Daisy Bell is
fine because it is 1892.

### If implementing `sing what you want`

The user's own constraint is the right one: the model may use only the tools
the Daisy Bell engine already has. A 4B model cannot invent a coherent melody.
The design that works is to let it write **lyrics** and select from prepared
rhythmic and melodic phrase templates over a fixed chord progression, with the
system guaranteeing musical validity. Free note generation will produce noise.

## Daisy Bell state

Intro is **52 measures, 65.52s**, vocal enters at 1:05.5, total 148.7s. The
user timed the vocal entry at 1:06 in a YouTube recording. **Unverified
assumption:** if that video has speech before the music, the musical intro is
shorter and this overshoots. One constant:
`offline_voice.DAISY_INTRO_TARGET_SECONDS`. Cache key is
`daisy_bell_machine_v11_`; bump it in `core/config.py` whenever the score,
intro or vocoder changes, or a stale WAV is played instead.

The consonant fix matters if touching the vocoder: a syllable stretched
uniformly to fill a long note smears its consonants, so a held "day" arrives
as "d-d-d-ay". `_sustain_warp` keeps onset and release at spoken pace and
spends the surplus on the vowel. It must not engage for speech rendered at its
own length -- the two frame spans are offset by different amounts, so a naive
comparison quietly reshapes ordinary speech.

## Releasing a beta

Maintainer steps, from `docs/RELEASE_CHECKLIST.md`:

```powershell
.\setup\test_assistant.bat
python tools\package_release.py --archive --skip-download
python tools\package_release.py --verify-only
```

Then record the archive SHA-256, split `dist/TORMENT_NEXUS.zip` into assets
under 2 GiB, and upload the parts with `REASSEMBLE_TORMENT_NEXUS.bat`. Put the
required filenames and the full ZIP checksum in the release notes. Confirm the
release link and filenames in `README.md`, `docs/INSTALL_WINDOWS.md` and
`docs/TROUBLESHOOTING.md`.

Use `--sanitize` if `setup.bat` has been test-run in the tree, because running
it creates the API key and memory files the denylist exists to exclude. Never
test `setup.bat` inside the staged package and then ship that folder.

The published Beta 3 also carries an additive music-visualizer patch built
from `bd74e42`. A **patch 2** must apply cleanly to both an untouched Beta 3
and one that already has `music-visualizer-patch.1`, which means dual accepted
baseline hashes for any file patch 1 already changed, a distinct patch ID and
asset name, and clean-apply plus upgrade tests. The two multi-gigabyte ZIP
parts stay unchanged.

**Ask the user before publishing anything.** They have not authorised a push
or a release in this session.

## Traps that cost time here

- **`core/config.py` has mixed line endings**: 631 CRLF and 10 bare LF. Any
  editor that normalises them turns a one-line change into a 39-line diff.
  Twice the fix was to rebuild the file from `git show HEAD:...` applying only
  the intended edit. `git diff --check` flags every CRLF line in a changed
  region; that is a false positive for this file.
- **Never use PowerShell `Set-Content` on source.** It writes a UTF-8 BOM and
  CRLF, and it double-encoded the deliberate mojibake in
  `DocumentationTests` (`markers = (...)`) via an ANSI round trip. Use the
  Edit tool or Python byte-level writes.
- **`OPENBLAS_NUM_THREADS=1`** for anything touching numpy or librosa audio,
  or it hangs forever rather than erroring.
- Long uptime fills the 65 GB commit limit until 2 MB allocations fail; it
  looks like a corrupt model and is not. Reboot.
- No `ffmpeg` on this machine, and `developer.valvesoftware.com` sits behind a
  bot wall that must not be worked around. Ask the user to paste content or
  export audio locally.

## Verification habits worth keeping

The user values honesty over agreeableness and expects fixes to be *verified*,
not described. Two failures here are worth remembering:

- A guard test that passes with the bug re-injected is worthless. Two written
  this session did exactly that and had to be strengthened. Inject the
  regression and confirm the test fails.
- A measurement can lie. A "last 20% of the phrase" metric reported a rise on
  a phrase whose contour ended 4.1 semitones down. Check the instrument
  before trusting a surprising result.

## Privacy and safety boundaries

Never commit, package, or quote in a bug report:

- `assistant/music/*` (someone else's copyright)
- `assistant/memory/activity_log.jsonl` (window titles: file names, URLs,
  message previews)
- conversation history, extracted memories, runtime logs
- API keys, passcodes, pairing PINs, tokens
- generated shortcuts containing absolute local paths

`DENY_PATTERNS` in `tools/package_release.py` and `.gitignore` are kept in
step. Preserve both.

`edit_guard` denies `main.py`, `command_handlers.py`, `core/config.py`,
`core/dev_auth.py`, `ui/ui.py`, `core/persona.py`, `editing/` and `tests/`.
The persona and the suite are on that list for the same reason as the rest: an
editor that can rewrite its own honesty rules, or the tests that judge it,
makes both a formality. **Do not widen this without asking.**

The repository still has no project-wide licence. Do not describe it as
freely redistributable beyond the licences of bundled third-party components.

## Historical open decisions (update before acting)

1. **Commit/review/push?** There are no commits ahead of origin; the relevant
   work is the current uncommitted continuation. Do not commit or push without
   the user's explicit approval.
2. **First-run consent.** Activity awareness currently defaults on, with full
   window titles, and may comment unprompted. That is what the user chose for
   their own machine. It also means a beta tester who installs the release
   gets their document names and URLs sampled without being asked. The
   suggestion on the table is to keep their install as-is and have a *fresh*
   install ask once. Undecided.
3. **Daisy intro length.** 66 seconds of instrumental before any singing is
   faithful to the reference but a long wait for a command-triggered easter
   egg.

## On the model editing this project

The user asked directly whether TORMENT_NEXUS can be trusted to code on its
own the way an external assistant does. The answer remains: not
unconditionally. A 4B model cannot reliably hold a large subsystem in mind,
and a coding model can still propose a plausible but wrong change.

Correct an earlier explanation here: the deployed Qwen3 4B companion is
already abliterated. Moving work to an abliterated model therefore does not
create a new safety transition, and a model's refusal behavior is not the
safety boundary. Authority must come from trusted Python enforcement: distinct
roles, protected paths and capabilities, small diffs, preview/approval,
backups, syntax/import checks, fixed regression validation, and rollback.
Keep those guardrails regardless of which local GGUF is active.

The intended division of labour is: the 4B companion directs conversation,
goals/subgoals, and plans; the 7B coder performs bounded autonomous repairs
and plan-directed edits; the on-demand 14B Instruct-abliterated coder performs
full, transactional, test-driven repair sessions. The models may recommend or
write a candidate patch, but they do not get to relax the enforcement that
judges it.

## Continuation update — 2026-07-28

The repository snapshot at the top of this handoff is historical. At the time
of this update, `HEAD` is `33f9364` and the worktree intentionally contains
uncommitted continuation work. Do not use the older `a6454df`/308-test count
as a release or validation claim; run the complete regression suite first.

### Work completed after the original handoff

- The Daisy-only arranger was generalized around `voice.offline_voice.Song`.
  This is groundwork only; it does **not** make Come Josephine playable yet.
- Speech received the Valve-inspired, generic machine treatment: constrained
  chromatic carrier pitch, flattened modulation, raised formant envelope, and
  a shared restrained digital finish for normal speech and singing. It is not
  a copied actor or reference-audio model. The supplied dialogue comparison
  should be rerun after any further voice changes.
- Music mode now has an improved low-frequency onset analyser, a glossy aqua
  player scene, a replacement layered digital-rain scene, and acid lattice:
  an original acid-green triangulated mesh with jagged voids and beat fracture
  bursts informed by the supplied music-video visual language, without using
  footage. These changes are still part of the uncommitted continuation work.

### User requests that remain open

1. **Come Josephine in My Flying Machine**: the engine groundwork exists, but
   a melody/chord transcription from an actual 1910 public-domain score,
   original parody lyrics, command/session plumbing, and listening validation
   remain. Follow `docs/SINGING_PLAN.md`; do not transcribe from memory.
2. **`sing what you want`**: still unimplemented. Use prebuilt musical phrase
   templates and model-written lyrics only, exactly as `docs/SINGING_PLAN.md`
   specifies; do not ask the small local model to invent a free melody.
3. **Faithful Daisy Bell alignment**: the supplied Max Mathews target has been
   compared at a high level, but its tempo/key/intro timing were not yet made
   to match. The generic refactor does not close this request.
4. **Activity-awareness first-run consent** and the desirable Daisy intro
   length are user decisions, not silent implementation tasks.
5. The external hako gist was reviewed on 2026-07-28. It recommends external
   TTS followed by Melodyne-style pitch correction and conventional audio
   editing; it adds no Piper-specific technique beyond the already implemented
   constrained-pitch/formant/digital-finish direction. Keep attribution in any
   future documentation; do not copy or claim the tutorial as project work.

### Reply-latency audit (diagnosis, no performance change yet)

The local server is single-slot (`-np 1`). Background memory extraction can
occupy it after its short grace period, voice mode waits for the entire model
reply before Piper and full-buffer vocal processing, and changing runtime
context comes before the stable few-shot prompt material. Some requests also
run an intent classifier before normal generation. Add private phase timing
without message text before changing this architecture; likely remedies are
idle-only memory work, prompt-cache-friendly ordering, and sentence-level
speech pipelining.

### Desktop model/runtime upgrade â€” 2026-07-28

- The existing `llama.cpp/build` remains the CPU-only, Pi-safe runtime. A
  separate, ignored local CUDA 12.4 runtime is installed at
  `llama.cpp/runtime/desktop-cuda-12.4-b9637/`. It contains the matching b9637
  CPU executable, CUDA backend, and CUDART DLL packages; do not mix its DLLs
  into the CPU build.
- Three developer launchers now keep the roles explicit:
  `start_desktop_cuda.bat` runs the deployed abliterated Qwen3 4B companion as
  the **director**; `start_maintenance_coder.bat` runs the downloaded
  `Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf` as the **autonomous coder**
  for an explicit bounded editing session; and
  `start_full_maintenance_coder.bat` expects
  `Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf` as the on-demand
  **full-maintenance** profile. The 7B and 14B launchers both default to
  `models/` and accept `TORMENT_NEXUS_CODER_MODEL_PATH` and
  `TORMENT_NEXUS_FULL_MAINTENANCE_MODEL_PATH` respectively.
- `start_desktop_q8.bat` is the separate experimental desktop launcher for
  `models/Qwen3-4B-abliterated-bf16_q8_0.gguf`. It remains a **director**
  profile with its own server alias and prompt cache; do not replace or move
  the Q5 model that the normal desktop and Pi-compatible launch paths use.
- The verified 14B file is now present at that default `models/` path:
  8,988,111,200 bytes, SHA-256
  `e89a7ae4e2b456bf33c75cff35664751df20ff273e551d7cf7640aa9e84d3b79`.
  `start_autonomous_self_heal.bat` is the separate explicit opt-in wrapper
  for one startup cycle with the 7B profile; the normal 7B launcher stays off.
- `core.config` and `core.llm_server` now support optional GPU layer, display
  name, server-alias, and prompt-cache overrides. The original launcher has no
  new defaults. An alias mismatch refuses to reuse a live model from another
  profile, and separate cache directories keep a coder session from deleting
  the companion's warm cache.
- Do not hot-swap models inside one running assistant yet. Model calls share
  one endpoint, memory work can run in the background, and the current main
  process retains the server ownership handle. Exit one profile before starting
  the next. The intended planned-edit sequence is: `modify plan`, `approve
  plan`, exit the director, launch the 7B coder, `preview plan`, then `confirm
  edit`. The 14B profile is intended primarily for the explicit `full self
  heal` transaction; it can also preview and confirm an already approved plan.
  Its full session validates after each bounded change and rolls back if it
  cannot return the fixed checks to green.
- Verified locally: RTX 4060 CUDA device detection; 4B Q8 full offload at
  about 48 tokens/sec; Coder 7B Q8 at 16 GPU layers and 4K context at about 21
  tokens/sec. The moved abliterated 7B Q8 was reverified at 16 GPU layers / 4K
  context with flash attention and Q8 KV cache: about 17.7 generated tokens/sec
  and 2.3 GB VRAM free. The 16-layer profile used about 5.6 GB VRAM while
  loaded. The
  14B Q4_K_M profile works at 20 GPU layers / 4K context with flash attention
  and Q8 KV cache: about 8.5 prompt tokens/sec and 12.2 generated tokens/sec,
  using about 4.0 GB extra VRAM and leaving 2.6 GB free. Full suite after this
  work: **346 tests, OK, 15.422 seconds**.
- The downloaded Qwen3 4B Q8 is only an experimental comparison model. The
  deployed Q5 companion is also abliterated, so do not frame this as a change
  in authority or a loss of a model-based safety boundary. Benchmark the Q8
  build before promoting it because it is a different conversion/source with a
  smaller recorded context, not because its alignment is the guardrail. The
  14B target is deliberately an *Instruct-abliterated* coder and must stay
  on-demand; remeasure its partial GPU offload rather than treating CUDA as a
  property of the model file.
