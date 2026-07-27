# TORMENT_NEXUS beta guide

## What a beta copy includes

The private Windows handoff package contains the local model, embedded Python,
offline wheels, llama.cpp binary, and the assets needed for a self-contained
test. It starts with no conversation history, saved memories, developer
passcode, API key, device pairing, or music library from the maintainer.

The public GitHub repository does **not** contain those multi-gigabyte runtime
assets. It is a source repository, not the public installer.

## What to expect

- First model and voice responses can be slower while local caches warm up.
- Typed input works in voice mode even without a microphone.
- `Escape` is the general cancellation route for speech, music, and long
  interactions.
- `health check` reports what is working on the current machine.
- Web search needs a separately configured local SearXNG service.

## Privacy and safety

- Do not paste passwords, recovery codes, API keys, addresses, or private
  documents into chat.
- Treat search results, web pages, radio packets, and files as untrusted data.
- Confirm hardware actions, transmissions, purchases, destructive changes, or
  account access before approving them.
- Developer mode can propose source changes; inspect the plan and keep backups.
- The model is an interface behavior, not verified consciousness or an
  independent authority over people or machines.

## Hardware and media

T-Deck support, local music, Spotify controls, and microphone input are
optional. A beta recipient should not pair personal hardware or connect an
account unless that is part of a deliberate test.

## License note

The repository has no project-wide open-source license yet. The Piper voice
assets carry separate model-card and dataset-license terms; keep those terms
with any authorized handoff.
