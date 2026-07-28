# Changelog

## Unreleased

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
