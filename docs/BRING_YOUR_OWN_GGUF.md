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

Model alignment is not an authority control. The deployed Qwen3 4B companion
is already an abliterated Instruct build; that is not a newly introduced
condition when using the desktop profiles. A model's willingness (or
unwillingness) to refuse a request does not grant it file, process, network,
or edit authority. Those boundaries are enforced by the trusted local code:
role dispatch, protected paths and capabilities, previews, backups, fixed
checks, regression tests, and rollback.

## Desktop companion and maintenance roles

`start_assistant.bat` remains the original CPU-compatible launch path for the
included Qwen3 4B companion. That is the Raspberry Pi-compatible path. On the
desktop, `start_desktop_cuda.bat` runs the same deployed abliterated companion
with GPU offload. It is the **director**: conversation, goals and subgoals,
and creating or approving a proposed change plan. It is not the profile that
executes source edits.

`start_desktop_q8.bat` is a separate desktop-only comparison launcher for
`Qwen3-4B-abliterated-bf16_q8_0.gguf`. It has its own server identity and
prompt cache, so it cannot silently reuse the Q5 session. It does not replace
the Q5 default or the Raspberry Pi model.

`start_maintenance_coder.bat` runs the local Qwen2.5-Coder 7B Instruct Q8
GGUF as the **autonomous coder**. It is an explicit, on-demand profile for
bounded self-heals and plan-directed edits. Its launcher deliberately leaves
automatic editing off at startup; a bounded run still has to be deliberately
requested.

For one explicitly requested startup repair attempt, use
`start_autonomous_self_heal.bat`. It starts that same 7B profile with the
one-cycle opt-in enabled; the normal 7B launcher never turns it on by itself.

`start_full_maintenance_coder.bat` is the separate **full-maintenance**
profile. It loads `Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf` on
demand for a full, test-driven repair session. This is intentionally not a
general chat profile and it does not run automatically. A full session is
transactional: it applies only bounded safe edits, validates with the fixed
health and regression checks after each step, and restores its backups if the
repair does not finish green.

Only one profile may run at a time. For a planned edit: start the director,
create and approve the plan, exit it, start the 7B coder, then use
`preview plan` and `confirm edit`. For a full repair: exit the current profile,
start the 14B full-maintenance profile, then request `full self heal`. Separate
server identities and prompt caches prevent one profile from silently reusing
another profile's model process.

No profile may bypass the edit safeguards. The local workflow keeps the diff
preview, syntax/import checks, regression validation, and rollback gates in
place regardless of whether the active model is abliterated, coder-tuned, or
both.

The 7B maintenance launcher expects this local file by default:

```text
models\Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf
```

If you store it elsewhere, set `TORMENT_NEXUS_CODER_MODEL_PATH` to its absolute
path before launching. Do not put model weights in Git or the release archive.

The verified 7B maintenance profile uses 16 GPU layers, a 4K context, flash
attention, and Q8 KV cache. On this desktop it generated about 17.7 tokens per
second while leaving roughly 2.3 GiB VRAM free.

The 14B full-maintenance launcher expects this file by default:

```text
models\Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf
```

If you store it elsewhere, set
`TORMENT_NEXUS_FULL_MAINTENANCE_MODEL_PATH` to its absolute path before
launching. It is a desktop on-demand model, not part of the Raspberry Pi
payload; do not put its weights in Git or the release archive.

The verified desktop profile uses 20 GPU layers, a 4K context, flash
attention, and Q8 KV cache. On the RTX 4060 it generated about 12 tokens per
second while leaving roughly 2.6 GiB VRAM free, which is appropriate for a
deliberate repair session rather than ordinary live conversation. The verified
14B file is 8,988,111,200 bytes with SHA-256
`e89a7ae4e2b456bf33c75cff35664751df20ff273e551d7cf7640aa9e84d3b79`.

## Sharing responsibly

Keep the GGUF zip separate from GitHub and verify the upstream model license
and redistribution terms before sending it. Share a checksum alongside the
archive so the recipient can verify they received the same file. Do not include
conversation history, memory files, API keys, passcodes, Spotify tokens, or
hardware pairing data.
