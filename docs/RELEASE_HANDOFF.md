# Private Handoff Checklist

This package is intended for a trusted technical reviewer, not public
distribution. It is a Windows x64 build; Raspberry Pi deployment is a separate
hardware-validation milestone.

Before sending:

- Run the source regression gate: `setup\test_assistant.bat`.
- Build with `python tools\package_release.py --archive --skip-download`.
- Run `python tools\package_release.py --verify-only` and require a clean result.
- Do not run `setup.bat` inside the final `dist\TORMENT_NEXUS` folder.
  Installer testing modifies that staging folder. If you test it, rebuild a
  fresh archive afterwards, then verify the fresh build again.
- Share only `dist/TORMENT_NEXUS.zip`, not the project folder, old AI_TORMENT_NEXUS
  archive, model cache, desktop shortcut, conversation history, or device files.
- Send the SHA-256 value printed by your file manager or PowerShell separately
  so the recipient can verify the copied ZIP.

What the recipient should do:

1. Extract the archive with at least 7 GB of free space available.
2. Run `setup.bat`; it uses only the bundled Python and bundled wheels.
3. Launch TORMENT_NEXUS from the created shortcut.
4. Run `setup\test_assistant.bat`, then try text chat, `voice status`, `audio mode`,
   `text mode`, and `health check`.
5. Do not connect personal accounts, paste credentials, or pair hardware unless
   that is part of a deliberate test.

Reviewer notes:

- Web search requires the sender or recipient to separately run local SearXNG.
- T-Deck support is optional and begins unpaired; no pairing PIN is included.
- Local music is intentionally absent from the handoff.
- Developer mode asks the recipient to create their own local numeric passcode.
- The included Piper model card must stay with the model. Its dataset is marked
  CC BY-NC-SA 4.0; confirm intended sharing remains compatible with that license.

Please report reproducible problems with the command used, what appeared on
screen, and whether text, voice, search, music, or hardware mode was active.
