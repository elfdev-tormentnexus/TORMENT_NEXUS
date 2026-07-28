# The read-only agent interface

A loopback HTTP window into a **running** TORMENT_NEXUS, so an outside agent
can ask it something instead of inferring behaviour from source.

That asymmetry is the reason this exists. Codex and Claude interact with this
project by reading and writing files; they cannot query state during a run or
have it report back, and a whole QC session went on reading source to work out
what the assistant does at runtime.

## What it will not do

There is no endpoint that changes anything. No edit, no goal, no config, no
restart, no shutdown. Every handler is a `GET` that reads, and the handler
class implements no other verb — a `POST` is refused by the HTTP machinery
before any project code runs.

The plan this comes from says anything that writes goes through `dev_auth`.
That remains true and **unbuilt**, deliberately: a write surface deserves its
own review rather than arriving attached to a diagnostic one.

## Turning it on

Off by default. It is a listening socket and an authentication boundary, and
both belong to the operator to switch on.

```bash
set TORMENT_NEXUS_AGENT_API=1
```

Then start TORMENT_NEXUS normally. It prints the port on startup.

| Variable | Default | Meaning |
| --- | --- | --- |
| `TORMENT_NEXUS_AGENT_API` | unset | `1` enables it. Nothing else does. |
| `TORMENT_NEXUS_AGENT_PORT` | `8099` | Must be 1024–65535. |
| `TORMENT_NEXUS_AGENT_TOKEN` | generated | Override the stored token. |

## Authentication

Every request needs a bearer token, **including the read-only ones**.

This project already decided localhost is not a trust boundary: the model API
key exists because llama-server's permissive CORS would otherwise let any web
page open on this computer submit requests to the local model. The same
applies here and more sharply, because `/memory/search` reads the operator's
memories — the files `.gitignore` and `DENY_PATTERNS` work hardest to keep
private.

The token is written to `assistant/.agent_token` with mode `600` on first use.
It is gitignored, deny-listed from release packages, and covered by both the
pattern check and the basename check the packager runs.

The `Host` header is checked as well. The token stops a page that has not read
the token file; the `Host` check stops a DNS-rebinding attempt being treated as
local in the first place.

```bash
curl -H "Authorization: Bearer $(cat assistant/.agent_token)" \
  http://127.0.0.1:8099/state
```

## Routes

| Route | Returns |
| --- | --- |
| `/state` | Model, role, uptime, developer mode, panel visibility, memory count |
| `/health` | `validation_blockers()` and `advisory_warnings()` |
| `/memory/search?q=` | Up to 10 memories `select_relevant()` returns for those terms |
| `/files/editable` | What is editable with a human reviewing, and what is editable unattended |
| `/entropy` | The last 64 per-token entropy values the panel's strip is drawing |

`/memory/search` is worth reading carefully. Retrieval here is literal word
overlap, so asking about "the radio" returns nothing for a memory phrased "the
T-Deck mesh transmitter". **That empty result is the finding, not a
malfunction** — it is the defect the vector panel exists to make visible.

## Auditing

Every call appends a line to `assistant/logs/agent_api.jsonl`: timestamp,
route, outcome, and peer. Rejected requests are logged too, so a wrong token
or a bad `Host` leaves a trace.

An interface that can be queried without leaving one is an interface nobody
can audit afterwards, which is the property that made unattended edits
acceptable in the first place.

## Where the surface is decided

The route table is built by `_agent_providers()` in `assistant/main.py`, not
in `core/agent_interface.py`. The socket module imports no project state and
serves whatever it is handed, so what a connected agent can see is one
reviewable list in one file. A regression test pins that list, so adding a
route has to be deliberate.

`core/agent_interface.py` is on `DENIED_FILES`. An unreviewed edit could widen
the bind address off loopback or weaken the token comparison, and both look
small in a diff nobody reads.
