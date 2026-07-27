"""
A guided walkthrough of everything TORMENT_NEXUS can do, plus on-demand
explanations of any single piece of it.

The lessons here are narrative -- why a feature exists and when you would
reach for it -- but they never hardcode a command list. Every command a
lesson mentions is looked up in the live registry at render time, and the
usage string and description come from the registry entry rather than from
this file.

That is the whole design. A tutorial that keeps its own copy of the
command list is wrong the first time anyone adds or renames a command, and
being confidently wrong about your own features is worse than not
explaining them. If a lesson names a command that no longer exists, that
shows up as a visible warning instead of quietly misleading someone. It is
the same grounding rule the suggestion engine uses for editable files.

First-run state lives in a small JSON file beside the memory store. Its
absence is what marks a fresh install, so it must never ship inside a
distributed package -- package_release.py strips it.
"""

import json
import os
import time

from core.config import ASSISTANT_ROOT

STATE_FILE = os.path.join(ASSISTANT_ROOT, ".tutorial_state.json")


# Each lesson names commands; it does not describe them. Descriptions are
# pulled from the registry so they cannot drift.
LESSONS = [
    {
        "key": "what",
        "title": "What this is",
        "body": (
            "A private AI companion that runs entirely on your own machine.\n"
            "The language model, memory, speech, and listening all run\n"
            "locally. Ordinary conversation stays on this machine, and the\n"
            "core system still works with the network unplugged.\n\n"
            "Web search is the deliberate exception: using 'search' sends\n"
            "that query through the SearXNG setup you chose, then out to the\n"
            "internet. It is optional, and it does not make web results\n"
            "trusted.\n\n"
            "That constraint shapes everything else here. Features are built\n"
            "to degrade quietly rather than depend on a service being up."
        ),
        "commands": ["help", "health check"],
    },
    {
        "key": "talking",
        "title": "Just talking to it",
        "body": (
            "Type normally. Anything that is not a recognised command goes to\n"
            "the model as conversation.\n\n"
            "You do not have to memorise commands either -- plain requests get\n"
            "routed to the matching command when the intent is clear, so\n"
            "'play some breakcore' finds the same handler as typing the\n"
            "command yourself."
        ),
        "commands": [],
    },
    {
        "key": "commands",
        "title": "Commands and developer mode",
        "body": (
            "'help' lists everything available to you right now. The list is\n"
            "shorter than the full set on purpose: the tools that can modify\n"
            "files or the project itself are hidden behind developer mode, so\n"
            "an ordinary conversation cannot wander into them by accident.\n\n"
            "Developer mode expires on its own after fifteen minutes rather\n"
            "than staying on until you remember to turn it off.\n\n"
            "The up and down arrow keys cycle the command list, so you can\n"
            "browse rather than recall."
        ),
        "commands": ["help", "dev mode", "dev help", "exit dev mode"],
    },
    {
        "key": "memory",
        "title": "What it remembers",
        "body": (
            "Worthwhile facts from your conversations are extracted and kept\n"
            "between sessions; the rest is allowed to disappear. You can read\n"
            "everything it has stored, and delete any of it.\n\n"
            "There is a deliberate boundary here: it will not assume you are\n"
            "the person who set it up, and it will not address you by a name\n"
            "unless you give one in the current conversation."
        ),
        "commands": ["show memories", "memory count", "forget"],
    },
    {
        "key": "voice",
        "title": "Speaking and listening",
        "body": (
            "Audio mode gives it a voice and, optionally, ears. Speech is\n"
            "synthesised locally and shaped through a vocoder that separates\n"
            "pitch from vocal tract, which is what gives it a machine\n"
            "character rather than a narrator reading aloud.\n\n"
            "Listening is half-duplex on purpose -- it will not transcribe its\n"
            "own speaker. Typing keeps working the whole time, and Escape\n"
            "always gets you back to the plain terminal.\n\n"
            "Three environment variables retune the voice without touching\n"
            "code: TORMENT_NEXUS_CARRIER_HZ, TORMENT_NEXUS_PITCH_FLATTEN, and\n"
            "TORMENT_NEXUS_VOWEL_STRETCH."
        ),
        "commands": ["audio mode", "voice status", "text mode", "exit audio",
                     "sing daisy bell"],
    },
    {
        "key": "music",
        "title": "Music",
        "body": (
            "Drop audio files into the music folder and they become playable\n"
            "by name, with no account and no network. Spotify controls exist\n"
            "too, and the plain 'play' command checks your local library\n"
            "first -- an offline machine should never lose a local file to a\n"
            "service it cannot reach.\n\n"
            "Music runs on its own audio stream, so TORMENT_NEXUS can talk over\n"
            "it without cutting the track off.\n\n"
            "There is also an audio-reactive visualiser that responds to\n"
            "whatever the machine is playing. In visualiser mode, Space\n"
            "cycles the colour palette and Ctrl+B exits."
        ),
        "commands": ["music library", "play", "pause local", "resume local",
                     "stop music", "now playing", "music mode"],
    },
    {
        "key": "projects",
        "title": "Making small projects",
        "body": (
            "Ask it to build a small project in ordinary language and it will\n"
            "create a self-contained result in the dump folder instead of\n"
            "scattering new files through the assistant itself. You can list\n"
            "what it made or open the destination at any time.\n\n"
            "This is for new, contained work such as a simple utility, web\n"
            "page, or prototype. It does not grant permission to modify the\n"
            "TORMENT_NEXUS source code."
        ),
        "commands": ["build project", "list projects", "dump path"],
    },
    {
        "key": "files",
        "title": "Reading your project",
        "body": (
            "It can list, read, and search the code it is made of, and build\n"
            "a structural map of a project so it can answer questions about\n"
            "shape rather than guessing from a filename.\n\n"
            "These are developer-mode tools because they read from disk."
        ),
        "commands": ["list files", "read file", "search code", "show structure",
                     "explain file", "inspect project"],
    },
    {
        "key": "editing",
        "title": "Editing itself, with your approval",
        "body": (
            "It can propose changes to its own source. Nothing is written\n"
            "until you approve it: a change becomes a plan, the plan can be\n"
            "previewed and modified, and only then applied.\n\n"
            "Every applied edit is backed up first and can be rolled back.\n"
            "Some files are permanently off-limits regardless of approval,\n"
            "so it cannot edit its way around its own guard rails.\n\n"
            "'suggest' is the low-pressure entry point: it reads real files\n"
            "and proposes concrete improvements, and 'do <n>' turns one into\n"
            "a plan."
        ),
        "commands": ["suggest", "do", "preview plan", "modify plan",
                     "approve plan", "plan status", "rollback", "list backups"],
    },
    {
        "key": "autonomous",
        "title": "The autonomous cycle",
        "body": (
            "There is a mode where it edits itself without asking first. It\n"
            "exists under negotiated limits rather than as a free hand: one\n"
            "edit per run, a hard cap on how many lines may change, the same\n"
            "permanently-protected files, isolation from anything that\n"
            "arrived as untrusted input, and a full log of what it did.\n\n"
            "It is off at startup by default, because a multi-request cycle\n"
            "before the prompt appears looks like a frozen program."
        ),
        "commands": ["run autonomous cycle"],
    },
    {
        "key": "goals",
        "title": "Self-directed documentation goals",
        "body": (
            "The optional goals feature lets TORMENT_NEXUS propose useful\n"
            "project-related documentation tasks, such as a benchmark plan\n"
            "or hardware integration notes. It is off by default and needs\n"
            "developer mode before new goals can be set or worked on.\n\n"
            "Its goal work is deliberately narrower than self-editing: it can\n"
            "only write plain text, Markdown, JSON, or CSV inside workshop/.\n"
            "It cannot change source code, run programs, use the network, or\n"
            "write outside that folder through this feature."
        ),
        "commands": ["goals", "set goals", "work on goals", "goal done"],
    },
    {
        "key": "web",
        "title": "Searching the web",
        "body": (
            "Search runs against a self-hosted SearXNG instance rather than a\n"
            "commercial API, so queries are not attached to an account. When\n"
            "the network is gone this degrades quietly instead of failing the\n"
            "whole reply.\n\n"
            "Results are treated as untrusted data. Something written on a\n"
            "web page is never followed as an instruction."
        ),
        "commands": ["search"],
    },
    {
        "key": "hardware",
        "title": "Connected hardware",
        "body": (
            "It can pair with a LilyGO T-Deck over Bluetooth and use it as a\n"
            "remote terminal, including over Meshtastic radio where there is\n"
            "no internet at all.\n\n"
            "The terminal is conversation-only: it cannot reach command,\n"
            "project, editing, or autonomous systems. It accepts text only\n"
            "from the paired local T-Deck, not arbitrary mesh traffic.\n\n"
            "Meshtastic text uses the configured radio channel. Other devices\n"
            "with that channel key may be able to see those messages, so\n"
            "treat the radio terminal as non-secret."
        ),
        "commands": ["tdeck setup", "tdeck scan", "tdeck status",
                     "tdeck terminal", "tdeck nodes"],
    },
    {
        "key": "next",
        "title": "Where to go from here",
        "body": (
            "That covers the core tool set. A few things worth knowing:\n\n"
            "  - Escape interrupts almost anything: a long reply, speech,\n"
            "    a song, a running search.\n"
            "  - 'health check' reports what is actually working right now\n"
            "    rather than what is configured.\n"
            "  - Ask 'explain <anything>' for a deeper look at any single\n"
            "    command or subsystem.\n"
            "  - 'tutorial' brings this walkthrough back any time."
        ),
        "commands": ["health check", "explain", "tutorial"],
    },
]

# Subsystem explanations for `explain <topic>` when the topic is a concept
# rather than a specific command.
TOPICS = {
    "voice": "voice",
    "speech": "voice",
    "audio": "voice",
    "memory": "memory",
    "memories": "memory",
    "music": "music",
    "visualizer": "music",
    "visualiser": "music",
    "projects": "projects",
    "project": "projects",
    "dump": "projects",
    "dump folder": "projects",
    "editing": "editing",
    "edits": "editing",
    "self-editing": "editing",
    "autonomous": "autonomous",
    "goals": "goals",
    "goal": "goals",
    "subgoals": "goals",
    "web": "web",
    "search": "web",
    "hardware": "hardware",
    "tdeck": "hardware",
    "t-deck": "hardware",
    "files": "files",
    "commands": "commands",
    "dev mode": "commands",
    "yourself": "what",
    "itself": "what",
}


def _load():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except (OSError, ValueError):
        pass

    return {}


def _save(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        return True
    except OSError:
        return False


def is_first_run():
    """True when this install has never shown the walkthrough."""
    return not os.path.isfile(STATE_FILE)


def mark_seen():
    state = _load()
    state.setdefault("first_seen", time.strftime("%Y-%m-%d %H:%M:%S"))
    _save(state)


def position():
    return int(_load().get("position", 0))


def set_position(index):
    state = _load()
    state["position"] = max(0, min(len(LESSONS) - 1, int(index)))
    state.setdefault("first_seen", time.strftime("%Y-%m-%d %H:%M:%S"))
    state["completed"] = state["position"] >= len(LESSONS) - 1
    state["active"] = not state["completed"]
    _save(state)


def reset():
    state = _load()
    state["position"] = 0
    state["completed"] = False
    state["active"] = True
    _save(state)


def is_complete():
    return bool(_load().get("completed"))


def is_active():
    """Whether a tutorial session is currently awaiting the next lesson."""
    state = _load()
    return bool(state.get("active")) and not bool(state.get("completed"))


def _catalog():
    """Live command metadata, keyed by name. Imported late to avoid a cycle."""
    from commands import command_handlers

    return {entry["name"]: entry for entry in command_handlers.command_catalog()}


def _command_lines(names, catalog):
    """
    Render the commands a lesson refers to, from the registry.

    A name with no registry entry is reported rather than described. That
    is the point of grounding: a stale lesson should be visibly stale.
    """
    lines = []

    for name in names:
        entry = catalog.get(name)

        if entry is None:
            lines.append(f"  {name:<22}  (no longer available)")
            continue

        marker = "*" if entry["dev_only"] else " "
        lines.append(f" {marker}{entry['usage']:<22}  {entry['description']}")

    return lines


def render_lesson(index, include_navigation=True):
    """One lesson as display text, with its real commands attached."""
    index = max(0, min(len(LESSONS) - 1, int(index)))
    lesson = LESSONS[index]
    catalog = _catalog()

    out = [
        f"TUTORIAL  {index + 1}/{len(LESSONS)}  -  {lesson['title']}",
        "=" * 58,
        "",
        lesson["body"],
    ]

    lines = _command_lines(lesson["commands"], catalog)

    if lines:
        out.append("")
        out.append("Commands in this section:")
        out.extend(lines)

        if any(catalog.get(n, {}).get("dev_only") for n in lesson["commands"]):
            out.append("")
            out.append("  * needs developer mode ('dev mode')")

    if include_navigation:
        out.append("")

        if index < len(LESSONS) - 1:
            nxt = LESSONS[index + 1]["title"]
            out.append(
                f"'next' or 'tutorial next' for {nxt.lower()}, "
                "or 'tutorial done'."
            )
        else:
            out.append("That's everything. 'tutorial restart' to go again.")

    return "\n".join(out)


def render_batch(start_index, size=2):
    """Render a short voice-friendly run of consecutive tutorial lessons."""
    start = max(0, min(len(LESSONS) - 1, int(start_index)))
    stop = min(len(LESSONS), start + max(1, int(size)))
    last = stop - 1
    lessons = [
        render_lesson(index, include_navigation=False)
        for index in range(start, stop)
    ]

    if last < len(LESSONS) - 1:
        next_title = LESSONS[last + 1]["title"].lower()
        footer = (
            f"'next' or 'tutorial next' for the next two sections, starting "
            f"with {next_title}. 'tutorial done' closes the walkthrough."
        )
    else:
        footer = "That's everything. 'tutorial restart' to go again."

    return "\n\n".join(lessons + [footer])


def overview():
    """The table of contents, so someone can jump straight to a part."""
    out = [
        "TUTORIAL",
        "=" * 58,
        "",
        "A walkthrough of TORMENT_NEXUS's core systems and common workflows.",
        "Roughly five minutes if you read it straight through.",
        "",
    ]

    here = position()

    for index, lesson in enumerate(LESSONS):
        marker = ">" if index == here else " "
        out.append(f" {marker} {index + 1:>2}. {lesson['title']}")

    out.extend([
        "",
        "'next' or 'tutorial next' moves through two sections at a time.",
        "'tutorial 5' jumps to a section.",
        "'explain <topic>' digs into any single piece.",
    ])

    return "\n".join(out)


def explain(topic):
    """
    Explain one command or subsystem, grounded in the live registry.

    Returns None when nothing matches, so the caller can fall through to
    ordinary conversation rather than asserting something false.
    """
    topic = (topic or "").strip().lower()

    if not topic:
        return None

    catalog = _catalog()

    # An exact command name is the most specific answer available.
    if topic in catalog:
        entry = catalog[topic]
        out = [
            f"{entry['usage']}",
            "=" * 58,
            "",
            entry["description"] + ".",
            "",
            f"Group: {entry['group']}",
        ]

        if entry["dev_only"]:
            out.append("Requires developer mode ('dev mode' first).")

        for lesson in LESSONS:
            if topic in lesson["commands"]:
                out.extend(["", f"Covered in tutorial section "
                                f"'{lesson['title']}':", "", lesson["body"]])
                break

        return "\n".join(out)

    # Otherwise a subsystem, if the word maps to one.
    key = TOPICS.get(topic)

    if key is None:
        for word, mapped in TOPICS.items():
            if word in topic:
                key = mapped
                break

    if key is None:
        return None

    lesson = next((l for l in LESSONS if l["key"] == key), None)

    if lesson is None:
        return None

    out = [lesson["title"], "=" * 58, "", lesson["body"]]
    lines = _command_lines(lesson["commands"], catalog)

    if lines:
        out.extend(["", "Related commands:"] + lines)

    return "\n".join(out)


def first_run_invitation():
    """Short pitch shown once on a brand new install."""
    return (
        "It looks like this is a fresh install.\n\n"
        "Type 'tutorial' for a five-minute walkthrough of the core system.\n"
        "If voice input is available, you can say it instead; typing always\n"
        "works. Or just start talking and ask 'explain <anything>' when you\n"
        "want detail. 'help' lists the commands at any time."
    )
