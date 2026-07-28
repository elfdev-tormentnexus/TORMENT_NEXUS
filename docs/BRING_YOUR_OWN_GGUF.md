# Bring your own GGUF

> [!NOTE]
> This is an advanced developer guide. It is not required for the ready-to-run
> Windows beta, which already includes its model and runtime.

This repository is source code, not a model host. You can provide a compatible
local GGUF separately, including in a private zip shared with an authorized
tester. Do not add model weights, personal runtime state, credentials, or
device pairings to the repository.

A **GGUF** is the file that contains a local language model. **llama.cpp** is
the local program that loads that file and provides responses to the Python
application.

## Before the first launch

The model cannot install itself before it is running. On a source checkout,
the developer or tester must first provide:

1. Python 3.14 and `setup/requirements.txt`.
2. A compatible `llama-server` build from llama.cpp.
3. One local GGUF file.

The simplest option is to place the GGUF at:

```text
models/Qwen3-4B-Instruct-2507-Q5_K_M.gguf
```

For a differently named model, set its absolute path before launching. On
Windows:

```bat
set "TORMENT_NEXUS_MODEL_PATH=C:\models\your-model.gguf"
start_assistant.bat
```

Run `health check` after the first prompt appears. If the model or llama.cpp
is missing, the launcher reports the expected path instead of pretending the
assistant is running.

For the complete ready-to-run user path instead, see
[Installing on Windows](INSTALL_WINDOWS.md).

## What changes with a different model

The Python application, local tool boundaries, backups, test suite, and
developer-mode restrictions stay the same. A different model changes the text
generation layer: tone, reliability, tool suggestions, and willingness to
follow instructions may differ. It does not add operating-system access or
make the project self-installing.

The local assistant can explain commands and propose guarded source edits after
it has launched. It cannot modify protected startup, authorization, test, or
guardrail modules through its autonomous edit system.

## Sharing responsibly

Keep the GGUF zip separate from GitHub and verify the upstream model license
and redistribution terms before sending it. Share a checksum alongside the
archive so the recipient can verify they received the same file. Do not include
conversation history, memory files, API keys, passcodes, Spotify tokens, or
hardware pairing data.
