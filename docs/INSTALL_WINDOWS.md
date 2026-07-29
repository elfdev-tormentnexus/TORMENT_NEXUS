# Installing TORMENT_NEXUS researchA on Windows

This is the ready-to-run path for a person who does not want to assemble a
llama.cpp development environment.

> [!CAUTION]
> **The researchA capsules carry the complete model-bearing Windows package.**
>
> It includes community-modified “abliterated” Qwen models with weakened
> learned refusal behavior. The models can produce false, harmful, illegal,
> explicit, biased, manipulative, or insecure material with confidence.
>
> Read [Safety](../SAFETY.md), [Privacy](../PRIVACY.md),
> [Models](../MODELS.md), [Third-party notices](../THIRD_PARTY_NOTICES.md),
> and [Rights](../RIGHTS.md) before downloading. Do not run the application as
> Administrator or use it as a high-stakes authority.

## Why researchA arrives as images

researchA deliberately puts machinesoul in the installation path. The large
package is split below GitHub's per-asset ceiling, and every numbered part is
carried as pixels in a lossless PNG capsule:

```text
TORMENT_NEXUS-researchA-windows-x64.zip.part01.png
TORMENT_NEXUS-researchA-windows-x64.zip.part02.png
...every later consecutive part shown...
```

These are not screenshots or decorative previews. The pixels are the payload.
`machinesoul.py` reads them in raster order, verifies the embedded SHA-256,
and writes the exact `.zip.partNN` bytes. A capsule either verifies or refuses;
it never presents a partial output as complete.

This is not encryption, a compression advantage, or a way around GitHub's
size limit. It is a byte-exact container that makes the project's decompiler
part of accessing the research build.

**Do not screenshot, crop, optimise, resize, or re-encode a capsule.** Download
each GitHub asset as a file. A social preview or image editor can change the
pixels and destroy the bytes they carry.

## Requirements

- 64-bit Windows.
- At least 16 GB of RAM.
- About 55 GB of free disk space while the PNG capsules, decoded parts,
  reassembled ZIP, and extracted folder coexist.
- Internet access for the initial multi-gigabyte download.
- A standard Python 3 installation for the published machinesoul decompiler.
- A microphone only if you later choose `audio mode`; researchA begins in
  text mode.

The decoded package contains its own private Python runtime for TORMENT_NEXUS.
The separately installed Python is only the bootstrap needed to run
`machinesoul.py` before that private runtime is accessible.

## Step 1: Download the researchA assets

Open the
[GitHub Releases page](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases),
select the release titled `researchA`, expand **Assets**, and download:

```text
machinesoul.py
DECOMPILE_SABLE_researchA.bat
SABLE_researchA_support.png
SABLE_researchA_research.png
TORMENT_NEXUS-researchA-windows-x64.zip.part01.png
TORMENT_NEXUS-researchA-windows-x64.zip.part02.png
...every later consecutive .partNN.png...
```

`machinesoul.py` and its one-click batch launcher are the unavoidable
plaintext bootstrap: without the decompiler nothing can open the first
capsule. Every other researchA download is itself carried through machinesoul.
The support capsule contains the checksum ledger and exact reassembler. The
research capsule contains the Rosetta Stone bridge, anchor material, tests,
and primary research documents. Neither support image is an installer part.

For the optional 14B full-maintenance companion, also download every
consecutive:

```text
TORMENT_NEXUS-researchA-full-maintenance-14b.part01.png
TORMENT_NEXUS-researchA-full-maintenance-14b.part02.png
...every later consecutive .partNN.png...
```

Those extra capsules are only for deliberately requested long self-heal and
extended editing sessions. They are current researchA companion assets, not
old Beta 6 clutter. Allow roughly 27 GB more temporary disk space while the
14B capsules, decoded parts, and final 8.4 GB model coexist.

Keep every file in one empty folder and do not rename it. GitHub's green
**Code** button and automatic **Source code (zip)** files are developer source
snapshots; they do not contain the models or complete Windows runtime.

## Step 2: Verify and decompile the capsules

Double-click:

```text
DECOMPILE_SABLE_researchA.bat
```

The helper uses the Python launcher (`py -3`) when available and falls back to
`python`. It first decompiles the support and research capsules, then calls the
published `machinesoul.py` once for every consecutive package capsule. For
each numbered image it writes the same filename without the final `.png`:

```text
TORMENT_NEXUS-researchA-windows-x64.zip.part01
TORMENT_NEXUS-researchA-windows-x64.zip.part02
...
```

Every part is SHA-256 verified by the capsule before it is kept. If a file is
missing, damaged, renamed, or re-encoded, the helper stops. Do not continue by
guessing or by using a partial output.

The recovered `SHA256SUMS_researchA.txt` records both layers:

- the SHA-256 of every downloaded PNG capsule and helper;
- the SHA-256 of every decoded `.zip.partNN` payload;
- the SHA-256 of the final ZIP.

If the optional 14B capsules are present, the same pass recovers their exact
numbered parts and checksum-gated installer. Install that companion only after
the main TORMENT_NEXUS folder has been extracted.

## Step 3: Reassemble and verify

Double-click the reassembler recovered from the support capsule:

```text
REASSEMBLE_TORMENT_NEXUS-researchA-windows-x64.bat
```

The generated helper knows the exact part count from this build. It refuses a
missing part, joins them in numerical order, and verifies:

```text
TORMENT_NEXUS-researchA-windows-x64.zip
```

You can independently compare the result with the release ledger:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath ".\TORMENT_NEXUS-researchA-windows-x64.zip"
```

A matching hash proves byte identity with the published archive. It does not
certify that the software, generated output, or model licensing is safe.

## Step 4: Extract and set up

Right-click the verified ZIP, select **Extract All**, open the extracted
`TORMENT_NEXUS` folder, and double-click:

```text
setup.bat
```

Do not run setup from inside the ZIP preview. Setup verifies the bundle,
prepares the private runtime, and creates a desktop shortcut. It does not
replace system Python or add TORMENT_NEXUS to PATH.

The ask guard, near-miss command guard, interface mode, machinespirit work,
and documentation corrections are already inside researchA. Do not apply the
separate Beta 6 patch assets to this package.

## Step 5: Read the first-launch notice

Launch the desktop shortcut or run `start_assistant.bat` from the extracted
folder.

Before the model loads and before any microphone, activity sampler, listener,
or network-capable subsystem starts, researchA displays its safety and privacy
notice. To proceed, type exactly:

```text
I UNDERSTAND
```

Anything else closes the application without starting those components. A
fresh installation begins with text mode on and microphone, activity
awareness, cloud escalation, agent API, autonomous startup maintenance, and
experimental sensing off.

## Updating and uninstalling

Install a later research build into a new folder rather than extracting it
over researchA. Keep the old folder until the new build passes
`health check`. Do not casually copy the whole `assistant` directory because
it can contain private memory, history, credentials, acknowledgements,
consent state, imported documents, indexes, logs, and music.

To uninstall:

1. Close TORMENT_NEXUS and its model-server windows.
2. Delete the extracted installation folder and desktop shortcut.
3. Delete the downloaded capsules, decoded parts, and rebuilt ZIP if you do
   not want to retain an installer.
4. Review the Recycle Bin, backups, cloud-sync folders, search indexes, and
   screenshots separately.

See [Troubleshooting](TROUBLESHOOTING.md) for refusal messages, missing parts,
or setup failures.
