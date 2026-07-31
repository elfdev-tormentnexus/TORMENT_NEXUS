# Your first TORMENT_NEXUS researchC session

This guide assumes you installed the complete Windows archive. You do not need
to memorize commands; `help` shows the current command list.

## 1. The acknowledgement comes before the model

On the first launch, TORMENT_NEXUS prints a safety and privacy disclosure
before loading the model or preparing the microphone.

Read it. Type exactly:

```text
I UNDERSTAND
```

Anything else closes the application without starting the model, microphone,
activity sampler, agent listener, or other network-capable subsystem.

The acknowledgement is not a claim that the software is safe for every use.
It confirms that you saw the model, authority, privacy, high-stakes, and
personification limits. Review [Safety](../SAFETY.md) and
[Privacy](../PRIVACY.md) whenever you enable an advanced feature.

## 2. researchC starts quiet

A fresh researchC installation starts with:

- text mode on;
- microphone listening and spoken replies off;
- foreground-window activity awareness off;
- cloud escalation off;
- local agent API off;
- autonomous startup editing off;
- experimental sensing off.

Local conversation, memory, clock context, the offline practical-reference
library, and the bundled embedding model remain available.

The model load can take several seconds. The first generated answer can be
slower than later answers because files and prompt caches are still warming.

## 3. Start with status and the tutorial

Type:

```text
health check
library status
tutorial
```

`health check` separates required blockers from optional warnings.
`library status` reports built-in and imported offline references.
`tutorial` shows two topics at a time; use `next`, `n`, or `continue`, and
restart it later with `tutorial restart`.

Useful commands:

```text
help
explain <topic>
show memories
memory count
library sources
library search <words>
```

## 4. Conversation and the abliterated model

The default local director is a community-modified abliterated Qwen3 model.
It may answer requests other assistants reject and can be confidently wrong
or unsafe. Voice, memory, a name, and a stylized personality do not make it
conscious or authoritative.

For important information:

- ask what source or local manual supported the answer;
- distinguish an offline reference from a current fact-check;
- verify changing or high-stakes facts with an authoritative source;
- review generated code before running it;
- never type credentials or irreplaceable private material.

See [Models](../MODELS.md) and
[Capabilities and limits](CAPABILITIES_AND_LIMITS.md).

## 5. Use the offline reference library

researchC ships with a small set of practical preparedness cards. Try:

```text
library sources
library search power outage
library search carbon monoxide alarm
```

Ordinary conversation can automatically receive a short offline excerpt only
when the question shares meaningful words with an indexed passage.
Embeddings may rerank those lexical matches but cannot add an unrelated
manual automatically.

An explicit `library search` is wider. It may label an item
`semantic-candidate`; that means the vector was similar, not that the passage
is correct or applicable.

To add personal manuals, encyclopedias, repair guides, or notes, read
[Offline knowledge](OFFLINE_KNOWLEDGE.md). Imports require developer mode
because the command copies files into the private library.

## 6. Understand memory and history

Selected durable facts and a bounded recent transcript are stored inside the
installation:

```text
show memories
memory count
forget <words from the memory>
```

Exact words and identifiers are strongest. Automatic semantic memory rescue
is deliberately conservative and adds no more than one zero-overlap memory
when the best match is both strong and clearly ahead of the runner-up.
Greetings and acknowledgements retrieve nothing.

Older conversation recall is narrower: it runs only when you clearly ask
about an earlier conversation, returns at most one confident exchange, and
otherwise stays silent. The current live chat remains separate from the
external `/ask` agent endpoint.

Memory, history, and their derived embedding cache are local files, not
encrypted storage. See [Privacy](../PRIVACY.md).

## 7. Opt in to voice only if wanted

researchC does not initialize the microphone on a fresh start.

```text
audio mode        enable offline spoken replies and microphone listening
text mode         return to typed, silent operation
voice status      inspect speech and device readiness
```

You can type while audio mode is active. Press **Escape** to cancel listening
or speech.

Speech recognition and synthesis run locally in the complete archive. A
microphone is optional; text mode remains the simplest privacy boundary.

## 8. Opt in to activity awareness only if wanted

Activity awareness can sample:

- the foreground application and complete window title;
- how long the keyboard and mouse have been idle;
- CPU and memory load;
- battery level and whether the computer is on battery;
- timestamps.

Window titles can reveal filenames, URLs, pages, and message previews.

```text
activity           show status or observations
activity on        enable sampling and retain the choice
activity off       stop sampling, retain the off choice, and delete the log
activity forget    delete observations without changing whether sampling is on
```

When enabled, changes are stored in
`assistant\memory\activity_log.jsonl` for up to 14 days by default.
`activity off` clears both in-memory observations and that file.

Activity samples are observations, not consciousness. The model must not
describe them as watching you.

## 9. Add local music

Copy your own MP3, WAV, FLAC, or OGG files into:

```text
assistant\music
```

Then use:

```text
music library
play <part of the filename>
repeat music
repeat music off
repeat music on
```

Starting a local song opens the ten-scene visualizer. In music mode:

| Key | Action |
| --- | --- |
| Left / Right | Change scene |
| Space | Play the next local song |
| `[` / `]` | Change local-song volume |
| Ctrl+B | Leave music mode |

Space controls local music, not Spotify or browser audio.

## 10. Read long answers

Long answers use a page view:

| Key | Action |
| --- | --- |
| Space, Enter, or Down | Next page |
| Up or Backspace | Previous page |
| Escape or Q | Close the page view |

## 11. Connected and advanced features remain choices

- Current-information search can use a configured SearXNG or Brave backend.
- `spotify search` sends a query to MusicBrainz and opens Spotify.
- `escalate` sends exactly its question to a configured cloud provider, but
  only after escalation is separately enabled.
- The experimental agent API is loopback-only, token authenticated, and off.
- Developer and self-maintenance modes can change project files under
  application guardrails; those rules are not an OS sandbox.
- T-Deck, Meshtastic, radar, and Wi-Fi experiments require separate hardware,
  consent, and documentation.

See [Capabilities and limits](CAPABILITIES_AND_LIMITS.md) before enabling
them.

## 12. End the session

Close the application normally after speech, music, and advanced work have
stopped. The next launch can use saved timestamps and explicitly retained
state. It was not thinking, watching, or waiting while closed.

If behavior differs from this guide, use
[Troubleshooting](TROUBLESHOOTING.md). Do not put conversations, memories,
manuals, activity logs, keys, tokens, pairing information, or private paths
in a public report.
