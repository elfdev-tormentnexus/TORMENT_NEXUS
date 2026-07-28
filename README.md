<p align="center">
  <img src="assets/sable_mark.png" width="520"
       alt="SABLE — a dark mark reading SABLE above the words SCAN ME, with a thin data stripe along the bottom edge">
</p>

<h1 align="center">TORMENT_NEXUS</h1>

<p align="center">
  <strong>An experimental, local-first Windows AI companion and systems-art research platform.</strong>
</p>

<p align="center">
  Offline conversation, voice, memory, practical reference retrieval,
  inspectable tool boundaries, reversible self-maintenance, and
  consent-based hardware research.
</p>

> [!CAUTION]
> **Read this before downloading or installing.**
>
> The ready-to-run Beta 6 Windows assets are **full, model-bearing archives**.
> They include community-modified “abliterated” Qwen language models whose
> learned refusal behavior has been deliberately weakened. This is not a
> sanitized client, a remote-model downloader, or a safety-filtered edition.
> The models can produce false, harmful, illegal, explicit, biased,
> manipulative, or insecure material with confidence.
>
> TORMENT_NEXUS’s Python controls restrict selected tools. They do not filter
> every generated sentence, sandbox Windows, or make advice safe. Do not run
> it as Administrator or use it as an emergency, medical, legal, financial,
> security, or safety-critical authority. Keep backups and review advanced
> actions yourself.
>
> Read [Safety](SAFETY.md), [Privacy](PRIVACY.md), and
> [Models and provenance](MODELS.md) before proceeding. The project is
> source-visible and does not yet grant a project-wide reuse license; see
> [Rights and reuse](RIGHTS.md).

<p align="center">
  <a href="https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases">
    Open GitHub Releases and select v0.2.0-beta.6
  </a>
</p>

## What this project is

TORMENT_NEXUS explores whether a useful personal AI system can remain locally
owned, inspectable, reversible, and honest about failure while running on
ordinary hardware. Its current goals are:

- useful offline conversation and voice without a required cloud account;
- visible local memory and an offline shelf of manuals and practical
  reference cards;
- application-enforced authority boundaries that can be inspected and tested;
- reversible, logged experimentation with self-maintenance;
- honest publication of failed approaches, including the desktop Wi-Fi
  sensing result;
- modest, consent-based hardware awareness without pretending radio or radar
  is sight.

It is not conscious or AGI, not a safety-certified assistant, not an
unrestricted agent, not a surveillance product, and not a replacement for
professionals or human relationships. Read the
[research goals](docs/RESEARCH_GOALS.md) for the questions the project is
actually trying to answer.

## Choose your path

| I want to... | Start here |
| --- | --- |
| Install the complete Windows beta | [Installing on Windows](docs/INSTALL_WINDOWS.md) |
| Understand the first-launch warning and privacy defaults | [Your first session](docs/FIRST_RUN.md) |
| See exactly what works and what does not | [Capabilities and limits](docs/CAPABILITIES_AND_LIMITS.md) |
| Add manuals, encyclopedias, and practical references | [Offline knowledge](docs/OFFLINE_KNOWLEDGE.md) |
| Test the beta | [Beta guide](docs/BETA_GUIDE.md) and [Testing](docs/TESTING.md) |
| Review models and third-party terms | [Models](MODELS.md) and [Third-party notices](THIRD_PARTY_NOTICES.md) |
| Work on the source | [Architecture](docs/ARCHITECTURE.md) and [Contributing](CONTRIBUTING.md) |
| Connect an outside development agent | [Agent interface](docs/AGENT_INTERFACE.md) |
| Understand vectors and AI bridges | [Semantic retrieval and agent bridges](docs/SEMANTIC_AND_AGENT_BRIDGES.md) |
| Review sensing and hardware research | [Sensing module notes](docs/SENSING_MODULE.md) |

## Install the full Windows Beta 6

You do not need to install Python, use a command line, create an online
account, provide an API key, or download a separate model. The full archive
contains:

- the abliterated Qwen3 4B Q8 director;
- the abliterated Qwen2.5-Coder 7B Q8 maintenance coder;
- the BGE embedding model used for conservative semantic retrieval;
- a private Python runtime and offline dependency set;
- llama.cpp binaries;
- offline speech recognition, voice activity detection, and Piper speech;
- the application, built-in practical reference cards, documentation, and
  guarded tools.

### Requirements

| Requirement | Reason |
| --- | --- |
| 64-bit Windows | The ready-to-run archive targets Windows x64. |
| At least 16 GB RAM | Required for the bundled director and on-demand coder; more leaves room for voice and other applications. |
| About 40 GB free during installation | Download parts, the reassembled ZIP, and the extracted installation temporarily coexist. |
| Internet for the initial download | Ordinary local conversation and the offline library work without it afterward. |
| Microphone only if desired | Beta 6 starts in text mode, with microphone use off. |

### Five steps

1. Open [GitHub Releases](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases),
   select `v0.2.0-beta.6`, expand **Assets**, and read its warning, manifest,
   checksums, model provenance, and known issues.
2. Download the single file
   `DOWNLOAD_TORMENT_NEXUS_v0.2.0-beta.6.bat` into an empty folder with room
   to spare, and double-click it. It fetches all twelve release files,
   verifies each one against its published SHA-256, and stops on any
   mismatch. Nothing else needs downloading by hand.
3. Run `REASSEMBLE_TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.bat`, verify the
   resulting `TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip` against the
   published SHA-256, extract it, and run `setup.bat`.
4. **Apply the two guard patches by hand.** Nothing does this for you. Move
   the four files below into the extracted `TORMENT_NEXUS` folder — the one
   containing `start_assistant.bat` — and double-click each installer. They
   are independent and may be run in either order.

   ```text
   INSTALL_ASK_GUARD_PATCH.bat
   TORMENT_NEXUS-v0.2.0-beta.6-ask-guard-patch.zip

   INSTALL_COMMAND_GUARD_PATCH.bat
   TORMENT_NEXUS-v0.2.0-beta.6-command-guard-patch.zip
   ```

   These replace manifest-hashed files, so an installed tree that has them
   applied no longer matches the published archive checksum. That is
   deliberate, and it is why the reassembler names them but refuses to run
   them. The documentation patch is different — the reassembler applies that
   one for you.
5. Launch the desktop shortcut. Before any model, microphone, activity
   sampler, listener, or network-capable subsystem starts, the application
   displays its disclosure and requires the exact text `I UNDERSTAND`.
   Anything else closes the application without starting those components.

<details>
<summary>Fallback: download the parts by hand</summary>

If the downloader cannot run — locked-down machine, blocked script host, or
a proxy that mangles it — fetch
`TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip.part01` and every consecutive
later `.partNN` file, plus
`REASSEMBLE_TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.bat` and the four guard
patch files above. Keep them together and do not rename them, then continue
from step 3.

</details>

`INSTALL_INTERFACE_MODE.bat` and the 14B full-maintenance coder are separate
optional add-ons. Neither is needed for a working install.

Do not use GitHub’s green **Code** button or automatic **Source code**
archives for this path. Those are developer source snapshots, not
ready-to-run, model-bearing Windows packages.

The complete procedure, checksum command, upgrade guidance, and uninstall
steps are in [Installing on Windows](docs/INSTALL_WINDOWS.md).

## Safe first-launch defaults

After the one-time acknowledgement:

- text mode is on and microphone use is off;
- foreground-window activity awareness is off;
- cloud escalation, the local agent API, autonomous startup editing, and
  experimental sensing are off;
- local conversation, memory, time awareness, the offline reference library,
  and conservative semantic retrieval are available;
- web search may use a configured search service when a question requests or
  appears to require current information.

Useful first commands:

```text
help                    show available commands
health check            explain what is ready
tutorial                start the guided tour
library status          inspect the offline reference shelf
library search <words>  search manuals explicitly
audio mode              opt in to offline speech and microphone listening
activity on             opt in to foreground-window sampling
activity off            stop sampling and delete its retained log
```

`activity on` records the foreground application and window title, idle time,
system load, battery, and timestamps in a local log for up to 14 days by
default. Window titles can reveal filenames, pages, and message previews.
The choice persists. `activity off` persists the off choice and deletes both
the in-memory observations and `assistant\memory\activity_log.jsonl`.

## What Beta 6 can do

### Local companion

- Generate ordinary replies through the bundled local Qwen3 director.
- Accept typed input and, after `audio mode`, listen and speak locally.
- Maintain visible durable memories and a bounded recent conversation file.
- Recall at most one older exchange only when the user clearly asks about an
  earlier conversation and the semantic match is unambiguous.
- Read the local clock and describe current time, session age, and elapsed
  time between completed conversations without claiming hidden experience.

### Offline practical knowledge

Beta 6 contains an independent local reference library with built-in Canadian
preparedness cards and a private user shelf. It supports:

```text
.txt .md .rst .html .htm .json .csv .pdf .epub .docx
```

Ordinary conversation requires a real full-text word match before a manual
excerpt can enter the prompt. Embeddings may rerank those lexical hits but
cannot manufacture an automatic match. Explicit `library search` and the
authenticated `/knowledge/search` endpoint may return wider
`semantic-candidate` results, clearly labeled as candidates rather than facts.

PDF extraction uses `pypdf`; scanned image-only PDFs need OCR first. Imported
documents, extracted text, metadata, and vectors remain local and are not
part of release packages. See [Offline knowledge](docs/OFFLINE_KNOWLEDGE.md).

### Memory and semantic retrieval

Exact words and identifiers remain the strongest automatic evidence. Automatic
chat retrieval may add at most one zero-word-overlap memory, and only when its
cosine score is at least `0.55` and at least `0.06` above the runner-up.
Greetings and acknowledgements do not perform semantic retrieval.

Explicit memory searches rank semantic candidates by cosine without mixing in
recency or confidence. History recall requires an explicit request about an
earlier conversation, returns at most one result, and requires a score of at
least `0.60` with the same `0.06` margin. If the embedder is unavailable,
ordinary memory and library search fall back to lexical behavior.

### Media, tools, and optional bridges

- Play local MP3, WAV, FLAC, and OGG files with a ten-scene reactive
  visualizer.
- Use optional SearXNG or Brave search for current information.
- Search public music metadata and open Spotify.
- Use guarded, reviewable project-editing tools in advanced modes.
- Expose an experimental, token-authenticated, loopback-only read API for
  development agents. `/ask` can use the stable persona and core memory but
  cannot see the live chat and does not append history or extract memory.
- Send one deliberately escalated question to Anthropic or an
  OpenAI-compatible provider using the operator’s own key.
- Connect optional T-Deck and Meshtastic hardware.

The [capability matrix](docs/CAPABILITIES_AND_LIMITS.md) states which features
are implemented, optional, experimental, planned, or failed.

## Sensing: active research, not sight

The desktop Intel AX211 Wi-Fi proxy experiment failed: its signal described
the adapter and traffic pattern, not reliable room occupancy. That result is
retained rather than tuned into agreement.

The active next experiment is an HLK-LD2450 24 GHz movement-tracking radar
through a USB-to-TTL adapter, pending hardware. It can estimate movement and
trajectory; it cannot identify a person, provide camera-like sight, reliably
prove occupancy, or guarantee that a motionless person is present.

The existing Wi-Fi seam remains disabled and accepts only an expiring,
aggregate local state (`unknown`, `still`, `motion`, or `approach`). It never
captures Wi-Fi frames, raw CSI, SSIDs, device addresses, identity, or a
history. Use sensing only with consent and never for security, alarms, covert
monitoring, or safety-critical decisions.

See [Sensing module notes](docs/SENSING_MODULE.md) and the
[research goals](docs/RESEARCH_GOALS.md).

## machinespirit: locating meaning, not just measuring it

An embedding is a mean over a sentence's token vectors. The mean can say
what a sentence is about. It cannot say *where* in the sentence a meaning
appeared, because averaging is exactly what destroys that.

**machinespirit** keeps the path instead of only the average, and reads
every token position against a fixed dictionary of concepts written in
plain English. The result locates a meaning at a token:

```text
trace I keep thinking about something my grandmother said before she died.

  token   7  +0.459  grandparents telling the same story again
  token  11  +0.421  a promise made to a dying person
```

`SABLE7` is the container that stores such a path; machinespirit is the
representation it carries. Run it with `start_assistant_hazard.bat`, or
`experimental mode` inside an ordinary session. It is **slower on purpose**
and keeps a second embedding server resident, because llama.cpp fixes
pooling when a server starts and a trajectory cannot come from the pooled
one.

**What it does not do: change retrieval.** Keeping the path has not been
shown to retrieve better. Late interaction over trajectories returned the
same documents as ordinary pooled cosine, and anchor-space coordinates
scored 0.689 against uint8's perfect 1.000. So trajectories run alongside
retrieval rather than replacing it, and the mode says so when you turn it
on. What machinespirit adds today is the trace — a thing the averaged
vector cannot produce at all, rather than one it produces slightly worse.

Two companion documents record the measurements, including the ones that
came out negative, and name the prior art first:

- [Vector-to-pixel encoding](docs/VECTOR_PIXEL_RESEARCH.md) — where
  quantisation pays (4.00×, at a cosine error 868× below the retrieval
  margin), where a pixel container costs, and why storing bytes as pixels
  is reach rather than compression.
- [Cross-model translation and token trajectories](docs/VECTOR_TRANSLATION_RESEARCH.md)
  — translating between two models that share no vector space, measured
  across a 384-dimension and a 768-dimension embedder, and what a sentence
  discards when it becomes a point.

## Privacy and network summary

| Feature | Default and boundary |
| --- | --- |
| Local chat, speech, memory, embeddings, and offline library | Local files and loopback services. Files are not encrypted by TORMENT_NEXUS. |
| Microphone | Off at first launch; enabled by `audio mode`. |
| Activity awareness | Off at first launch; explicit opt-in, persistent choice, maximum 14-day default retention, deleted by `activity off`. |
| Web search | May send a derived query to configured SearXNG/Brave when current information is requested or inferred. |
| Cloud escalation | Off; sends only the explicit `escalate` question when separately enabled. |
| Agent API | Off; loopback-only and bearer-token authenticated, but capable of returning private memory/reference results. |
| Custom director/model URL | Can receive prompts and retrieved context; “local” no longer applies to that traffic. Beta 6 rejects non-loopback embedding URLs. |
| Spotify and MusicBrainz | Optional; search/account/playback metadata crosses their service boundaries. |
| T-Deck and LoRa | Optional; messages cross Bluetooth and the configured mesh. |

Read [Privacy](PRIVACY.md) before importing private manuals or enabling
activity, connected services, or agent access.

## Project status and rights

Beta 6 is experimental. Important claims and generated code require human
verification. The functional test suite does not certify content safety,
security, legality, factuality, or fitness for high-stakes use.

There is no project-wide license grant yet. Viewing or cloning the repository
does not grant general permission to modify or redistribute project-authored
material. Third-party models and runtimes retain their own terms, including
unresolved or restrictive terms documented in
[Models](MODELS.md) and [Third-party notices](THIRD_PARTY_NOTICES.md).

Security-boundary failures should follow [Security](SECURITY.md). Ordinary bug
reports and proposed changes should follow [Contributing](CONTRIBUTING.md).
Never attach conversations, memories, knowledge databases, imported manuals,
activity logs, keys, tokens, passcodes, pairing data, or personal paths.

## Documentation map

### Use and understand

- [Installing on Windows](docs/INSTALL_WINDOWS.md)
- [Your first session](docs/FIRST_RUN.md)
- [Capabilities and limits](docs/CAPABILITIES_AND_LIMITS.md)
- [Offline knowledge](docs/OFFLINE_KNOWLEDGE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Beta guide](docs/BETA_GUIDE.md)

### Safety, privacy, and rights

- [Safety](SAFETY.md)
- [Privacy](PRIVACY.md)
- [Models and provenance](MODELS.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Rights and reuse](RIGHTS.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

### Technical and research

- [Architecture](docs/ARCHITECTURE.md)
- [Testing](docs/TESTING.md)
- [Agent interface](docs/AGENT_INTERFACE.md)
- [Semantic retrieval and agent bridges](docs/SEMANTIC_AND_AGENT_BRIDGES.md)
- [Research goals](docs/RESEARCH_GOALS.md)
- [Sensing module notes](docs/SENSING_MODULE.md)
- [Bring your own GGUF](docs/BRING_YOUR_OWN_GGUF.md)

## Developer verification

Source contributors install the declared Python dependencies from
`setup/requirements.txt`. On Windows, run the complete project regression
suite from the repository root with:

```powershell
.\setup\test_assistant.bat
```

The test count is evidence about the checked behaviors, not a certification
that model output is safe, factual, lawful, or suitable for high-stakes use.
See [Testing](docs/TESTING.md) for the narrower test commands and release
verification boundaries.

## Acknowledgements

**sundog** - voice recognition testing and extensive first-session and
interface feedback. Several features began as ideas offered in conversation.
