# T-Deck custom terminal firmware

> [!WARNING]
> This is an advanced, optional hardware guide. It is not required to install
> or use the Windows beta. Flashing the wrong firmware can leave a device
> unusable until its correct official firmware is restored.

TORMENT_NEXUS can use a LilyGO T-Deck running Meshtastic as a compact,
Bluetooth-connected companion terminal. The normal bridge in
`assistant/hardware/tdeck.py` remains the authority for pairing, message
exchange, and session state. The firmware described here changes only the
on-device presentation of those messages.

## What changes on the T-Deck

Messages sent by a local TORMENT_NEXUS terminal session have headers such as
`[TORMENT_NEXUS // ONLINE]`, `[TORMENT_NEXUS // WORKING]`, and
`[TORMENT_NEXUS // REPLY]`. On a compatible custom build, those messages open
a dedicated dark terminal panel with red and violet accents, an explicit
connection state, and a focused message field. Ordinary Meshtastic messages
continue to use the normal interface.

The device remains a companion terminal:

- Its input is ordinary conversation only.
- It cannot enable developer mode, invoke tools, alter files, or bypass the
  desktop application's confirmations.
- The desktop application decides when the terminal is online or offline.

## Compatibility and source base

The current build target is **`t-deck-tft`** (the LCD LilyGO T-Deck / T-Deck
Plus), not the separate e-ink T-Deck Pro target. Its source is pinned to the
same Meshtastic release family reported by the connected device:
`2.7.26.54e0d8d`.

The custom UI is a small patch over the official
[Meshtastic firmware](https://github.com/meshtastic/firmware) and
[device UI](https://github.com/meshtastic/device-ui) source trees. Those
projects are GPL-3.0 licensed. If a custom binary is distributed, provide the
corresponding source and retain the upstream license notices.

## Safe flashing practice

1. Confirm the normal desktop bridge works with `tdeck status` first.
2. Use a known-good USB **data** cable and keep the existing stock build as
   the recovery point.
3. Flash only the verified `t-deck-tft` image; other T-Deck variants use
   different display and input hardware definitions.
4. After the first boot, test the touchscreen, keyboard, Bluetooth, one normal
   Meshtastic message, and one `tdeck terminal` session before relying on it.
5. If anything is wrong, re-flash the matching official Meshtastic release
   using the [Meshtastic Web Flasher](https://flasher.meshtastic.org/).

The flash step is intentionally manual and requires an operator at the
physical device. Building an image does not modify the T-Deck.
