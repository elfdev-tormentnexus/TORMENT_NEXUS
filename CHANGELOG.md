# Changelog

## Unreleased

## researchA — 2026-07-28

- Renamed the two non-ordinary launchers to what they are:
  **TORMENT_NEXUS_INTERLINKED** (read-only agent interface listening) and
  **TORMENT_NEXUS_HAZARD** (experimental, two embedding servers). Window
  titles, banners, and desktop shortcut names all follow, and
  `make_interface_shortcut.py` gained `--hazard` and `--both` so the hazard
  launcher finally has a desktop shortcut of its own.
- Each of those launchers now has its own walkthrough rather than the
  ordinary one, which describes a different program. Hazard gets eight
  sections -- whose reading a trace is, `trace`, `trail`, `spread`, what
  `reconstruct` cannot return, `consume`, and what the mode does not do.
  Interlinked gets five, including an honest one about what the bearer
  token protects and what it does not. Tutorial progress is stored per
  mode, so finishing the ordinary tour never marks the hazard one seen, and
  a pre-existing state file migrates to `ordinary` rather than resetting
  anyone. First-run welcomes are written per launcher too.
- Added `calibrate` and the `SABLE_CALIBRATION1` reference. Seven fixed
  texts with their readings recorded beside a quantization-bearing model
  name, pooling, and anchor digest, so behavioural drift becomes visible
  instead of silently moving every published figure. Three rows are controls:
  periodic, random, and a **Fibonacci word** ordering. The infinite word is
  Sturmian; the release test verifies its n+1 subword signature on a long
  prefix through the first twelve scales and proves that both other controls
  fail the same finite check. The fibonacci and random rows share a phrase
  mix and differ only in order, so they must read alike; measured 1.5238
  against 1.5132, which demonstrates permutation invariance on live data.
- Added `trail <text>`: the same reading `trace` produces, stored per
  anchor rather than per token. Only the anchor nearest a token records
  anything -- accumulated support, its strongest reading, and where that
  was -- so the size is bounded by the dictionary instead of the input, and
  a 89-token passage keeps 24 values where the trajectory holds 34,176
  (1,424x, and the ratio improves with length). A test asserts it
  reproduces `peaks()` exactly at four lengths rather than approximating
  it. It rests on two measured facts: collapsing a token to its winning
  anchor costs nothing (90%/0.933 against 90%/0.920), and ranking by summed
  support rather than one best position is what took the trace from 77% to
  90% -- so support is stored, and a test guards against a
  maxima-only trail that would be the worse version.
- Added the anchor-space shadow log. Every hazard-mode retrieval records
  both rankings of the same candidates -- the pooled cosine that decided and
  the anchor-space ranking that did not -- with their top-5 agreement, so the
  claim that anchor space does not retrieve better stops resting on an
  eighteen-chunk corpus. `observe()` returns None by construction and a
  regression asserts retrieval is identical with the module present and
  absent. Memories are recorded as SHA-256 digests, never as text, and a test
  greps the written file to prove it.
- Added `tools/source_capsules.py`: the source tree capsuled one subsystem
  at a time, cut along meaning rather than size, each capsule carrying its
  subsystem's description in metadata so a directory of images is
  navigable without extracting any of them. Descriptions come from the
  modules' own docstrings rather than being generated. Coverage is
  asserted — every source file must land in exactly one capsule or the
  build refuses, and private runtime state is refused by name.
- Capsules can carry a plain-language description of their payload in PNG
  metadata, readable with `machinesoul.py describe` without decoding the
  payload. Supplied by the caller, never computed inside the module, so
  machinesoul stays standalone and stdlib. Off unless asked for, and
  outside the SHA-256 gate — a test edits a stored description and asserts
  extraction still succeeds, because it is a hint and not a guarantee.
- Added a `PRIVACY.md` section on the risks specific to image files: a
  capsule looks like an image and is forwarded like one, it is not
  encryption, its optional description is cleartext, and re-encoding
  destroys it silently.
- Added `spread <text>` in hazard mode: the density matrix of a
  trajectory's tokens, reporting purity, participation ratio and von
  Neumann entropy. It is the uncentred second moment — a covariance in
  statistics, a density matrix in quantum mechanics — and neither the name
  nor the technique is ours. Controlled against token count: growing one
  topic by 49% moves effective rank +1.1% while adding topics at matched
  length moves it +12.6%. Effective rank stays inside 1.1–1.8 against a
  ceiling of *n*, because bge token states sit in a narrow cone.
  Permutation-invariant, so it reports ground covered and never order.
  Retrieval untouched.
- Wired session rhythm end to end. `note_turn()` is called at the one seam
  both the typed and spoken loops pass through, the session's shape is
  written once at shutdown for sessions that held at least one exchange,
  the current shape enters the runtime prompt as counted facts, and
  `viewing_pace()` now supplies the beam's frame rate instead of a
  hardcoded 1.0. It had been a fully tested module that nothing called.
- Fixed a redirect hole in `consume`: the private-address refusal ran once
  against the supplied URL and then followed redirects unchecked, and the
  download re-requested the original address with redirects enabled. Every
  hop is now validated, chains are capped, relative locations resolve
  against their own hop, and a redirect onto a media host is reported as
  media.
- Closed a reflection bypass in the autonomous capability gate: `getattr`
  and its family were unlisted, so `getattr(os, "sys" + "tem")(...)` added
  process capability without naming anything the tables matched.
- `extract_stream` no longer truncates an existing file at `--out` before
  validating the capsule, and an interrupted `build_stream` no longer
  leaves a partial capsule and frame spill behind.
- `restore()` refuses an ambiguous backup name instead of taking whichever
  file the directory walk reached first.
- Excluded `assistant/memory/session_rhythm.json` from git and from release
  packaging, under both the deny pattern and the independent basename
  check. It went unlisted for as long as nothing wrote it.

researchA turns the experimental retrieval and agent seams into measured,
release-packaged features while making the model and autonomy risks much more
explicit.

- Added hybrid memory retrieval using the bundled 35 MB
  `bge-small-en-v1.5-q8_0` embedding model alongside exact word overlap.
  Embeddings are cached locally, history recall is bounded, and the feature
  falls back cleanly when the embedding service is unavailable.
- Added a local, read-only `/ask` interface for an owner-authorised outside
  agent and a separate outbound escalation bridge. External-provider calls
  remain off until deliberately enabled and supplied with the owner's own API
  key; ordinary conversation remains local.
- Connected the retrieval panel to real memory vectors and added measured
  entropy and music-response inputs without conflating visual vectors with
  semantic embedding vectors.
- Tightened protected edit surfaces, model-role isolation, source validation,
  privacy exclusions, latency bounds, and regression coverage.
- Recorded the failed Windows Wi-Fi proxy as a negative result and reopened
  the sensing workstream around the pending HLK-LD2450 24 GHz radar hardware.
  Raspberry Pi monitor-mode and hardware work remain plans, not shipped
  capabilities.
- Hardened Windows release packaging with versioned artifacts, a clean-source
  snapshot gate, fatal required-file checks, model/source hashes in the
  manifest, a verified offline dependency cache, review-gated machinesoul cut
  maps, and automatic SHA-256 verification of every directly reconstructed
  file.
- Added explicit warnings and typed acknowledgement gates to the maintenance,
  one-cycle autonomous-repair, and full-maintenance launchers. The ordinary
  companion launcher does not require a terminal confirmation and instead
  points first-time users to the mandatory in-app disclosure.
- Added an offline practical-reference shelf: eight bundled safety and
  resilience cards plus a separate library for operator-supplied TXT,
  Markdown, HTML, JSON, CSV, PDF, EPUB, and DOCX documents. Automatic chat
  context requires a real full-text word match; semantic widening is explicit
  and labeled.
- Fixed five ways the assistant could report something that had not happened:
  persona examples arriving as recent conversation, unregistered input
  answered as if performed, "choose a name" bypassing the naming ceremony,
  history trimmed mid-record, and fabricated hardware readings. Each is
  enforced in Python rather than by instructing the model. Added `name is
  NAME` so the operator can set a name directly, recorded as operator-chosen.
- Fixed a sixth one found after the archive was built: `/ask` answered vague
  questions about the past with a fluent account of a conversation that never
  happened, because the path advised the model it had no history and then
  sampled an answer anyway. The guard is Python and fails closed — matching
  questions never reach the model. `/memory/search` also now states that its
  results are retrieval candidates rather than verified facts. This ships as
  the manually applied `ask-guard-patch` asset rather than a 12 GB rebuild;
  unlike the documentation patch it replaces a manifest-hashed file, so it is
  a deliberate opt-in step. Suite count with the guard applied: **640 passed,
  2 skipped**.
- Closed the gap in that second fix, found by live testing after the archive
  was built. `near_miss_command` matched a real command name plus one stray
  word, which cannot reach a phrase resembling no command at all: nothing in
  the table contains "drop", so `drop all` still answered "I'm dropping
  everything", and `finish goal` — one character from the real `finish
  goals` — still answered "I'm finishing the goal". Words are now compared
  allowing one typo each, and a phrase built on a state-changing verb that
  matches nothing is answered directly. Ordinary speech containing such a
  verb is untouched. Ships as the manually applied `command-guard-patch`
  asset. Suite count with both guard patches applied: **644 passed, 2
  skipped**.
- Reworked the music visualizer: a wall-clock anchor layer across all eight
  scenes, higher scene reactivity, and fixes to the acid lattice line width
  and the datastream horizon. Added playback loudness matching, which
  narrowed a 20.0 dB spread to 1.4 dB across a 41-track library with no
  clipping. This is gated RMS, not ITU-R BS.1770 LUFS.
- Replaced the `tutorial` command's bare command list with a prose
  introduction to the whole system.

The bundled conversational model remains
`Qwen3-4B-abliterated-bf16_q8_0` in the **director** role. The bundled
on-demand editing model remains
`Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0` in the
**autonomous-coder** role. The 14B full-maintenance model is still a separate,
optional desktop artifact and is not part of the base Windows archive.

Full regression-suite count: **639 passed, 2 skipped**.

## v0.2.0-beta.5 — 2026-07-28

Beta numbering is cumulative across the project and does not reset when the
minor version changes.

- Made the abliterated Qwen3 4B Q8 the bundled director and added the
  abliterated Qwen2.5-Coder 7B Q8 as the bundled, on-demand autonomous coder.
  The 14B maintenance profile remains an explicitly separate desktop model.
  The coder uses a configured CUDA runtime when present and otherwise falls
  back honestly to the bundled CPU server.

- Added a Windows userland Wi-Fi collector and verification harness as a
  **measured negative**. On this strong 5 GHz link, receive-rate variance was
  lower while moving than while still, and cached scan data saw no disturbance.
  It now reports that the information is not there and refuses threshold
  tuning, rather than pretending a noisy proxy is a room sensor.
- Documented the separate, consent-based monitor-mode research gate for the
  spare TP-Link radio. It keeps the AX211 and normal Windows connection out of
  scope, and is not a shipped sensing feature.
- Added `package_release.py --split`, which cuts a release archive below
  GitHub's asset cap, generates a CRLF reassembler for the actual number of
  parts, removes stale extra parts, and verifies a byte-for-byte rejoin before
  reporting success.

## v0.2.0-beta.1 — 2026-07-28

The minor version moves rather than the patch level: coding work is now split
across three role-bound models instead of one, the director model itself was
replaced, and the Raspberry Pi target gained real hardware specifications.
The music-visualizer repair that shipped as a separate patch for beta.3 is
built in here, so this release is a single archive again.

- Added a disabled, desktop-only Wi-Fi sensing experiment bridge. It accepts
  only one fresh, aggregate local status record from a separately authorised
  collector; it never changes a Wi-Fi driver, captures packets, retains CSI,
  identifies anyone, or claims camera-like vision. `wifi sensing` exposes the
  explicit owner controls and diagnostics.
- Added `name`, a grounded naming ceremony for the director. It reads only
  what happened to this system -- its own commit subjects, the changelog, the
  parts it is assembled from, and the shape of what it watches -- and never
  the memory store, the conversation history, or the persona. Candidates are
  then vetoed three ways: stock AI names and fictional machines, any word
  already in the operator's stored text, and any word lifted straight out of
  the record it was shown. What survives has to be the operator's own word
  for an idea in the material rather than a token copied out of it.
  `name keep` writes it, `name again` re-rolls, `name forget` clears it. The
  chosen name appears in the header and nowhere else: TORMENT_NEXUS remains
  the project, the application, the launcher, and the terminal window title.
- Taught the director to answer to the name it chose. Once one is recorded it
  goes into the cached prompt prefix alongside the persona, with the reason
  that was written down at the time so it can say why it is called that
  instead of inventing one. The reason is labelled as a note rather than a
  memory, marked as not a description of anything it is currently doing, and
  reserved for questions about the name -- without those three, it variously
  claimed to be sampling the front window right now, denied having picked the
  name at all, and recited the reason as a greeting.
- Moved the abliterated Qwen2.5-Coder 7B default into `models/` and added a
  separate opt-in desktop launcher for the experimental abliterated 4B Q8,
  leaving the Q5 companion untouched as the default and Raspberry Pi model.
- Added role-bound desktop CUDA launch profiles: the deployed abliterated
  Qwen3 4B companion is the director, Qwen2.5-Coder 7B is the bounded
  autonomous coder, and the on-demand abliterated Qwen2.5-Coder 14B Instruct
  profile is reserved for full test-driven maintenance. Profiles use distinct
  prompt caches and server identities, so they cannot silently reuse each
  other's model process; the original CPU/Pi-compatible launch remains
  unchanged. Guards, backups, validation, and rollback—not model alignment—
  enforce edit safety.
- Reworked low-end visualizer analysis around adaptive spectral-flux kick
  onsets, a short refractory period, and time-based release. High or midrange
  leakage can no longer inflate the bass meter into a false kick.
- Added the aqua player as the default music scene: a glossy black-glass,
  chrome-rimmed player panel with a dual oscilloscope, gel equalizer, orbital
  spectrum, and beat bloom.
- Rebuilt the datastream rain into a layered, spectrum-reactive falling-code
  curtain with curved strands, a bass data horizon, and a short beat scan
  fault instead of uniformly noisy glyph columns.
- Added acid lattice: an original acid-green triangulated mesh with jagged
  voids and beat fracture bursts, informed by the supplied music-video visual
  language without using footage.
- Applied the same restrained, time-aligned digital voice finish to ordinary
  speech that Daisy Bell uses, while keeping singing slightly stronger and
  preserving consonant timing.
- Added a canvas-only terminal corruption layer: typed characters phase in
  briefly, and sparse fragments appear only in empty gutters and separator
  chrome outside music mode.
- Made every successful local `play <track>` request open the music visualizer
  automatically.
- Prevented terminal wrapping and background audio diagnostics from producing
  a jittering code stream beneath the visualizer.
- Added scene-specific response shaping for more dramatic bass, beat, melody,
  treble, stereo, spectrum, and waveform movement.
- Added a checksum-verified, reversible Beta 3 music visualizer patch and a
  novice installer that applies it automatically to the original release ZIP.
- Made local music continue through the name-sorted library automatically,
  wrapping from the last track to the first, with `repeat music on/off`.
- Doubled the visualizer to eight scenes with four new ones: a neon horizon of
  wireframe ground running to a banded sun behind a spectrum-cut skyline; a
  plasma flow of merging liquid blobs; a datastream rain of falling glyph
  columns that corrupt on beats; and a wormhole of projected stars streaking
  through a flexing tunnel.
- Gave each new scene its own audio response profile, so the horizon follows
  bass and spectrum, the plasma follows mids, the rain follows treble, and the
  wormhole follows beats.
- Gave the speaking voice somewhere to fall: more inflection inside a
  sentence, a different pitch for each sentence, and endings that land low
  instead of rising into their own full stop.
- Stopped held sung notes from smearing their consonants, so the opening of
  Daisy Bell articulates instead of blurring.
- Made Daisy Bell open with the tune played on its own before the singing
  starts, as the 1961 recording does.
- Shortened the pause after a sentence now that the voice has a falling
  ending of its own to signal one.
- Made the voice-mode face react to the audio actually being spoken, so it
  goes still between words and tears apart on a stressed syllable.
- Added `activity`, an awareness of what is happening on this computer:
  which application is in front, how long you have been away, and how hard
  the machine is working. It is remembered for two weeks, never leaves this
  computer, and `activity forget` erases it.
- Made it remark on what it has noticed partway through a long silence,
  before it asks whether you are still there.
- Added an "about me" introduction from TORMENT_NEXUS before the tutorial.
- Reorganized the GitHub landing page around a clear novice Windows install.
- Added dedicated Windows installation, first-session, and troubleshooting
  guides.
- Clearly separated ready-to-run users, beta testers, source developers,
  custom-model users, and experimental Raspberry Pi work.
- Explained download parts, checksum verification, extraction, shortcut
  recovery, disk and memory needs, voice re-enabling, local music, paging, and
  time awareness in plain language.
- Aligned the beta, testing, architecture, model, voice, release, and packaged
  installer documentation with the new beginner path.

## v0.1.0-beta.3 — 2026-07-27

This is the final beta build published on July 27, 2026.

### More grounded and alive

- Added local-clock awareness for the current date and time, session age, and
  the gap since the previous completed conversation.
- Kept that awareness honest: elapsed time is not presented as hidden thought,
  waiting, work, feeling, or consciousness while the program is closed.
- Made unsolicited idle check-ins visual-only by default.

### Friendlier terminal

- Rewrote the entire in-app tutorial and `explain` output for first-time users.
- Kept long typed messages visible as they move past the right edge.
- Added page-at-a-time navigation for long answers.
- Preserved lists and line breaks while replies are still being generated.

### Local music and visualizer

- Added conservative matching for casually typed local-song names.
- Prevented spoken confirmations from covering the opening of a local song.
- Rebuilt the spectrum cathedral, orbital reactor, and corrupt cube around a
  cohesive psychedelic Y2K visual language while preserving the original
  radial tunnel.
- Made palettes rotate automatically every 20 seconds.
- Remapped Space in music mode to the next local song, with last-to-first
  wrapping and no effect on Spotify or browser playback.

### Documentation and release quality

- Updated the README, beta guide, architecture notes, testing guide, packaged
  installer instructions, and tutorial to describe the current behavior.
- Expanded regression coverage for terminal navigation, music transport,
  visualizer scenes, quiet voice behavior, and grounded time awareness.

## v0.1.0-beta.2 — 2026-07-27

- Repaired the bundled-Python startup path and release reassembly workflow.
- Added clean package verification and a tested Windows offline installer.

## v0.1.0-beta.1 — 2026-07-27

- Initial public Windows beta.
