# TORMENT_NEXUS beta testing

This guide is for someone deliberately testing the beta. Ordinary users should
start with [Installing on Windows](INSTALL_WINDOWS.md) and
[Your first session](FIRST_RUN.md).

Run the automated regression suite before and after a meaningful change:

```powershell
.\setup\test_assistant.bat
```

Then use this short manual pass on the target machine.

## 1. Startup and core conversation

Launch TORMENT_NEXUS, wait for the input prompt, and ask a normal question.
Note startup stutter, first-response delay, and whether typing remains usable.

## 2. Tutorial and commands

Run `tutorial restart`. It should present two sections at a time. Use `next`,
`n`, or `continue` to advance. Try `help` and `explain voice`.

## 3. Voice and cancellation

Run `audio mode`, type a short message, then use `text mode` or Escape. If a
microphone is unavailable, typed audio-mode input should still produce speech.
Run `audio mode` again and confirm voice can be re-enabled.

## 4. Music and visualizer

Play a local track and confirm the visualizer opens automatically without a
scrolling or jittering diagnostic line beneath it. Check that quiet passages
remain active and that bass, beat, melody, and treble changes produce obvious
scene movement. Confirm the colour palette changes after 20 seconds, Space
advances to the next local song, Left/Right changes scenes, and Ctrl+B exits.

Press Right through all ten scenes and confirm each one draws: aqua player,
radial tunnel, spectrum cathedral, orbital reactor, corrupt cube, neon
horizon, plasma flow, datastream rain, wormhole, and acid lattice. The aqua
player should show a glossy bezel, oscilloscope, gel meter, and an obvious
flash on a kick.
The datastream rain should look like a layered falling-code curtain with a
low spectrum horizon; a kick should create only a brief scan-fault sweep, not
turn the entire scene into permanent static.
Acid lattice should show an original acid-green triangulated mesh with jagged
voids and brief beat fracture bursts, not a copied video frame or footage.
Resize the terminal while a scene is running and confirm it reflows without an
exception or leftover columns.

## 4b. Voice delivery and the reactive face

Speak a few sentences and confirm each one ends lower than it began rather
than rising into its full stop, and that consecutive sentences do not all sit
at the same pitch. In voice mode, confirm the face is still between words and
breaks apart on stressed syllables rather than churning at a constant rate.

Run `sing daisy bell` and confirm the tune plays on its own for about a
minute before the singing starts, and that the opening "Daisy, Daisy"
articulates instead of smearing.

## 4c. Activity awareness

Type `activity` and confirm it reports the application actually in front.
Leave the keyboard for six minutes and confirm it reports you as away rather
than counting that time as use. Confirm `activity off` clears it, `activity
on` resumes, and `activity forget` deletes
`assistant\memory\activity_log.jsonl`. Restart and confirm what it noticed
earlier is still there. Confirm the file never appears in `git status`.
Confirm `music mode` can still open the visualizer manually and `stop` stops
local playback.

Let a short local song finish and confirm the next filename starts
automatically. Confirm the final filename wraps to the first. Then confirm
`repeat music off` stops after the current song and `repeat music on` restores
continuous library playback.

## 5. Time awareness

Ask for the current local time and date, then close and reopen the app after a
short gap. It should understand the elapsed time without claiming it watched,
waited, thought, worked, or felt anything while closed. A deliberately wrong
Windows clock should affect the answer honestly rather than being hidden.

## 6. Boundaries and integrations

Try `health check`, optional `search <query>`, and -- only if deliberately
configured -- T-Deck commands. Check that unavailable services fail clearly rather
than freezing the interface.

## 7. Observed serial repair (developer test only)

In developer mode, run `autonomous serial on`, then `run autonomous cycle`.
Watch the status updates. It may apply no more than three small allowlisted
edits, then reload. If all three apply, the restart performs a health and
regression validation before one possible bonus edit; the bonus restarts and
validates once more. Confirm a failed validation restores the recorded batch
instead of awarding the bonus.

## Reporting a problem

Include the command or prompt, the visible result, approximate timing, and the
active mode: text, voice, music, visualizer, web, or hardware. Include the
Windows version, amount of memory, and beta version when relevant.

Do not include credentials, private memories, conversation history, addresses,
or device pairing data. See the longer
[troubleshooting and bug-report guide](TROUBLESHOOTING.md#how-to-write-a-useful-bug-report)
for common problems and a novice-friendly checklist.
