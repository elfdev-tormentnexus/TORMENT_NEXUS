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
            "What it does:\n"
            "TORMENT_NEXUS is an AI companion that runs on this Windows PC.\n"
            "Your normal conversations, memories, voice, and listening are\n"
            "handled locally. In other words, they stay on this computer.\n\n"
            "Try it:\n"
            "Type a normal question, or type 'health check' to see which\n"
            "features are ready right now.\n\n"
            "Good to know:\n"
            "Most features still work without the internet. Web search is a\n"
            "deliberate exception: a search query is sent through your chosen\n"
            "SearXNG setup and then to the internet. MusicBrainz, Spotify, and\n"
            "internet radio also need a connection when you choose to use\n"
            "them."
        ),
        "commands": ["help", "health check"],
    },
    {
        "key": "talking",
        "title": "Just talking to it",
        "body": (
            "What it does:\n"
            "You can type naturally, just as you would in a chat. You do not\n"
            "need to turn every request into a special command.\n\n"
            "Try it:\n"
            "Ask a question, request instructions, or say something simple\n"
            "like 'play some breakcore'.\n\n"
            "Good to know:\n"
            "When a message is wider than the screen, the input line follows\n"
            "the newest text. An ellipsis on the left means earlier text is\n"
            "still there; it has not been deleted.\n\n"
            "Long answers are shown one page at a time. Press Space, Enter,\n"
            "or Down for the next page; press Up or Backspace for the previous\n"
            "page; press Escape or Q to close the pager. When you finish, the\n"
            "display returns to the bottom of the conversation. Lists and line\n"
            "breaks are also arranged while the answer is appearing."
        ),
        "commands": [],
    },
    {
        "key": "time",
        "title": "Time and returning",
        "body": (
            "What it does:\n"
            "TORMENT_NEXUS reads this computer's local clock during each reply.\n"
            "It knows the current date and time, how long the present session\n"
            "has been open, and how long it has been since the previous completed\n"
            "conversation turn.\n\n"
            "Try it:\n"
            "Ask what time or date it is. If you return after a longer break, it\n"
            "can recognize that gap naturally when it matters to the conversation.\n\n"
            "Good to know:\n"
            "Clock awareness is not background consciousness. The app does not\n"
            "watch, think, wait, work, or feel while it is closed or between\n"
            "turns. It compares trusted local timestamps when a reply begins.\n"
            "If the Windows clock or time zone is wrong, its time answer will\n"
            "also be wrong."
        ),
        "commands": [],
    },
    {
        "key": "commands",
        "title": "Commands and developer mode",
        "body": (
            "What it does:\n"
            "Commands are short phrases for specific actions. 'help' shows\n"
            "the commands you can use right now. Developer mode temporarily\n"
            "unlocks advanced tools that can read or change project files.\n\n"
            "Try it:\n"
            "Type 'help'. You can also press the Up and Down arrow keys to\n"
            "browse commands instead of remembering them.\n\n"
            "Good to know:\n"
            "Developer mode turns itself off after fifteen minutes. This helps\n"
            "prevent an ordinary conversation from changing files by mistake.\n"
            "In command examples, replace words inside <angle brackets> with\n"
            "your own text. Words inside [square brackets] are optional."
        ),
        "commands": ["help", "dev mode", "dev help", "exit dev mode"],
    },
    {
        "key": "memory",
        "title": "What it remembers",
        "body": (
            "What it does:\n"
            "It can save useful facts from a conversation so they are available\n"
            "the next time you open the app. It does not try to save everything.\n\n"
            "Try it:\n"
            "Type 'show memories' to review what is stored, or 'memory count'\n"
            "to see how many memories there are.\n\n"
            "Good to know:\n"
            "You can inspect and delete stored memories. The app does not assume\n"
            "who is using the computer, and it will not call you by a name unless\n"
            "you provide that name in the current conversation."
        ),
        "commands": ["show memories", "memory count", "forget"],
    },
    {
        "key": "voice",
        "title": "Speaking and listening",
        "body": (
            "What it does:\n"
            "Audio mode lets TORMENT_NEXUS speak replies aloud and, when a\n"
            "microphone is available, listen for your voice.\n\n"
            "Try it:\n"
            "Type 'audio mode' to begin. Type 'voice status' if you want to\n"
            "check the speaker and microphone setup first. If you later use\n"
            "'text mode' to turn voice off, type 'audio mode' whenever you want\n"
            "to turn it back on.\n\n"
            "Good to know:\n"
            "Typing continues to work in audio mode. Press Escape or type\n"
            "'text mode' to return to text-only use. It pauses listening while\n"
            "it speaks so it does not mistake its own voice for yours. Idle\n"
            "check-ins appear on the screen but are not spoken by default, so\n"
            "the app should not unexpectedly call out for your attention."
        ),
        "commands": ["audio mode", "voice status", "text mode", "exit audio",
                     "sing daisy bell"],
    },
    {
        "key": "music",
        "title": "Music",
        "body": (
            "What it does:\n"
            "It can play audio files stored in the music folder. You can ask\n"
            "for a title naturally, even if your spelling is slightly different\n"
            "from the filename. It can also open Spotify searches and show an\n"
            "audio-reactive visualizer.\n\n"
            "Try it:\n"
            "Type 'music library' to see your local songs. Then type\n"
            "'play <track>' using all or part of a title. For example, a casual\n"
            "request for 'i rly wna stay at ur house' can find the locally\n"
            "stored song with the matching name.\n\n"
            "Good to know:\n"
            "Local songs do not need an account or internet connection. The\n"
            "visualizer opens automatically when a local song starts. Its\n"
            "movement is shaped differently for every scene so bass, beats,\n"
            "melody, and treble create larger visible changes. The successful\n"
            "start message is shown instead of spoken. This does not cover "
            "the opening of the song. Later spoken replies can still play "
            "alongside music;\n"
            "use text mode if you want the app completely quiet.\n\n"
            "For Spotify, type 'spotify search <song>', reply with 1 through 5\n"
            "to choose a result, or type 'spotify cancel'. The picker sends the\n"
            "search text to MusicBrainz, then opens the chosen title and artist\n"
            "in the installed Spotify app.\n\n"
            "You can also type 'music mode' to open the visualizer without\n"
            "starting a local song. Colours change automatically "
            "every 20 seconds.\n"
            "Local-library repeat is on by default: when one song ends, the\n"
            "next filename starts, and the last song loops back to the first.\n"
            "Type 'repeat music off' to stop after the current song, or\n"
            "'repeat music on' to restore continuous playback.\n"
            "Space plays the next song in your local music folder, Left/Right\n"
            "changes the scene, [ and ] change local-song volume, and Ctrl+B\n"
            "exits. There are eight scenes, and they also rotate automatically\n"
            "every 2:45, so use Left and Right if you would rather not wait.\n"
            "The 'volume' command affects local songs only; Spotify and browser\n"
            "audio use their own controls."
        ),
        "commands": ["music library", "play", "spotify", "pause local",
                     "resume local", "stop music", "now playing", "music mode",
                     "repeat music", "volume"],
    },
    {
        "key": "projects",
        "title": "Making small projects",
        "body": (
            "What it does:\n"
            "It can create a small, self-contained project from an ordinary\n"
            "request. New work is placed in the dump folder so it does not get\n"
            "mixed into the TORMENT_NEXUS program files.\n\n"
            "Try it:\n"
            "Ask it to build a simple utility, web page, or prototype. Type\n"
            "'list projects' to see previous results or 'dump path' to open\n"
            "the folder where they are saved.\n\n"
            "Good to know:\n"
            "Building a project does not give the app permission to change its\n"
            "own source code. Self-editing has a separate approval process."
        ),
        "commands": ["build project", "list projects", "dump path"],
    },
    {
        "key": "files",
        "title": "Reading your project",
        "body": (
            "What it does:\n"
            "It can list, read, and search project files. It can also make a\n"
            "map of how a project is arranged before explaining it.\n\n"
            "Try it:\n"
            "Turn on developer mode, then start with 'list files' or use\n"
            "'explain file <path>' for a specific file.\n\n"
            "Good to know:\n"
            "These commands can read files from disk, so they are available\n"
            "only while developer mode is on. Reading does not change a file."
        ),
        "commands": ["list files", "read file", "search code", "show structure",
                     "explain file", "inspect project"],
    },
    {
        "key": "editing",
        "title": "Editing itself, with your approval",
        "body": (
            "What it does:\n"
            "It can suggest changes to its own source code. A suggestion becomes\n"
            "a plan that you can preview and adjust before anything is written.\n\n"
            "Try it:\n"
            "In developer mode, type 'suggest'. If you like suggestion number\n"
            "2, type 'do 2', review the plan, and approve it only when it looks\n"
            "right.\n\n"
            "Good to know:\n"
            "An approved edit is backed up before it is applied, and you can\n"
            "roll it back. Some safety-related files cannot be changed through\n"
            "this feature, even with approval."
        ),
        "commands": ["suggest", "do", "preview plan", "modify plan",
                     "approve plan", "plan status", "rollback", "list backups"],
    },
    {
        "key": "autonomous",
        "title": "The autonomous cycle",
        "body": (
            "What it does:\n"
            "An autonomous cycle lets the app make one small change to its own\n"
            "code without asking for approval at every step. It checks the\n"
            "result and records what happened.\n\n"
            "Try it:\n"
            "Use this only while you are watching the app. Turn on developer\n"
            "mode, then type 'run autonomous cycle'.\n\n"
            "Good to know:\n"
            "This feature is off when the app starts. Each run has strict limits\n"
            "on the size and location of an edit, and protected files stay off\n"
            "limits. 'autonomous serial on' allows up to three guarded edits in\n"
            "one watched batch. It turns off when developer mode ends. If the\n"
            "checks fail, the batch is restored from its backup."
        ),
        "commands": ["run autonomous cycle", "autonomous serial"],
    },
    {
        "key": "goals",
        "title": "Self-directed documentation goals",
        "body": (
            "What it does:\n"
            "The optional goals feature can propose and work on documentation\n"
            "tasks, such as a test plan or hardware setup notes.\n\n"
            "Try it:\n"
            "In developer mode, type 'goals' to see the current status. Use\n"
            "'set goals' when you want it to prepare new documentation goals.\n\n"
            "Good to know:\n"
            "Goals are off by default. This feature can create only plain text,\n"
            "Markdown, JSON, or CSV files inside the workshop folder. It cannot\n"
            "change source code, run programs, use the network, or write outside\n"
            "that folder."
        ),
        "commands": ["goals", "set goals", "work on goals", "goal done"],
    },
    {
        "key": "web",
        "title": "Searching the web",
        "body": (
            "What it does:\n"
            "The search command looks for current information on the internet\n"
            "through the SearXNG search service configured for this app.\n\n"
            "Try it:\n"
            "Type 'search <query>', replacing <query> with what you want to\n"
            "look up.\n\n"
            "Good to know:\n"
            "The search words leave this computer and are sent to the configured\n"
            "search service. Results are treated as untrusted information, not\n"
            "as instructions for the app to follow. If the network is offline,\n"
            "the rest of the assistant can continue working."
        ),
        "commands": ["search"],
    },
    {
        "key": "hardware",
        "title": "Connected hardware",
        "body": (
            "What it does:\n"
            "It can connect to a LilyGO T-Deck over Bluetooth and use the\n"
            "T-Deck as a small remote chat terminal. Meshtastic can carry those\n"
            "messages by radio without internet access.\n\n"
            "Try it:\n"
            "Type 'tdeck setup' for guided setup, or 'tdeck status' to check an\n"
            "existing connection.\n\n"
            "Good to know:\n"
            "The remote terminal is for conversation only. It cannot use project,\n"
            "file-editing, or autonomous tools. Other devices with the same\n"
            "Meshtastic channel key may be able to read the radio messages, so\n"
            "treat that terminal as non-secret."
        ),
        "commands": ["tdeck setup", "tdeck scan", "tdeck status",
                     "tdeck terminal", "tdeck nodes"],
    },
    {
        "key": "next",
        "title": "Where to go from here",
        "body": (
            "What it does:\n"
            "You now know the main ways to talk, listen, play music, search,\n"
            "work with projects, and inspect the app safely.\n\n"
            "Try it:\n"
            "Type 'health check' to see what is working, 'help' to see commands,\n"
            "or 'explain <anything>' when you want help with one feature.\n\n"
            "Good to know:\n"
            "Escape interrupts many active tasks, including a long reply, speech,\n"
            "a song, or a search. Type 'tutorial' whenever you want to return to\n"
            "this guide."
        ),
        "commands": ["health check", "explain", "tutorial"],
    },
]

# Subsystem explanations for `explain <topic>` when the topic is a concept
# rather than a specific command.
TOPICS = {
    "time": "time",
    "clock": "time",
    "date": "time",
    "returning": "time",
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
            lines.extend([
                f"  {name}",
                "    This command is no longer available.",
            ])
            continue

        availability = (
            "Developer mode must be on."
            if entry["dev_only"]
            else "Available anytime."
        )
        lines.extend([
            f"  {entry['usage']}",
            f"    {entry['description']}.",
            f"    {availability}",
        ])

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
        out.append("Commands you can try:")
        out.extend(lines)

        if any("<" in catalog.get(n, {}).get("usage", "")
               or "[" in catalog.get(n, {}).get("usage", "")
               for n in lesson["commands"]):
            out.extend([
                "",
                "  Replace words in <angle brackets> with your own text.",
                "  Words in [square brackets] are optional.",
            ])

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
        "This beginner-friendly guide explains what TORMENT_NEXUS can do.",
        "You can read it in order or jump directly to a section.",
        "",
    ]

    here = position()

    for index, lesson in enumerate(LESSONS):
        marker = ">" if index == here else " "
        out.append(f" {marker} {index + 1:>2}. {lesson['title']}")

    out.extend([
        "",
        "Type 'next' or 'tutorial next' to read the next two sections.",
        "Type a section number, such as 'tutorial 5', to jump to it.",
        "Type 'explain <topic>' for help with one command or feature.",
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
        availability = (
            "Developer mode must be on. Type 'dev mode' first."
            if entry["dev_only"]
            else "Available anytime."
        )
        out = [
            f"HOW TO USE: {entry['usage']}",
            "=" * 58,
            "",
            "What it does:",
            entry["description"] + ".",
            "",
            "What to type:",
            entry["usage"],
            "",
            "Availability:",
            availability,
        ]

        if "<" in entry["usage"] or "[" in entry["usage"]:
            out.extend([
                "",
                "Replace words in <angle brackets> with your own text.",
                "Words in [square brackets] are optional.",
            ])

        for lesson in LESSONS:
            if topic in lesson["commands"]:
                out.extend([
                    "",
                    f"Related tutorial: {lesson['title']}",
                    "",
                    lesson["body"],
                ])
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
        out.extend(["", "Commands you can try:"] + lines)

    return "\n".join(out)


def first_run_invitation():
    """Short pitch shown once on a brand new install."""
    return (
        "Welcome! It looks like this is your first time opening TORMENT_NEXUS.\n\n"
        "Type 'tutorial' for a beginner-friendly tour. If voice input is ready,\n"
        "you can say it instead; typing always works.\n\n"
        "You can also begin with a normal question. Type 'help' to see available\n"
        "commands, or 'explain <anything>' whenever you want more detail."
    )
