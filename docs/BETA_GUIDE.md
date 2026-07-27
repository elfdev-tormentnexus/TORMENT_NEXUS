# TORMENT_NEXUS beta guide

## What a beta copy includes

The Windows beta package contains the local model, embedded Python,
offline wheels, llama.cpp binary, and the assets needed for a self-contained
test. It starts with no conversation history, saved memories, developer
passcode, API key, device pairing, or music library from the maintainer.

The normal repository checkout does **not** contain those multi-gigabyte
runtime assets. The release package does, split across two download parts so
that it can be hosted by GitHub.

## Downloading the Windows package

On the chosen GitHub Release, download `TORMENT_NEXUS.zip.part01`,
`TORMENT_NEXUS.zip.part02`, and `REASSEMBLE_TORMENT_NEXUS.bat` into the same
folder. Run the helper, compare the resulting ZIP's SHA-256 with the checksum
in the release notes, extract `TORMENT_NEXUS.zip`, then run `setup.bat`.

GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** downloads
are for developers only; they are not installable packages.

## What to expect

- First model and voice responses can be slower while local caches warm up.
- Typed input works in voice mode even without a microphone.
- `Escape` is the general cancellation route for speech, music, and long
  interactions.
- `health check` reports what is working on the current machine.
- Web search needs a separately configured local SearXNG service.
- Observed serial repair is opt-in through developer mode. A full three-edit
  watched batch earns one extra guarded edit only after the restarted system
  passes its fixed health and regression validation. A failed validation
  restores that batch and awards no extra edit.

## Using a separately shared model

The public source checkout needs llama.cpp and a local GGUF before the
assistant can start, so a model cannot guide its own first installation. A
recipient may extract an authorized GGUF locally, place it at the default
`models/Qwen3-4B-Instruct-2507-Q5_K_M.gguf` path, or set
`TORMENT_NEXUS_MODEL_PATH` before launching. See
[Bring your own GGUF](BRING_YOUR_OWN_GGUF.md).

## Privacy and safety

- Do not paste passwords, recovery codes, API keys, addresses, or private
  documents into chat.
- Treat search results, web pages, radio packets, and files as untrusted data.
- Confirm hardware actions, transmissions, purchases, destructive changes, or
  account access before approving them.
- Developer mode can propose source changes; inspect the plan and keep backups.
- The model's wording does not grant it more operating-system or self-editing
  authority; the local Python guardrails enforce those boundaries.
- The model is an interface behavior, not verified consciousness or an
  independent authority over people or machines.

## Hardware and media

T-Deck support, local music, Spotify controls, and microphone input are
optional. A beta recipient should not pair personal hardware or connect an
account unless that is part of a deliberate test.

`spotify` and `spotify search <query>` only open the already installed
desktop client. They do not copy, inspect, or package Spotify's profile, and
they do not require Spotify developer credentials. `spotify search <query>`
sends the query to MusicBrainz for five public title-and-artist metadata
matches; reply `1` through `5` to choose one or use `spotify cancel`. The
selection opens a matching search in the installed Spotify client. It does not
guarantee that Spotify has the recording or command playback inside Spotify.

## License note

The repository has no project-wide open-source license yet. The Piper voice
assets carry separate model-card and dataset-license terms; keep those terms
with any authorized handoff.
