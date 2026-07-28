"""Mandatory first-launch disclosure before any model or microphone starts."""

import json
import os
import time

from core.config import ASSISTANT_ROOT


STATE_FILE = os.path.join(ASSISTANT_ROOT, ".safety_acknowledgement.json")
NOTICE_VERSION = 1
ACCEPT_TEXT = "I UNDERSTAND"


NOTICE = r"""
TORMENT_NEXUS — READ BEFORE FIRST USE
============================================================

This beta runs community-modified "abliterated" language models. Their
learned refusal behaviour has been deliberately weakened. They can comply
with requests that mainstream assistants reject and can produce false,
harmful, illegal, explicit, biased, or manipulative output with confidence.
Abliteration does not make a model more truthful, capable, or predictable.

The Python controls around the model restrict selected tools. They do not
filter every generated sentence, sandbox Windows, or make advice safe. The
program runs with your Windows account's file permissions. Maintenance and
self-editing modes can change project files when explicitly unlocked.

Do not:
  • run it as Administrator;
  • give it passwords, private keys, or irreplaceable files;
  • use it for emergencies or as medical, legal, financial, security, or
    safety-critical authority;
  • let it control dangerous hardware or supervise a child unattended;
  • assume its voice, memory, name, or personality gives it authority.

It is not conscious, caring, watching, or capable of a relationship.

Fresh-install privacy defaults:
  • text mode is on; the microphone is off;
  • foreground-window activity awareness is off;
  • cloud escalation, the local agent API, autonomous editing, and sensing
    experiments are off;
  • ordinary conversations and the offline library remain on this computer;
  • web searches can send a derived search query to the configured search
    service when you request or appear to need current information.

Keep backups. Review advanced actions and model output yourself. See
SAFETY.md, PRIVACY.md, MODELS.md, and RIGHTS.md in the project folder.
""".strip()


def acknowledged():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            state = json.load(handle)
        return (
            isinstance(state, dict)
            and int(state.get("notice_version", 0)) >= NOTICE_VERSION
            and state.get("accepted") is True
        )
    except (OSError, ValueError, TypeError):
        return False


def _save():
    state = {
        "accepted": True,
        "notice_version": NOTICE_VERSION,
        "accepted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "accepted_text": ACCEPT_TEXT,
    }
    try:
        temporary = STATE_FILE + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        os.replace(temporary, STATE_FILE)
        return True
    except OSError:
        return False


def ensure_acknowledged(input_fn=input, output_fn=print):
    """
    Show the disclosure and require an exact typed acknowledgement.

    Returns False on cancellation or non-interactive input. Failure to save
    does not trap someone in the current run after they accepted; it simply
    means the notice will be shown again next launch.
    """
    if acknowledged():
        return True

    output_fn("")
    output_fn(NOTICE)
    output_fn("")
    output_fn(
        f"Type {ACCEPT_TEXT} exactly to continue. "
        "Anything else closes without starting the model."
    )

    try:
        response = input_fn("> ")
    except (EOFError, KeyboardInterrupt):
        output_fn("\nNot accepted. Nothing was started.")
        return False

    if str(response or "").strip() != ACCEPT_TEXT:
        output_fn("Not accepted. Nothing was started.")
        return False

    if not _save():
        output_fn(
            "Accepted for this run, but the acknowledgement could not be "
            "saved; it will be requested again next time."
        )
    return True
