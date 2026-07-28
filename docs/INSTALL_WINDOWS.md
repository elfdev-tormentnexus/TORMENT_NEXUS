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
[TORMENT_NEXUS v0.2.0-beta.1 release](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases/tag/v0.2.0-beta.1).

Scroll to **Assets** and click the small arrow if the file list is collapsed.

## Step 2: Download all three files

Download these exact files:

1. `TORMENT_NEXUS.zip.part01`
2. `TORMENT_NEXUS.zip.part02`
3. `REASSEMBLE_TORMENT_NEXUS.bat`

Keep all three in the same folder, normally **Downloads**. Do not rename them.
The two large files are pieces of one ZIP archive; neither piece can be opened
by itself.

Ignore the automatically generated **Source code** downloads at the bottom of
the release.

## Step 3: Join the parts and install

Double-click `REASSEMBLE_TORMENT_NEXUS.bat`. It joins the two parts back into
a single `TORMENT_NEXUS.zip` and stops safely if either part is missing.

Compare the resulting ZIP against the SHA-256 fingerprint published in the
release notes before going further. In PowerShell, from the folder containing
the ZIP:

```powershell
Get-FileHash .\TORMENT_NEXUS.zip -Algorithm SHA256
```

Then right-click `TORMENT_NEXUS.zip`, choose **Extract All**, open the
extracted `TORMENT_NEXUS` folder, and double-click `setup.bat`.

Allow roughly 10 GB of free space while the two parts, the joined ZIP, and the
extracted folder are all on the same drive. The parts and the ZIP can be
deleted once the application launches.

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
