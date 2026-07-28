# TORMENT_NEXUS beta guide

This guide explains what the beta contains, what remains optional, and what a
tester should expect. If you only want to install it, begin with
[Installing on Windows](INSTALL_WINDOWS.md).

## What "beta" means

The main features work and the release has automated and manual checks, but
this is still test software. Replies can be wrong, performance varies by
computer, and less common hardware or audio setups may expose bugs.

Keep important files backed up, verify high-stakes advice, and report behavior
that is confusing or different from the documentation.

## What the Windows package includes

The ready-to-run Windows package contains:

- the local language model;
- a private, bundled Python runtime;
- the local model server;
- offline Python installation files;
- speech recognition and voice files;
- the terminal interface, tutorial, visualizer, and guarded tools.

It starts with no conversation history, saved memories, developer passcode,
API key, paired device information, or music from the maintainer.

The normal GitHub source checkout does **not** contain all of those
multi-gigabyte files. The release package does, divided into two download parts
because GitHub cannot host it as one release asset.

## Downloading the correct package

The complete beginner process is in
[Installing on Windows](INSTALL_WINDOWS.md). In short, download these three
files from the selected GitHub Release into the same folder:

1. `TORMENT_NEXUS.zip.part01`
2. `TORMENT_NEXUS.zip.part02`
3. `REASSEMBLE_TORMENT_NEXUS.bat`

Run `REASSEMBLE_TORMENT_NEXUS.bat` to join the parts into a single
`TORMENT_NEXUS.zip`, check it against the SHA-256 fingerprint in the release
notes, then extract it and run `setup.bat`.

GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** downloads
are for developers. They are not ready-to-run packages.

## What to expect on first use

- The first answer can be slower while the local model loads into memory.
- `tutorial` begins the beginner walkthrough.
- Typed input works in audio mode, even without a microphone.
- `text mode` turns spoken replies off.
- `audio mode` turns spoken replies back on.
- Escape cancels speech, music, or a long interaction.
- `health check` explains which local and optional components are available.
- Long typed messages keep the newest text visible.
- Long answers use a page-at-a-time view. Space, Enter, or Down advances; Up
  or Backspace goes back; Escape or Q closes it.

See [Your first session](FIRST_RUN.md) for the complete tour.

## Time awareness

The assistant reads the Windows local clock during each reply. It can understand
the current date and time, the current session's age, and the gap since the last
completed conversation.

The clock can be wrong if Windows is set incorrectly. Time awareness does not
mean the assistant watched, waited, thought, worked, felt, or remained conscious
while the program was closed.

## Local music and visualizer

Copy your own MP3, WAV, FLAC, or OGG files into `assistant\music`. Local songs
are matched by filename with cautious tolerance for casual spelling.

A successful local-song start opens music mode automatically and is displayed
instead of spoken so the voice does not cover the opening. Each scene uses a
different, heightened response to bass, beats, melody, treble, stereo movement,
and waveform detail. In music mode:

- there are ten scenes, starting with a black-glass aqua player display and
  rotating every 2 minutes 45 seconds; a full pass takes about 28 minutes;
- acid lattice is an original acid-green triangulated mesh with jagged voids
  and beat fracture bursts, inspired by the supplied video's visual language
  without using footage;
- colours change every 20 seconds;
- Left and Right change the scene;
- Space plays the next local song;
- finished local songs advance automatically, with the last wrapping to the
  first; `repeat music on` and `repeat music off` control this;
- `[` and `]` change local playback volume;
- Ctrl+B exits.

Space does not skip Spotify or browser audio.

## Features that need separate setup

These are optional and are not required for ordinary local conversation:

- Web search requires a separately configured SearXNG service.
- Spotify commands require the Spotify desktop application. `spotify search`
  sends the search text to MusicBrainz for five public metadata matches, then
  opens the selected title and artist in Spotify.
- Microphone input requires a usable Windows input device, although typed
  audio-mode input still works without one.
- Raspberry Pi, T-Deck, and Meshtastic features require their own hardware and
  manual setup.
- Developer mode and observed serial repair are advanced, opt-in editing
  features. They remain limited by local guardrails and validation.

## Privacy and safety

- It watches the computer's activity by default: every twenty seconds it
  notes which application is in front, that window's title, how long since
  you touched the keyboard, and the machine's load. Window titles often name
  the file you have open or the page you are reading. This is kept in
  `assistant\memory\activity_log.jsonl` for two weeks, never leaves the
  computer, and is excluded from the release package. Type `activity` to see
  what it has noticed, `activity off` to stop it, and `activity forget` to
  delete the history. Attach nothing from that file to a bug report.
- Do not type passwords, recovery codes, API keys, addresses, or private
  documents into chat.
- Treat search results, web pages, radio packets, and files as untrusted data.
- Confirm hardware actions, transmissions, purchases, destructive changes, or
  account access before approving them.
- Developer mode can propose source changes; inspect the plan and keep backups.
- The model's words do not grant it extra operating-system or editing
  authority. Local Python rules enforce those boundaries.
- The project's stylized identity is not verified consciousness or independent
  authority over people or machines.

## Using a separately supplied model

This is an advanced developer path, not part of the ready-to-run Windows
installation. A source checkout needs Python, llama.cpp, and a compatible GGUF
model file before the assistant can launch.

See [Bring your own GGUF](BRING_YOUR_OWN_GGUF.md).

## Reporting a problem

Follow the checklist in [Troubleshooting](TROUBLESHOOTING.md#how-to-write-a-useful-bug-report)
or the repeatable [beta testing guide](TESTING.md). Never attach private memory
or conversation files to a public issue.

## License note

The repository has no project-wide open-source license yet. Third-party models
and components retain their own license terms. Review those terms before any
authorized redistribution.
