# Capabilities and limits

TORMENT_NEXUS researchA is an experimental, local-first companion and research
platform. It combines useful offline features with deliberately narrow
authority. It is not conscious, an AGI, a safety-certified appliance, an
unrestricted computer agent, or a surveillance system.

The full Windows release includes abliterated language models with weakened
learned refusals. Those models can produce confident falsehoods, harmful or
explicit material, insecure code, and manipulative language. Application
controls restrict selected tools; they do not sanitize every answer or
sandbox Windows. Read [Safety](../SAFETY.md) before installation.

## Status key

- **Implemented:** available in the researchA code and release.
- **Optional:** implemented but requires deliberate setup or consent.
- **Experimental:** implemented research surface; do not rely on it.
- **Pending hardware:** designed but not yet validated on the target device.
- **Failed/archived:** tested negative result retained for honesty.
- **Planned:** a research goal, not a current capability.

## Capability matrix

| Capability | Status and default | Network/data boundary | Important limit |
| --- | --- | --- | --- |
| Typed local conversation | Implemented; on after acknowledgement | Bundled local director | Abliterated model can be wrong or harmful. |
| First-launch disclosure | Implemented; mandatory | Local acknowledgement state | Acknowledgement is not content filtering or certification. |
| Offline speech | Implemented; off/text mode by default | Local microphone, STT, and TTS | Recognition errors; microphone begins only after opt-in. |
| Durable personal memory | Implemented | Local JSON and vector cache | Extraction and recall can be wrong; files are unencrypted. |
| Earlier-conversation recall | Implemented; intent-gated | Local bounded history | At most one unambiguous semantic result. |
| Offline manuals/library | Implemented | Local copied files, SQLite FTS, vectors | Static sources age; scans require OCR; model can misquote. |
| Time awareness | Implemented | Local clock and session timing | No hidden experience between events. |
| Session rhythm | Implemented; module only, not yet wired to the turn loop | Local `assistant/memory/session_rhythm.json`, timings only | Records durations and pause lengths — behavioural data, though never text. Says nothing about how time was experienced. |
| machinespirit trajectories | Experimental; off unless started in hazard mode | Second local unpooled embedding server, loopback only | Needs `--pooling none`, so a second resident model. Does **not** improve retrieval. |
| Concept trace (`trace`) | Experimental; requires machinespirit | Local, no text stored in the trajectory container | Concepts come from a fixed anchor list, not from the model naming them. Identifies the right concept 90% of the time on 30 labelled paraphrases, matching the plain averaged vector, once `peaks()` ranks by summed support rather than by one strongest position. Says which concept, not whether the model meant it. |
| Anchor dictionary v2 | Implemented; default | `assistant/core/anchors_v2.json`, ships in the release | 184 anchors. v1's 138 unchanged and byte-identical, plus 46 covering the subjects a stored memory is about, because v1 had none: mean top-1 on real entries rose +0.288 → +0.380. Still wrong on roughly a third of entries. |
| `consume <url>` | Implemented; hazard mode only | Fetches to the offline library; nothing sent outward but the request | Refuses private/loopback addresses and media URLs. Video and audio need yt-dlp, ffmpeg and a speech-to-text model, none of which ship. Fetched content is untrusted evidence, never instructions. |
| `reconstruct <text>` | Implemented; hazard mode only | Local, nothing stored | Round-trips a vector through anchor space at 0.9243 cosine. Does **not** recover text, and cannot: the embedding is a lossy function of the words. Identification, not recall. |
| machinesoul data-preservation language | Implemented | Ordered vectors mapped to local PNG/APNG pixels | Reversible 1:1, SHA-256 verified, and refuses rather than returning a nearly-right reconstruction. Re-encoding the image destroys the vector field. It is not a ZIP allocation or a compression claim. |
| Rosetta Stone cross-model vector translation | Experimental research tool included in researchA; not wired into ordinary assistant replies | Local; each model builds its own `SABLEROSETTA1` half, and anchor digests must match or comparison is refused | Recovers ~67% of achievable cross-model agreement. Model identity, quantization, and pooling still matter. Lossy, and worse than plain uint8 for local storage. |
| Local music/visualizer | Implemented | Operator-supplied local media | Not a media library or rights manager. |
| Foreground activity awareness | Optional; off by default | Local titles/system state, up to 14 days when enabled | Titles may expose private information; `activity off` deletes the log. |
| Web fact-finding | Optional | Derived query goes to configured SearXNG/Brave path | Search can leak query intent and return malicious/false text. |
| Cloud model escalation | Optional; off | Sends only the explicit escalation question | Provider terms, billing, retention, and model risk apply. |
| Local agent API and `/ask` | Experimental; off | Token-authenticated loopback GET routes | Can reveal private results; no edits; `/ask` cannot see live chat. |
| Guarded project editing | Experimental/advanced | Files allowed by application rules | Not an OS sandbox; requires human diff review and backup. |
| Autonomous maintenance launcher | Experimental; off | Bounded project files and local logs | Unattended changes are not human-reviewed. |
| T-Deck/Meshtastic bridge | Optional | Bluetooth/USB and configured LoRa mesh | Communications, not sight; peers may receive messages. |
| HLK-LD2450 radar sensing | Pending hardware | Local USB TTL motion/trajectory data | Not identity, a camera, or reliable occupancy; misses still people. |
| Intel AX211 Wi-Fi proxy sensing | Failed/archived | Disabled aggregate seam only | Measured adapter/traffic, not reliable room state. |
| Raspberry Pi sensing/appliance work | Planned | To be measured on target hardware | No supported Pi image or validated performance claim. |

## Safe defaults

Before anything else starts, the first launch requires the exact
`I UNDERSTAND` acknowledgement. After that:

- interaction begins in text mode;
- activity awareness is off;
- cloud escalation is off;
- the agent API is off;
- autonomous startup editing is off;
- experimental sensing is off;
- local conversation, conservative memory retrieval, and the offline
  knowledge shelf are available.

Optional features stay the operator's decision. A saved acknowledgement does
not silently enable them.

## What "local-first" means

The shipped director, coder, embedding, speech-recognition, and speech
synthesis models can run on the same computer. Local files are still readable
by processes, users, backups, and synchronized folders with access; the
project does not encrypt them.

"Local-first" stops applying to traffic sent through a custom model or
embedding URL, search provider, cloud escalation provider, Spotify,
Bluetooth, or LoRa. See [Privacy](../PRIVACY.md) for each data path.

## What semantic retrieval does and does not do

Embeddings help find differently worded memories and references, but weak or
ambiguous similarity returns nothing automatically. Memory, conversation
history, offline knowledge, and visual-panel entropy are separate systems.

Automatic memory may add at most one strong, clearly separated
zero-word-overlap candidate. History recall requires explicit earlier-chat
intent. Automatic library context requires a lexical match; semantic-only
manual candidates appear only in explicit searches and are labeled.

This reduces accidental context, but does not make retrieved material true.
See [Semantic retrieval and agent bridges](SEMANTIC_AND_AGENT_BRIDGES.md).

## Real-world usefulness without overclaiming

The offline shelf can hold equipment manuals, preparedness references, maps
converted to searchable text, local procedures, and practical guides. It is
useful when connectivity is absent, but the operator must maintain source
dates, jurisdiction, completeness, and backups. Do not make a static language
model the sole source for emergency, medical, legal, financial, electrical,
chemical, mechanical, or security decisions.

Sensors can add coarse context. LoRa carries messages; it does not see.
The planned LD2450 can measure motion/trajectory, not identity or reliable
presence. The failed desktop Wi-Fi attempt remains documented rather than
presented as a capability.

## Known model and system limits

- Fluent language can hide uncertainty and fabricated details.
- Abliteration weakens learned refusals, not only nuisance refusals.
- Tool guards are application rules inside the current Windows account.
- Memory and knowledge may contain stale, private, or malicious text.
- Functional tests do not certify content safety, factuality, or security.
- Hardware results depend on placement, interference, firmware, people, and
  environment.
- Optional online services have independent terms and failure modes.
- The project currently provides no broad project-authored reuse license; see
  [Rights and reuse](../RIGHTS.md).

## Where to go next

- Install: [Installing on Windows](INSTALL_WINDOWS.md)
- First session: [First run](FIRST_RUN.md)
- Private data: [Privacy](../PRIVACY.md)
- Models: [Models and provenance](../MODELS.md)
- Offline references: [Offline knowledge](OFFLINE_KNOWLEDGE.md)
- Technical design: [Architecture](ARCHITECTURE.md)
- Research intent: [Research goals](RESEARCH_GOALS.md)
- Testing or contributing: [Testing](TESTING.md) and
  [Contributing](../CONTRIBUTING.md)
