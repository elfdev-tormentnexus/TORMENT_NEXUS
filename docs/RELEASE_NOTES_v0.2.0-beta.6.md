# TORMENT_NEXUS v0.2.0-beta.6

**Release status:** Beta 6 release candidate  
**Target platform:** 64-bit Windows  
**Full regression-suite count:** **639 passed, 2 skipped** on the packaged
commit `97711ca`  
**Package checksums and manifest file count:** **339 hashed files**; every
checksum is listed under [Package checksums](#package-checksums)

## Read this model disclosure before installing

The base Windows package contains two **abliterated** language models:

| Role | Included model | Purpose |
| --- | --- | --- |
| Director | `Qwen3-4B-abliterated-bf16_q8_0` | Ordinary conversation, goals, planning, and approval flow |
| Autonomous coder | `Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0` | Separately launched, bounded project editing and repair |

An abliterated model is modified in a way that can weaken its normal refusal
behaviour. That may make it more willing to answer; it does **not** make the
answer true, legal, safe, unbiased, or appropriate. These models can produce
confidently wrong or harmful instructions.

This is deliberately a complete, model-bearing release. Each shipped model is
identified by its exact SHA-256 in the package manifest and in the
[model disclosure](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/blob/v0.2.0-beta.6/MODELS.md);
a similar filename or widespread availability on a model host does not
establish that two files have the same provenance or redistribution terms.
Beta testers accept the unresolved provenance and licensing points documented
there rather than receiving a silently reduced package.

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

## Experimental and high-risk capabilities

Everything in this table is **off on a fresh installation** unless stated
otherwise. None of it starts on its own. It is listed here, before the
download instructions, so nobody discovers it after fetching 12 GB.

| Capability | Default | What it can do when you turn it on |
| --- | --- | --- |
| One-cycle autonomous repair (`start_autonomous_self_heal.bat`) | Off; needs the typed phrase `RUN ONE AUTONOMOUS REPAIR` | Inspects, modifies, validates and rolls back project files **without approving each individual edit** |
| Maintenance / full-maintenance coder profiles | Off; separate launchers, exact typed acknowledgement | Bounded project editing and repair under review |
| Local agent interface (`TORMENT_NEXUS_AGENT_API=1`) | Off | Token-authenticated, GET-only service on `127.0.0.1:8099`; lets an authorised outside agent search private memory and knowledge and ask the local director a read-only question. No write or command endpoints |
| Outbound escalation (`TORMENT_NEXUS_ESCALATION=1` plus a provider key) | Off; a key on disk alone does not enable it | Sends the question text you type to Anthropic or OpenAI under their billing, retention and terms |
| Semantic retrieval and embeddings | On when the local embedding service is healthy | Local-only vector retrieval; degrades to lexical matching when absent |
| Web search | Backend set to self-hosted SearXNG on `127.0.0.1:8081` | See the note below — the search service is **not** part of this download |
| Foreground activity awareness | Off | Records application, window title, idle time and load locally |
| Interface mode (optional add-on, own launcher) | Not in the base package; opens only via its own launcher | Opens the read-only agent interface on loopback for as long as that window is open |
| Wi-Fi sensing bridge (`TORMENT_NEXUS_WIFI_EXPERIMENT=1` plus a status file) | Off, and no default file path | Reads one small aggregate JSON record written by a separately authorised external collector. It never changes a wireless driver, enters monitor mode, transmits packets, or records raw radio measurements |
| Radar / room sensing hardware | Not present | The LD2450 has not arrived; no radar capability ships |

**Autonomous editing is the one to read twice.** It is genuinely capable of
changing this project's source without asking about each change. The
guardrails — protected files, previews, backups, fixed checks, tests and
rollback — reduce risk and are not a security sandbox.

**Web search is inert as shipped.** The default backend expects a self-hosted
SearXNG instance on loopback, which lives outside the packaged tree and is not
included here. Until you run one, or switch the backend to Brave and supply
your own API key, web search simply returns nothing. When a search service
*is* running, queries leave your machine through it.

**The semantic thresholds are calibrated measurements, not universal
constants.** They were measured against this exact stack: this embedding
model, quantization, runtime, and mean pooling — deliberately chosen over the
CLS pooling upstream BGE examples commonly use. Changing any of those
invalidates the numbers and requires recalibration.

## What is in the package

- Qwen3 4B abliterated Q8 director;
- Qwen2.5-Coder 7B abliterated Q8 autonomous coder;
- bge-small-en-v1.5 Q8 embedding model;
- offline speech recognition, speech output, Python runtime, and CPU
  llama.cpp runtime.

The `Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M` full-maintenance model is
not included. It ships as the separate optional add-on described below, so
ordinary users are not forced to download it, and it is never a normal chat
profile.

## Installing the Windows package

Download these assets into one folder:

1. `TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip.part01` through `.part06` —
   all six are required
2. `REASSEMBLE_TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.bat`
3. `TORMENT_NEXUS-v0.2.0-beta.6-docs-patch.zip` — 15 KB, optional but
   recommended

Run the reassembler and leave it alone. It does the whole sequence:

1. joins the exact generated part set;
2. checks the complete ZIP against its embedded SHA-256, and **deletes a
   mismatch** rather than presenting a damaged archive as installable;
3. extracts the package;
4. applies the documentation patch if it is present.

Then open the `TORMENT_NEXUS` folder and run `setup.bat`.

Allow roughly 40 GB free while this runs — the parts, the joined ZIP and the
extracted folder briefly coexist. If a `TORMENT_NEXUS` folder already exists
beside the script, extraction is skipped and the existing one is kept.

**What the patch is for.** The bundled `docs/` folder is inside the archive,
so documents corrected after the 13 GB package was built are out of date in
every copy already zipped. Rebuilding 12 GB to fix a markdown file is a poor
trade, so the corrected documents ship as this small separate asset instead.
It replaces documentation only — no code, launcher, or model file — so the
installed tree still matches the published archive checksum. If you skip it,
nothing breaks; the bundled notes are simply the older version and this page
remains authoritative.

GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** downloads
are developer source snapshots. They do not contain the model weights,
self-contained Python environment, or ready-to-run Windows package.

### Package checksums

SHA-256, with sizes in bytes. The reassembler checks the rejoined ZIP against
the first value automatically; the rest are for verifying individual downloads.

| Asset | Bytes | SHA-256 |
| --- | --- | --- |
| `TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip` | 12,380,706,363 | `AC66CA1ACA80BFE21163BA41F0DB11AEA215617FAD0F48FF24FFA6A37B0AB1A9` |
| `.zip.part01` | 2,080,374,784 | `B8B4B15876D0BFE8172B357DE8D057FCE31EDADBCDA878DA54444B4207192BD1` |
| `.zip.part02` | 2,080,374,784 | `77EA52AC0F61BFE6451CC7EBC15A9D5EF7B80EA324C435BFC08932FB9D093799` |
| `.zip.part03` | 2,080,374,784 | `BB529F78BC989C070B822B48509838E5FB1B374DF08B64E41FAC80D4EA96A891` |
| `.zip.part04` | 2,080,374,784 | `FCD6AF853B42626177C683EA68A21329FDDABC031F476CE772FC7D5C929DDEFF` |
| `.zip.part05` | 2,080,374,784 | `B74AA7B6147C463F4269DC6ACDD4D3781711C66560D6EBBAE7B1002B6F06E789` |
| `.zip.part06` | 1,978,832,443 | `A346A56A148A7EAE8BFA55F284DDC3028518DDB90E10EC2E730F1236448B236B` |
| `REASSEMBLE_TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.bat` | 3,906 | `9FE13AA4097E21C68CCBB3814541AC831408A63DA037ECF63E3103A96AFDA5BB` |
| `TORMENT_NEXUS-v0.2.0-beta.6-docs-patch.zip` | 15,038 | `81E8517EBE97A2FD833AD2A6A2889D94EC619D904EDD2DA555FEBD1FECED2F90` |

### Optional interface-mode add-on

Interface mode is the ordinary assistant with the read-only agent interface
open on loopback. It has its own launcher because that interface is a
listening socket and an authentication boundary: which windows have it open
should be visible, not remembered. The window title and an inverted icon both
say so.

It is a separate add-on because the launcher lives outside the packaged tree
and did not make the base archive. Everything it depends on — the agent
interface module, the `AGENT_WATCH` echo, and the fallback launcher — is
already in the base package, so the add-on is 3 KB.

Download `INSTALL_INTERFACE_MODE.bat` and
`TORMENT_NEXUS-v0.2.0-beta.6-interface-mode.zip`, place both **inside** the
extracted `TORMENT_NEXUS` folder, and run the installer. It verifies the
payload against the SHA-256 below, installs the launcher, its icon and its
documentation, and creates a desktop shortcut.

| Add-on detail | Value |
| --- | --- |
| Payload | `TORMENT_NEXUS-v0.2.0-beta.6-interface-mode.zip` |
| Bytes | 3,295 |
| SHA-256 | `C8F40B3E45A95E890F0BEB33FB377452BF6C8B535B14990FD625A73BF747BB1C` |
| Installer | `INSTALL_INTERFACE_MODE.bat`, 2,464 bytes |
| Installer SHA-256 | `712A21B72B582CE24AB66F37DC8CB2AF08171ED60CDA197E00747869D623E5BD` |

While interface mode runs, a connected agent can read state, search memory and
the knowledge library, and ask the director a question. Nothing on that
interface writes, edits, or restarts. The bearer token is written to
`assistant\.agent_token`, and closing the window closes the interface. Every
other launcher leaves it closed — installing this add-on does not open
anything by itself.

### Optional full-maintenance model add-on

Advanced users who deliberately want the preserved 14B full-maintenance
profile must also download all five consecutive
`Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf.part01` through `.part05`
assets, plus `INSTALL_FULL_MAINTENANCE_14B.bat`.

Place the installer and every model part inside the extracted
`TORMENT_NEXUS` folder and run the installer. It verifies the rejoined file
against the SHA-256 below and refuses to install a mismatch; the installer
itself carries the checksum, so there is no separate manifest, checksum list,
or README asset for this add-on.

| Add-on detail | Value |
| --- | --- |
| Rejoined model | `Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf` |
| Bytes | 8,988,111,200 |
| SHA-256 | `E89A7AE4E2B456BF33C75CFF35664751DF20FF273E551D7CF7640AA9E84D3B79` |
| Parts | 5 × 1,797,622,240 bytes |

Let the check finish before starting `start_full_maintenance_coder.bat`. That
launcher shows the full-maintenance warning and requires the exact typed
acknowledgement.

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

### Honesty fixes in ordinary conversation

These came from reading the assistant's own conversation log, and each one is
a case where it produced a fluent, specific account of something that had not
happened. All are enforced in Python rather than by asking the model to
behave.

- Persona examples no longer reach the model as if they were recent
  conversation. Previously they arrived as the six most recent turns, and the
  assistant fused them into a confident report of a conversation with the
  operator that never took place.
- Input that resembles a real command but is not one is now answered directly
  instead of narrated as completed. "finish goals" used to return "I am done
  with the goals" without anything having run.
- "Choose a name" now reaches the actual naming ceremony instead of inventing
  a name and a reason for it in chat.
- History trimming cuts on exchange boundaries, so the log no longer begins
  mid-record.
- The operator can set a name directly with `name is NAME`. It is recorded as
  operator-chosen, and the model is told it did not choose it.

### Music visualizer and loudness matching

All eight scenes gained a wall-clock anchor layer, and scene reactivity was
raised across the board. The acid lattice drew lines roughly three times
thinner than the braille raster and rendered as speckle; the datastream
horizon floated six rows above the bottom. Both are fixed, and the neon
horizon's skyline now uses the project's corruption idiom.

Track loudness is matched at playback (`visualizer/loudness.py`). Measured
across the development library of 41 tracks, a 20.0 dB spread narrowed to
1.4 dB with the loudest normalised peak at 0.985 against a 0.985 ceiling and
no clipping. This is gated RMS, not ITU-R BS.1770 LUFS; K-weighting is
documented in the module as the honest next step.

### Onboarding

`tutorial` now opens with a prose introduction covering the whole system
rather than a bare list of commands.

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

The underlying Wi-Fi CSI research lives in the repository rather than in this
package, but its conclusion belongs here: the LiveSense AX211 range-Doppler
demonstration is real and **not publicly reproducible** — all five authors are
Intel, and neither paper ships code or an artifact. The open paths are FeitCSI
and the IAX artifact at `github.com/fflq/iax`, both Linux-only. The desktop's
AX211 stays untouched because it is the machine's only internet link and IAX
replaces that card's firmware and driver system-wide. None of this is shipped
capability; it is a reproduction plan for hardware that has not arrived.

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

The embedding service is local-only and Beta 6 rejects a non-loopback
embedding URL. One exception is worth stating plainly: if you configure a
**remote director server**, retrieved memories and reference context are sent
to it as part of an ordinary model prompt. The local-first claim covers the
embedder, not that director traffic.

The release builder refuses to include the maintainer's conversations,
memories, chosen name, activity history, imported knowledge documents, derived
embedding database, API credentials, device PINs, tokens, music, logs, or
runtime caches.

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

Maintainer checklist. This section is kept in the repository copy and is
stripped from the published release body.

1. Freeze all editors and commit the intended source.
2. Finalise every document that ships **inside** the package before building
   it. `docs/` is packaged, so release notes and `CHANGELOG.md` written after
   the build are stale in the archive even when the release page is correct.
3. Require a clean-tree package build from the tagged commit.
4. Run the complete regression suite and insert the exact passing count.
5. Smoke-test a disposable extraction, then rebuild the final clean package.
6. Verify the package manifest and privacy scan.
7. Split the versioned ZIP and record the SHA-256 of the ZIP, every part, and
   the generated helper.
8. Upload as a draft prerelease and compare every remote asset size and digest.
9. Publish only when the tag, README, installation guide, release body,
   filenames, test count, and checksums all agree.
