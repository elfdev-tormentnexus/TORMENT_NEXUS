# TORMENT_NEXUS v0.2.0-beta.6

**Release status:** Beta 6 release candidate  
**Target platform:** 64-bit Windows  
**Full regression-suite count:** **verified at release** after the final clean
source freeze  
**Package checksums and manifest file count:** generated and inserted only
after the final package is rebuilt

Do not publish these notes while either verification line above is still
provisional.

## Read this model disclosure before installing

The base Windows package contains two **abliterated** language models:

| Role | Included model | Purpose |
| --- | --- | --- |
| Director | `Qwen3-4B-abliterated-bf16_q8_0` | Ordinary conversation, goals, planning, and approval flow |
| Autonomous coder | `Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0` | Separately launched, bounded project editing and repair |

This is deliberately a complete, model-bearing release. Each shipped model
is identified by its exact SHA-256 in the package manifest and
[model disclosure](../MODELS.md); a similar filename or widespread
availability on a model host does not establish that two files have the same
provenance or redistribution terms. Beta testers accept the unresolved
provenance/licensing points documented there rather than receiving a silently
reduced package.

An abliterated model is modified in a way that can weaken its normal refusal
behaviour. That may make it more willing to answer; it does **not** make the
answer true, legal, safe, unbiased, or appropriate. These models can produce
confidently wrong or harmful instructions.

TORMENT_NEXUS uses trusted Python rules, protected files, previews, backups,
fixed checks, tests, and rollback to constrain supported tool and editing
paths. Those controls reduce risk but are not a security sandbox and cannot
guarantee that every output or change is safe.

- Do not run the advanced editing profiles as Administrator.
- Keep credentials, recovery codes, private keys, and irreplaceable files
  outside the project.
- Maintain a separate backup and review proposed and completed changes.
- Independently verify medical, legal, financial, security, electrical,
  radio, hardware-control, and other high-stakes advice.
- Do not treat the system's stylized identity as consciousness, authority, or
  proof that it understands consequences.

The ordinary launcher does not require terminal confirmation. First launch
presents the mandatory in-app safety, privacy, and model disclosure. The
maintenance, one-cycle autonomous-repair, and full-maintenance launchers show
additional warnings and require exact typed acknowledgement before starting.

## What is new in Beta 6

### Semantic memory and bounded history recall

The package adds the 35 MB `bge-small-en-v1.5-q8_0` embedding model. Memory
retrieval now combines semantic similarity with the existing exact
word-overlap path, preserving exact identifiers while finding genuinely
related memories that use different words.

Embeddings are calculated locally and cached. The cache is treated as private
derived memory and is excluded from release packages. If the embedding service
is absent or unhealthy, retrieval falls back to the literal path instead of
blocking ordinary conversation.

Recent conversation history gains separately bounded semantic recall. It does
not turn the complete transcript into unlimited prompt context.

### Offline practical-reference shelf

Eight compact, Canada-focused safety and resilience cards ship with a
separate offline library for operator-supplied TXT, Markdown, HTML, JSON, CSV,
PDF, EPUB, and DOCX references. Full-text search works without the embedding
model; explicit semantic widening is labeled and bounded.

Imported passages remain untrusted data. Automatic retrieval requires
meaningful subject-word coverage, serializes bounded excerpts as reference
data, and does not use semantic resemblance alone to inject a manual into
ordinary conversation. `library remove` deletes the live copy and searchable
rows synchronously, with a best-effort database compaction that is not a
forensic erase of backups or storage-device remnants.

### Real retrieval and entropy displays

The retrieval panel now displays real memory-vector state. The entropy strip
uses the sampler's measured distribution, and music response is coupled to the
shape actually rendered. Visual panel vectors and semantic embedding vectors
remain separate systems.

### Deliberate AI-to-AI bridges

The local `/ask` interface allows an owner-authorised outside agent to submit a
read-only question through a scoped local token.

The outbound escalation bridge is separate and disabled by default. It
requires an explicit environment opt-in plus an owner-supplied Anthropic or
OpenAI API key. Only the text deliberately supplied to the escalation command
is sent; ordinary local conversation does not silently become a cloud session.
External calls may incur provider charges and are governed by that provider's
terms and data practices.

### Guardrail and release integrity work

- Broader protected edit surfaces and stricter model-role isolation.
- Bounded latency and failure fallback for semantic services.
- Privacy exclusions for API keys, agent tokens, embeddings, knowledge
  databases, imported documents, activity records, and ordinary memories.
- Versioned Windows archive names.
- A clean-source and stable-snapshot requirement for final builds.
- Fatal checks for a missing model or required user document.
- Release manifests that bind the version and source commit to every shipped
  file and record the identity, size, and SHA-256 of each bundled model.
- A generated reassembler that verifies the complete ZIP automatically and
  deletes a mismatched join.

### Sensing remains honest and experimental

The Windows userland Wi-Fi proxy failed its measurement gate and is not a
working room sensor. The sensing workstream is active again pending the
HLK-LD2450 24 GHz movement-tracking radar and CP2102 USB adapter.

The separate Raspberry Pi monitor-mode, display, battery, and thermal work is
documented as future hardware validation. It is not present hardware and is
not a shipped sensing capability.

## Models and optional components

The base package includes:

- Qwen3 4B abliterated Q8 director;
- Qwen2.5-Coder 7B abliterated Q8 autonomous coder;
- bge-small-en-v1.5 Q8 embedding model;
- offline speech recognition, speech output, Python runtime, and CPU
  llama.cpp runtime.

The `Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M` full-maintenance model is
distributed as a separately split, checksum-verified optional desktop add-on.
It is preserved as part of the complete release asset set without forcing
every ordinary user to download it, and it is never a normal chat profile.

## Privacy and network boundaries

Conversation, normal memory, semantic retrieval, speech, and local music stay
on the computer by default.

Activity awareness is off on a fresh installation. When the operator
explicitly enables it, it records the foreground application, window title,
idle time, and machine load locally. Window titles can reveal documents,
websites, or conversations. The in-app disclosure explains retention and the
commands that inspect, disable, or erase it.

Web search, provider escalation, Spotify metadata lookup, radio transmission,
and connected hardware are separate optional paths. Each can cross a local or
network boundary only when configured and used.

The release builder refuses to include the maintainer's conversations,
memories, chosen name, activity history, imported knowledge documents, derived
embedding database, API credentials, device PINs, tokens, music, logs, or
runtime caches.

## Installing the Windows package

Download the generated Beta 6 assets into one folder:

1. `TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip.part01`
2. every later consecutive `.partNN` file shown in the release
3. `REASSEMBLE_TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.bat`

Run the reassembler. It joins the exact generated part set and automatically
checks the complete ZIP against its embedded SHA-256. A mismatch is deleted
instead of being presented as an installable package.

After it reports **Verified**, extract
`TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip`, open the extracted
`TORMENT_NEXUS` folder, and run `setup.bat`.

GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** downloads
are developer source snapshots. They do not contain the model weights,
self-contained Python environment, or ready-to-run Windows package.

### Optional full-maintenance model add-on

Advanced users who deliberately want the preserved 14B full-maintenance
profile must also download:

1. all five consecutive assets from
   `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b.part01` through
   `.part05`;
2. `INSTALL_TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b.bat`;
3. `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b-MANIFEST.json`;
4. `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b-SHA256SUMS.txt`; and
5. `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b-README.txt`.

Place the installer and every model part inside the extracted
`TORMENT_NEXUS` folder, run the installer, and let its baked-in SHA-256 check
finish before starting `start_full_maintenance_coder.bat`. The launcher then
shows the full-maintenance warning and requires the exact typed acknowledgement.
The model-pack manifest records the exact reviewed 14B size, SHA-256, source
revision, and uploader-declared license; the declaration is evidence, not an
independent legal conclusion.

## Known limitations

- This remains beta software. Replies and edits can be wrong.
- The ready-to-run package targets 64-bit Windows.
- The local models require substantial memory and can be slow on CPU.
- GPU acceleration depends on a separately compatible runtime and hardware.
- External provider escalation is optional, online, and user-billed.
- Radar sensing waits for hardware arrival and calibration.
- Raspberry Pi deployment remains an advanced manual target.
- Offline reference knowledge can become outdated; changing medical, legal,
  security, recall, weather, price, and regulatory facts require current
  authoritative verification when available.

## Final release gate

Before publishing:

1. Freeze all editors and commit the intended source.
2. Require a clean-tree package build from the tagged commit.
3. Run the complete regression suite and replace **verified at release** with
   the exact passing count.
4. Smoke-test a disposable extraction, then rebuild the final clean package.
5. Verify the package manifest and privacy scan.
6. Split the versioned ZIP and record the SHA-256 of the ZIP, every part, and
   the generated helper.
7. Upload as a draft prerelease and compare every remote asset size and digest.
8. Publish only when the tag, README, installation guide, release body,
   filenames, test count, and checksums all agree.
