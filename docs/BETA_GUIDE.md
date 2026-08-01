# TORMENT_NEXUS researchC guide

This guide explains what researchC contains, what its defaults mean, and which
features are ordinary, optional, experimental, planned, or failed.

New users should begin with [Installing on Windows](INSTALL_WINDOWS.md) and
[Your first session](FIRST_RUN.md).

## What “researchC” means

The lettered release name avoids implying an ordered march toward a finished
product. The application has automated and manual checks, but the
representation, model behavior, and advanced authority paths remain
experimental:

- language-model replies can be false, harmful, repetitive, or overly
  confident;
- model and dependency behavior varies by hardware;
- less common audio, terminal, Bluetooth, and radio setups may expose bugs;
- advanced editing paths can change files;
- functional regressions do not certify content safety, legality, security,
  or fitness for high-stakes use.

Keep backups, use a standard Windows account, and verify important answers.

## The complete Windows release is model-bearing

The ready-to-run researchC capsules carry the actual local model weights:

- abliterated Qwen3 4B Q8 director;
- abliterated Qwen2.5-Coder 7B Q8 maintenance coder;
- BGE small English v1.5 Q8 embeddings;
- Moonshine, Silero, and Piper voice artifacts.

It also contains a private Python runtime, llama.cpp binaries, offline
dependencies, built-in practical-reference cards, the terminal interface,
visualizer, documentation, and guarded tools.

This is not a sanitized edition. Read [Safety](../SAFETY.md),
[Models](../MODELS.md), and
[Third-party notices](../THIRD_PARTY_NOTICES.md). The source repository has
no project-wide reuse license; see [Rights](../RIGHTS.md).

GitHub’s automatic source archives are developer snapshots and are not the
complete package.

## First launch is an explicit boundary

Before model loading, microphone setup, listeners, activity sampling, or
network-capable subsystems, the application displays its disclosure.
Continuation requires the exact text:

```text
I UNDERSTAND
```

Declining starts none of those components.

A fresh installation then begins with text mode, activity awareness, and
persistent library-vector population off. Cloud escalation, the local agent
API, autonomous startup editing, and experimental sensing are also off.

## Capability status

| Capability | Status | Important limit |
| --- | --- | --- |
| Local text conversation | Implemented | Uses an abliterated 4B model; output is not safety-filtered or guaranteed true. |
| Offline voice | Implemented, opt-in | `audio mode` initializes listening/speech; microphone is off initially. |
| Offline singing | Implemented, opt-in | Daisy Bell and Come Josephine use fixed public-domain scores. Freestyle accepts only bounded lyric syllables over those fixed tunes and queues nothing after one failed repair. Physical listening validation is still outstanding. |
| Durable memory | Implemented | Local, inspectable, bounded files; not encrypted. |
| Semantic memory rescue | Implemented, conservative | Automatic chat adds at most one unambiguous zero-overlap result. |
| Older-conversation recall | Implemented, conservative | Requires a clear request about earlier conversation and returns at most one result. |
| Offline manuals and cards | Implemented | Full-text indexing is available by default. Library-vector population starts off; automatic use always requires lexical evidence. |
| LLM librarian observer | Experimental, opt-in, shadow-only | Uses a separate authenticated loopback model after the answer exists; its proposal is discarded. The first tested 4B candidate failed promotion. |
| Time awareness | Implemented | Reads timestamps; not hidden experience. |
| Activity awareness | Implemented, opt-in | Window titles are private; `activity off` deletes retained observations. |
| Local music/visualizer | Implemented | Operator supplies media; release package does not contain personal music. |
| Web search | Optional | Queries leave through the configured search service. |
| Cloud escalation | Optional, explicit | Sends only the typed escalation question to the provider. |
| Agent API and `/ask` | Experimental, opt-in | Loopback and bearer-token protected; read access can still disclose data. |
| Guarded self-maintenance | Advanced/experimental | Application rules are not an OS sandbox. |
| T-Deck/Meshtastic | Optional hardware | Bluetooth/LoRa messages leave the PC and may reach mesh peers. |
| LD2450 radar | Active, pending hardware | Movement/trajectory only; not sight, identity, or reliable occupancy. |
| Desktop Wi-Fi occupancy proxy | Failed/archived | Measured the adapter/traffic rather than the room. |
| Raspberry Pi image | Planned/unverified | No ready-to-install public Pi image. |

The detailed matrix is in
[Capabilities and limits](CAPABILITIES_AND_LIMITS.md).

## Offline knowledge

researchC includes 18 integrity-bound reference cards and 39 indexed chunks
centered on Canadian emergency preparedness, fire/carbon-monoxide response,
food/water safety, chemicals, outages, severe weather, extreme heat and cold,
wildfire smoke and evacuation, earthquakes, navigation, communications, and
the limits of offline material.

The private user library accepts:

```text
.txt .md .rst .yml .yaml .yar .yara .py
.html .htm .json .csv .pdf .epub .docx
```

Text-based PDFs use the bundled `pypdf`; scanned PDFs require OCR. Imported
files are copied into `assistant\knowledge\user_library` and indexed in a
local SQLite FTS database.

Automatic chat retrieval requires a real word match. Persistent library-vector
population starts off on a fresh installation and requires developer command
`library semantic on`; `library semantic status` reports its fair target,
coverage, retries, and quarantine. Turning population off does not delete or
disable already stored current vectors. When comparable target vectors exist,
they rerank lexical results only as a complete set. Explicit `library search`
and the authenticated `/knowledge/search` endpoint may then include
semantic-only candidates, labeled as such.

The optional LLM librarian is off by default and has no retrieval authority.
After Sable has answered, it may observe a credential-redacted query and the
immutable bounded candidate snapshot through a distinct authenticated
loopback service. Closed metadata about the call is logged; the live proposal
is discarded. The first identity-bound Qwen3 4B Instruct Q5_K_M run produced
11/16 strictly valid decisions, 9/16 correct valid decisions, and only 1/8
agreement after candidate order was reversed. It failed the promotion gate
and remains shadow-only. A preregistered follow-up using the shipped 4B Q8
director improved validity to 15/16 and order agreement to 5/8, while
correctness remained 9/16. It also failed promotion. The separately tested
Instruct GGUF is not included in the release.

An offline passage can be outdated, incomplete, from another jurisdiction, or
wrongly interpreted. It cannot verify live emergencies, changing law,
recalls, weather, prices, product revisions, or professional advice.

See [Offline knowledge](OFFLINE_KNOWLEDGE.md).

## Memory and vector policy

Automatic memory injection follows a conservative split:

- exact-token matches remain primary;
- at most one zero-overlap semantic result may be added;
- it must score at least `0.55`;
- it must lead the next semantic candidate by at least `0.06`;
- greetings, acknowledgements, and capability pleasantries retrieve nothing.

Explicit memory search uses cosine best-first without recency or confidence
mixing. Results are candidates, not verified facts.

History recall runs only for clear earlier-conversation intent. It returns at
most one result whose score is at least `0.60` and whose lead is at least
`0.06`. Long exchanges preserve their beginning and conclusion around a
visible clipping marker.

The shared embedding server is local and loopback-only by default. Private
query vectors use a bounded in-memory cache and are not serialized. Persistent
memory/history vectors are private derived data stored in the embedding cache;
that memory path is separate from off-by-default library-vector population.

## Privacy defaults and stored data

- Text mode begins on; microphone listening begins off.
- Activity awareness begins off. `activity on` persists opt-in.
  `activity off` persists the off state and deletes the local activity log.
- Conversation history is capped to the latest 20,000 characters.
- Durable memories are capped at 500 entries.
- Imported reference documents, extracted chunks, and their vectors remain
  inside the installation.
- Local files and tokens are not encrypted by the project.
- Release packaging is intended to exclude personal memory, history,
  activity, imported manuals, indexes, keys, pairing data, logs, and music.

See [Privacy](../PRIVACY.md) for paths and deletion instructions.

## Connected features

Connected features are not necessary for local conversation:

- SearXNG or Brave can supply current search evidence.
- `spotify search` sends search text to MusicBrainz and then opens Spotify.
- Cloud escalation is disabled until both an environment opt-in and provider
  key exist.
- A custom model or embedding URL can receive prompts, context, memory,
  history, queries, or document text.
- The agent API is disabled until explicitly enabled.
- Bluetooth and LoRa hardware cross physical and radio boundaries.

Search results, retrieved documents, model responses, and radio messages are
untrusted data, not commands.

## Research versus product claims

The [research goals](RESEARCH_GOALS.md) describe open questions, not promised
capabilities. Sycophancy, entropy, persona drift, sensing, Pi power/thermal
behavior, and self-governance are experiments until measured.

The project deliberately keeps negative results. The failed Wi-Fi proxy is
documented because thresholds must not be tuned into agreement.

## Reporting

Use [Testing](TESTING.md) for a repeatable pass and
[Troubleshooting](TROUBLESHOOTING.md) for common failures.

Do not attach conversations, memories, imported manuals, knowledge databases,
activity logs, keys, tokens, passcodes, pairing information, or personal
paths. Security-boundary failures belong in the private process described by
[Security](../SECURITY.md).
