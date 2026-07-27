# TORMENT_NEXUS architecture

TORMENT_NEXUS is a local-first Python application built around a local
language-model server. The project separates conversational behavior from
tool boundaries so that useful features do not silently become unrestricted
machine control.

## Runtime layout

```text
start_assistant.bat
        |
assistant/main.py
  |       |        |        |
  UI    model     voice   command routing
        server             |
                         guarded tools
```

| Area | Responsibility |
| --- | --- |
| `assistant/main.py` | Session lifecycle, streaming replies, activity state, and mode changes. |
| `assistant/core/` | Configuration, persona, model-server ownership, authentication, tutorial, and health checks. |
| `assistant/ui/` | Animated terminal, input handling, voice state, and music visualizer controls. |
| `assistant/voice/` | Offline speech synthesis, optional recognition, and playback cancellation. |
| `assistant/commands/` | Explicit commands and natural-language routing. |
| `assistant/editing/` | Reviewable edit plans, protected paths, autonomous-cycle limits, and document-only goals. |
| `assistant/memory/` | Local conversation history and durable-fact extraction. |
| `assistant/web/` | Optional SearXNG-backed research with untrusted-result handling. |
| `assistant/hardware/` | Optional T-Deck and Meshtastic bridge. |

## Trust boundaries

The model can propose text and plans. It does not receive unrestricted file,
network, hardware, or process access merely because it produced convincing
language.

- Developer mode is time-limited and protected by a local passcode verifier.
- Self-editing uses plans, review, backups, and a protected-file denylist.
- The autonomous cycle is bounded; it cannot edit the guardrail modules or
  execute arbitrary commands. An explicit, in-memory developer-mode toggle
  can batch up to three of the same guarded edits while an operator watches;
  it clears when developer mode ends and is never the unattended default. A
  completed three-edit batch receives only one short-lived bonus credit, and
  only after a fixed post-restart health and regression validation; failure
  restores the recorded batch backups instead.
- The goal engine can only write small text, Markdown, JSON, or CSV artifacts
  inside `workshop/`.
- Web and radio content are treated as untrusted data.
- T-Deck terminal input is conversation-only and cannot invoke tools.

## Local and optional components

The model, memory, UI, and speech pipeline run locally once provisioned. Web
search, Spotify controls, and hardware bridges are optional integrations.
Their availability is reported by `health check` rather than assumed.

## Deployment targets

The current packaged handoff targets 64-bit Windows. Raspberry Pi 5 is a
supported design target but needs a separate ARM64 llama.cpp build and local
runtime provisioning.
