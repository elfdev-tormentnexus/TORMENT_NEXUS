"""
Generates a short menu of concrete self-improvement ideas the
assistant could act on right now.

Every suggestion is grounded to a real, currently-editable file (see
edit_guard.list_editable_files()) instead of letting the model invent
a target or propose touching something denylisted -- accepting one
should flow straight into the existing propose() / preview / confirm
pipeline, not hit a wall on the first step.
"""

import json

import requests

from core.config import DEBUG, MODEL_REQUEST_HEADERS, SERVER_URL
from editing import edit_guard
from ui import ui


TIMEOUT = 90
MAX_TOKENS = 500


SYSTEM = """You suggest small, concrete improvements to your own codebase.

Reply with ONE JSON array of exactly 3 objects and nothing else:

[{"title": "<one short sentence for a human>",
  "file": "<path from the list>",
  "change": "<precise instruction for what to change in that file>"}]

Rules:
- Every suggestion must be small enough to review as a single diff.
- Pick real files from the list. Never invent a file or a path.
- Prefer genuinely useful things: fixing something rough, adding a
  small missing safeguard, tidying an inconsistency -- not cosmetic
  busywork or a rewrite.
- Do not suggest anything about memory data, model weights, or
  anything outside the project's own code."""


# The last generated batch, so a later "do <n>" can look one up
# without asking the model again (and without re-deriving file/change
# from scratch, which could drift from what was actually shown).
_pending = []


def _inventory(autonomous=False):
    files = (
        edit_guard.list_autonomous_files()
        if autonomous
        else edit_guard.list_editable_files()
    )
    return "\n".join(files)


def generate(autonomous=False):
    """
    Returns (suggestions, error). suggestions is a list of
    {"title", "file", "change"} dicts, already validated against the
    real editable-file list.
    """
    global _pending

    ui.set_status("Listing editable files")
    inventory = _inventory(autonomous=autonomous)

    if not inventory:
        return None, "no editable files found"

    ui.set_status("Generating improvement ideas")
    try:
        response = requests.post(
            SERVER_URL + "/v1/chat/completions",
            headers=MODEL_REQUEST_HEADERS,
            json={
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"PROJECT FILES:\n{inventory}"},
                ],
                "temperature": 0.7,
                "max_tokens": MAX_TOKENS,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
    except Exception as e:
        return None, f"could not reach the model: {e}"

    choices = result.get("choices")

    if not choices:
        return None, "no response from the model"

    raw = (choices[0].get("message", {}).get("content") or "").strip()

    if DEBUG:
        print("\nDEBUG SUGGESTIONS RAW:")
        print(raw)

    start = raw.find("[")
    end = raw.rfind("]")

    if start == -1 or end == -1:
        return None, "the model did not return a JSON list"

    try:
        data = json.loads(raw[start:end + 1])
    except Exception:
        return None, "the model returned malformed JSON"

    if not isinstance(data, list):
        return None, "the model's JSON was not a list"

    ui.set_status("Validating improvement ideas")
    valid_files = set(
        edit_guard.list_autonomous_files()
        if autonomous
        else edit_guard.list_editable_files()
    )
    cleaned = []

    for item in data:
        if not isinstance(item, dict):
            continue

        file = str(item.get("file", "")).strip().replace("\\", "/")
        change = str(item.get("change", "")).strip()
        title = str(item.get("title", "")).strip() or change

        if file in valid_files and change:
            cleaned.append({"title": title, "file": file, "change": change})

    if not cleaned:
        return None, "none of the suggestions named a real, editable file"

    _pending = cleaned

    return cleaned, None


def get(index):
    """1-based index into the last generated batch, or None."""
    if not _pending or index < 1 or index > len(_pending):
        return None

    return _pending[index - 1]


def clear():
    global _pending
    _pending = []
