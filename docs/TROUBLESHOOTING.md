# TORMENT_NEXUS troubleshooting

Start with:

```text
health check
```

That command explains which local and optional parts are available. If the
application will not open, use the installation and launch sections below.

## I downloaded a ZIP but there is no working installer

You probably downloaded GitHub's automatic **Source code (zip)** file. It does
not include the AI model or self-contained Windows runtime.

Return to the
[v0.2.0-beta.5 release](https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases/tag/v0.2.0-beta.5)
and download every consecutive release part, starting at `part01`, plus:

```text
REASSEMBLE_TORMENT_NEXUS.bat
```

Keep every file in the same folder and follow
[Installing on Windows](INSTALL_WINDOWS.md).

## The reassembly helper says a file is missing

- Confirm every consecutive `.partNN` file in the release finished downloading.
- Put every part and `REASSEMBLE_TORMENT_NEXUS.bat` in the same folder.
- Do not rename the files.
- Check whether the browser added `(1)` or another suffix after a repeated
  download. Remove the incomplete duplicate and download the correct file
  again.
- Make sure the files are not still represented by temporary browser download
  names.

Run the helper again only after every filename matches the release exactly.

## The rebuilt ZIP will not open or its checksum is wrong

One of the parts may be incomplete or damaged. Delete `TORMENT_NEXUS.zip`,
download every part again, and rerun `REASSEMBLE_TORMENT_NEXUS.bat`. Compare
the rebuilt ZIP against the SHA-256 fingerprint in the release notes before
extracting. Do not run setup when the release checksum does not match.

## Windows or security software blocks a file

Confirm all of the following before doing anything else:

- the files came from the official TORMENT_NEXUS GitHub release;
- the rebuilt ZIP's SHA-256 matches the release notes;
- the filenames have not been changed;
- the files were not forwarded through an untrusted source.

Do not bypass workplace or school security policy. If a managed computer blocks
the package, use a personal test computer or ask its administrator to inspect
the release and checksum.

## Setup cannot find files

Make sure you used **Extract All** and opened the extracted folder. Running
`setup.bat` from the ZIP preview prevents it from seeing neighbouring files.

The same folder as `setup.bat` should also contain `assistant`, `models`,
`python`, and `start_assistant.bat`.

Do not move individual files out of the installation folder.

## Setup finished but there is no desktop shortcut

Open the extracted TORMENT_NEXUS folder and double-click:

```text
start_assistant.bat
```

The application is still usable if shortcut creation failed. Keep
`start_assistant.bat` inside the installation folder.

## The desktop shortcut stopped working

The shortcut points to the folder where setup was originally run. It stops
working if that folder is moved, renamed, or deleted.

1. Open the current TORMENT_NEXUS folder.
2. Confirm `start_assistant.bat` launches the application.
3. Run `setup.bat` again to recreate the shortcut for the current location.

If `start_assistant.bat` also fails, keep the terminal window open and include
its final error lines in a bug report. Remove personal paths or private data
before posting screenshots.

## The first answer is slow

The local model loads into memory on the first message. Later messages are
normally faster. Closing the application releases that memory, so a new
session must load it again.

Close other memory-heavy applications if Windows is struggling. The bundled Q8
director and 7B coder need at least 16 GB of memory; more leaves more room for
voice and other applications.

## I turned voice off and cannot turn it back on

Type:

```text
audio mode
```

Use `text mode` to turn spoken replies off again. `voice status` shows whether
speech and microphone components are ready.

## There is no microphone, or speech recognition is not working

Typed input still works in audio mode, and replies can still be spoken.

- Type `voice status`.
- Check the Windows microphone privacy and input-device settings.
- Make sure another application is not holding the microphone exclusively.
- Press Escape once to cancel a stuck listening state, then try again.
- Use `text mode` if you want to continue without speech.

The ready-to-run Windows beta already includes its voice assets. The separate
voice setup script is for source checkouts, not the normal packaged install.

## The assistant spoke unexpectedly

Unsolicited idle attention messages are visual-only by default. Local-song
start confirmations are also visual-only.

Use `text mode` to disable spoken replies completely. If speech still occurs
without a submitted prompt, note what was on screen, the active mode, and the
approximate idle time in a bug report.

## The voice talks over the beginning of a local song

Current local-song starts should be confirmed on screen without speech. Confirm
that the song is inside `assistant\music` and was started as local music rather
than through Spotify or a browser.

If it still happens, report the exact request and whether `music mode` was
active.

## A local song is not found

1. Put the audio file in `assistant\music` inside the current installation.
2. Type `music library` to confirm it appears.
3. Try a distinctive part of the filename rather than a very short word.
4. If several files have similar names, use more of the title.

Supported file types are MP3, WAV, FLAC, and OGG.

## Space does not play the next song

Space advances local music only while the visualizer is in music mode. It does
not control Spotify or browser playback.

Playing a local song should open music mode automatically. If the visualizer
was closed manually, type `music mode`, confirm a local song is active, and
press Space again.

## Local music stops instead of continuing through the library

Type `repeat music`. Local-library repeat is on by default. If it reports off,
type `repeat music on`.

Tracks play in filename order. When one finishes, the next starts
automatically; after the last filename, playback returns to the first. A file
that cannot be decoded is skipped so one damaged addition does not stop the
rest of the library.

## Text, code, or diagnostics appear beneath the visualizer

The current visualizer protects the terminal's bottom-right cell from automatic
line wrapping and redirects background Python audio diagnostics to:

```text
assistant\logs\visualizer_output.log
```

That log is local and is not displayed over the animation. If the screen still
scrolls or jitters, include the Windows terminal application, terminal size,
active scene, and the final non-private lines of that log in a bug report.

## Text disappears at the right edge

The current beta keeps the newest part of a long typed message visible. If it
does not:

- confirm you are running v0.2.0-beta.1;
- avoid resizing the terminal while actively typing;
- note the terminal width and exact input in a bug report.

## A long answer disappears above the screen

The current beta opens a page-at-a-time view for long replies:

- Space, Enter, or Down moves forward;
- Up or Backspace moves backward;
- Escape or Q closes the page view.

If normal Windows terminal scrolling is needed afterward, use its standard
scroll bar or scroll gesture.

## Time or elapsed-time information is wrong

TORMENT_NEXUS uses the Windows local clock. Check the Windows date, time, time
zone, and automatic time synchronization settings.

It should not claim that it watched, waited, thought, worked, or felt anything
while closed. Report such a claim with the exact prompt and reply.

## How to write a useful bug report

Include:

- what you typed or clicked;
- what you expected;
- what actually happened;
- roughly how long it took;
- whether text, audio, music, visualizer, web, or hardware mode was active;
- the Windows version, amount of memory, and beta version when relevant.

Do not include passwords, private memories, conversation history, API keys,
addresses, or device pairing information.
