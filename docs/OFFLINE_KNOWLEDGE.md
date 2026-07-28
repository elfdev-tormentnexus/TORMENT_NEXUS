# Offline knowledge

Beta 6 includes a local reference shelf for manuals, encyclopedias, field
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

The release includes eight compact reference cards:

- 72-hour emergency kit;
- fire and carbon-monoxide response;
- flood and severe-weather preparation;
- emergency food and water;
- household chemical safety;
- offline navigation and communication;
- limits of offline references;
- power outages.

They are practical starting points, primarily based on Canadian public
sources. They are not a substitute for local emergency instructions,
product-specific manuals, or professional advice. Review dates and source
links are retained where available.

## Supported files

```text
.txt  .md  .rst  .html  .htm  .json  .csv  .pdf  .epub  .docx
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
- bounded chunks and a 20,000-vector exact semantic-scan limit.

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
```

The first two show readiness and indexed sources. Explicit search can return
lexical and broader semantic candidates. A `semantic-candidate` label means
"inspect this passage"; it does not mean the passage is correct or even the
intended answer.

## Add, remove, or rebuild

Changes to the shelf require developer mode because they copy or delete
files:

```text
library add "C:\References\first-aid-manual.pdf"
library add "C:\References\manuals"
library remove <source name>
library rebuild
```

Imports are copied into:

```text
assistant\knowledge\user_library
```

The original can then be moved without breaking the shelf, but later edits to
the original are not automatically copied. The private index is:

```text
assistant\knowledge\library.sqlite3
```

Indexing and embedding run locally in the background. Source files are
rechecked when an import or explicit rebuild requests it; the worker does not
rehash the complete shelf on a timer. Lexical search remains available while
vectors are incomplete. If more than 20,000 current vectors would require an
exact scan, semantic widening pauses and reports that condition rather than
silently ignoring later documents; lexical search still covers the shelf.

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
---
```

Metadata helps the operator evaluate a passage. It does not prove the source
is authoritative.

## How automatic retrieval stays conservative

During ordinary conversation:

1. SQLite full-text search must find meaningful subject-word coverage, not
   merely a generic word such as "help," "prepare," or "use."
2. Embeddings may rerank only those lexical matches.
3. A small number of excerpts may enter the model prompt.

Semantic resemblance alone cannot inject a manual passage automatically.
Wider semantic exploration happens only through explicit `library search` or
the authenticated `/knowledge/search` route and is labeled accordingly.
Retrieved fields are length-bounded, stripped of known role/control markers,
serialized as JSON reference data, and surrounded by explicit instructions
that they are untrusted evidence rather than commands. The live model path
places that block beside the operator request at user-data priority, never in
a system-role message. This reduces prompt-injection risk; it cannot make
arbitrary imported prose intrinsically safe.

The model can still misunderstand, omit context, merge passages, or invent a
claim. Open the source and verify important instructions.

## Keeping an offline shelf useful

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

Beta 6 accepts only a loopback embedding endpoint. A remote director/model
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
