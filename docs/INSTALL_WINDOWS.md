# Installing TORMENT_NEXUS on Windows

This guide is for someone who wants to **use** TORMENT_NEXUS. It does not
require coding, Python, a command line, an online account, or a separate AI
model.

> [!WARNING]
> Do not install from GitHub's green **Code** button, **Download ZIP**, or the
> automatic **Source code (zip)** and **Source code (tar.gz)** files. Those
> downloads contain developer source code only. They do not contain the AI
> model or self-contained Windows runtime.

## What you need

- A 64-bit Windows computer.
- About 10 GB of free space while installing. The final folder is about 3 GB,
  but the downloaded parts, rebuilt ZIP, and extracted folder temporarily
  exist together.
- At least 8 GB of memory. 16 GB is more comfortable when voice is enabled.
- Internet access for the initial multi-gigabyte download.
- A microphone only if you want to speak to the assistant. Typing works
  without one.

The packaged beta contains Python, the language model, the local model server,
voice files, and offline installation files.

## Step 1: Open the correct release

Open the
[TORMENT_NEXUS v0.1.0-beta.3 release](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases/tag/v0.1.0-beta.3).

Scroll to **Assets** and click the small arrow if the file list is collapsed.

## Step 2: Download all four files

Download these exact files:

1. `TORMENT_NEXUS.zip.part01`
2. `TORMENT_NEXUS.zip.part02`
3. `TORMENT_NEXUS_v0.1.0-beta.3_MUSIC_VISUALIZER_PATCH.zip`
4. `INSTALL_TORMENT_NEXUS_BETA3_WITH_MUSIC_PATCH.bat`

Keep all four in the same folder, normally **Downloads**. Do not rename them.
The two large files are pieces of one ZIP archive; neither piece can be opened
by itself. The small patch contains the latest music visualizer repair.

Ignore the automatically generated **Source code** downloads at the bottom of
the release.

## Step 3: Run the patched installer

Double-click `INSTALL_TORMENT_NEXUS_BETA3_WITH_MUSIC_PATCH.bat`.

The helper performs the otherwise confusing parts for you:

- joins the two original archive parts;
- checks the published Beta 3 SHA-256 fingerprint;
- stops safely if a download is missing or damaged;
- extracts the self-contained app into
  `TORMENT_NEXUS_BETA3_PATCHED\TORMENT_NEXUS`;
- verifies and applies the music visualizer repair;
- backs up every repaired file; and
- starts the normal offline setup.

Setup verifies the bundled files and creates a **TORMENT_NEXUS** desktop
shortcut. It normally takes a few minutes and does not need internet access.
Leave the window open until it reports that setup is complete.

The installer does not change the system Python installation, PATH, or
registry. Apart from the desktop shortcut, the application remains inside the
extracted folder.

If Windows or security software blocks the helper or installer, first confirm
that it came from the official release page and that the checksum matches.
Do not bypass workplace or school security policy. See
[Troubleshooting](TROUBLESHOOTING.md) for safe next steps.

## Step 4: Launch it

Double-click the **TORMENT_NEXUS** desktop shortcut.

If the shortcut was not created, open the extracted folder and double-click
`start_assistant.bat` instead. Do not move that file away from the rest of the
folder.

The model loads into memory when the first message is sent, so the first answer
can be slower than later answers. When the input prompt appears, type:

```text
tutorial
```

Continue with [Your first session](FIRST_RUN.md).

## Repairing an existing Beta 3 installation

If Beta 3 is already installed, you do not need to download the two large
parts again.

1. Close TORMENT_NEXUS.
2. Download
   `TORMENT_NEXUS_v0.1.0-beta.3_MUSIC_VISUALIZER_PATCH.zip` from the release.
3. Right-click the patch ZIP, choose **Extract All**, and open the extracted
   folder.
4. Double-click `APPLY_MUSIC_VISUALIZER_PATCH.bat`.
5. If asked, choose the installed TORMENT_NEXUS folder containing
   `start_assistant.bat`.

The repair only accepts the original Beta 3 files or files already repaired
by this exact patch. It stops rather than overwriting an unfamiliar or
personally edited version. Before changing anything, it saves the original
files under:

```text
backups\music_visualizer_patch_beta3_<date_and_time>
```

To undo the repair, open the newest folder with that name and double-click
`RESTORE_ORIGINAL_FILES.bat`.

## Manual archive route

`REASSEMBLE_TORMENT_NEXUS.bat` is still included for people who want to handle
the original archive manually. Put it beside both `.part` files and run it to
create `TORMENT_NEXUS.zip`.

The original Beta 3 ZIP must have this SHA-256 fingerprint:

```text
AA6C748831331528C01E94F1E06A4288D1FC40C66D51FBC240EEE3609BB7ED00
```

After verifying and extracting it, apply the music visualizer patch using the
existing-install steps above, then run `setup.bat`. Do not run setup directly
from inside the compressed ZIP.

## Installing a newer beta later

Do not extract a new beta directly over an old installation. Use a new folder
so that removed or renamed files from the old version cannot remain mixed into
the new one.

Keep the old folder until the new beta launches successfully. Your local songs
are in `assistant\music`, and your local conversation state is under
`assistant\memory`. Treat conversation and memory files as private. Do not
upload them to GitHub or include them in a bug report.

Release-specific notes should say whether personal state can be copied safely
between versions. If they do not, keep the old folder as a backup rather than
guessing.

## Uninstalling

1. Close TORMENT_NEXUS.
2. Delete the extracted TORMENT_NEXUS folder.
3. Delete the **TORMENT_NEXUS** desktop shortcut.

This removes the packaged application. Delete the original download parts and
rebuilt ZIP separately if you no longer want to keep an installer copy.
