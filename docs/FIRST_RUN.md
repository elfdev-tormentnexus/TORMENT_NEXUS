# Your first TORMENT_NEXUS session

This is a plain-language tour. You do not need to memorize the commands.
Whenever you are unsure, type `help` or `explain <topic>`.

## Starting the tutorial

At the input prompt, type:

```text
tutorial
```

The tutorial shows two short topics at a time. Type `next`, `n`, or `continue`
to move forward. Type `tutorial restart` whenever you want to begin again.

## Talking and typing

TORMENT_NEXUS starts in audio mode by default. Audio mode means replies can be
spoken, but it does not force you to use a microphone. You can type normally
while audio mode is active.

```text
text mode         stop spoken replies
audio mode        turn spoken replies back on
voice status      check voice and microphone readiness
```

Press **Escape** to cancel speech or listening. A completed message typed while
an answer is being produced is kept for the next turn.

## Checking that everything works

Type:

```text
health check
```

The result describes the model, voice, optional search service, and optional
hardware available on this computer. An unavailable optional feature does not
necessarily mean the basic assistant is broken.

## Understanding local memory

Conversation history and selected memories are stored inside this installation,
not in a cloud account. Useful commands include:

```text
show memories
memory count
forget <words from the memory>
```

Do not type passwords, recovery codes, private keys, or other secrets into
chat. Local storage improves privacy, but anyone with access to the installation
folder may be able to read its text files.

## Adding and playing local music

Open the installed TORMENT_NEXUS folder, then open:

```text
assistant\music
```

Copy your own MP3, WAV, FLAC, or OGG files into that folder. Return to the
assistant and type:

```text
music library
play <part of the song name>
```

Song matching tolerates casual spelling when there is one clear local match.
A successful local-song start is shown on screen instead of spoken, so the
voice does not cover the opening lyrics. The visualizer opens automatically as
soon as a local song starts.

Type `music mode` only when you want to open the visualizer without starting a
new local song:

| Key | Action |
| --- | --- |
| Left / Right | Select another scene |
| Space | Play the next local song, wrapping to the first after the last |
| `[` / `]` | Change local-song volume in 5% steps |
| Ctrl+B | Exit the visualizer |

The scene changes every 2 minutes 45 seconds. The colour palette changes every
20 seconds. Space does not skip Spotify or browser audio. The scenes use
different response profiles: bass expands the tunnel and reactor, spectrum
detail raises the cathedral, and mids and treble drive the cube's motion and
corruption.

## Reading long answers

Long answers appear one page at a time when they do not fit on screen.

| Key | Action |
| --- | --- |
| Space, Enter, or Down | Next page |
| Up or Backspace | Previous page |
| Escape or Q | Close the page view and return to the conversation |

Lists and line breaks are formatted while the answer is generated. Long typed
messages keep the newest part visible instead of disappearing beyond the right
side of the screen.

## Time awareness

TORMENT_NEXUS reads the computer's local clock during every reply. This lets it
understand:

- the current local date and time;
- how long the current session has been open;
- how much time passed since the previous completed conversation.

It relies on the Windows clock, so an incorrect computer clock produces
incorrect time information. It does not run thoughts or have experiences while
the application is closed.

## Optional connected features

Ordinary conversation, memory, speech, time awareness, local music, and the
visualizer work locally after installation.

- Web search requires a separately configured SearXNG service.
- `spotify` opens the installed Spotify desktop application.
- `spotify search <query>` sends that search text to MusicBrainz for public
  title-and-artist matches, then opens the selected result in Spotify.
- Raspberry Pi, Meshtastic, and T-Deck features require separate hardware
  setup.
- Developer mode and project-editing tools are advanced features with local
  guardrails and review steps.

These optional features are not required for ordinary conversation.

## Ending a session

Use the application's normal exit command or close its terminal window after
speech and music have stopped. The next launch can use the saved timestamp to
understand how much time passed, but it was not active in the meantime.

If something behaves differently from this guide, see
[Troubleshooting](TROUBLESHOOTING.md).
