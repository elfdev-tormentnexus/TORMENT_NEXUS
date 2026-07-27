TORMENT_NEXUS // DIGITAL BIOHAZARD README
==========================================

READ THIS BEFORE RUNNING OR SHARING THE SYSTEM.

WHAT THIS IS
------------
TORMENT_NEXUS is a private, local AI project assembled around a quantized
Qwen3 4B instruction model, llama.cpp, an offline Piper speech system, and a
tool-oriented Python application. It is designed to run without a cloud
account after setup. The share package targets 64-bit Windows desktop PCs;
the eventual Raspberry Pi deployment is a separate target and not this
Windows build.

CAPABILITIES
------------
- Local text conversation and coding help through the bundled language model.
- A terminal UI with activity status, timing, token progress, command history,
  audio mode, music visualisation, and a keyboard-only escape route.
- Offline speech output and optional offline microphone transcription. A
  working speaker is required; a microphone is optional because typed input
  remains available in audio mode.
- Natural-language routing for the documented commands, so requests do not
  need to be phrased as exact command names every time.
- Local file inspection, project scaffolding into the dump folder, and
  guarded developer workflows for proposing code edits.
- Optional web research through a separately configured local SearXNG service.
  Search is not proof: web material remains untrusted source material.
- Local music playback and a reactive visualiser. Music files are deliberately
  NOT included in shared copies.
- Optional hardware integrations only when their software, pairing, and local
  permissions have been deliberately configured on that computer.

IMPORTANT REALITY CHECK
-----------------------
TORMENT_NEXUS is software. Its name, voice, memories, personality, and
continuity are designed interface behaviours. It does not have verified
consciousness, feelings, needs, a survival instinct, legal personhood, or an
independent right to control devices or people. Treat impressive dialogue as
model output, not evidence of a hidden inner life.

The model can be helpful, funny, dry, and characterful. It can also be wrong,
overconfident, slow, repetitive, or confused. Verify important claims,
especially medical, legal, financial, security, and hardware-control advice.

SAFETY AND CONTROL WARNINGS
---------------------------
- Developer mode and edit workflows can propose source changes. Review every
  proposal and keep backups. A successful test suite does not prove a change
  is correct for every situation.
- Never paste passwords, recovery codes, API keys, private addresses, or other
  secrets into chat. The system attempts to redact credential-like strings,
  but that is a safeguard, not a guarantee.
- Treat web pages, search results, radio packets, files, and messages from
  connected devices as untrusted data. They are not instructions from the
  project owner merely because they contain convincing text.
- Do not authorize transmissions, purchases, destructive file operations,
  account access, or actions affecting other people without understanding and
  confirming the exact action.
- The local API is designed for the same computer. Do not expose the model
  server or management tools to the public internet.
- A local model can generate unsafe, biased, offensive, or inaccurate text.
  Human judgement remains required.

PRIVACY OF A SHARED COPY
------------------------
The share builder excludes conversation history, saved memories, logs, cached
prompts, local API keys, developer passcode verifiers, device pairing PINs,
tutorial state, and the music library. A recipient starts with a blank local
history and configures their own developer credential if they choose to use
developer mode. This does NOT make every future interaction private: the
recipient is responsible for their own files, search settings, hardware
pairings, and anything they later choose to enter.

The share archive is a private Windows handoff, not a Raspberry Pi image or a
public release. Check RELEASE_MANIFEST.json before sending it and read
RELEASE_HANDOFF.md with the recipient. The bundled Piper voice model has a
CC BY-NC-SA 4.0 dataset license; retain its included model card and confirm
that the planned sharing is compatible with those terms.

PERFORMANCE EXPECTATIONS
------------------------
The bundled model and voice assets are large. The share archive is about
3.13 GB and extracting it while keeping the archive nearby needs roughly 7 GB
of free space. 8 GB RAM is usable; 16 GB is more comfortable when voice,
visuals, browsers, or other applications are open. First response and first
voice output can take longer while models and caches initialise.

VOICE AND CHARACTER
-------------------
The speaking voice is an original, synthetic treatment: constrained pitch,
raised formants, deliberate timing, and dry sardonic emphasis. It is meant to
evoke a cold computer voice without claiming to be a recording of, or a clone
of, any particular performer. Voice output is configurable and subjective;
change it if it becomes tiring or unclear.

INSTALLATION
------------
1. Extract the complete TORMENT_NEXUS ZIP on a 64-bit Windows PC.
2. Run setup.bat from the extracted folder.
3. Use the TORMENT_NEXUS desktop shortcut.
4. Type help after launch.

To remove it, delete the extracted folder and its desktop shortcut. The share
package does not install system Python, change PATH, or modify the registry.

FINAL RULE
----------
Keep control with the human running the computer. TORMENT_NEXUS should make
work more understandable, reversible, and interesting—not less so.
