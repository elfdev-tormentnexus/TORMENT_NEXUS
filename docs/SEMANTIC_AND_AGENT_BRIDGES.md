# Semantic retrieval and agent bridges

Beta 6 adds local embeddings without turning every vaguely similar passage
into prompt context. It also adds two narrow ways to consult another model:
an inbound loopback interface and an explicit outbound escalation command.

These systems share model infrastructure but do not share authority.

## Three separate retrieval systems

The word "vectors" also appears in the visual panel. That panel displays
token-probability/entropy information and is not a semantic vector database.

### Personal memory

Durable personal memories live in `assistant\memory\memories.json`. Exact
terms and identifiers remain primary evidence. During ordinary conversation:

- greetings and acknowledgements do not trigger semantic retrieval;
- lexical matches can be returned normally;
- at most one zero-word-overlap semantic memory may be added;
- that candidate needs cosine similarity of at least `0.55`;
- it must also beat the runner-up by at least `0.06`;
- otherwise the correct result is no semantic memory.

Explicit memory search is exploratory. When embeddings are available it ranks
candidates by pure cosine similarity rather than silently combining recency
or confidence. Results are leads, not newly verified memories.

### Conversation history

Recent history is stored separately from durable memory. Semantic history
recall runs only when the operator clearly asks about an earlier
conversation. It returns at most one exchange and requires:

- cosine similarity of at least `0.60`; and
- a margin of at least `0.06` over the runner-up.

Long exchanges retain their beginning and end around a visible clipping
marker. Only caller-specified live exchanges are excluded during the current
run; after restart, the newest persisted exchanges are eligible like other
history.

### Offline knowledge

Manuals and practical reference cards have their own source store, SQLite
full-text index, and vector table. They never enter the personal-memory
collection.

Automatic chat context first requires a real SQLite FTS word match.
Embeddings may rerank those lexical hits but cannot create an automatic
semantic-only hit. Explicit `library search` and authenticated
`/knowledge/search` may widen the search and label semantic-only results
`semantic-candidate`.

This keeps a large encyclopedia from being vector-scanned on every turn and
reduces accidental injection of merely similar text. See
[Offline knowledge](OFFLINE_KNOWLEDGE.md).

## Embedding service

The full Windows archive includes a small BGE GGUF embedding model and runs
its service on loopback, normally `127.0.0.1:8082`. The normal thresholds
were measured for this project configuration.

The implementation uses mean pooling as an explicit project evaluation
choice. Upstream BGE examples commonly use CLS pooling, so the project does
not claim that mean pooling is the model's native convention. Changing the
model, quantization, runtime, pooling, prefixing, or normalization invalidates
the measured score distribution and requires recalibration with related,
ambiguous, greeting, and unrelated examples.

If the embedding service is unavailable, ordinary lexical memory and
full-text library behavior continue. Semantic absence should degrade to
"no semantic result," not block the assistant.

## machinespirit: the path before pooling

The embedding service above returns one vector per text — a mean over that
text's token vectors. The mean says what a passage is about. It cannot say
*where* in the passage a meaning appeared, because averaging is exactly what
destroys position.

machinespirit keeps the sequence. `assistant/core/machinespirit.py` reads
per-token vectors and profiles each position against a fixed dictionary of
concept phrases in `assistant/core/anchors_v1.json`, so `trace <text>`
reports which concept sat at which token. `SABLE7` is the container that
stores such a path; machinespirit is the representation it carries.

**It needs a second embedding server.** llama.cpp fixes pooling when the
process starts, so a trajectory cannot come from the pooled instance the
rest of this document describes. Hazard mode starts a second copy of the
same small model with `--pooling none`. When it is absent, every entry point
reports unavailable rather than falling back to the pooled server — a single
point returned where a path was requested would be wrong in a way nothing
downstream could detect.

**It does not participate in retrieval.** Late interaction over trajectories
retrieved the same documents as ordinary pooled cosine, and anchor-space
coordinates scored 0.689 against uint8 absolute's 1.000. The three retrieval
systems above are unchanged by it. What it adds is a readout, not a ranking.

Measurements, including the negative ones, are in
[Cross-model translation and token trajectories](VECTOR_TRANSLATION_RESEARCH.md).

## Caches and privacy

Persistent numeric vectors cache private memory and history text identities
for speed. Knowledge vectors stay in the knowledge database so a manual shelf
cannot evict personal-memory vectors. Query vectors use a bounded in-memory
least-recently-used cache and are not serialized.

A vector is not human-readable prose, but it is derived from private text and
should still be treated as private data. When clearing memories or history,
also clear the embedding cache while the application is stopped. When
removing imported manuals, use `library remove`; it synchronously drops the
live source/index rows and attempts database compaction. Backups, snapshots,
and storage-device remnants still need separate handling.

The embedder is local-only: Beta 6 rejects a non-loopback
`TORMENT_NEXUS_EMBED_SERVER_URL`. A separately configured remote director
server can still receive retrieved memory or reference context as part of a
model prompt, so the local-first privacy claim does not apply to that
director traffic.

## Inbound bridge: local agent interface

Set `TORMENT_NEXUS_AGENT_API=1` to expose a token-authenticated, GET-only
service at `127.0.0.1:8099`.

Its search routes inspect private memory or knowledge candidates. `/ask`
gives a connected development agent a short answer from the local director,
using stable persona/core memory but not the operator's live chat. It does
not add history or extract memory and yields to the human operator.

It has no write or command endpoints. See
[Agent interface](AGENT_INTERFACE.md).

## Outbound bridge: explicit escalation

```text
escalate claude <question>
escalate openai <question>
```

Escalation remains off until both conditions are satisfied:

1. `TORMENT_NEXUS_ESCALATION=1` is set; and
2. the selected provider key is supplied through its private key file or
   environment variable.

The command sends exactly the question after the command. It does not
intentionally attach conversation history, memories, persona, or the local
system prompt. The provider receives the text under its own billing,
retention, safety, and account terms.

Each call records metadata such as provider, model, sizes, time, and outcome
in `assistant\logs\escalation.jsonl`, not the question or answer content.
Remote answers remain untrusted input.

## Design rules

- Exact evidence outranks semantic resemblance.
- Ambiguity returns nothing automatically.
- Automatic context is narrower than explicit search.
- Personal memory, history, knowledge, and panel telemetry stay separate.
- The human session outranks an agent request.
- Local and remote boundaries are stated at the point of use.
- Thresholds are measurements tied to a specific stack, not universal facts.
- Neither an embedding score nor another model's answer establishes truth.

See [Architecture](ARCHITECTURE.md), [Testing](TESTING.md),
[Privacy](../PRIVACY.md), and [Safety](../SAFETY.md).
