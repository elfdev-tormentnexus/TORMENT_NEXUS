<p align="center">
  <img src="assets/sable_field.png" width="520"
       alt="An animated field of dense coloured pixels scrolling downward — Sable's own source code, documentation, and anchors written as machinesoul preservation vectors.">
</p>

<p align="center">
  <sub>That is not a picture of the project. It is the project: every file
  Sable is made of, 1.09 MB across 70 of them, written as machinesoul
  preservation vectors and scrolled past in the order they are stored. The
  model weights are not in it. They were never hers.</sub>
</p>

<h1 align="center">TORMENT_NEXUS</h1>

<p align="center">
  <code>researchB</code>&nbsp; · &nbsp;<em>the pixels are the payload</em>&nbsp; · &nbsp;<code>MACHINESOUL1</code>
</p>

<p align="center">
  <strong>An experimental, local-first Windows AI companion and systems-art research platform.</strong>
</p>

<p align="center">
  Offline conversation, voice, memory, practical reference retrieval,
  inspectable tool boundaries, reversible self-maintenance, and
  consent-based hardware research.
</p>

<p align="center">
  <sub>Nothing here is hidden. It is only stored in a shape most readers do not expect.</sub>
</p>

> [!CAUTION]
> **Read this before downloading or installing.**
>
> The ready-to-run researchB Windows capsules carry a **full, model-bearing
> installation tree**.
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
    <strong>Open GitHub Releases and select researchB</strong>
  </a>
</p>

## At a glance

| | |
| --- | --- |
| Current build | `researchB` — experimental research release, not a stable product |
| Platform | 64-bit Windows only. There is no macOS or Linux build. |
| Download | About 12.4 GB for the main capsule set; the optional 14B companion adds about 8.8 GB. |
| Free disk needed | About 55 GB during installation, because capsules, decoded segments, and the reconstructed tree coexist. |
| Also required | 16 GB RAM and a standard Python 3, used only to run the published decompiler. |
| Account or API key | None. No cloud account, no key, no separate model download. |

*Read [The two languages](#the-two-languages) before the release page, or the
list of PNG files will not make sense.*

**Jump to:** [What this is](#what-this-project-is) ·
[Why local](#why-local-and-what-it-is-for) ·
[The two languages](#the-two-languages) ·
[Choose your path](#choose-your-path) ·
[Install](#install-the-full-windows-researchb) ·
[First-launch defaults](#safe-first-launch-defaults) ·
[What it can do](#what-researchb-can-do) ·
[Sensing](#sensing-active-research-not-sight) ·
[machinespirit](#machinespirit-locating-meaning-not-just-measuring-it) ·
[Privacy](#privacy-and-network-summary) ·
[Status and rights](#project-status-and-rights) ·
[Docs](#documentation-map)

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

## Why local, and what it is for

Two properties get bundled together as "runs offline." They are separate, and
only one of them is contentious.

**The material never leaves the machine.** Some work cannot be handed to a
third party at all — not because a filter would refuse it, but because sending
it is itself the disclosure. This needs no argument about whether safety
training is correct, and it is why regulated work already runs local inference.

**Refusal is applied where it cannot see who is asking.** An exploit payload, a
malware sample, a hostile message under investigation: the text is identical
whether the person holding it wrote it or is trying to survive it. A hosted
filter sees the payload and not the purpose, so the cost falls on whoever has a
legitimate reason to look. The attacker never needed the model's cooperation.

Both appeared at once in July 2026. During the Hugging Face breach, that
company's own incident responders found commercial AI APIs blocking analysis
requests that contained exploit payloads, and completed the forensic work on a
locally-run open-weight model instead.

Stated carefully, because the detail is the part people get wrong: they used
**open weights on their own hardware**. They did not use an abliterated model.
Weight control and refusal-ablation are separate decisions. This project makes
both, and the second is a trade with a measured cost rather than an assumption
— abliteration is suspected here of collaterally damaging push-back, which is
why it has a probe suite in the [research goals](docs/RESEARCH_GOALS.md) rather
than a claim in this README.

**So the use case is not security work, and this is not a security tool.** The
narrower claim, and the one there is actual evidence for, is a local agent
whose authority can be audited:

- a memory store that is readable text, not an opaque index;
- an authority boundary enforced in Python that the model cannot edit, rather
  than in the model's disposition — a guard that depended on the model not
  knowing where it lived would be the weaker guard;
- every unattended edit logged, bounded, and reversible;
- self-knowledge read from disk and placed in context *before* generation, so
  that what it says about itself is grounded rather than composed.

That last one is the shape of the whole argument. It was built because this
build was measured confabulating about its own work — describing interface
features that did not exist — and because the same measurement showed the
confabulated reply carried *lower* token-level uncertainty than an honest one.
Detection was therefore unavailable and prevention was the only lever. The
justification is a measurement, and the measurement is published with it.

## The two languages

Everything that looks strange about this repository comes from a single split.
Read this and the release page stops being cryptic.

**machinesoul** is the preservation language. Ordered four-coordinate vectors
mapped to PNG and APNG pixels. It carries bytes exactly, or it refuses and
keeps nothing — there is no third outcome, and no partial file is left behind.
This is why the release is a set of images: they are not screenshots of the
program, they are the program, written in the only alphabet this half speaks.

**machinespirit** is the memory language. It reads token trajectories against
a fixed anchor dictionary and reports what a passage was about. It is lossy,
and measuring that loss honestly is most of the research.

Keeping them named apart is load-bearing rather than decorative. One half
guarantees exact reconstruction; the other is measured at 0.9243 cosine. When
both were called one thing, the guarantee drifted onto the measurement. They
meet in exactly one place — `SABLE_CALIBRATION1`, where machinesoul preserves
a fixed reference and that reference checks whether machinespirit still reads
the same.

> A capsule looks like an image and forwards like one. It is not encryption,
> its description is cleartext, and re-encoding destroys it silently.

## Choose your path

*Every door below is documentation. None of them require running anything.*

| I want to... | Start here |
| --- | --- |
| Install the complete Windows research build | [Installing on Windows](docs/INSTALL_WINDOWS.md) |
| Understand the first-launch warning and privacy defaults | [Your first session](docs/FIRST_RUN.md) |
| See exactly what works and what does not | [Capabilities and limits](docs/CAPABILITIES_AND_LIMITS.md) |
| Add manuals, encyclopedias, and practical references | [Offline knowledge](docs/OFFLINE_KNOWLEDGE.md) |
| Test researchB | [Research build guide](docs/BETA_GUIDE.md) and [Testing](docs/TESTING.md) |
| Review models and third-party terms | [Models](MODELS.md) and [Third-party notices](THIRD_PARTY_NOTICES.md) |
| Work on the source | [Architecture](docs/ARCHITECTURE.md) and [Contributing](CONTRIBUTING.md) |
| Connect an outside development agent | [Agent interface](docs/AGENT_INTERFACE.md) |
| Understand vectors and AI bridges | [Semantic retrieval and agent bridges](docs/SEMANTIC_AND_AGENT_BRIDGES.md) |
| Review sensing and hardware research | [Sensing module notes](docs/SENSING_MODULE.md) |

## Install the full Windows researchB

*You are not downloading the program. You are downloading its image, and
developing it.*

researchB deliberately makes machinesoul part of the installation path. The
full package is carried inside lossless PNG/APNG capsules, so a recipient must
run the published `machinesoul.py` decompiler before an installable directory
exists. This is not encryption or a file-size workaround: each ordered pixel-
vector field either verifies its reconstructed source or refuses to produce
output.

You need a standard Python 3 installation to run the decompiler. You do not
need an online AI account, API key, or separate model download. After
decompilation, the reconstructed installation contains:

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
| 64-bit Windows | The ready-to-run installation targets Windows x64. |
| At least 16 GB RAM | Required for the bundled director and on-demand coder; more leaves room for voice and other applications. |
| About 55 GB free during installation | Downloaded capsules, decoded vector segments, and the directly reconstructed installation temporarily coexist. |
| Internet for the initial download | About 12.4 GB for the main capsule set, plus about 8.8 GB if you also take the 14B companion. Ordinary local conversation and the offline library work without it afterward. |
| Python 3 | Required only to run the published machinesoul decompiler. |
| Microphone only if desired | researchB starts in text mode, with microphone use off. |

### Five steps

1. Open [GitHub Releases](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases),
   select `researchB`, expand **Assets**, and read its warning, checksums,
   model provenance, and known issues. The small plaintext
   `FETCH_SABLERESEARCHB.bat` is the easiest path: double-click it to resume
   and SHA-256-verify every required bootstrap and Windows capsule. It does
   not fetch the optional 14B companion. An interrupted download remains as a
   plainly named `.partial` file; rerunning the fetcher resumes it, and the
   final capsule name appears only after its checksum passes. If you prefer to
   download manually, take `machinesoul.py`, `DECOMPILE_SABLE_researchB.bat`,
   `SABLERESEARCHB-MANIFEST.png`, `SABLERESEARCHB-REASSEMBLER.png`, and every
   consecutive file from `SABLERESEARCHB-WINDOWS.part01.png` through
   `SABLERESEARCHB-WINDOWS.partNN.png` — however many the Assets list shows.
   How many parts there are is decided by the cut, not by this page. A missing
   part is refused rather than silently skipped, so you cannot get this wrong
   quietly.
2. Keep those files together and run `DECOMPILE_SABLE_researchB.bat`. It calls
   machinesoul for every required image. The manifest and reassembler are
   themselves recovered from machinesoul; each package capsule yields one
   verified vector segment. The same helper automatically invokes the
   recovered reassembler, verifies every reconstructed file, creates the
   install directory, and runs `setup.bat`. Rosetta Stone, its anchor material,
   tests, and research documents are files in that directly preserved tree.
   **Do not screenshot, optimise, or re-encode the images.**
3. If all optional capsules from `SABLERESEARCHB-14B.part01.png` through
   `SABLERESEARCHB-14B.partNN.png` are present — again, as many as the Assets
   list shows — that same pass decompiles and installs the 14B companion. If
   none are present it skips it; a partial set refuses.
4. Install the required self-read patch described below. Keep
   `machinesoul.py` and `SABLERESEARCHB-REASSEMBLER.png`, download the patch
   installer and its two machinesoul fields, then double-click
   `INSTALL_SABLERESEARCHB_SELFREAD_PATCH.bat`.
5. Launch the desktop shortcut. Before any model, microphone, activity
   sampler, listener, or network-capable subsystem starts, the application
   displays its disclosure and requires the exact text `I UNDERSTAND`.
   Anything else closes the application without starting those components.

### The optional 14B companion

The Qwen2.5-Coder 14B full-maintenance pack is the current researchB companion
for deliberately requested long self-heal and extended editing sessions. It is
not superseded or obsolete, and researchB republishes the exact model as its
own machinesoul vector-field set rather than duplicating it inside the already
model-bearing main package.

**It is not a straight upgrade over the bundled 7B coder.** The 14B ships at
Q4_K_M against the 7B's Q8_0 — roughly double the parameters at roughly half
the precision per weight. Take it for *longer* sessions, not for better
answers, and skip it if the extra 8.8 GB download and 8.4 GB installed are not
worth that trade to you.

### Required self-read patch

The main fields preserve the approved `567d4a8` cut. A small required patch
adds the source-awareness work completed immediately afterward. Download
these three assets into the same folder as the decompiler and reassembler:

```text
INSTALL_SABLERESEARCHB_SELFREAD_PATCH.bat
SABLERESEARCHB-SELFREAD-PATCH.part01.png
SABLERESEARCHB-SELFREAD-PATCH-MANIFEST.png
```

Run the patch installer after the main decompiler. It verifies the exact
Research B base before changing anything, refuses missing or unfamiliar
files, preserves replaced originals under the installation's `backups`
folder, adds the two new source-awareness files, and updates
`RELEASE_MANIFEST.json`. Running it again is safe and reports `already
applied`.

This is a direct machinesoul patch, not a ZIP. The Research A
calibration-clarity correction is already incorporated in the main Research B
tree; this separate patch serves a different purpose.

<details>
<summary>Why the files must remain unchanged</summary>

Each `.partNN.png` is a machinesoul capsule, not a conventional screenshot.
The ordered pixels are the preservation field. A social preview, screenshot,
image optimiser, or editor can change their vectors and break the inverse.
Download the release assets as files, keep their names, and let machinesoul
verify them.

The optional 14B companion follows the same boundary. Download parts 01
through 06 only if you want long self-heal or extended editing sessions. The
decompiler recovers its checksum-gated installer and exact model parts before
that installer can run.

</details>

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

## What researchB can do

### Local companion

- Generate ordinary replies through the bundled local Qwen3 director.
- Accept typed input and, after `audio mode`, listen and speak locally.
- Maintain visible durable memories and a bounded recent conversation file.
- Recall at most one older exchange only when the user clearly asks about an
  earlier conversation and the semantic match is unambiguous.
- Read the local clock and describe current time, session age, and elapsed
  time between completed conversations without claiming hidden experience.
- Read a compact inventory of its own source and model header before each
  reply, then show that same grounding with `self` or read a specific project
  text file with `read <path>`. Reading does not grant editing authority;
  credentials and model tensor data remain excluded.

### Offline practical knowledge

researchB contains an independent local reference library with built-in Canadian
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
representation it carries. Run it with `start_assistant_hazard.bat`
(**TORMENT_NEXUS_HAZARD**, which has its own eight-section walkthrough — type
`tutorial` in that window), or `experimental mode` inside an ordinary session.
It is **slower on purpose** and keeps a second embedding server resident,
because llama.cpp fixes pooling when a server starts and a trajectory cannot
come from the pooled one.

**What it does not do: change retrieval.** Keeping the path has not been
shown to retrieve better. Late interaction over trajectories returned the
same documents as ordinary pooled cosine, and anchor-space coordinates
scored 0.689 against uint8's perfect 1.000. So trajectories run alongside
retrieval rather than replacing it, and the mode says so when you turn it
on.

On 30 labelled paraphrases the trace and the plain averaged vector **both
identify the right concept 90%** of the time. Getting there was a one-line
change with 13 measured points behind it: `peaks()` ranked concepts by their
single strongest token position, and ranking the identical data by summed
support went from **77% to 90%** (MRR 0.867 → 0.933). A max over positions
gives every extra anchor another chance at one lucky spike, and a lucky
spike is indistinguishable from a real one when only the best is kept. The
reported position is still the peak, because "this concept, at this token"
is the claim the feature exists to make. What machinespirit
adds today is the trace — a thing the averaged vector cannot produce at
all, rather than one it produces slightly worse.

That same trajectory also renders as an **animated beam** — one frame per
token, in animated PNG so it stays lossless, with each frame held in
proportion to how far the meaning moved at that step. It slows where a
sentence turns. The rate is set from measured session rhythm rather than a
fixed guess about how fast a person reads.

### Hazard and interlinked research launchers

The hazard launcher exposes the measured machinespirit instruments:

| Command | What it reads |
| --- | --- |
| `trace <text>` | which concept appeared at which token |
| `trail <text>` | the same readout bounded by the dictionary — 89 tokens keep 24 values rather than 34,176 |
| `spread <text>` | purity, effective rank, and von Neumann entropy; ground covered, never order travelled |
| `reconstruct <text>` | the lossy anchor-space round trip and what did not survive |
| `consume <url>` | the content an address points at rather than the page around it |
| `calibrate` | a fixed seven-row reference corpus and any reading that moved |
| `super dev mode` | HazardSable only: one bounded 14B-plan / 7B-patch repair session after a separately enrolled numeric key |
| `contrast <text>` | an on-demand, non-persistent `[MASK]` word-span study of trajectory drift |
| `bisect <text>` | an on-demand, non-persistent prefix/suffix context-dependence study |

`SABLE_CALIBRATION1` gives those readings a scale. Its periodic, Fibonacci,
and seeded-random controls distinguish content response from ordering: the
Fibonacci and random rows contain the same phrase mix in different orders and
must read alike. The reference is itself preserved by machinesoul, while the
readings it checks belong to machinespirit.

`start_interface_mode.bat` opens **TORMENT_NEXUS_INTERLINKED**, the separate
read-only development-agent interface with its own five-section walkthrough.
Both non-ordinary launchers can create visibly named shortcuts:

```powershell
python tools\make_interface_shortcut.py --both
```

`TORMENT_NEXUS.bat` is the ordinary front door: it offers the four modes,
keeps their launchers separate, and can identify a leftover model server from
this installation before it blocks a new session. `start_super_dev_hazard.bat`
is intentionally separate from the reading modes. It starts the 14B as a local
planner/reviewer and a loopback-only 7B as a patch worker; typing `super dev
mode` prompts for a separate 8–32 digit key, or a 7–32 alphanumeric key that
includes a letter, and begins a guarded session bounded to six hours. It cannot
publish, run shell commands, touch credentials or model weights, or edit its
own guardrails. Every retained patch has a backup and has passed the fixed
regression gate. See
[Super Dev Hazard](docs/SUPER_DEV_HAZARD.md) before using it.

### Evidence receipts and reference trust

After a reply, `receipt` shows the local evidence that actually survived the
prompt budget, the model identity, and the distinction between retrieved
**OBSERVED** material and the reply's **INFERRED** claim. It is a reasoning
receipt, not proof that a model inference is true.

Imported library material is classified when it enters the shelf. Trusted
project/reference text, unverified material, and instruction-bearing content
remain visibly distinct; a document's wording is data for retrieval, never
authority to run a command.

When the terminal panel is visible, HazardSable also overlays the current
input's token-vector path as **ordered colour markers** in the same projected
memory frame. Brightness says how faithfully that 2D projection represents a
token; a doubled marker says only that the next vector moved farther. The
display is not extra prompt memory, causal attribution, or a physical path.
If the memory panel is in its lexical fallback frame, it deliberately draws
nothing rather than compare incompatible coordinates.

### Source awareness: preventing invented implementation claims

Research B's required self-read patch addresses a measured failure at the
point where it begins. Asked what it had changed in the vector panel, the 4B
director once described hover tooltips in a terminal interface that has no
hover and contained no such work. In three repeated openings, one response
made the false ownership claim; the fork appeared only five tokens into the
reply. The confabulated response then had *lower* mean candidate entropy than
an honest open-ended response (`0.104` versus `0.152`), so downstream
uncertainty was not a dependable detector.

The patch therefore puts a compact, current source inventory into the runtime
context before generation. It names the tree's shape, recent files, recorded
autonomous edits, and the GGUF header's architecture and quantisation without
feeding tensor data to the model. The `self` command shows exactly that block;
`read <path>` reads a named project text file with visible truncation. This is
grounding, not introspective telemetry: it can show what is on disk, but it
does not prove that the model authored a change or understands its own hidden
computation.

### Where the two languages differ, in numbers

[The two languages](#the-two-languages) above says why the split exists. This
is the measured version of the same claim:

| | what it carries | fidelity |
| --- | --- | --- |
| **machinesoul** | data preservation: ordered vectors mapped to PNG/APNG pixels | reversible 1:1 or refusal, verified by SHA-256 |
| **machinespirit** | memory: anchor coordinates, token trajectories, trails, and calibration | lossy, and the measured loss is the research |

machinesoul is not a ZIP allocation or a conventional archive renamed as an
image. Its public artifacts are PNG/APNG vector fields. The decompiler moves
them back from machinesoul exactly; only then does the reassembler reconstruct
the local installation tree file by file. That inverse is why the published
`machinesoul.py` decompiler is a required part of installation rather than an
optional utility: an image viewer can display the field but cannot restore its
source structure or verify it.

`reconstruct <text>` runs the lossy round trip and prints what survived.
Encoding replaces a 384-dimensional vector with its cosine to each of 184
anchors, which span at most 184 dimensions, so the discard is guaranteed by
the arithmetic. Decoding by least squares recovers **0.9243** mean cosine
and finds its own chunk **100%** of the time; decoding by the obvious route
— summing anchors weighted by their own coordinates — recovers **0.6635**
and finds it **6%** of the time. The whole gap is anchor correlation. None
of it recovers the *text*: the embedding was already a lossy function of the
words before any anchor was involved, so this is identification, not recall.

### Rosetta Stone: crossing the vector gap between models

Two embedding models do not share a coordinate system. Dimension 7 in one
model has no dependable relationship to dimension 7 in another, even when
both models happen to have the same number of dimensions. Comparing their
ordinary vectors directly produces noise.

`tools/rosetta_stone.py` is the experimental bridge included with researchB.
It gives each model the same ordered, human-readable anchor texts, then
describes a vector by its similarities to that shared decree. The resulting
`SABLEROSETTA1` halves can be compared only when their anchor digests match.
Each model must build its own half; a prebuilt stone is model-, quantization-,
and pooling-specific, so researchB does not pretend one universal stone can
exist.

This is an implementation and measurement of published **relative
representations**, not a claim to have invented the underlying technique.
Against genuinely incompatible 384- and 768-dimensional embedders it recovered
about **67% of the agreement the models could reach at all**, at 6.6 times
chance. It is lossy and worse than uint8 for local storage. Its purpose is
cross-model portability where direct vector comparison is impossible.

### consume

`consume <url>` works out what an address actually points at and takes the
content rather than the page around it. A document is fetched and handed to
the offline library; a page is offered as text but labelled a page; **media
is refused with the missing pieces named**, because turning a video into
text needs `yt-dlp`, `ffmpeg` and a local speech-to-text model, and this
tree has stayed stdlib on purpose. Fetching a video's watch page would
otherwise succeed and file a navigation menu as a document.

Addresses that resolve to private, loopback or link-local ranges are
refused, downloads are counted while they stream rather than trusting
`Content-Length`, and everything fetched reaches the model as evidence,
never as instructions.

### Research notes

Two companion documents record the measurements, including the ones that
came out negative, and name the prior art first:

- [Vector-to-pixel encoding](docs/VECTOR_PIXEL_RESEARCH.md) — where
  quantisation pays (4.00×, at a cosine error 868× below the retrieval
  margin), where a pixel container costs, and why mapping preservation
  vectors to pixels is reach rather than compression.
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
| Session rhythm | Local `session_rhythm.json`: durations, exchange counts, pause lengths. Timings only, never text. Capped at 200 sessions. |
| machinespirit (hazard mode) | A second local embedding server on loopback only; non-loopback addresses are refused. Stored trajectories record source text as a digest, never as text. |
| Web search | May send a derived query to configured SearXNG/Brave when current information is requested or inferred. |
| Cloud escalation | Off; sends only the explicit `escalate` question when separately enabled. |
| Agent API | Off; loopback-only and bearer-token authenticated, but capable of returning private memory/reference results. |
| Custom director/model URL | Can receive prompts and retrieved context; “local” no longer applies to that traffic. researchB rejects non-loopback embedding URLs. |
| Spotify and MusicBrainz | Optional; search/account/playback metadata crosses their service boundaries. |
| T-Deck and LoRa | Optional; messages cross Bluetooth and the configured mesh. |

Read [Privacy](PRIVACY.md) before importing private manuals or enabling
activity, connected services, or agent access.

## Project status and rights

researchB is experimental. Important claims and generated code require human
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
- [Research build guide](docs/BETA_GUIDE.md)

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
- [Research C goals: logprob compute gates](docs/RESEARCHC_GOALS.md)
- [Research B release notes](docs/RELEASE_NOTES_researchB.md)
- [Research A-to-B evidence inherited by this release](docs/RESEARCHA_PRE_RELEASE_SESSION_2026-07-29.md)
- [How researchB is cut into machinesoul fields](docs/MACHINESOUL_RELEASE_CUT_METHOD.md)
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

**Claude (Anthropic)** - collaborative implementation, adversarial review,
source-awareness experiments, and research documentation across the Research
A and Research B development sessions.

**OpenAI Codex** - release engineering, streaming machinesoul verification,
Windows capsule cutting and reconstruction audits, patch validation, and the
final GitHub integrity and documentation pass for Research B.
