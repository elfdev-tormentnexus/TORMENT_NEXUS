# Experimental local agent interface

TORMENT_NEXUS can expose a small, read-only HTTP interface so a development
tool such as Codex can inspect a running session. It is experimental, off by
default, and intended for one trusted operator on the same computer.

It is not a general automation API. There are no edit, command, restart,
shutdown, goal, or configuration routes. “Read-only” describes route
authority: each call appends bounded audit metadata, and startup may prepare
or migrate a local search index before the listener opens.

## Safety and privacy boundary

Even a read-only route can reveal private memories, imported-document
excerpts, runtime state, or model output. The interface therefore:

- binds only to `127.0.0.1`, never every network interface;
- requires a bearer token on every request;
- rejects non-local `Host` headers;
- accepts only HTTP `GET`;
- sends `Cache-Control: no-store` and `Pragma: no-cache` on every response;
- records route, time, outcome, and peer metadata in
  `assistant\logs\agent_api.jsonl`;
- gives the human operator priority over `/ask`.

Loopback is not protection from another process running as the same Windows
user. Keep the token private, do not expose the port through a proxy or
tunnel, and do not paste authenticated URLs into logs or screenshots.

## Enable it

Close TORMENT_NEXUS, open PowerShell in the installation folder, and launch
with:

```powershell
$env:TORMENT_NEXUS_AGENT_API = "1"
.\start_assistant.bat
```

The default address is:

```text
http://127.0.0.1:8099
```

The application creates `assistant\.agent_token` on first use. You may use
`TORMENT_NEXUS_AGENT_TOKEN` to supply a different session token and
`TORMENT_NEXUS_AGENT_PORT` to choose a loopback port from 1024 through 65535.
Environment variables affect only processes launched from that environment.

Delete `.agent_token` while the application is stopped to rotate the
file-based token. Do not commit, publish, or share it.

## Make a request

This PowerShell example avoids putting the bearer token directly in the
command:

```powershell
$token = (Get-Content .\assistant\.agent_token -Raw).Trim()
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Headers $headers `
  -Uri "http://127.0.0.1:8099/health"
```

Search endpoints accept a URL query parameter named `q`:

```powershell
$query = [uri]::EscapeDataString("where is the mesh radio")
Invoke-RestMethod -Headers $headers `
  -Uri "http://127.0.0.1:8099/memory/search?q=$query"
```

Queries are limited to 400 characters. URLs can be retained in shell history,
proxy logs, and debugging tools, so do not place passwords or API keys in
them.

## Routes

| Route | What it returns |
| --- | --- |
| `/health` | Current validation blockers and advisory warnings. |
| `/state` | A bounded runtime snapshot, including offline-library and shadow-librarian status but no endpoint, key, query, or excerpt. |
| `/entropy` | Up to 64 recent director-token entropy observations used by the visual panel. |
| `/files/editable` | Human-reviewed and unattended file allowlists; it does not edit them. |
| `/memory/search?q=...` | Explicit personal-memory candidates. |
| `/knowledge/search?q=...` | Explicit offline-library candidates and source metadata. |
| `/ask?q=...` | One short, stateless question to the local director. |

An empty search or question explains the required parameter. Unknown routes
return the current route list.

### `/memory/search`

When the embedder is ready, this explicit search ranks memory candidates by
cosine similarity without adding recency or confidence to the score. The
response identifies the retrieval mode as `hybrid`. If embeddings are
unavailable, it falls back to `word-overlap`.

This endpoint is deliberately wider than automatic chat recall. Returned
strings are candidates, not verified facts.

### `/knowledge/search`

This searches the independent offline manual library. A result includes its
title, heading, excerpt, source URL when available, review metadata, staleness
flag, `current_conditions` limitation, similarity, and retrieval label. A
semantic-only result is possible only where current target vectors exist and
is marked as a candidate rather than silently inserted as fact. Persistent
library-vector population starts off and is controlled locally through the
developer-only library commands, not through this read interface.

Imported documents and their extracted text are private. An authenticated
caller can receive excerpts, so review [Privacy](../PRIVACY.md) before
enabling this route.

### `/ask`

`/ask` uses the same local director as the human session, so only one caller
can hold the model slot. It:

- sees the stable persona and core memory;
- does **not** see the operator's live chat or recent conversation history;
- does not append its exchange to conversation history;
- does not extract a durable memory;
- is limited to 128 generated tokens;
- returns `busy` if startup context, the operator, or another agent request
  is using the director;
- is cancelled if the operator starts a turn while it is generating.

This is a bounded way to ask the running project a diagnostic question, not
a bridge between two unrestricted agents. A client should use a slow,
finite retry policy and stop when the operator takes priority.

## What authentication does not provide

- The token is an application secret, not Windows account isolation.
- The interface is not encrypted; it is intended only for loopback.
- A compromised same-user process may read the token file.
- A model answer remains untrusted content.
- Read-only results can still be sensitive.
- The audit log does not record query or response content, but it has no
  documented automatic retention period.

Leave the feature disabled when it is not needed. Report a route that writes,
binds beyond loopback, bypasses authentication, or exposes unintended data
through [Security](../SECURITY.md).

## Related documentation

- [Semantic retrieval and agent bridges](SEMANTIC_AND_AGENT_BRIDGES.md)
- [Offline knowledge](OFFLINE_KNOWLEDGE.md)
- [Architecture](ARCHITECTURE.md)
- [Privacy](../PRIVACY.md)
- [Safety](../SAFETY.md)
