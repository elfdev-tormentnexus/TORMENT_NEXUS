# TORMENT_NEXUS

A private local assistant built around Qwen3-4B-Instruct-2507 and llama.cpp.
It provides a voice-first terminal, persistent memory, guarded tools and
self-editing, SearXNG web lookup, and standalone project generation. Typed
input remains available in voice mode; type `text mode` for the standard
text-only terminal.

## Windows development

Install the core dependency and launch:

```powershell
python -m pip install -r requirements.txt
.\start_assistant.bat
```

Run `health check` inside the assistant at any time. Run
`test_assistant.bat` for the regression suite.

Developer tools require a local owner passcode. On first use, type `dev mode`
and enter the chosen digits twice in the masked prompt. Only a salted PBKDF2
verifier is stored in `assistant/.dev_passcode`; the passcode is never written
to chat history, memory, or logs. An unlocked developer session expires after
15 minutes or immediately when `exit dev mode` is used.

## Raspberry Pi 5

Use 64-bit Raspberry Pi OS, build `llama.cpp` so its server exists at
`llama.cpp/build/bin/llama-server`, and place the GGUF under `models/`.
Then:

```sh
python3 -m pip install -r requirements.txt
chmod +x start_assistant.sh test_assistant.sh
./start_assistant.sh
```

ARM64 launches automatically use four llama.cpp inference threads. Override
locations or resource settings without changing protected source files:

```sh
export AI_BUDDY_LLAMA_SERVER="/path/to/llama-server"
export AI_BUDDY_MODEL_PATH="/path/to/model.gguf"
export AI_BUDDY_CONTEXT_SIZE="4096"
export AI_BUDDY_MAX_TOKENS="420"
export AI_BUDDY_LLAMA_THREADS="4"
export AI_BUDDY_LLAMA_CACHE_RAM_MB="256"
```

The model API binds to loopback and is protected by a locally generated key.
The key is stored in `assistant/.model_api_key` and must not be published.
The first launch builds a model-specific prompt cache under
`assistant/cache/prompt`; later launches restore it so the stable persona and
core-memory prefix does not need to be reprocessed before the first answer.

## Optional services

- Web search: start the local stack in `searxng/` with Docker Compose.
- Voice: run `setup_voice.bat` on Windows, or follow
  `assistant/voice/README.md` on Raspberry Pi OS.
- T-Deck companion: run `setup_hardware.bat` on Windows or
  `sh setup_hardware.sh` on Raspberry Pi OS. The setup connects to the one
  nearby Meshtastic device and applies the requested always-on display setting.
  Keep Meshtastic Bluetooth on and Wi-Fi off, then use `tdeck scan`,
  `tdeck status`, or `tdeck nodes`.
  In developer mode, `tdeck screen always on` disables the normal display
  timeout and `tdeck power saving off` prevents whole-device sleep from
  overriding it. The corresponding `default` and `on` commands restore normal
  battery-saving behavior. Run `tdeck stable pairing` once to assign a
  separate persistent six-digit Bluetooth PIN and apply Wi-Fi-off,
  power-saving-off, and screen-always-on in one reboot transaction. After the
  resulting one-time Windows re-pair, ordinary T-Deck reboots should reconnect
  without requesting a newly generated code. `tdeck terminal` starts a guarded
  companion-chat
  mode: send `torment_nexus: <message>` from the T-Deck and press Escape on the host
  to stop. T-Deck packets are conversation-only and cannot authorize tools.
  This uses stock Meshtastic text packets, so use a private channel if the
  content should not be visible to other nodes sharing the channel key.
- Generated deliverables are written beneath `dump/` and are never executed
  automatically.
