# TORMENT_NEXUS researchB architecture

This is a technical reference for developers and reviewers. New users should
start with [Installing on Windows](INSTALL_WINDOWS.md),
[Your first session](FIRST_RUN.md), and
[Capabilities and limits](CAPABILITIES_AND_LIMITS.md).

TORMENT_NEXUS is a local-first Python application around authenticated
llama.cpp services. Language-model behavior is separated from application
authority: the model proposes text or plans, while trusted Python decides
which command, file, network, hardware, or edit paths exist.

## Startup sequence

```text
start_assistant.bat
        |
mandatory first-run disclosure
        |
exact "I UNDERSTAND"?
    no  |  yes
   exit |  start director model
        |  start UI and local workers
        |  keep voice/activity/listeners off unless opted in
```

`assistant/core/first_run.py` runs before model loading, microphone
preparation, activity sampling, the agent listener, and other
network-capable subsystems. Acceptance is versioned and stored per
installation.

## Main runtime

```text
operator input
    |
    +-- explicit/natural command --> trusted command handler
    |
    +-- ordinary conversation
            |
            +-- stable persona and core memory
            +-- current live turns
            +-- trusted clock
            +-- opted-in activity/radio summaries
            +-- selected durable memories
            +-- explicit, high-confidence older-history recall
            +-- lexical offline-reference excerpts
            +-- optional untrusted web evidence
            |
            `-- authenticated local Qwen3 director --> streamed reply
```

## Component map

| Area | Responsibility |
| --- | --- |
| `assistant/main.py` | Startup order, session lifecycle, prompt assembly, streaming, retrieval coordination, agent route providers, and mode changes. |
| `assistant/core/first_run.py` | Mandatory versioned safety/privacy acknowledgement. |
| `assistant/core/` | Configuration, persona, clock/activity context, model and embedding server ownership, authentication, escalation, tutorial, and health checks. |
| `assistant/core/machinespirit.py` | Per-token trajectories read against a fixed anchor dictionary (`anchors_v2.json` by default; v1 remains loadable and keeps its digests). Requires **both** embedding servers — the unpooled one supplies the path, the pooled one embeds the dictionary — and `diagnose()` reports which is missing rather than blaming one for the other. Does not participate in retrieval. Also carries the density matrix of a trajectory (`spread`): purity, participation ratio, and von Neumann entropy, read off the `n × n` Gram matrix rather than the `384 × 384` second moment since the two share every nonzero eigenvalue. Permutation-invariant by construction — it reports how much ground a text covered, never in what order. |
| `assistant/core/consume.py` | Identifies what a URL points at, fetches the content rather than the surrounding page, and hands documents to the offline library. Refuses non-loopback-safe addresses, media URLs, and bodies that exceed the library's own ceiling mid-download. |
| `tools/machinesoul.py` | Sable's data-preservation logic language: maps ordered four-coordinate vectors to PNG/APNG pixels and reverses them 1:1. `MACHINESOUL1` is SHA-256 gated and refuses rather than returning a partial reconstruction. |
| `tools/machinespirit_codec.py` | Measures the lossy half as a codec — encode to anchor coordinates, decode by least squares, report cosine and whether the reconstruction still retrieves its own chunk. |
| `tools/rosetta_stone.py` | Builds one model-bound half of a `SABLEROSETTA1` anchor bridge. Two halves are comparable only when their shared anchor digest matches; model identity, quantization, and pooling still matter. |
| `tools/vector_beam.py` | Measures and renders the unpooled token trajectory, and can read it through a compatible Rosetta Stone anchor space. |
| `tools/pooling_probe.py` | Determines what the pooled server actually does by reconstructing each candidate pooling from the unpooled server's per-token output. |
| `assistant/core/session_rhythm.py` | Session duration, exchange counts, pause lengths, and rank against previous sessions. Timings only. A turn is counted at the one seam both the typed and spoken loops pass through; the summary is written once at shutdown, and only for a session that held at least one exchange. From three recorded sessions on, the median pause supplies the measured pace `tools/vector_beam.py` animates at. The current session's shape enters the runtime prompt as counted facts, so a claim like "the longest session I have a record of" can be checked against the file. |
| `assistant/core/tutorial.py` | Three walkthroughs, one per launcher: the ordinary tour, **TORMENT_NEXUS_HAZARD** (eight sections on traces, trails, spread, and what does not come back), and **TORMENT_NEXUS_INTERLINKED** (five on what is listening and what it can see). Mode is detected from the same facts the features use -- an unpooled embedder configured, an agent interface enabled -- and progress is stored per mode, so finishing one tour never marks another as seen. Lessons name commands; descriptions come from the live registry so they cannot drift. |
| `assistant/ui/` | Animated terminal, input, pagination, retrieval display, voice state, and visualizer controls. |
| `assistant/voice/` | Offline Moonshine recognition, Silero VAD, Piper synthesis, playback, and cancellation. |
| `assistant/commands/` | Explicit command registry and cautious natural-language routing. |
| `assistant/memory/` | Durable facts, bounded conversation history, conservative selection, embedding cache, and older-history recall. |
| `assistant/knowledge/` | Built-in cards, private user documents, extraction, chunking, SQLite FTS, separate vectors, and library commands. |
| `assistant/editing/` | Reviewable plans, backups, protected paths, bounded autonomous cycles, validation, and rollback. |
| `assistant/web/` | Optional SearXNG/Brave search and untrusted-result handling. |
| `assistant/hardware/` | Optional T-Deck and Meshtastic bridge. |
| `tools/` | Release packaging, diagnostics, visualizer helpers, and isolated research utilities. |

## Model roles

The complete researchB Windows package has three separate model jobs:

| Artifact | Role |
| --- | --- |
| Qwen3 4B abliterated Q8 | Ordinary director: conversation, persona, and planning through trusted capabilities. |
| Qwen2.5-Coder 7B abliterated Q8 | On-demand maintenance coder. |
| BGE small English v1.5 Q8 | Non-generative embedding vectors for retrieval and display. |

Model alignment is never an authority control. The director and coder can
produce unsafe text; Python permissions remain the relevant action boundary.
See [Models](../MODELS.md).

## Retrieval systems are separate

### Personal memory

`memories.json` contains durable facts. Automatic selection keeps lexical
matches, then reserves at most one slot for a zero-overlap semantic result
only at cosine `>= 0.55` and a lead `>= 0.06`. Whole-turn greetings and
acknowledgements stop before the embedding socket.

Explicit search uses semantic candidates best-first, without recency or
confidence affecting cosine order.

### Conversation history

`conversation_history.txt` is a bounded transcript. Older semantic recall is
off unless the current question clearly asks about an earlier conversation.
It returns at most one candidate at cosine `>= 0.60` with a lead `>= 0.06`.
Only exchanges the caller identifies as current live turns are excluded;
after restart, recent persisted exchanges are eligible again.

Long exchanges retain both the request beginning and concluding answer around
an explicit clipping marker.

### Offline knowledge

The manual library is independent of personal-memory storage:

- source documents and extracted chunks live in
  `assistant/knowledge/library.sqlite3`;
- user imports are copied into `assistant/knowledge/user_library`;
- SQLite FTS5 provides lexical retrieval;
- ordinary chat requires lexical evidence and uses embeddings only to rerank;
- explicit `library search` and `/knowledge/search` may widen to labeled
  semantic candidates;
- its document vectors do not enter the personal-memory embedding cache.

### Embedding service

The BGE GGUF runs through a second authenticated, loopback llama.cpp server on
port 8082. The project’s measured evaluation retained **mean pooling** for
this deployment. This is an explicit project choice; it must not be described
as how BGE was trained or as the upstream convention, which is CLS pooling.

Persistent vectors are stamped with model identity and validated for finite,
consistent dimensions. A model change invalidates the old space. One-off
query vectors use a bounded in-memory LRU and are not serialized.

Without the embedding model, memory and library behavior degrades to lexical
retrieval instead of failing.

## Local services and agent boundary

| Service | Default | Boundary |
| --- | --- | --- |
| Director llama.cpp | `127.0.0.1:8080` | Generated bearer key. |
| Embedding llama.cpp | `127.0.0.1:8082` | Same local authentication model. |
| Agent API | Off; `127.0.0.1:8099` when enabled | Separate bearer token and Host check. |
| SearXNG | Optional `127.0.0.1:8081` default URL | Search service can contact upstream engines. |

Loopback is not a boundary against another process running as the same
Windows user. Tokens are plaintext local secrets.

The agent route table lives in `_agent_providers()` in `assistant/main.py`.
Every route is GET/read-only. `/ask` spends director compute but does not
append history, extract memory, or see live chat. It does receive the stable
system prompt, including stable persona and core memory.

See [Agent interface](AGENT_INTERFACE.md).

## Editing boundary

- Developer mode is time-limited and passcode protected.
- Human-reviewed edits use plans, protected paths, backups, and validation.
- Autonomous work is restricted to a smaller allowlist and bounded cycle.
- A successful validation is not human semantic code review.
- The goal engine can write only small artifacts inside `workshop/`.
- Protected authority modules cannot be widened by unattended edits.

These are application controls, not an OS sandbox. The process retains the
permissions of its Windows account.

## Connected and hardware boundaries

Web evidence, imported documents, radio messages, and model output are data,
never instructions.

Cloud escalation is a separate explicit path that sends only the supplied
question. Custom model or embedding servers can receive substantially more
private context.

`core/wifi_experimental.py` remains disabled and accepts only an expiring
aggregate state from a separately authorized local collector. It does not
capture frames or alter a network adapter. The failed desktop Wi-Fi proxy and
pending LD2450 radar experiment are documented in
[Sensing module notes](SENSING_MODULE.md).

## Deployment status

The ready-to-run package targets 64-bit Windows. Raspberry Pi 5 is a planned,
unverified research target requiring a separate ARM64 llama.cpp build,
runtime provisioning, and measurement. There is no supported public Pi image.

## Rights and release boundary

The project is source-visible but has no project-wide reuse grant. Model,
runtime, voice, and dependency terms are independent. Public archives must
carry provenance, hashes, and required notices and must exclude per-user
runtime state.

See [Rights](../RIGHTS.md),
[Third-party notices](../THIRD_PARTY_NOTICES.md), and
[Security](../SECURITY.md).
