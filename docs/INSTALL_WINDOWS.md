# Installing TORMENT_NEXUS researchB on Windows

This is the ready-to-run path for a person who does not want to assemble a
llama.cpp development environment.

> [!CAUTION]
> **The researchB capsules carry the complete model-bearing Windows package.**
>
> It includes community-modified “abliterated” Qwen models with weakened
> learned refusal behavior. The models can produce false, harmful, illegal,
> explicit, biased, manipulative, or insecure material with confidence.
>
> Read [Safety](../SAFETY.md), [Privacy](../PRIVACY.md),
> [Models](../MODELS.md), [Third-party notices](../THIRD_PARTY_NOTICES.md),
> and [Rights](../RIGHTS.md) before downloading. Do not run the application as
> Administrator or use it as a high-stakes authority.

## Why researchB arrives as images

researchB deliberately puts machinesoul in the installation path. The large
package is split below GitHub's per-asset ceiling, and every numbered part is
carried as an ordered vector field in a lossless PNG/APNG capsule:

```text
SABLERESEARCHB-WINDOWS.part01.png
...every consecutive field...
SABLERESEARCHB-WINDOWS.partNN.png
```

These are not screenshots or decorative previews. The ordered pixel vectors
are the preservation language. `machinesoul.py` reads them in raster order,
verifies the embedded SHA-256, and writes the exact internal `.msv` segment.
A capsule either verifies or refuses; it never presents a partial output as
complete.

This is not encryption, a compression advantage, a ZIP allocation with an
image suffix, or a way around GitHub's size limit. machinesoul is Sable's
data-preservation logic language: ordered vectors map to pixels, and the
inverse is 1:1 or refuses. The reassembler restores each reviewed source file
directly; it does not create a ZIP or tar layer.

**Do not screenshot, crop, optimise, resize, or re-encode a capsule.** Download
each GitHub asset as a file. A social preview or image editor can change the
ordered pixel vectors and break the inverse.

## Requirements

- 64-bit Windows.
- At least 16 GB of RAM.
- About 55 GB of free disk space while the downloaded capsules, decoded
  vector segments, and directly reconstructed installation coexist.
- Internet access for the initial multi-gigabyte download.
- A standard Python 3 installation for the published machinesoul decompiler.
- A microphone only if you later choose `audio mode`; researchB begins in
  text mode.

The decoded package contains its own private Python runtime for TORMENT_NEXUS.
The separately installed Python is only the bootstrap needed to run
`machinesoul.py` before that private runtime is accessible.

## Step 1: Download the researchB assets

Open the
[GitHub Releases page](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases),
select the release titled `researchB`, expand **Assets**, and download:

```text
FETCH_SABLERESEARCHB.bat
machinesoul.py
DECOMPILE_SABLE_researchB.bat
SABLERESEARCHB-MANIFEST.png
SABLERESEARCHB-REASSEMBLER.png
SABLERESEARCHB-WINDOWS.part01.png
...every consecutive field...
SABLERESEARCHB-WINDOWS.partNN.png
```

`FETCH_SABLERESEARCHB.bat` is the small, readable download helper. Double-click
it to fetch every required asset, resume interrupted transfers, and verify
each file against the SHA-256 recorded at the cut. It deliberately does **not**
download the optional 14B companion. Interrupted bytes remain in a visibly
named `.partial` file so the next run can resume them; that temporary name is
promoted to the real asset name only after SHA-256 verification. If you use
it, wait for its verification message and continue at Step 2. If you download
manually, take every other file in the list.

**How many parts there are is decided by the cut, not by this page.** Take the
count from the Assets list. A missing part is refused rather than skipped, so
an incomplete download cannot quietly produce a broken install.

`machinesoul.py` and the one-click batch launcher are the unavoidable
plaintext bootstrap: without the decompiler nothing can open the first
capsule. The install, manifest, and reassembler payloads are carried
through machinesoul. The cut-map APNGs are optional visual review records.
Rosetta Stone, anchor material, tests, and the primary research documents live
in the directly preserved install tree rather than in a ZIP, tar, or separate
research encoder.

researchA published a separate calibration-clarity patch as three extra
assets. researchB has none: that correction is built into the tree this
release is cut from, so there is nothing to download and nothing to apply
afterwards.

For the optional 14B full-maintenance companion, also download every
consecutive:

```text
SABLERESEARCHB-14B.part01.png
...every consecutive field...
SABLERESEARCHB-14B.partNN.png
```

Those extra capsules are only for deliberately requested long self-heal and
extended editing sessions. They are current researchB companion assets, not
old Beta 6 clutter. The 55 GB temporary-space estimate above includes the
14B reconstruction path; the installed companion adds about 8.4 GB.

Keep every file in one empty folder and do not rename it. GitHub's green
**Code** button and automatic **Source code (zip)** files are developer source
snapshots; they do not contain the models or complete Windows runtime.

## Step 2: Run the one-step decompiler and installer

Double-click:

```text
DECOMPILE_SABLE_researchB.bat
```

This is the only installation action after downloading. The helper uses the
standard `python` command to bootstrap machinesoul. It:

1. decompiles the encoded combined manifest and verified reassembler;
2. moves every required Windows vector field back from machinesoul;
3. invokes the recovered reassembler and verifies every reconstructed file;
4. creates the install directory directly, without a ZIP or tar layer;
5. installs the optional 14B companion when its complete field set is present;
   and
6. runs `setup.bat`.

The internal vector segments appear only during that local process:

```text
SABLERESEARCHB-WINDOWS.part01.msv
SABLERESEARCHB-WINDOWS.part02.msv
...
```

Every part is SHA-256 verified by the capsule before it is kept. If a file is
missing, damaged, renamed, or re-encoded, the helper stops. Do not continue by
guessing or by using a partial output.

The recovered machinesoul release manifests record both payload layers:

- the size and SHA-256 of every required data-field PNG;
- the SHA-256 of every decoded `.msv` vector segment;
- the size and SHA-256 of every reconstructed file.

GitHub's release-asset digest and the post-upload audit cover the plaintext
bootstrap and the encoded manifest/reassembler images themselves; a manifest
cannot safely contain its own final digest.

If every optional 14B capsule is present, the same pass recovers and installs
its exact model. If none are present, it skips that companion. A partial set
refuses rather than silently installing an incomplete model.

## What the one-step process verifies

The recovered reassembler knows every approved cut, source path, file offset,
and digest. It refuses a missing capsule, an altered vector segment, a gap or
overlap, an unsafe path, or a final file whose SHA-256 differs from the staged
source. A complete verified tree proves exact reconstruction of the locally
staged source. It does not certify that the software, generated output, or
model licensing is safe.

## After setup

The one-step helper has already extracted the package and run:

```text
setup.bat
```

Setup verifies the bundle, prepares the private runtime, and creates a desktop
shortcut. It does not replace system Python or add TORMENT_NEXUS to PATH.

The ask guard, near-miss command guard, interface mode, machinespirit work,
and documentation corrections are already inside researchB. Do not apply the
separate Beta 6 patch assets to this package.

## Read the first-launch notice

Launch the desktop shortcut or run `start_assistant.bat` from the extracted
folder.

Before the model loads and before any microphone, activity sampler, listener,
or network-capable subsystem starts, researchB displays its safety and privacy
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
over researchB. Keep the old folder until the new build passes
`health check`. Do not casually copy the whole `assistant` directory because
it can contain private memory, history, credentials, acknowledgements,
consent state, imported documents, indexes, logs, and music.

To uninstall:

1. Close TORMENT_NEXUS and its model-server windows.
2. Delete the extracted installation folder and desktop shortcut.
3. Delete the downloaded capsules and decoded vector segments if you do not
   want to retain an installer.
4. Review the Recycle Bin, backups, cloud-sync folders, search indexes, and
   screenshots separately.

See [Troubleshooting](TROUBLESHOOTING.md) for refusal messages, missing parts,
or setup failures.
