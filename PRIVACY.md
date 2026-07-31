# Privacy

Status: researchC data-handling disclosure, reviewed 2026-07-31.

TORMENT_NEXUS is local-first. That does not mean "nothing is stored" or
"nothing can go online." Local conversation, speech, embeddings, memory, and
the reference library write files on the computer. Optional search, cloud,
custom-server, agent, Bluetooth, and LoRa features cross additional
boundaries.

The project does not provide encryption at rest. Files below are readable by
people or processes that can access the same Windows account, project folder,
backup, search index, or synchronized copy.

## First-launch sequence and defaults

On a clean researchC installation, a mandatory disclosure appears before the
model, microphone, activity sampler, listeners, or network-capable
subsystems start. The exact `I UNDERSTAND` acknowledgement is saved locally.
Anything else exits without starting those components.

After acknowledgement:

- interaction begins in text mode and the microphone is off;
- foreground activity awareness is off;
- semantic memory retrieval and full-text offline-library indexing can start
  when their bundled components are present; persistent library-vector
  population starts off and requires a developer opt-in;
- cloud escalation, the agent API, experimental sensing, and autonomous
  startup maintenance remain off;
- web search is used only through the configured backend when a request
  appears to need current information.

The later tutorial invitation is informational. The mandatory disclosure
acknowledgement records that the warning was shown; neither is consent to
every optional feature.

## Local data inventory

Paths are relative to the project root.

| Data | Why it exists | Retention and deletion |
| --- | --- | --- |
| `assistant/.safety_acknowledgement.json` | Records acceptance of the first-launch disclosure. | Remains until manual deletion or uninstall. Delete it while stopped to show the disclosure again. |
| `assistant/.activity_consent.json` | Persists the explicit activity on/off choice. | Absent on a fresh install, which means off. `activity on` and `activity off` update it. |
| `assistant/memory/core_memory.txt` | Fixed project/persona context shipped with the application. It is not prior user chat. | Remains until the installation is changed or removed. |
| `assistant/memory/conversation_history.txt` | Bounded conversation transcript used for continuity and intent-gated semantic recall. Credential-like text is redacted when recognized. | Capped to the latest 20,000 characters. Close the app and delete it for a full reset. |
| `assistant/memory/memories.json` | Durable facts extracted from conversations. | Capped at 500 records. `forget <text>` removes matching records; close and delete the file to clear all. |
| `assistant/cache/embeddings.json` | Numeric vectors derived from personal memory and history so semantic recall stays fast. | Capped at 4,000 entries. Deleting source text may not immediately remove its old vector; close the app and delete the cache when clearing private scope. |
| In-memory embedding query cache | Reuses a bounded number of recent query vectors. | Not serialized; disappears when the process exits. |
| `assistant/cache/prompt/` or the configured prompt-cache directory | Potentially large serialized llama.cpp slot/KV state derived from the stable model, persona, core-memory, and system prefix. Treat it as sensitive local state even though it is not a plain-text transcript. | A successful rebuild removes obsolete matching prefix caches, but an interrupted temporary file or unrelated cache can remain. Close the application and delete the directory for a full prompt-state reset; the next launch rebuilds it. Release tooling excludes prompt caches. |
| `assistant/cache/track_loudness.json` | Per-track playback gain keyed by the local file's absolute path, size, and modification time. It can therefore reveal private media names and folder layout. | Entries are not age-pruned. Close the application and delete the file to clear them; tracks are measured again when played. Release tooling excludes this cache. |
| `assistant/knowledge/user_library/` | Private copies of operator-imported manuals and references. | `library remove <name>` deletes the selected copy synchronously. Manual deletion should be done while stopped. |
| `assistant/knowledge/library.sqlite3` | Extracted document text, metadata, SQLite FTS index, and knowledge vectors. | `library remove` synchronously deletes matching live rows and attempts a checkpoint/vacuum. This is not forensic erasure of backups, snapshots, or SSD-remapped blocks. Remove the database while stopped for a complete shelf-index reset. |
| `assistant/logs/librarian_shadow.jsonl` | When the optional librarian observer is enabled: closed outcome labels, counts, coarse UTC hours, timings, experiment/model/server digests, and per-install HMAC pseudonyms. Questions, excerpts, titles, paths, URLs, and raw model output are not intentionally logged. | Capped to the latest 20,000 rows. Close the application and delete it to clear the retained observer evidence. Release tooling excludes runtime logs. |
| `assistant/memory/activity_log.jsonl` | When opted in: foreground application/title, idle time, CPU/memory load, battery, and timestamps. | Samples about every 20 seconds, stores changes plus a slow heartbeat, and removes entries older than 14 days by default. `activity off` and `activity forget` delete it. |
| `assistant/memory/session_rhythm.json` | Per-session timings so the assistant can say how long a session ran and how it compares to previous ones: start time, duration, exchange count, median and longest pause, and how many breaks over twenty minutes occurred. **Timings only — never message text, window titles, or what was discussed.** Pause length is still behavioural data about the operator. | Capped at the latest 200 sessions. Plain JSON the operator can read; close the app and delete the file to clear it. |
| `assistant/memory/chosen_name.json` | A name the operator explicitly keeps for the assistant header. | Remains until `name forget` or manual deletion. |
| `assistant/.tutorial_state.json` | Records whether the first-session invitation was shown. | Remains until manual deletion or uninstall. |
| `assistant/.model_api_key` | Random bearer secret for the local llama.cpp service. | Retained across launches; delete only while stopped to rotate it. |
| `assistant/.audit_hmac_key` | Per-install secret used to pseudonymize private prompt and question identifiers in Research C receipts and sidecars, and to authenticate the closed-field retained-edit records used by source-authorship answers. It is not sent to a model. | Retained across launches so local identifiers remain comparable and retained-edit evidence remains verifiable. Delete only while stopped to rotate it. Rotation intentionally breaks joins and makes earlier `APPLIED_RECORD` log entries unverifiable, so they will no longer support an authorship claim. An installation that cannot persist the key uses a process-local random fallback and cannot join those identifiers across launches. |
| `assistant/.agent_token` | Bearer secret for the optional read-only agent API. | Created only when enabled; delete while stopped to rotate it. |
| `assistant/.dev_passcode`, `assistant/.super_dev_passcode` | Developer- and super-developer-mode passcode material. | Retained until reset/deletion. These prevent accidental use; they are not encryption. |
| `assistant/.anthropic_api_key`, `assistant/.openai_api_key` | Optional cloud-escalation credentials. | Retained until the operator removes or rotates them; environment variables can be used instead. |
| `assistant/.spotify_token` | Optional Spotify authorization data. | Retained until disconnected/removed or revoked at Spotify. |
| `assistant/.tdeck_ble_pin` | Optional T-Deck pairing PIN. | Retained until removed or replaced. |
| `assistant/logs/escalation.jsonl` | Provider, model, sizes, outcome, and time for escalation. | Question and answer content are not intentionally logged; no automatic retention period is documented. |
| `assistant/logs/agent_api.jsonl` | Route, time, outcome, and peer metadata for the optional agent API. | Query/result content is not intentionally logged; no automatic retention period is documented. |
| Other `assistant/logs/`, `dump/`, `workshop/`, recovery, invalid-data, and backup files | Diagnostics, generated work, edits, and recovery material. | May contain excerpts, filenames, or private state; inspect and remove manually. |
| `models/voice/cache/` and local music folders | Generated audio cache and operator-supplied media. Freestyle cache filenames contain a content digest, not plain lyrics. | Fixed-song renders remain until manually removed; generated freestyle renders retain only the newest eight by default (configurable up to 32). Release tooling is intended to exclude personal media and runtime data. |

Git ignore rules and release deny lists reduce accidental publication. They
do not stop another same-user process, backup client, cloud-sync tool, or
malware from reading the files.

Existing tracked handoff and audit history contains maintainer-local path and
profile identifiers from earlier investigations, including old absolute
workspace and temporary-file examples. The project records this rather than
rewriting Git history. Release packaging excludes raw and private handoffs and
private runtime data. It includes only an exact whitelist of sanitized
aggregate librarian evidence, then path-scans fresh staged binaries, source,
documentation, and configuration. Those controls do not scrub earlier commits;
cloning or fetching the full repository history can reveal old identifiers.

## Activity awareness

Activity awareness is **off on a fresh installation**. `activity on` is an
explicit opt-in and persists that choice. While enabled it samples foreground
application/window title and basic system state. Titles can contain document
names, URLs, message previews, and other private information.

The default maximum retention is 14 days:

- `activity off` stops collection, persists off, and deletes both in-memory
  observations and `assistant/memory/activity_log.jsonl`;
- `activity forget` deletes observations without changing whether collection
  is enabled;
- setting `TORMENT_NEXUS_ACTIVITY_RETENTION_DAYS=0` before launch requests
  zero-day retained history while activity is otherwise enabled.

No activity command erases copies already made by backup, sync, antivirus,
screenshots, or another process.

## Where information can go

### Local model and embedding services

By default, the director uses an authenticated loopback service at
`http://127.0.0.1:8080`, embeddings use `http://127.0.0.1:8082`, and the
optional agent API uses `127.0.0.1:8099`.

Loopback limits ordinary network exposure but is not protection from another
process running under the same account. Bearer keys remain secrets.

If `TORMENT_NEXUS_SERVER_URL` points elsewhere, complete prompts and supplied
context—including retrieved offline-reference excerpts—can go to that
server. researchC rejects a non-loopback `TORMENT_NEXUS_EMBED_SERVER_URL`, so
personal memory, history, imported passages, and embedding queries are not
sent to a remote embedding endpoint by this implementation. The local-first
claim no longer applies to prompts sent through a remote director server.

`sing what you want` is narrower than that general custom-server setting: it
refuses a non-loopback director URL, proxy inheritance, and redirects before
sending its bounded subject or the local bearer credential.

### machinespirit trajectories

Hazard mode starts a **second local embedding server** on loopback, because
llama.cpp fixes pooling when a process starts and a per-token trajectory
cannot come from the pooled one. It is the same small model already
bundled, running a second time.

Text sent to it is embedded exactly as text sent to the ordinary embedder
is. The module refuses any non-loopback address outright: a trajectory is
per-token, so a remote endpoint would be an unusually direct way to leak
what was typed. When the server is absent, every entry point reports
unavailable rather than falling back to the pooled server.

A stored trajectory records the source text as a SHA-256 digest, never as
text. `trace` output names concepts from a fixed anchor list shipped with
the application — the assistant is not describing your sentence in its own
words, it is reporting which fixed phrases the vectors sat nearest.

An anchor profile is a readable description of what a piece of text is
about. Applied to a private memory it would describe that memory's subject
in shareable terms, which is worth knowing before sharing any file produced
this way.

Hazard mode also writes `assistant/logs/machinespirit_shadow.jsonl`: for
each retrieval, which memories the deciding pooled ranking placed in its
top five and which the anchor-space ranking would have, so the question of
whether anchor space retrieves better can be answered with evidence rather
than an eighteen-chunk corpus. Memories appear as **SHA-256 digests, never
as text** — a row records that some memory ranked third and nothing about
what it said. The file is bounded, sits under `logs/` which is excluded
from git and from release packaging, and can be deleted at any time; losing
it costs a measurement and nothing else.

### machinesoul capsules, and the risks specific to image files

A machinesoul capsule is a real PNG or APNG whose pixels **are** the
payload. That is the point of the format, and it carries privacy
consequences that ordinary archives do not.

**A capsule looks like an image and gets handled like one.** Nothing in a
file manager, a preview pane, a chat client, or a social card distinguishes
a capsule carrying an install tree from a screenshot. Archives invite
caution; images invite forwarding. Anything placed in a capsule should be
assumed to travel as easily as a photograph, because to every tool that
touches it, that is what it is.

**A capsule is not encryption and was never intended as any.** Its SHA-256
gate proves the payload arrived unaltered. It proves nothing about who may
read it, and anyone holding the file and the published decompiler can
extract everything inside. Do not capsule anything you would not send in
the clear.

**An optional description is stored in cleartext metadata.** A capsule may
carry a plain-language description of its own payload, readable without
extracting a single byte. It is **off unless explicitly requested**, and no
code path supplies one automatically, precisely because describing private
contents in a forwardable file would disclose the subject even to someone
who never opened the payload. It also sits outside the SHA-256 gate, so it
is a hint about the contents and never a guarantee of them — it can be
edited without extraction failing.

**Re-encoding destroys a capsule silently.** A screenshot, an optimiser, or
a platform that recompresses images leaves the picture looking identical
while the bytes underneath no longer reconstruct. The failure is loud at
extraction — the digest refuses — but invisible before it.

The files this document lists as private are excluded from release
packaging by both a deny pattern and an independent basename check. That
exclusion protects the packager, not a capsule you build by hand. If
private material ever needs to travel this way, encrypt it before it
becomes pixels.

### Offline knowledge

Normal library import, extraction, indexing, and full-text search run locally
and do not require the internet. The bundled embedding service is also local,
but persistent library-vector population starts off and requires the persisted
developer choice `library semantic on`. Source URLs stored as metadata are not
automatically proof that the source remains current.

Imported files are copied into the private shelf. The copied source,
extracted text, metadata, and knowledge vectors are release-excluded runtime
data but remain unencrypted locally. See
[Offline knowledge](docs/OFFLINE_KNOWLEDGE.md).

If the optional LLM librarian observer is explicitly configured, a
credential-redacted completed-turn query and an immutable bounded candidate
snapshot, including short excerpts, are sent after the answer exists to a
distinct authenticated loopback model service. Proxy inheritance and
redirects are refused, so this path is designed to remain on the machine, but
loopback is not encryption or isolation from other processes running as the
same user. The observer's proposal is discarded and cannot alter retrieval,
the completed answer, or a future answer. Its first tested 4B model failed the
promotion gate and remains shadow-only.

### Web search

Questions that appear to need current information can produce a derived
search query:

- a local SearXNG instance at `http://127.0.0.1:8081` may contact its
  configured upstream search services;
- the Brave backend sends the query to the Brave Search API with the
  operator's key.

Do not put secrets in a question that could require current fact-checking.
Retrieved pages are untrusted input and can contain prompt injection,
malicious links, or misinformation.

### Cloud escalation

Escalation is off unless `TORMENT_NEXUS_ESCALATION=1` and a selected provider
key are both present. The command sends exactly the question after
`escalate`; it does not intentionally attach conversation history, memories,
persona, or the local system prompt.

Anthropic, OpenAI, or another configured compatible provider applies its own
privacy, retention, billing, and safety terms. Never give a valuable provider
key to an untrusted endpoint or send it over plain HTTP.

### Agent API

The optional agent API is off by default, loopback-only, bearer-token
authenticated, Host-checked, and GET-only. It can return health/runtime
information, private memory candidates, private reference excerpts, or a
short local-model answer.

`/ask` receives stable persona/core-memory context but not the operator's live
chat. It does not append history or extract memory. "Read-only" means routes
do not edit project state; it does not mean returned data is non-sensitive.

Queries use URL parameters. URLs often remain in command histories and
debugging tools, so do not place credentials in them. See
[Agent interface](docs/AGENT_INTERFACE.md).

### Music and media

`spotify search` sends search text to MusicBrainz and opens a Spotify search
URI. Optional Spotify authorization can expose account, device, and playback
metadata under Spotify's terms.

Operator-supplied local media stays local unless another application or sync
service uploads it.

### T-Deck, Bluetooth, and LoRa

T-Deck commands and messages cross USB/Bluetooth. Meshtastic messages may
then cross the LoRa mesh, where peers with relevant channel credentials may
receive them. Region, channel, and encryption choices remain the operator's
responsibility.

The planned LD2450 sensor uses local USB TTL data. It cannot identify a
person, but movement/trajectory observations are still information about a
sensed space and require consent.

### Installation and model downloads

The complete researchC release is model-bearing. Initial release download
contacts GitHub and exposes ordinary request metadata. Source setup or model
replacement may contact package, GitHub, Hugging Face, Piper, or other
documented upstream services. These downloads are not designed to include
conversation history.

## Clearing an installation

For a deliberate privacy reset:

1. Close TORMENT_NEXUS and confirm its local model processes stopped.
2. Delete conversation history, memories, personal embedding and prompt-state
   caches, the track-loudness cache, activity state/log, chosen-name state,
   tutorial state, safety acknowledgement, imported library, knowledge
   database, logs, cached audio, and recovery files that you no longer want.
3. Remove the audit HMAC key, bearer tokens, developer passcode, pairing data,
   and API keys. Removing the audit key intentionally makes retained-edit
   records from the old key unverifiable. Revoke cloud and Spotify credentials
   at their providers when appropriate.
4. Check backups, recycle bins, antivirus quarantine, Windows search indexes,
   Git history, screenshots, and synchronized copies separately.

Deleting the installation does not erase copies already made by Windows,
another application, a cloud provider, backup software, or a LoRa peer.

## Bug reports and support

Never attach these to a public report:

- conversations, memories, embeddings, imported documents, the knowledge
  database, or activity logs;
- API keys, bearer tokens, passcodes, pairing PINs, or environment dumps;
- complete user paths, private filenames, window titles, or message content.

Create a minimal synthetic reproduction instead. Use
[Security](SECURITY.md) for a possible data leak or authentication failure
and [Contributing](CONTRIBUTING.md) for ordinary bugs.
