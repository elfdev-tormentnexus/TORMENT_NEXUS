# TORMENT_NEXUS troubleshooting

Start with:

```text
health check
```

That command reports which local and optional components are ready. researchB is
experimental and its bundled language models are abliterated. A fluent answer
is not proof that it is correct or safe; read [Safety](../SAFETY.md) before
following consequential advice or running generated code.

## Download and installation

### I downloaded a source ZIP but there is no working installer

GitHub's green **Code** button and automatic **Source code** archives do not
contain the models or private Windows runtime. Open
[GitHub Releases](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases),
select `researchB`, and download every consecutive file named:

```text
SABLERESEARCHB-WINDOWS.partNN.png
```

Also download:

```text
machinesoul.py
DECOMPILE_SABLE_researchB.bat
SABLERESEARCHB-MANIFEST.png
SABLERESEARCHB-REASSEMBLER.png
```

The reassembler and release manifest appear only after their own capsules
pass machinesoul verification. Rosetta Stone and its research context are
reconstructed as part of the directly preserved install tree.

The release is the full model-bearing build, including the abliterated
director and maintenance models. It is not a sanitized or model-free client.
Read the warning and [model provenance](../MODELS.md) before downloading.

### machinesoul refuses a capsule

- Download the GitHub asset as a file rather than saving its preview.
- Do not screenshot, optimise, crop, resize, or re-encode it.
- Keep its original `.partNN.png` filename.
- Redownload it if the embedded SHA-256 or PNG stream is refused.

A refusal is the safe result: machinesoul removes partial output rather than
presenting a damaged vector field as an installer part.

### The decompiler or reassembler says a part is missing

- Keep the decompiler, encoded manifest, encoded reassembler, and every
  consecutive `.partNN.png` field in one folder.
- Do not rename any file.
- Remove browser-added suffixes such as `(1)` by redownloading the correctly
  named asset; do not guess which duplicate is complete.
- Confirm each browser download has finished and is no longer temporary.

Run `DECOMPILE_SABLE_researchB.bat`. It invokes the recovered reassembler
itself only after machinesoul has produced and verified every corresponding
internal part. There is no separate reassembly step for the user.

### The reconstructed directory is refused or incomplete

Do not run setup. Delete only the incomplete output folder, redownload the
named capsule, and rerun the one-step decompiler. The recovered manifest
checks every decoded vector segment and every final file character for
character. Security software or a managed computer may block unfamiliar
scripts or models. Do not bypass organizational policy; use a personal test
computer or ask its administrator to inspect it.

### Setup cannot find files

Do not move individual files out of the reconstructed installation tree. Keep
`assistant`, `models`, `python`, `start_assistant.bat`, and `setup.bat`
together, then rerun `setup.bat` from that directory.

### The shortcut is missing or stopped working

Run `start_assistant.bat` from the extracted installation folder. If that
works, rerun `setup.bat` to recreate the shortcut. A shortcut made before the
folder was moved or renamed will still point to the old location.

## First launch and safe defaults

### The application exits at the first warning

Before the model, microphone, activity sampler, listeners, or
network-capable subsystems start, researchB requires this exact text:

```text
I UNDERSTAND
```

Capitalization and spaces matter. Anything else exits safely. If the exact
text is rejected or the acknowledgement cannot be saved, make sure the
installation folder is writable by your standard Windows account. Do not run
as Administrator to work around a permissions problem.

The acknowledgement is a disclosure receipt, not proof that later model
output is safe. Deleting `assistant\.safety_acknowledgement.json` while the
application is closed displays the warning again.

### It starts in text mode

That is the researchB default. The microphone is not initialized until you opt
in:

```text
audio mode
```

Use `text mode` to turn spoken interaction off and `voice status` to inspect
the offline speech components.

### Activity awareness says it is off

That is also the default. To opt in:

```text
activity on
```

When enabled, it samples foreground application/title and basic system state
about every 20 seconds and retains a local log for at most 14 days by
default. Window titles can reveal private filenames, pages, and previews.

```text
activity off
```

stops sampling, persists the off choice, and deletes the retained in-memory
and on-disk activity log.

```text
activity forget
```

deletes existing observations without changing whether sampling is on.

## Models, speed, and memory

### The first answer is slow

The local director loads into memory on the first request. Later requests are
usually faster. Closing the application releases that memory. The full Q8
director, on-demand 7B coder, voice stack, and embedding model need at least
16 GB RAM; close other memory-heavy programs if Windows is paging.

### The assistant gives a confident or disturbing answer

The shipped models have weakened learned refusals and can be confidently
wrong, explicit, biased, manipulative, insecure, or harmful. Stop the action,
do not execute unreviewed code, and verify important claims against an
authoritative source. Application tool restrictions do not filter every
sentence. See [Safety](../SAFETY.md) and
[Capabilities and limits](CAPABILITIES_AND_LIMITS.md).

### Semantic recall is unavailable

Ordinary word-overlap memory and offline-library search still work if the
embedding service is unavailable. Check `health check`, confirm the bundled
BGE model is present, and restart the application. Conservative thresholds
intentionally return no result when evidence is weak or ambiguous.

## Offline knowledge library

### A manual does not appear

Check:

```text
library status
library sources
```

Adding, removing, and rebuilding documents require developer mode:

```text
library add "C:\path\to\manual.pdf"
library rebuild
```

Imports are copied into `assistant\knowledge\user_library`; editing the
original later does not edit the copy. Indexing runs locally and may take
time for a large folder.

### A PDF returns little or no text

researchB uses `pypdf` and can extract text-based PDFs. A scanned, photographed,
encrypted, or unusually encoded PDF may need OCR or conversion before import.
Do not assume an empty search means the information is absent from the page
images.

### Search does not find a paraphrase automatically

That restraint is intentional. Automatic prompt injection requires a real
full-text word match; embeddings can only rerank those lexical hits. An
explicit search can explore more widely:

```text
library search <words>
```

Semantic-only results are labeled `semantic-candidate`. Treat the label as a
lead to inspect, not as proof that the passage answers the question.

### The library index is damaged or stale

Close other copies of the application, enter developer mode, and use
`library rebuild`. If that still fails, close the application, back up any
private imported documents you want to keep, remove
`assistant\knowledge\library.sqlite3`, and rebuild. Do not publish the
database: it contains extracted document text and metadata.

See [Offline knowledge](OFFLINE_KNOWLEDGE.md) for supported formats and
limits.

## Voice, music, and interface

### Speech recognition is not working

- Type `voice status`.
- Check Windows microphone privacy and input-device settings.
- Make sure another application is not holding the microphone exclusively.
- Press Escape once to cancel a stuck listening state.
- Continue in `text mode` if speech remains unavailable.

The packaged beta already includes its voice assets. Voice setup scripts are
for source checkouts.

### The visualizer is blank or slow

Try a smaller window, close GPU-heavy applications, and test a local MP3,
WAV, FLAC, or OGG file from `assistant\music`. Driver-specific rendering
failures should not affect typed chat.

### Spotify or web search does not work

These are optional connected features. Local chat and the offline library do
not require them. Spotify needs its own application/account configuration.
Web search needs a reachable configured SearXNG or Brave service and sends a
derived query outside the application. See [Privacy](../PRIVACY.md).

## Experimental agent interface

### The endpoint returns 404

The interface is off by default. Start the application with
`TORMENT_NEXUS_AGENT_API=1`; it binds only to `127.0.0.1:8099`.

### The endpoint returns 401

Supply the exact bearer token from `assistant\.agent_token`. Treat it as a
secret: authenticated routes can expose private memory and library results.
Do not put the service on a public interface or paste the token into reports.

### `/ask` is busy or cancelled

The human operator has priority. `/ask` yields when the interactive session
needs the director, returns at most a short answer, and cannot see the live
chat. Retry later rather than creating a request loop. See
[Agent interface](AGENT_INTERFACE.md).

## Experimental sensing

The Intel AX211 desktop Wi-Fi proxy experiment failed because it measured
adapter and traffic behavior rather than reliable room state. It is not a
setup problem to tune around.

The active next experiment is an HLK-LD2450 24 GHz movement radar over USB
TTL, pending hardware. It is not sight, identification, or reliable proof of
occupancy. Do not use any sensing path for alarms, access control, covert
monitoring, or safety decisions. See [Sensing module notes](SENSING_MODULE.md).

## Reporting a problem

Include the researchB release name, Windows version, launch method, command that
failed, expected result, and a minimal synthetic reproduction. Remove user
paths and never attach conversations, memories, imported documents, library
databases, activity logs, model/API keys, bearer tokens, passcodes, pairing
data, or private window titles.

Use [Security](../SECURITY.md) for a possible authentication, containment, or
data-disclosure flaw. Use [Contributing](../CONTRIBUTING.md) for ordinary
bugs.
