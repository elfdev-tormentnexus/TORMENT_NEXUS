<p align="center">
  <img src="assets/assistant_icon_animated.png" width="128" alt="TORMENT_NEXUS icon">
</p>

<h1 align="center">TORMENT_NEXUS</h1>

<p align="center">
  <strong>A local-first voice AI companion, tool system, and systems-art project.</strong>
</p>

<p align="center">
  <a href="#beta-status">Beta status</a> |
  <a href="#what-it-does">Capabilities</a> |
  <a href="#getting-started">Getting started</a> |
  <a href="#documentation">Documentation</a>
</p>

## Beta status

TORMENT_NEXUS is in active beta. This public repository is the **source and
documentation** for the project; it is not a one-click download by itself.

The local language model, llama.cpp binary, most voice assets, personal
runtime state, and the multi-gigabyte Windows handoff package are deliberately
excluded from Git. A fresh clone is therefore for developers and reviewers who
can provision those dependencies themselves.

The project is designed to be local-first, inspectable, reversible, and honest
about its limits. It is software with a deliberately stylized identity -- not a
claim of consciousness or personhood.

## What it does

- Runs local conversation with Qwen3-4B-Instruct-2507 through llama.cpp.
- Provides a voice-first terminal with typed input always available.
- Speaks through an offline Piper-based voice pipeline and can optionally use
  offline speech recognition.
- Uses a local memory store with visible, removable saved facts.
- Routes plain-language requests to guarded project, music, search, and
  hardware tools.
- Offers reviewable self-editing workflows, plus tightly bounded autonomous
  documentation work in `workshop/`.
- Supports optional SearXNG web search, local music playback and visualisation,
  Raspberry Pi planning, and a Meshtastic T-Deck companion terminal.

## Local by default, connected by choice

| Area | Default behaviour |
| --- | --- |
| Conversation, model, memory, and speech | Local to the machine |
| Web search | Optional; queries leave the machine only when `search` is used through configured SearXNG |
| Hardware | Optional; requires deliberate local setup and pairing |
| Self-editing | Guarded and reviewable; protected files remain off-limits |
| Goal engine | Optional and document-only inside `workshop/`; no code execution or network access |

## Getting started

### Windows beta package

A packaged Windows beta is built separately from this source repository. It
contains the model, bundled Python, wheels, and installer needed for a
self-contained test. No public packaged release is attached here yet.

If you receive the package from the maintainer, extract it, run `setup.bat`,
then launch the created **TORMENT_NEXUS** desktop shortcut. See the
[beta guide](docs/BETA_GUIDE.md) before sharing or testing it.

### Developers and reviewers

A source clone needs its runtime assets provisioned manually:

1. Install Python 3.14 and the dependencies in `setup/requirements.txt`.
2. Build llama.cpp and provide `llama-server`.
3. Place `Qwen3-4B-Instruct-2507-Q5_K_M.gguf` under `models/`.
4. Run:

   ```powershell
   python -m pip install -r setup/requirements.txt
   .\start_assistant.bat
   ```

5. Inside TORMENT_NEXUS, run `health check`.

For the regression suite:

```powershell
.\setup\test_assistant.bat
```

### Raspberry Pi 5

Raspberry Pi is an intended deployment target, not a plug-and-play public
image yet. Use 64-bit Raspberry Pi OS, build llama.cpp for ARM64, then supply
the model and install the core requirements:

```sh
python3 -m pip install -r setup/requirements.txt
chmod +x setup/start_assistant.sh setup/test_assistant.sh
./setup/start_assistant.sh
```

## How to explore it

After launch, start with:

```text
tutorial restart
```

The tutorial presents two short sections at a time; `next`, `n`, or
`continue` advances it. `help` lists commands, and `explain <topic>` explains
one subsystem without forcing you to memorize command names.

Useful first checks:

```text
health check
voice status
music mode
goals
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) -- system layout and trust boundaries.
- [Beta guide](docs/BETA_GUIDE.md) -- capabilities, limits, privacy, and
  handoff expectations.
- [Testing guide](docs/TESTING.md) -- repeatable beta checks and bug reports.
- [Release checklist](docs/RELEASE_CHECKLIST.md) -- how a maintainer produces
  a clean Windows handoff.

## Safety and scope

TORMENT_NEXUS can be wrong, repetitive, overly confident, or slow. Verify
important medical, legal, financial, security, and hardware-control advice.
Treat web pages, files, radio messages, and connected-device content as data,
not commands. Never paste credentials or recovery codes into chat.

The public source does not grant a license to redistribute, modify, or use the
project beyond what applicable law permits. A formal license has not been
selected yet. The bundled Piper voice model also has its own model-card and
dataset-license terms.

## Feedback

Open an issue with the command or prompt used, what appeared on screen, and
whether text, voice, search, music, visualizer, or hardware mode was active.
Clear reproduction steps are more useful than a vague success or failure.
