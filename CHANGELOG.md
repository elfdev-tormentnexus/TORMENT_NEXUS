# Changelog

## Unreleased

## v0.2.0-beta.6 — 2026-07-28

Beta 6 turns the experimental retrieval and agent seams into measured,
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
  manifest, a verified offline dependency cache, and automatic SHA-256
  verification after the numbered ZIP parts are joined.
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
