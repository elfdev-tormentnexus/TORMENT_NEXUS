# Changelog

## Unreleased

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
