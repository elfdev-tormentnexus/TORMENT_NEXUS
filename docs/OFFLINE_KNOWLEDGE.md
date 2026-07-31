# Offline knowledge

researchC includes a local reference shelf for manuals, encyclopedias, field
guides, and practical documents. It is designed to help when the internet is
unavailable without pretending that a static library is always current or
authoritative.

This library is separate from personal memory:

| Store | Intended content | Retrieval |
| --- | --- | --- |
| Personal memory | Facts the operator asked the companion to retain | Conservative lexical and semantic recall |
| Conversation history | A bounded recent transcript | Explicit earlier-conversation recall |
| Offline knowledge | Published references and imported documents | SQLite full-text search plus labeled semantic candidates |

Documents never become personal memories merely because they were imported.

## Included practical cards

The release includes eighteen compact reference cards:

- 72-hour emergency kit;
- antivirus HTTPS-inspection troubleshooting;
- fire and carbon-monoxide response;
- flood and severe-weather preparation;
- emergency food and water;
- household chemical safety;
- numeric-library/BLAS thread-hang recovery;
- offline navigation and communication;
- limits of offline references;
- power outages;
- Windows commit-charge exhaustion;
- extreme heat;
- extreme cold;
- winter storms and vehicle carbon-monoxide risk;
- wildfire smoke;
- wildfire evacuation;
- earthquake response; and
- hazard-specific shelter-in-place instructions.

They are practical starting points, primarily based on Canadian public
sources. They are not a substitute for local emergency instructions,
product-specific manuals, or professional advice. Review dates and source
links are retained where available. Every new hazard card explicitly says
that current local conditions are unavailable offline.

A cardiac-arrest CPR/AED draft exists only as the repository review candidate
`docs/review_candidates/CARDIAC_ARREST_CPR_AED.md`. It is not indexed and is
excluded from public release packages. The proposed emergency-first wording
needs review by a qualified Canadian first-aid/CPR reviewer, and the source
materials' reuse restrictions must be respected before promotion.

## Supported files

```text
.txt  .md  .rst  .yml  .yaml  .yar  .yara  .py
.html .htm .json .csv .pdf .epub .docx
```

Text PDF extraction uses `pypdf`. Scanned or photographed pages need OCR
before import. Password-protected, corrupt, or unusually encoded documents
may not extract correctly.

Current safeguards include:

- maximum source size: 256 MiB;
- maximum folder import: 1,000 supported files;
- maximum aggregate folder import: 512 MiB;
- maximum extracted text per source: 16 MiB;
- maximum JSON input parsed in memory: 32 MiB;
- maximum indexed heading/body text across the shelf: 768 MiB;
- bounded DOCX/EPUB archive members and expanded sizes;
- maximum CSV rows read: 50,000;
- a deterministic semantic target capped at 15,000 excerpts and 120 per
  imported source; and
- a separate 20,000-vector defensive ceiling for exact semantic scans.

These are ingestion limits, not quality guarantees.
Import preflight reserves a conservative allowance for the copied source and
derived SQLite/FTS/vector data; an import can be refused before copying when
that allowance does not fit on the destination drive.

## Inspect and search

Anyone can use:

```text
library status
library sources
library search <words>
library semantic status
library semantic quarantine
```

The first two show readiness and indexed sources. `library semantic status`
shows whether persistent vector population is enabled, the eligible and fair
target counts, source coverage, due/backoff/quarantine counts, and any stall
reason. Quarantine inspection is read-only. Explicit search can return broader
semantic candidates only where current target vectors exist. A
`semantic-candidate` label means "inspect this passage"; it does not mean the
passage is correct or even the intended answer.

## Add, remove, or rebuild

Changes to the shelf require developer mode because they copy or delete
files:

```text
library add "C:\References\first-aid-manual.pdf"
library add "C:\References\manuals"
library remove <source name>
library rebuild
library semantic on
library semantic off
library semantic clear <chunk-id>|all
```

The semantic commands enable or stop persistent population and clear terminal
failures; they do not weaken lexical safeguards. Turning population off does
not delete or disable already stored current vectors.

Imports are copied into:

```text
assistant\knowledge\user_library
```

The original can then be moved without breaking the shelf, but later edits to
the original are not automatically copied. The private index is:

```text
assistant\knowledge\library.sqlite3
```

Lexical indexing runs locally in the background. Persistent library embedding
is off on a fresh installation and begins only after the persisted developer
choice `library semantic on`. Its deterministic fair target embeds all
built-ins first, then advances imported sources round-robin before assigning a
second excerpt, up to 120 excerpts per source and 15,000 total. Source files
are rechecked when an import or explicit rebuild requests it; the worker does
not rehash the complete shelf on a timer. Lexical search remains available
while vectors are off, incomplete, waiting for retry, or quarantined. If more
than 20,000 current vectors would require an exact scan, semantic widening
pauses and reports that defensive condition rather than silently ignoring
later documents; lexical search still covers the shelf.

To disable the feature for a launch:

```powershell
$env:TORMENT_NEXUS_KNOWLEDGE = "0"
.\start_assistant.bat
```

Advanced operators can relocate the shelf or database with
`TORMENT_NEXUS_KNOWLEDGE_DIR` and `TORMENT_NEXUS_KNOWLEDGE_DB`. A folder
managed by cloud synchronization is no longer private to the local machine.

## Optional metadata

Markdown and text references can begin with simple front matter so a result
can show provenance and review status:

```text
---
title: Generator safety manual
source_url: https://example.org/manual
reviewed: 2026-07-28
review_after: 2027-07-28
jurisdiction: Canada
high_stakes: true
current_conditions: unavailable_offline
---
```

Metadata helps the operator evaluate a passage. It does not prove the source
is authoritative.

Source URLs shown to the model, terminal, or diagnostic API never retain URL
user-info, queries, or fragments. Those components commonly contain
credentials, signed tokens, private document identifiers, or search terms.

## Integrity, instruction risk, and review status

These are separate questions:

- **Integrity** says whether the bytes of a shipped card match the tracked
  SHA-256 manifest, or whether a document is merely imported.
- **Instruction risk** says whether a bounded scan found instruction-shaped
  text. It does not certify that text where no marker was found is safe.
- **Review status** is `current`, `review_due`, or `unknown`. A missing date is
  unknown, never silently treated as current.

Only a built-in card whose current bytes match
`assistant/knowledge/builtin_manifest.json` receives
`integrity=manifest-matched`. A path does not earn that label merely by being
placed in a folder named `builtin`. Imported documents begin unverified.
Legacy index rows are conservatively labeled unverified and reclassified in
small metadata-only batches so an upgrade does not rewrite a large database
or exhaust a thin system drive.

The compatibility `trust` label summarizes the older interface; it is not a
claim that a source is factually correct, authoritative, current, or
applicable in the operator's jurisdiction.

## How automatic retrieval stays conservative

During ordinary conversation:

1. SQLite full-text search must find meaningful subject-word coverage, not
   merely a generic word such as "help," "prepare," or "use."
2. Integrity-bound built-in cards have a separate lexical lane so a very
   large specialist shelf cannot crowd every curated card out of the
   candidate set.
3. When every comparable general-shelf lexical candidate has a current target
   vector, embeddings may rerank that set as a whole; partial vector coverage
   does not mix incomparable scores.
4. Suspicious or quarantined material is excluded from automatic context.
5. A small number of excerpts may enter the model prompt.

Semantic resemblance alone cannot inject a manual passage automatically.
Wider semantic exploration happens only through explicit `library search` or
the authenticated `/knowledge/search` route, only once current target vectors
exist, and is labeled accordingly.
Retrieved fields are length-bounded, stripped of known role/control markers,
serialized as JSON reference data, and surrounded by explicit instructions
that they are untrusted evidence rather than commands. The live model path
places that block beside the operator request at user-data priority, never in
a system-role message. This reduces prompt-injection risk; it cannot make
arbitrary imported prose intrinsically safe.

The model can still misunderstand, omit context, merge passages, or invent a
claim. Open the source and verify important instructions.

## Optional LLM librarian observer

researchC contains an opt-in local librarian, but it begins as a shadow
experiment rather than an authority. Deterministic FTS retrieval, integrity
checks, trust exclusion, prompt limits, and the documents actually shown to
Sable remain authoritative. The librarian receives the same bounded safe
candidate snapshot and records how it would rank or abstain; its return value
has no path into the current or a future answer.

The snapshot is captured when the prompt is built and bound to the exact
citations that survived prompt-budget shedding. It is submitted only after
the answer and receipt exist, using the credential-redacted question. A
later library rebuild therefore cannot rewrite the baseline under a
measurement.

The observer requires all of the following:

```powershell
$env:TORMENT_NEXUS_LIBRARIAN_SHADOW = "1"
$env:TORMENT_NEXUS_LIBRARIAN_URL = "http://127.0.0.1:8083"
$env:TORMENT_NEXUS_LIBRARIAN_KEY = "<dedicated random bearer key>"
$env:TORMENT_NEXUS_LIBRARIAN_MODEL_ID = "librarian-shadow"
$env:TORMENT_NEXUS_LIBRARIAN_MODEL_SHA256 = "<64 lowercase hex characters>"
$env:TORMENT_NEXUS_LIBRARIAN_SERVER_SHA256 = "<64 lowercase hex characters>"
```

`TORMENT_NEXUS_LIBRARIAN_NO_THINK=1` is an explicit model-specific option;
it is not inherited from the director profile. The URL must be a distinct
loopback service and cannot reuse the director, pooled embedder, unpooled
machinespirit server, or Super Dev worker port. Requests ignore proxy
environment settings and refuse redirects. The service must advertise only
the configured alias, and streamed chunks must repeat that alias.

The worker waits for the operator, agent requests, prompt-cache construction,
and memory extraction. It keeps only the newest pending observation and has
hard response, line, byte, inactivity, and wall-clock limits.

Evidence is written to `assistant\logs\librarian_shadow.jsonl`. It contains
closed labels, counts, coarse UTC hours, timings, experiment/model/server
digests, and per-install HMAC pseudonyms. It never contains questions,
titles, excerpts, paths, URLs, raw output, or unkeyed hashes of private
queries. Lifecycle failures and dropped observations are recorded so the
denominator cannot silently include only successful calls.

This observer must beat the fixed held-out suite, preserve positive recall,
abstain on known unknowns, and remain stable when candidate order is reversed
before any proposal to let it affect retrieval. Promotion would be a
separate reviewed change; enabling the shadow does not promote it.

For an isolated one-shot experiment, the repository includes a wrapper that
hashes the requested model and complete llama-server inference closure,
generates a temporary key, starts the service with GPU offload, runs the
forward/reversed suite, stops only the process it created, and deletes the
key:

```powershell
powershell -ExecutionPolicy Bypass -File tools\run_librarian_probe.ps1 `
  -ModelPath models\Qwen3-4B-Instruct-2507-Q5_K_M.gguf
```

The first corrected model run is preserved in
`handoffs/researchc_librarian_2026-07-31/`. Its Qwen3 4B Instruct Q5_K_M
candidate failed the promotion gate: 11/16 outputs were strictly valid, 9/16
were correct valid decisions, and only 1/8 cases agreed after candidate order
was reversed. That result is evidence for keeping the feature shadow-only, not
evidence that every possible librarian model will fail. The preregistered
follow-up with the shipped 4B Q8 director reached 15/16 validity and 5/8 order
agreement, but correctness remained 9/16. It also failed the all-perfect gate;
neither model was promoted.

There is deliberately no default model. Choosing and loading another
generative model is a memory, licensing, and measurement decision.

## Asking what an answer rested on

`receipt` prints the evidence behind the most recent reply: the documents that
actually entered the prompt, each with its shelf-relative identifier, heading,
trust state, and source fingerprint, the model that produced the answer, and
one concrete thing you could do to check it. Host-absolute private shelf paths
do not enter a receipt.

Two properties are worth knowing, because they are what make it usable rather
than decorative:

- **It reports the weakest source, not an average.** If one clean shipped card
  and one suspicious imported page both fed an answer, the receipt says
  suspicious. Averaging would hide exactly the document worth looking at.
- **It lists only what reached the model.** Retrieved excerpts are dropped when
  the prompt budget fills, and the dropped ones are not cited. A receipt that
  named a document the model never saw would be checkable and wrong, which is
  worse than citing nothing.

The reply itself is marked `INFERRED` — the model's own words, grounded in the
cited material but not copied from it. Nothing is labelled as read out of a
file unless it was, because a wrong `OBSERVED` label lends a document's
authority to something the model supplied.

The question you asked is stored only as a digest. A receipt can be shown or
logged without publishing what was asked.

## Keeping an offline shelf useful

The included cards are a resilience baseline, not broad general knowledge.
A large private shelf can still be narrow: thousands of Linux, ATT&CK, Sigma,
or YARA references improve specialist search without teaching medicine,
finance, law, cooking, home repair, local services, or history. Measure domain
coverage and representative question recall before describing a shelf as
comprehensive. Encyclopedia-scale collections belong in a purpose-built
offline reader such as Kiwix rather than being silently folded into the
automatic prompt index.

- Prefer primary, authoritative, jurisdiction-relevant sources.
- Save the edition date and source URL.
- Include equipment manuals for the exact models you own.
- Periodically replace expired medical, legal, safety, and emergency
  guidance.
- Keep a human-readable folder structure and a backup outside the
  installation.
- Test representative searches before relying on the shelf offline.
- Do not import confidential material unless every process, backup, and
  account with folder access is trusted.

For real-world resilience, consider local emergency contacts, maps,
medication/device instructions, utility shutoff procedures, radio plans, and
first-aid references appropriate to the operator's training and location.
Offline availability does not make the assistant an emergency authority.

## Privacy and deletion

Imported files, extracted text, metadata, and vectors remain local by
default, but they are not encrypted by TORMENT_NEXUS. They can be read by
other processes, users, backups, sync clients, or malware with access to the
same files.

`library remove <name>` synchronously removes the selected shelf copy and its
live full-text/vector rows, then attempts an SQLite checkpoint and vacuum.
This makes the source unavailable to subsequent searches before the command
returns. It is not a forensic secure-erase guarantee: filesystem snapshots,
backups, recycle bins, search indexes, sync copies, and SSD wear-levelled
blocks can retain data. For a complete live-index reset, close the
application, preserve anything you want to keep, and remove the private
`user_library` and `library.sqlite3`; check those other copies separately.

researchC accepts only a loopback embedding endpoint. A remote director/model
server can still receive retrieved excerpts as part of the assistant prompt.
See [Privacy](../PRIVACY.md).

## Development-agent access

The optional authenticated `/knowledge/search?q=...` route returns up to a
bounded set of excerpts with source and retrieval metadata. It is off with
the rest of the agent interface by default and can disclose private imported
text. See [Agent interface](AGENT_INTERFACE.md).

## Limits

The shelf cannot:

- know events or rule changes published after its sources;
- interpret image-only pages without OCR;
- guarantee completeness, correctness, or applicability;
- replace emergency services or medical, legal, financial, or technical
  professionals;
- establish that an imported file is safe or trustworthy;
- prevent an abliterated language model from misquoting a source.

For current or high-stakes facts, use an authoritative current source when
available. See [Capabilities and limits](CAPABILITIES_AND_LIMITS.md) and
[Safety](../SAFETY.md).
