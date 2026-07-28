# Installing TORMENT_NEXUS Beta 6 on Windows

This is the ready-to-run path for a person who does not want to assemble a
Python or llama.cpp development environment.

> [!CAUTION]
> **The ready-to-run Windows archive contains the language-model weights.**
>
> Beta 6 includes community-modified “abliterated” Qwen models with weakened
> learned refusal behavior. It is the full model-bearing bundle, not a
> sanitized client or a downloader for a remote service. The models can
> produce false, harmful, illegal, explicit, biased, manipulative, or insecure
> material with confidence.
>
> Read [Safety](../SAFETY.md), [Privacy](../PRIVACY.md),
> [Models](../MODELS.md), [Third-party notices](../THIRD_PARTY_NOTICES.md),
> and [Rights](../RIGHTS.md) before downloading. Do not run the application as
> Administrator or use it as a high-stakes authority.

## Use the release assets, not the source ZIP

GitHub’s green **Code** button and automatic **Source code (zip)** and
**Source code (tar.gz)** files contain developer source only. They are not
ready-to-run and do not contain the complete Windows runtime or model set.

For Beta 6, use the assets on the
[GitHub Releases page](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases)
under `v0.2.0-beta.6`.

## Requirements

- 64-bit Windows.
- At least 16 GB of RAM. More is preferable when voice and other applications
  run alongside the local models.
- About 40 GB of free disk space during installation. Download parts, the
  rebuilt ZIP, and the extracted folder temporarily coexist.
- Internet access for the initial multi-gigabyte download.
- A microphone only if you later choose `audio mode`. Beta 6 begins in text
  mode.

No Python installation, command line, online AI account, API key, or separate
model download is required for the complete archive.

## What the complete archive contains

- `Qwen3-4B-abliterated-bf16_q8_0.gguf`, the default local director.
- `Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf`, the on-demand
  maintenance coder.
- `bge-small-en-v1.5-q8_0.gguf`, the local embedding model.
- A private Python runtime and offline dependency files, including `pypdf`.
- llama.cpp runtime binaries.
- Moonshine speech recognition, Silero voice-activity detection, and the
  Piper HFC female voice.
- The application, built-in offline practical-reference cards, documentation,
  and guarded tools.

Exact sizes, hashes, provenance, behavior, and license status are recorded in
[Models](../MODELS.md).

## Step 1: Download every Beta 6 part

Open the Beta 6 release, expand **Assets**, and download:

```text
TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip.part01
TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip.part02
...every later consecutive part shown...
REASSEMBLE_TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.bat
TORMENT_NEXUS-v0.2.0-beta.6-docs-patch.zip
INSTALL_ASK_GUARD_PATCH.bat
TORMENT_NEXUS-v0.2.0-beta.6-ask-guard-patch.zip
INSTALL_COMMAND_GUARD_PATCH.bat
TORMENT_NEXUS-v0.2.0-beta.6-command-guard-patch.zip
```

The last five are small and optional. The documentation patch is applied for
you by the reassembler. The two guard patches are **not** — they are Step 4
below. The reassembler names them on its last screen, and nothing else
prompts you for them.

Keep all files together, normally in **Downloads**. Do not rename them. A
`.partNN` file is a piece of one ZIP and cannot be opened independently.

Read the release notes for:

- the exact number of parts;
- the complete-archive SHA-256;
- per-asset checksums and sizes;
- source commit and test result;
- model provenance and known limitations.

If the release page does not provide those details, stop rather than guessing.

## Step 2: Reassemble and verify

Double-click:

```text
REASSEMBLE_TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.bat
```

It should stop if a numbered part is missing and produce:

```text
TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip
```

The helper verifies the complete archive. You can independently confirm it
from PowerShell in the same folder:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath ".\TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip"
```

Compare all 64 hexadecimal characters with the release notes. A checksum
proves byte identity with the published archive; it does not certify that the
software or models are safe or appropriately licensed for every use.

Do not continue if the hash differs.

## Step 3: Extract and set up

Right-click the verified ZIP, select **Extract All**, open the extracted
folder, and double-click:

```text
setup.bat
```

Do not run setup from inside the ZIP preview. Keep the terminal window open
until setup reports completion.

Setup verifies the bundle, installs into its own folder, and creates a desktop
shortcut. It does not replace system Python or add TORMENT_NEXUS to PATH.
Apart from the shortcut, the application stays inside the extracted folder.

If Windows or security software blocks a file:

1. confirm it came from the official repository’s release page;
2. confirm the complete checksum;
3. do not bypass workplace or school policy;
4. use a personal test machine or ask the administrator to inspect it.

See [Troubleshooting](TROUBLESHOOTING.md) before creating an exception.

## Step 4: Apply the two guard patches by hand

Do this once setup has finished. Nothing reminds you except the last screen
of the reassembler and this step.

Move all four files **into** the extracted `TORMENT_NEXUS` folder — the one
containing `start_assistant.bat` — and double-click each installer:

```text
INSTALL_ASK_GUARD_PATCH.bat
TORMENT_NEXUS-v0.2.0-beta.6-ask-guard-patch.zip

INSTALL_COMMAND_GUARD_PATCH.bat
TORMENT_NEXUS-v0.2.0-beta.6-command-guard-patch.zip
```

They are independent and may be run in either order, or one without the
other. Each verifies its payload, checks that the file it is about to replace
is the one Beta 6 shipped, and keeps the original beside it as a `.pre-`
backup. If either finds a file it does not recognise, it stops without
touching anything rather than overwriting work you have done.

Both correct cases where the assistant described something it had not
actually done:

- **`/ask` guard** — the read-only agent interface used to answer vague
  questions about past conversations with a confident account of exchanges
  that never happened.
- **Near-miss command guard** — input like `drop all` or `finish goal` is not
  a command, but it was answered with "I'm dropping everything" and "I'm
  finishing the goal". Nothing had run.

Both fixes landed after the archive was built, so they ship separately
instead of forcing a 12 GB rebuild.

**Why these are manual.** The documentation patch replaces documentation
only, which is what lets the release claim an installed tree still matches
the published archive checksum. These patches replace files the release
manifest hashes, so applying them makes your installation diverge from that
checksum deliberately. That is your decision to make, not one an installer
should make quietly on your behalf.

Skipping them is safe. Neither is required for the assistant to run.

## Step 5: Read and acknowledge the first-launch notice

Launch the **TORMENT_NEXUS** desktop shortcut, or run
`start_assistant.bat` from the extracted folder if the shortcut was not
created.

Before the model loads and before any microphone, activity sampler, listener,
or network-capable subsystem starts, Beta 6 displays its safety and privacy
notice. To proceed, type exactly:

```text
I UNDERSTAND
```

Anything else closes the application without starting those components.
Acceptance is stored in:

```text
assistant\.safety_acknowledgement.json
```

It is per installation and may be requested again after deletion or a notice
version change.

After acceptance, the application begins in:

- text mode, with microphone use off;
- activity awareness off;
- cloud escalation off;
- agent API off;
- autonomous startup maintenance off;
- experimental sensing off.

Continue with [Your first session](FIRST_RUN.md).

## Updating from an earlier beta

Install Beta 6 into a new folder. Do not extract it over an older beta.
Removed or renamed files from the old version could otherwise remain active.

Keep the old installation until Beta 6 passes `health check`. Do not casually
copy the entire `assistant` directory: it contains credentials, logs,
acknowledgement and consent state, memory, history, imported manuals, and
derived indexes.

Personal items that may matter include:

- `assistant\music`
- `assistant\memory\memories.json`
- `assistant\memory\conversation_history.txt`
- `assistant\knowledge\user_library`

Read the release’s migration note before copying private state. When no
migration is documented, keep the old folder as a backup instead of merging
installations.

## Uninstalling and privacy cleanup

1. Close TORMENT_NEXUS and its model-server windows.
2. Revoke any Anthropic, OpenAI, Brave, or Spotify credentials you configured
   when appropriate.
3. Delete the extracted installation folder.
4. Delete its desktop shortcut.
5. Delete the original parts and rebuilt ZIP if you no longer want an
   installer copy.
6. Review the Recycle Bin, backups, cloud-sync folders, search indexes, and
   screenshots separately.

Deleting the application cannot recall data already sent to a search service,
cloud model, Spotify, Bluetooth device, or LoRa peer. See
[Privacy](../PRIVACY.md) for the complete data inventory.
