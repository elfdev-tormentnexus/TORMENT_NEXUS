"""
Spotting "hey, make the header green" in ordinary conversation.

Two stages, deliberately:

1. A cheap regex prefilter. Running a classifier inference on every
   single message would double the cost of normal chat for no reason,
   so most turns never get that far.

2. A classifier call, only on messages that survive the prefilter. It
   decides whether this really is an edit request and, if so, which
   file it means. "The header colour" has to become "ui/ui.py" before
   anything can act on it.

The prefilter is deliberately loose. A false positive costs one extra
inference and then falls through to normal chat; a false negative
means the feature silently does not work.
"""

import json
import os
import re

import requests

from core.config import DEBUG, MODEL_REQUEST_HEADERS, SERVER_URL


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TIMEOUT = 90


_ACTION = re.compile(
    r"\b(change|updat|modif|edit|make|set|add|remove|delete|fix|rename|"
    r"swap|adjust|tweak|turn|switch|replace|increase|decrease|shrink|grow)",
    re.IGNORECASE,
)

_SUBJECT = re.compile(
    r"\b(your|yourself|your own|ui|interface|header|banner|title|colou?r|"
    r"font|theme|prompt|persona|memory|terminal|display|screen|code|source|"
    r"script|module|file|command|corruption|ripple|glyph|border|layout|"
    r"streak|chat|window)\b",
    re.IGNORECASE,
)


def looks_like_edit_request(text):
    """Cheap gate. Both an action word and something to act on."""
    if not text or len(text) < 8:
        return False

    return bool(_ACTION.search(text) and _SUBJECT.search(text))


def _file_inventory():
    """
    What the classifier gets to choose from. Uses the stored project
    description when there is one, since its per-file roles are far
    more useful than bare filenames.
    """
    described = os.path.join(PROJECT_ROOT, "project", "project_description.json")

    if os.path.exists(described):
        try:
            with open(described, "r", encoding="utf-8") as f:
                data = json.load(f)

            files = data.get("files") or {}

            if files:
                return "\n".join(f"{name} - {role}" for name, role in files.items())
        except Exception:
            pass

    # Fall back to walking for .py files.
    out = []

    for root, dirs, names in os.walk(PROJECT_ROOT):
        dirs[:] = [
            d for d in dirs
            if d not in ("__pycache__", "logs", ".git", "backups", "change_plans")
        ]

        for name in sorted(names):
            if name.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, name), PROJECT_ROOT)
                out.append(rel.replace("\\", "/"))

    return "\n".join(out)


SYSTEM = """You decide whether the user is asking to CHANGE THE ASSISTANT'S OWN CODE.

Reply with ONE JSON object and nothing else:

{"is_edit_request": true/false,
 "file": "<path from the list, or null>",
 "change": "<precise description of the change, or null>"}

It IS an edit request when the user asks for the assistant's own
appearance, behaviour or code to be altered:
  "make the header green"
  "change your prompt colour"
  "add a command that lists backups"

It is NOT an edit request when the user is:
  asking a question about anything
  asking about code that is not this project
  chatting, or talking about their own separate work

Pick the single file most likely to contain the thing being changed.
Rewrite "change" as a clear instruction naming what to alter."""


def classify(user_message):
    """
    Returns (edit_request_dict, None) or (None, reason_it_is_not).
    The dict is {"file", "change"}.
    """
    inventory = _file_inventory()

    prompt = (
        f"PROJECT FILES:\n{inventory}\n\n"
        f"USER MESSAGE:\n{user_message}"
    )

    try:
        response = requests.post(
            SERVER_URL + "/v1/chat/completions",
            headers=MODEL_REQUEST_HEADERS,
            json={
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 200,
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
        print("\nDEBUG INTENT RAW:")
        print(raw)

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:
        return None, "classifier returned no JSON"

    try:
        data = json.loads(raw[start:end + 1])
    except Exception:
        return None, "classifier returned malformed JSON"

    if not data.get("is_edit_request"):
        return None, "not an edit request"

    target = data.get("file")
    change = data.get("change")

    if not target or not change:
        return None, "classifier could not identify a file or a change"

    return {"file": str(target).strip(), "change": str(change).strip()}, None
