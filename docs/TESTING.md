# TORMENT_NEXUS beta testing

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

## 4. Music and visualizer

Play a local track, then test `music mode`. Space cycles the visualizer palette
and Ctrl+B exits. Confirm `stop` stops local playback.

## 5. Boundaries and integrations

Try `health check`, optional `search <query>`, and -- only if deliberately
configured -- T-Deck commands. Check that unavailable services fail clearly rather
than freezing the interface.

## Reporting a problem

Include the command or prompt, the visible result, approximate timing, and the
active mode: text, voice, music, visualizer, web, or hardware. Do not include
credentials, private memories, or device pairing data.
