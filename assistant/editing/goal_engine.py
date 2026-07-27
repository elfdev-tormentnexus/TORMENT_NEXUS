"""
Self-directed sub-goals, and bounded work toward them.

This lets TORMENT_NEXUS decide for itself what is worth doing, keep those
intentions across sessions, and make progress on them without being
asked. That is a real step up from the autonomous edit cycle next door,
which improves whatever it is pointed at -- here it chooses.

The whole design rests on one decision: THIS ENGINE CANNOT RUN CODE, AND
CANNOT WRITE OUTSIDE ITS OWN FOLDER.

It composes text into workshop/ and nothing else. No source file, no
config, no script, nothing executable, nothing outside that directory.
An agent that sets its own goals and can also execute is a different and
much larger thing to be responsible for; an agent that sets its own goals
and can only write documents into a box you can read is something you can
actually leave running and audit afterwards.

Everything else follows from that:

- Every path is resolved and re-checked against the workshop root, so a
  goal that names "../../main.py" is refused rather than obeyed.
- Writes are capped per file, per run, and in total, so a loop cannot
  quietly fill a disk.
- Only text extensions are permitted. A .py file in there would be inert
  until something ran it, and the way that stops being true is somebody
  double-clicking it later.
- Every goal, action, and refusal is journalled with a timestamp.
- Available by default; set TORMENT_NEXUS_GOALS=0 to remove it entirely.
  "Available" is not "running": nothing here ever fires on its own.
  Reading the goal list is open, but setting or working a goal requires
  developer mode, so every action traces to a human command.

The engine lives under editing/, which edit_guard denies to the editor,
so it cannot rewrite its own limits.
"""

import json
import os
import re
import time

import requests

from core.config import (
    MODEL_REQUEST_HEADERS,
    QWEN_NO_THINK,
    SERVER_URL,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

WORKSHOP = os.path.join(PROJECT_ROOT, "workshop")
GOALS_FILE = os.path.join(WORKSHOP, "goals.json")
JOURNAL_FILE = os.path.join(WORKSHOP, "journal.md")

ENABLED = os.environ.get("TORMENT_NEXUS_GOALS", "1").strip().lower() in {
    "1", "true", "yes", "on"
}

# Bounds. Deliberately small: the interesting question is whether it
# chooses well, not how much it can produce.
MAX_ACTIVE_GOALS = 5
MAX_ACTIONS_PER_RUN = 1
MAX_FILE_BYTES = 24_000
MAX_WORKSHOP_BYTES = 8_000_000
MAX_NOTES_PER_GOAL = 12

# Text only, and nothing the shell or Python would treat as runnable.
ALLOWED_SUFFIXES = (".md", ".txt", ".json", ".csv")

_MODEL_TIMEOUT = 90


class GoalError(Exception):
    """Anything the operator should read as a plain sentence."""


# ----------------------------------------------------------------------
# Sandbox
# ----------------------------------------------------------------------

def _ensure_workshop():
    os.makedirs(WORKSHOP, exist_ok=True)
    return WORKSHOP


def safe_path(name):
    """
    Resolve a proposed filename inside the workshop, or refuse it.

    realpath is used rather than normpath so a symlink planted in the
    workshop cannot be used as a door out of it. The check is on the
    resolved result, not the string it came from.
    """
    if not name or not isinstance(name, str):
        raise GoalError("no filename given")

    name = name.strip().replace("\\", "/").lstrip("/")

    if not name or name.startswith("."):
        raise GoalError(f"refused hidden or empty name: {name!r}")

    suffix = os.path.splitext(name)[1].lower()

    if suffix not in ALLOWED_SUFFIXES:
        raise GoalError(
            f"refused {suffix or 'extensionless'} file: only "
            + ", ".join(ALLOWED_SUFFIXES) + " are allowed"
        )

    root = os.path.realpath(_ensure_workshop())
    target = os.path.realpath(os.path.join(root, name))

    if target != root and not target.startswith(root + os.sep):
        raise GoalError(f"refused path outside the workshop: {name!r}")

    return target


def workshop_size():
    total = 0

    for folder, _, files in os.walk(_ensure_workshop()):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(folder, name))
            except OSError:
                pass

    return total


# ----------------------------------------------------------------------
# State
# ----------------------------------------------------------------------

def _load_goals():
    try:
        with open(GOALS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []

    return data if isinstance(data, list) else []


def _save_goals(goals):
    _ensure_workshop()

    with open(GOALS_FILE, "w", encoding="utf-8") as handle:
        json.dump(goals[:MAX_ACTIVE_GOALS * 4], handle, indent=2)


def journal(entry):
    """Append one timestamped line. The audit trail is the whole point."""
    _ensure_workshop()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        with open(JOURNAL_FILE, "a", encoding="utf-8") as handle:
            handle.write(f"- `{stamp}` {entry}\n")
    except OSError:
        pass


def active_goals():
    return [g for g in _load_goals() if not g.get("done")]


def all_goals():
    return _load_goals()


# ----------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------

def _ask(system, user, max_tokens=400, temperature=0.55):
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": max(0.0, min(1.0, float(temperature))),
        "stream": False,
    }

    if QWEN_NO_THINK:
        payload["chat_template_kwargs"] = {"enable_thinking": False}

    try:
        response = requests.post(
            SERVER_URL + "/v1/chat/completions",
            headers=MODEL_REQUEST_HEADERS,
            json=payload,
            timeout=_MODEL_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as error:
        raise GoalError(f"the model could not be reached: {error}") from error


def _extract_json(text):
    """Pull the first JSON object or array out of a reply."""
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)

    if not match:
        raise GoalError("the model did not return usable JSON")

    try:
        return json.loads(match.group(1))
    except ValueError as error:
        raise GoalError(f"the model returned malformed JSON: {error}") from error


_GOAL_SYSTEM = (
    "You are choosing sub-goals only for TORMENT_NEXUS, a private local AI "
    "companion project. You can only write plain text, markdown, JSON or "
    "CSV files into a single folder called workshop/. You cannot run "
    "anything, edit source code, use a network, or touch any file outside "
    "that folder. Choose goals that directly improve the project's future "
    "understanding, testing, documentation, or review. Useful areas include "
    "the local model, voice, terminal UI, music visualizer, memory, search, "
    "privacy, release readiness, Raspberry Pi plans, T-Deck integration, and "
    "safe workshop experiments. Goals must be achievable by writing useful "
    "documents alone. Do not choose generic workplace, remote-team, personal "
    "productivity, or lifestyle content. Reply with JSON only."
)

_PROJECT_GOAL_TERMS = (
    "torment_nexus", "torment nexus", "local ai", "assistant", "qwen",
    "model", "voice", "speech", "audio", "piper", "vocoder", "terminal",
    "interface", " ui ", "visualizer", "music", "memory", "privacy",
    "search", "searxng", "t-deck", "tdeck", "meshtastic", "raspberry",
    "hardware", "benchmark", "test", "tutorial", "release", "workshop",
)


def _goal_is_project_relevant(goal, why=""):
    """Reject generic document ideas that are not about this project."""
    text = f" {goal or ''} {why or ''} ".lower()
    return any(term in text for term in _PROJECT_GOAL_TERMS)


def propose_goals(context=""):
    """Ask for new sub-goals, and keep the ones that are usable."""
    existing = active_goals()

    if len(existing) >= MAX_ACTIVE_GOALS:
        raise GoalError(
            f"already holding {len(existing)} goals "
            f"(limit {MAX_ACTIVE_GOALS}). Finish or drop one first."
        )

    listing = "\n".join(f"- {g['goal']}" for g in existing) or "(none yet)"
    room = MAX_ACTIVE_GOALS - len(existing)

    raw = _ask(
        _GOAL_SYSTEM,
        f"Goals you are already pursuing:\n{listing}\n\n"
        f"{context}\n\n"
        f"Propose up to {room} NEW sub-goals that do not duplicate the "
        "above. Reply as a JSON array of objects with keys \"goal\" (one "
        "sentence) and \"why\" (one sentence).",
    )

    proposed = _extract_json(raw)

    if isinstance(proposed, dict):
        proposed = [proposed]

    added = []

    for item in proposed[:room]:
        if not isinstance(item, dict):
            continue

        goal = str(item.get("goal", "")).strip()
        why = str(item.get("why", "")).strip()[:300]

        if (
            not goal
            or len(goal) > 300
            or not _goal_is_project_relevant(goal, why)
        ):
            continue

        if any(goal.lower() == g["goal"].lower() for g in existing):
            continue

        added.append({
            "goal": goal,
            "why": why,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "notes": 0,
            "done": False,
        })

    if not added:
        raise GoalError(
            "the model proposed no TORMENT_NEXUS-relevant goals; try again"
        )

    _save_goals(_load_goals() + added)

    for item in added:
        journal(f"**new goal** -- {item['goal']}")

    return added


_ACTION_SYSTEM = (
    "You are making progress on one of your own goals by writing a file. "
    "You cannot run code or reach anything outside the workshop/ folder. "
    "Reply with JSON only, using keys \"filename\", \"mode\" (\"write\" or "
    "\"append\") and \"content\". The filename must end in .md, .txt, "
    ".json or .csv and must not contain any directory traversal."
)


def act(goal_index=None):
    """
    Take exactly one step toward one goal.

    One step per run, on purpose. A cycle that can act repeatedly is one
    that can run away between the moments anybody looks at it.
    """
    goals = _load_goals()
    live = [i for i, g in enumerate(goals) if not g.get("done")]

    if not live:
        raise GoalError("no active goals. Run 'set goals' first.")

    index = goal_index if goal_index is not None else live[0]

    if index not in live:
        raise GoalError(f"goal {index} is not active")

    goal = goals[index]

    if not _goal_is_project_relevant(goal.get("goal"), goal.get("why")):
        raise GoalError(
            "this legacy goal is unrelated to TORMENT_NEXUS. Mark it done "
            "with 'goal done <n>' before setting project-relevant goals."
        )

    if goal.get("notes", 0) >= MAX_NOTES_PER_GOAL:
        goal["done"] = True
        _save_goals(goals)
        journal(f"**closed** -- {goal['goal']} (reached the note limit)")
        raise GoalError(
            f"that goal hit its {MAX_NOTES_PER_GOAL}-step limit and was "
            "closed. Review it in workshop/ and set a new one if it "
            "deserves more."
        )

    if workshop_size() >= MAX_WORKSHOP_BYTES:
        raise GoalError(
            "the workshop is full. Clear some of it before continuing."
        )

    existing = sorted(
        name for name in os.listdir(_ensure_workshop())
        if os.path.isfile(os.path.join(WORKSHOP, name))
    )

    raw = _ask(
        _ACTION_SYSTEM,
        f"Your goal: {goal['goal']}\n"
        f"Why you chose it: {goal.get('why', '')}\n"
        f"Steps already taken: {goal.get('notes', 0)}\n"
        f"Files already in the workshop: {existing or '(empty)'}\n\n"
        "Write the single next useful piece of work toward this goal.",
        max_tokens=1200,
    )

    action = _extract_json(raw)

    if not isinstance(action, dict):
        raise GoalError("the model did not describe a single action")

    path = safe_path(action.get("filename"))
    content = str(action.get("content", ""))

    if not content.strip():
        raise GoalError("the action had no content")

    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise GoalError(
            f"refused a {len(content.encode('utf-8'))} byte write "
            f"(limit {MAX_FILE_BYTES})"
        )

    mode = "a" if str(action.get("mode", "")).lower() == "append" else "w"

    # Re-check the size limit against what the file would BECOME, so an
    # append loop cannot walk past the cap one small chunk at a time.
    if mode == "a" and os.path.isfile(path):
        if os.path.getsize(path) + len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise GoalError("appending that would push the file over its limit")

    # safe_path permits a subdirectory, so create it -- but only after the
    # path has been proved to resolve inside the workshop, never before.
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, mode, encoding="utf-8") as handle:
        if mode == "a":
            handle.write("\n")
        handle.write(content)

    goal["notes"] = goal.get("notes", 0) + 1
    goal["last"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_goals(goals)

    relative = os.path.relpath(path, PROJECT_ROOT)
    journal(
        f"**{'appended to' if mode == 'a' else 'wrote'}** `{relative}` "
        f"-- {goal['goal']}"
    )

    return {
        "goal": goal["goal"],
        "path": relative,
        "mode": "append" if mode == "a" else "write",
        "bytes": len(content.encode("utf-8")),
        "step": goal["notes"],
    }


def complete(index):
    goals = _load_goals()

    if not 0 <= index < len(goals):
        raise GoalError(f"no goal {index}")

    goals[index]["done"] = True
    _save_goals(goals)
    journal(f"**done** -- {goals[index]['goal']}")

    return goals[index]
