import os
import json
import re
import time

from memory import memory_store as mem
from ui import ui
from core import file_utils
from core import health_check
from core import dev_auth
from project import project_mapper
from project import project_analyzer
from project import project_builder
from editing import change_planner
from editing import approval_manager
from editing import edit_engine
from editing import suggestion_engine
from editing import autonomous_engine
from web import search_engine
from voice import offline_voice
from voice import session as voice_session
from hardware import tdeck


# ============================================================
# PATHS
#
# This module lives in commands/, so dirname(__file__) is the
# commands folder, NOT the project root. Everything that walks the
# project has to start one level up or it only ever sees this file.
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DEV_MODE = False
DEV_MODE_EXPIRES_AT = 0.0
DEV_MODE_DURATION_SECONDS = 15 * 60
AUTONOMOUS_SERIAL_MODE = False


def is_dev_mode():
    _expire_dev_mode()
    return DEV_MODE


def _expire_dev_mode():
    global DEV_MODE, DEV_MODE_EXPIRES_AT, AUTONOMOUS_SERIAL_MODE

    if (
        DEV_MODE
        and DEV_MODE_EXPIRES_AT
        and time.monotonic() >= DEV_MODE_EXPIRES_AT
    ):
        DEV_MODE = False
        DEV_MODE_EXPIRES_AT = 0.0
        AUTONOMOUS_SERIAL_MODE = False


# ============================================================
# COMMAND REGISTRY
#
# The decorator registers AND documents in one step. That is
# deliberate: the old file had six handlers that were written but
# never added to the list, so they were unreachable -- including
# "dev help" itself. With this you cannot define a command without
# it being both callable and described in the help output.
#
# Each handler returns:
#   str   -> handled, display this
#   False -> not this command, keep looking
# ============================================================

COMMANDS = []


def command(name, description, usage=None, dev_only=True, group="general",
            arg_pattern=None):
    """
    Register a command, and document it, in one step.

    `arg_pattern` is an optional regex the argument must match before the
    developer-mode gate treats the input as an attempted invocation. It
    exists for commands whose names are also ordinary English words --
    without it, "do you like music" is refused as a malformed "do <number>".
    """
    def wrap(fn):
        COMMANDS.append({
            "name": name,
            "usage": usage or name,
            "description": description,
            "dev_only": dev_only,
            "group": group,
            "arg_pattern": arg_pattern,
            "handler": fn,
        })
        return fn

    return wrap


def _match_exact(user_input, word):
    return user_input.lower().strip() == word


def _match_prefix(user_input, prefix):
    return user_input.lower().strip().startswith(prefix.lower())


def _run_with_activity(status, operation):
    """Keep long synchronous commands visible in the live activity area."""
    ui.set_generating(True)
    ui.set_status(status)

    try:
        return operation()
    finally:
        ui.finish_activity("Completed")


# ============================================================
# HELP
# ============================================================

def _grouped_commands(include_dev):
    """(ordered group keys, {group: [commands]}), filtered by dev mode."""
    groups = {}

    for c in COMMANDS:
        if c["dev_only"] and not include_dev:
            continue

        groups.setdefault(c["group"], []).append(c)

    order = [
        "session",
        "hardware",
        "memory",
        "files",
        "project",
        "editing",
        "general",
    ]
    keys = [g for g in order if g in groups] + [
        g for g in sorted(groups) if g not in order
    ]

    return keys, groups


def _render_help(include_dev):
    keys, groups = _grouped_commands(include_dev)

    out = []
    out.append("DEVELOPER COMMANDS" if include_dev else "COMMANDS")
    out.append("=" * 58)

    width = max((len(c["usage"]) for c in COMMANDS), default=20)
    width = min(max(width, 18), 30)

    for key in keys:
        out.append("")
        out.append(key.upper())

        for c in sorted(groups[key], key=lambda x: x["name"]):
            out.append(f"  {c['usage']:<{width}}  {c['description']}")

    if not include_dev:
        out.append("")
        out.append("Type 'dev mode' for the full toolset.")

    return "\n".join(out)


def visible_command_names():
    """
    Command names (not full usage strings, so the result is directly
    typable) for the UI's arrow-key cycling, respecting dev mode and
    ordered the same way as 'help'.
    """
    keys, groups = _grouped_commands(is_dev_mode())

    names = []

    for key in keys:
        names.extend(c["name"] for c in sorted(groups[key], key=lambda x: x["name"]))

    return names


def command_catalog():
    """
    Serializable command metadata for the natural-language router.

    Handlers are intentionally omitted: the router can choose from this table,
    but execution still has to come back through try_handle_command().
    """
    return [
        {
            "name": entry["name"],
            "usage": entry["usage"],
            "description": entry["description"],
            "dev_only": entry["dev_only"],
            "group": entry["group"],
            "arg_pattern": entry.get("arg_pattern"),
        }
        for entry in COMMANDS
    ]


@command("voice speed", "Set how fast speech is read (0.5 fast - 3.0 slow)",
         usage="voice speed <number>", dev_only=False, group="session",
         arg_pattern=r"^\d+(\.\d+)?$")
def handle_voice_speed(user_input):
    if not _match_prefix(user_input, "voice speed"):
        return False

    argument = user_input.strip()[len("voice speed"):].strip()

    if not argument:
        return (
            f"Reading speed is {offline_voice.speech_pace():.2f}.\n\n"
            "Higher is slower. This project runs slower than Piper's\n"
            "natural pace by default, because the flattened pitch needs\n"
            "the extra time to stay intelligible.\n\n"
            "Usage: voice speed 1.3"
        )

    try:
        applied = offline_voice.set_speech_pace(float(argument))
    except ValueError:
        return "Usage: voice speed <number>, for example: voice speed 1.3"

    return (
        f"Reading speed set to {applied:.2f}.\n\n"
        "Takes effect on the next spoken reply."
    )


@command("audio devices", "List microphones and speakers",
         dev_only=False, group="session")
def handle_audio_devices(user_input):
    if not _match_exact(user_input, "audio devices"):
        return False

    inputs, outputs, error = offline_voice.audio_devices()

    if error:
        return f"AUDIO DEVICES\n{'=' * 58}\n\n{error}"

    chosen_in = offline_voice.input_device()
    chosen_out = offline_voice.output_device()
    lines = [f"AUDIO DEVICES\n{'=' * 58}\n"]

    for title, devices, chosen in (
        ("INPUTS (microphones)", inputs, chosen_in),
        ("OUTPUTS (speakers)", outputs, chosen_out),
    ):
        lines.append(title)

        for index, name, _channels, is_default in devices:
            marks = []
            if is_default:
                marks.append("system default")
            if chosen is not None and str(chosen) == str(index):
                marks.append("selected")
            suffix = f"   [{', '.join(marks)}]" if marks else ""
            lines.append(f"  {index:>3}  {name[:42]}{suffix}")

        if not devices:
            lines.append("  (none found)")

        lines.append("")

    lines.append("'audio input <number>' or 'audio output <number>' to choose.")
    lines.append("'audio input default' returns to the system default.")

    return "\n".join(lines)


def _select_device(kind, argument):
    """Shared body for choosing an input or output."""
    inputs, outputs, error = offline_voice.audio_devices()

    if error:
        return error

    available = inputs if kind == "input" else outputs
    setter = (offline_voice.set_input_device if kind == "input"
              else offline_voice.set_output_device)

    if argument.lower() in ("default", "auto", "system"):
        setter(None)
        return f"Audio {kind} returned to the system default."

    if not argument.isdigit():
        return f"Usage: audio {kind} <number>, or 'audio {kind} default'"

    index = int(argument)
    match = next((d for d in available if d[0] == index), None)

    if match is None:
        return (f"No {kind} device numbered {index}. "
                "Run 'audio devices' to see the list.")

    setter(str(index))

    return (f"Audio {kind} set to {index}: {match[1]}\n\n"
            "Takes effect the next time audio mode starts.")


@command("audio input", "Choose which microphone to listen with",
         usage="audio input <number>", dev_only=False, group="session",
         arg_pattern=r"^(\d+|default|auto|system)$")
def handle_audio_input(user_input):
    if not _match_prefix(user_input, "audio input "):
        return False

    return _select_device("input", user_input[len("audio input "):].strip())


@command("audio output", "Choose which speaker to play through",
         usage="audio output <number>", dev_only=False, group="session",
         arg_pattern=r"^(\d+|default|auto|system)$")
def handle_audio_output(user_input):
    if not _match_prefix(user_input, "audio output "):
        return False

    return _select_device("output", user_input[len("audio output "):].strip())


@command("tutorial", "Walk through TORMENT_NEXUS's core features",
         usage="tutorial [next|<n>|restart]", dev_only=False, group="session")
def handle_tutorial(user_input):
    from core import tutorial

    normalized = (user_input or "").strip().lower()

    # Once someone has deliberately started the walkthrough, the obvious
    # "next" should work without making them repeat the tutorial command.
    # Outside that state it remains ordinary conversation.
    if normalized in ("next", "n", "continue") and tutorial.is_active():
        user_input = "tutorial next"
    elif not _match_prefix(user_input, "tutorial"):
        return False

    argument = user_input.strip()[len("tutorial"):].strip().lower()
    tutorial.mark_seen()

    if not argument:
        # Bare 'tutorial' shows the contents rather than dumping section
        # one, so someone returning to it can jump to the part they want.
        return tutorial.overview()

    if argument in ("next", "n", "continue"):
        index = tutorial.position() + 1

        if index >= len(tutorial.LESSONS):
            tutorial.set_position(len(tutorial.LESSONS) - 1)
            return ("That was the last section. 'tutorial restart' to go "
                    "again, or 'explain <topic>' for any single piece.")

        end = min(len(tutorial.LESSONS) - 1, index + 1)
        tutorial.set_position(end)
        return tutorial.render_batch(index)

    if argument in ("restart", "start", "begin"):
        tutorial.reset()
        end = min(len(tutorial.LESSONS) - 1, 1)
        tutorial.set_position(end)
        return tutorial.render_batch(0)

    if argument in ("done", "stop", "exit", "quit"):
        tutorial.set_position(len(tutorial.LESSONS) - 1)
        return "Tutorial closed. 'tutorial' brings it back any time."

    if argument.isdigit():
        index = int(argument) - 1

        if not 0 <= index < len(tutorial.LESSONS):
            return (f"Sections are numbered 1 to {len(tutorial.LESSONS)}. "
                    "Type 'tutorial' to see them.")

        tutorial.set_position(index)
        return tutorial.render_lesson(index)

    # Anything else is treated as a topic, so "tutorial voice" works the
    # way someone would naturally expect it to.
    explanation = tutorial.explain(argument)

    if explanation:
        return explanation

    return (f"No tutorial section matches '{argument}'.\n\n"
            + tutorial.overview())


@command("explain", "Explain any command or subsystem in depth",
         usage="explain <topic>", dev_only=False, group="session")
def handle_explain_topic(user_input):
    if not _match_prefix(user_input, "explain "):
        return False

    topic = user_input[len("explain "):].strip()

    # 'explain file <path>' is the developer file-reader and predates this;
    # leave it alone.
    if topic.lower().startswith("file "):
        return False

    from core import tutorial

    explanation = tutorial.explain(topic)

    if explanation:
        return explanation

    # Falling through to the model is better than inventing an answer about
    # a feature that may not exist.
    return False


@command("help", "Show available commands", dev_only=False, group="session")
def handle_help(user_input):
    if not _match_exact(user_input, "help"):
        return False

    return _render_help(include_dev=DEV_MODE)


@command("dev help", "Show every developer command", group="session")
def handle_dev_help(user_input):
    if not _match_exact(user_input, "dev help"):
        return False

    if not DEV_MODE:
        return "Not in developer mode. Type 'dev mode' first."

    return _render_help(include_dev=True)


# ============================================================
# SESSION
# ============================================================

@command("dev mode", "Unlock developer tools with the owner passcode",
         dev_only=False, group="session")
def handle_dev_mode(user_input):
    global DEV_MODE, DEV_MODE_EXPIRES_AT, AUTONOMOUS_SERIAL_MODE

    if _match_exact(user_input, "dev mode"):
        _expire_dev_mode()

        if DEV_MODE:
            return "Developer mode is already ON."

        unlocked, message = dev_auth.unlock_interactive(ui.input_secret)
        DEV_MODE = bool(unlocked)
        DEV_MODE_EXPIRES_AT = (
            time.monotonic() + DEV_MODE_DURATION_SECONDS
            if unlocked
            else 0.0
        )
        # Serial work must be deliberately enabled for each unlocked session.
        AUTONOMOUS_SERIAL_MODE = False
        return message

    if _match_prefix(user_input, "dev mode "):
        return (
            "For privacy, never put the passcode in command text. Type only "
            "'dev mode'; a masked prompt will appear."
        )

    return False


@command("exit dev mode", "Return to the everyday command set",
         group="session")
def handle_exit_dev_mode(user_input):
    global DEV_MODE, DEV_MODE_EXPIRES_AT, AUTONOMOUS_SERIAL_MODE

    if not _match_exact(user_input, "exit dev mode"):
        return False

    DEV_MODE = False
    DEV_MODE_EXPIRES_AT = 0.0
    AUTONOMOUS_SERIAL_MODE = False
    return "Developer mode: OFF"


def _start_audio_mode():
    ready, report = _run_with_activity(
        "Checking voice setup",
        offline_voice.setup_report,
    )

    if not ready:
        return report

    voice_session.request_start()
    return (
        "Audio mode is starting. Type a message or speak after the listening "
        "status appears. Type 'text mode' or press Escape to return to the "
        "standard terminal."
    )


@command("voice mode", "Start offline audio chat by typing or speaking",
         dev_only=False, group="session")
def handle_voice_mode(user_input):
    if not _match_exact(user_input, "voice mode"):
        return False

    return _start_audio_mode()


@command("audio mode", "Start offline audio chat by typing or speaking",
         dev_only=False, group="session")
def handle_audio_mode(user_input):
    if not _match_exact(user_input, "audio mode"):
        return False

    return _start_audio_mode()


@command("exit audio", "Leave audio mode and use the standard text terminal",
         dev_only=False, group="session")
def handle_exit_audio(user_input):
    if not _match_exact(user_input, "exit audio"):
        return False

    return "Text mode is already active. Type 'audio mode' to speak again."


@command("text mode", "Switch spoken replies to the standard text terminal",
         dev_only=False, group="session")
def handle_text_mode(user_input):
    if not _match_exact(user_input, "text mode"):
        return False

    return "Text mode is already active. Type 'audio mode' to speak again."


@command("voice status", "Check the microphone, speaker, and speech models",
         dev_only=False, group="session")
def handle_voice_status(user_input):
    if not _match_exact(user_input, "voice status"):
        return False

    _ready, report = _run_with_activity(
        "Checking voice setup",
        offline_voice.setup_report,
    )
    return report


@command("health check", "Check the model, storage, search, memory, and voice",
         dev_only=False, group="session")
def handle_health_check(user_input):
    if not _match_exact(user_input, "health check"):
        return False

    return _run_with_activity(
        "Checking assistant health",
        health_check.report,
    )


@command("sing daisy bell", "Perform the offline robotic Daisy Bell chorus",
         dev_only=False, group="session")
def handle_sing_daisy_bell(user_input):
    if not _match_exact(user_input, "sing daisy bell"):
        return False

    ready, report = _run_with_activity(
        "Checking singing voice",
        offline_voice.setup_report,
    )

    if not ready:
        return report

    voice_session.request_daisy_bell()
    voice_session.request_start()
    return (
        "Preparing the machine-voice performance of Daisy Bell. The first "
        "performance is built and cached locally; later performances start "
        "immediately."
    )


# ============================================================
# HARDWARE
# ============================================================

@command("tdeck setup", "Check whether local T-Deck Bluetooth support is ready",
         dev_only=False, group="hardware")
def handle_tdeck_setup(user_input):
    if not _match_exact(user_input, "tdeck setup"):
        return False

    _ready, report = tdeck.setup_report()
    return report


@command("tdeck scan", "Find nearby Meshtastic devices over Bluetooth",
         dev_only=False, group="hardware")
def handle_tdeck_scan(user_input):
    if not _match_exact(user_input, "tdeck scan"):
        return False

    return _run_with_activity(
        "Scanning for the T-Deck over Bluetooth",
        tdeck.scan_report,
    )


@command("tdeck status", "Check the T-Deck connection and its current settings",
         dev_only=False, group="hardware")
def handle_tdeck_status(user_input):
    if not _match_exact(user_input, "tdeck status"):
        return False

    return _run_with_activity(
        "Reading T-Deck settings over Bluetooth",
        tdeck.status_report,
    )


@command("tdeck nodes", "List mesh nodes currently known by the T-Deck",
         dev_only=False, group="hardware")
def handle_tdeck_nodes(user_input):
    if not _match_exact(user_input, "tdeck nodes"):
        return False

    return _run_with_activity(
        "Reading the T-Deck mesh node list",
        tdeck.nodes_report,
    )


@command(
    "tdeck stable pairing",
    "Give the T-Deck one permanent Bluetooth PIN and configure it in one reboot",
    group="hardware",
)
def handle_tdeck_stable_pairing(user_input):
    if not DEV_MODE or not _match_exact(user_input, "tdeck stable pairing"):
        return False

    return _run_with_activity(
        "Stabilizing T-Deck Bluetooth in one transaction",
        tdeck.stable_pairing_report,
    )


@command(
    "tdeck pairing pin",
    "Show the saved permanent T-Deck Bluetooth PIN without connecting",
    group="hardware",
)
def handle_tdeck_pairing_pin(user_input):
    if not DEV_MODE or not _match_exact(user_input, "tdeck pairing pin"):
        return False

    return tdeck.saved_pairing_pin_report()


@command(
    "tdeck terminal",
    "Use the T-Deck keyboard and screen as a compact TORMENT_NEXUS terminal",
    group="hardware",
)
def handle_tdeck_terminal(user_input):
    if not DEV_MODE or not _match_exact(user_input, "tdeck terminal"):
        return False

    ready, report = tdeck.setup_report()

    if not ready:
        return report

    tdeck.request_terminal_start()
    return (
        "T-Deck terminal is starting over Bluetooth.\n\n"
        "Once the ONLINE message appears, type normally on the T-Deck. "
        "Only locally originated messages are accepted, and they are "
        "conversation-only—not tool commands. Stock Meshtastic text can use "
        "the configured radio channel, so devices sharing that channel key "
        "may be able to see it.\n\n"
        "Send '/exit' from the T-Deck, press Escape here, or type "
        "'exit tdeck terminal' on this computer to stop."
    )


@command("tdeck screen always on",
         "Keep the T-Deck display awake until you change it",
         group="hardware")
def handle_tdeck_screen_always_on(user_input):
    if not DEV_MODE or not _match_exact(
        user_input,
        "tdeck screen always on",
    ):
        return False

    return _run_with_activity(
        "Setting the T-Deck display to always on",
        tdeck.set_screen_always_on_report,
    )


@command("tdeck screen default",
         "Restore the T-Deck's normal one-minute display timeout",
         group="hardware")
def handle_tdeck_screen_default(user_input):
    if not DEV_MODE or not _match_exact(
        user_input,
        "tdeck screen default",
    ):
        return False

    return _run_with_activity(
        "Restoring the T-Deck display timeout",
        tdeck.restore_screen_default_report,
    )


@command("tdeck power saving off",
         "Prevent device sleep from overriding the always-on display",
         group="hardware")
def handle_tdeck_power_saving_off(user_input):
    if not DEV_MODE or not _match_exact(
        user_input,
        "tdeck power saving off",
    ):
        return False

    return _run_with_activity(
        "Disabling T-Deck power saving",
        tdeck.disable_power_saving_report,
    )


@command("tdeck power saving on",
         "Allow the T-Deck to sleep again when it is idle",
         group="hardware")
def handle_tdeck_power_saving_on(user_input):
    if not DEV_MODE or not _match_exact(
        user_input,
        "tdeck power saving on",
    ):
        return False

    return _run_with_activity(
        "Enabling T-Deck power saving",
        tdeck.enable_power_saving_report,
    )


# ============================================================
# MEMORY
# ============================================================

@command("show memories", "List every stored memory",
         dev_only=False, group="memory")
def handle_show_memories(user_input):
    if not _match_exact(user_input, "show memories"):
        return False

    active = mem.active_memories()

    if not active:
        return "No memories stored."

    return "\n".join("- " + item["memory"] for item in active)


@command("memory count", "How many memories are stored",
         dev_only=False, group="memory")
def handle_memory_count(user_input):
    if not _match_exact(user_input, "memory count"):
        return False

    return f"Stored memories: {len(mem.active_memories())}"


@command("forget", "Delete any stored memory that mentions this text",
         usage="forget <text>", dev_only=False, group="memory")
def handle_forget(user_input):
    if not _match_prefix(user_input, "forget "):
        return False

    target = user_input[7:].strip()

    if not target:
        return "Usage: forget <text>"

    removed = mem.forget_memory(target)

    if removed == 0:
        return f"No memories matched: {target}"

    return f"Removed {removed} memor{'y' if removed == 1 else 'ies'} matching: {target}"


# ============================================================
# FILES
# ============================================================

@command("list files", "List every file in the project", group="files")
def handle_list_files(user_input):
    if not DEV_MODE or not _match_exact(user_input, "list files"):
        return False

    files = file_utils.list_files()

    if not files:
        return "No files found."

    return "PROJECT FILES\n" + "=" * 58 + "\n" + "\n".join(files)


# The first token has to look like a filename -- carrying an extension or
# a path separator. Requiring a single token would have been wrong, since
# "read file main.py lines 5-40" is valid; requiring a dot or slash keeps
# that working while "read file this book later" stays a sentence.
_PATH_ARGUMENT = r"^\S*[./\\]\S*"


@command("read file", "Show a file's contents (add 'lines 5-40' to view just those lines)",
         usage="read file <name>", group="files",
         arg_pattern=_PATH_ARGUMENT)
def handle_read_file(user_input):
    if not DEV_MODE or not _match_prefix(user_input, "read file "):
        return False

    request = user_input[len("read file "):].strip()

    filename = request
    start_line = None
    end_line = None

    if " lines " in request.lower():
        parts = request.lower().split(" lines ")
        filename = request[:len(parts[0])].strip()

        try:
            start_line, end_line = parts[1].strip().split("-")
            start_line = int(start_line)
            end_line = int(end_line)
        except Exception:
            return "Invalid line format. Use: read file main.py lines 1-50"

        if start_line < 1 or end_line < 1:
            return "Line numbers start at 1. Use: read file main.py lines 1-50"

        if end_line < start_line:
            return "The ending line must be at or after the starting line."

    try:
        filepath = file_utils.safe_join(PROJECT_ROOT, filename)
    except file_utils.PathError as e:
        return f"{e}"

    if not os.path.exists(filepath):
        return f"File not found: {filename}"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        selected_start = start_line or 1
        selected_end = min(end_line or len(lines), len(lines))
        lines = lines[selected_start - 1:selected_end]
        omitted = 0

        if len(lines) > 400:
            omitted = len(lines) - 400
            lines = lines[:400]

        content = "".join(lines)

        if len(content) > 30_000:
            content = content[:30_000]
            content = content.rsplit("\n", 1)[0] + "\n"
            omitted = max(omitted, 1)

        note = (
            "\n[Output shortened for terminal responsiveness. "
            "Use 'read file <name> lines <start>-<end>' for another section.]\n"
            if omitted
            else ""
        )

        return (
            f"FILE: {filename}\n"
            + "=" * 58 + "\n"
            + content
            + note
            + "=" * 58
        )

    except Exception as e:
        return f"Error reading file: {e}"


@command("backup file", "Save a timestamped copy without replacing older backups",
         usage="backup file <path>", group="files",
         arg_pattern=_PATH_ARGUMENT)
def handle_backup_file(user_input):
    if not DEV_MODE or not _match_prefix(user_input, "backup file "):
        return False

    filename = user_input[len("backup file "):].strip()

    backup = file_utils.backup_file(filename)

    if backup:
        return f"Backup created: {backup}"

    return f"Could not back up: {filename}"


@command("search code", "Find a string across every .py file",
         usage="search code <term>", group="files")
def handle_search_code(user_input):
    if not DEV_MODE or not _match_prefix(user_input, "search code "):
        return False

    term = user_input[len("search code "):].strip().lower()

    if not term:
        return "Usage: search code <term>"

    matches = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "logs", ".git")]

        for name in files:
            if not name.endswith(".py"):
                continue

            path = os.path.join(root, name)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    for number, line in enumerate(f, start=1):
                        if term in line.lower():
                            rel = os.path.relpath(path, PROJECT_ROOT)
                            matches.append(f"{rel}:{number} - {line.strip()}")
            except Exception:
                continue

    if not matches:
        return f"No matches found for: {term}"

    header = f"SEARCH RESULTS: {term}  ({len(matches)} hits)"

    return header + "\n" + "=" * 58 + "\n" + "\n".join(matches[:100])


# ============================================================
# PROJECT
# ============================================================

@command("build project",
         "Create a small standalone project in the dump folder",
         usage="build project <description>",
         dev_only=False, group="project")
def handle_build_project(user_input):
    prefixes = ("build project ", "create project ", "make project ")
    matched = next(
        (prefix for prefix in prefixes if _match_prefix(user_input, prefix)),
        None,
    )

    if matched is None:
        return False

    request = user_input[len(matched):].strip()

    if not request:
        return "Usage: build project <description>"

    ui.set_generating(True)
    ui.set_status("Planning dump project")

    try:
        project, error = project_builder.build_project(request)
    except Exception:
        ui.finish_activity("Project build failed")
        raise

    ui.finish_activity(
        "Project build failed" if error else "Project created"
    )
    return project_builder.format_result(project, error)


@command("list projects", "List projects created in the dump folder",
         dev_only=False, group="project")
def handle_list_projects(user_input):
    if not _match_exact(user_input, "list projects"):
        return False

    projects = project_builder.list_projects()

    if not projects:
        return f"No generated projects yet.\nDump: {project_builder.DUMP_FOLDER}"

    return (
        "GENERATED PROJECTS\n"
        + "=" * 58 + "\n"
        + "\n".join(f"- {path}" for path in projects)
    )


@command("dump path", "Show where generated projects are saved",
         dev_only=False, group="project")
def handle_dump_path(user_input):
    if not _match_exact(user_input, "dump path"):
        return False

    return f"Project dump: {project_builder.ensure_dump_folder()}"


@command("show structure", "Show the project's folder and file layout", group="project")
def handle_show_structure(user_input):
    if not DEV_MODE or not _match_exact(user_input, "show structure"):
        return False

    out = ["PROJECT STRUCTURE", "=" * 58]

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "logs", ".git")]

        level = root.replace(PROJECT_ROOT, "").count(os.sep)
        indent = "    " * level

        out.append(f"{indent}{os.path.basename(root) or '.'}/")

        for name in files:
            if name.endswith(".py"):
                out.append(f"{indent}    {name}")

    return "\n".join(out)


@command("update project map", "Rescan the project so the file map reflects recent changes", group="project")
def handle_update_project_map(user_input):
    if not DEV_MODE or not _match_exact(user_input, "update project map"):
        return False

    project = project_mapper.build_project_map()

    return (
        "PROJECT MAP UPDATED\n" + "=" * 58 + "\n"
        + f"Files indexed: {len(project['files'])}\n"
        + f"Folders indexed: {len(project['folders'])}"
    )


@command("inspect project", "Show what the assistant knows about this project's files",
         group="project")
def handle_inspect_project(user_input):
    if not DEV_MODE or not _match_exact(user_input, "inspect project"):
        return False

    # Lives in project/, not next to this file.
    description_file = os.path.join(
        PROJECT_ROOT, "project", "project_description.json"
    )

    if not os.path.exists(description_file):
        return f"No project description found at {description_file}"

    try:
        with open(description_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        out = ["PROJECT ANALYSIS", "=" * 58]
        out.append(f"Name: {data.get('name', 'unknown')}")
        out.append("")
        out.append(data.get("description", ""))
        out.append("")
        out.append("SYSTEMS:")

        for system in data.get("systems", []):
            out.append(f"  - {system}")

        out.append("")
        out.append("FILES:")

        for name, role in data.get("files", {}).items():
            out.append(f"  {name}")
            out.append(f"      {role}")

        return "\n".join(out)

    except Exception as e:
        return f"Project inspection failed: {e}"


@command("explain file", "Summarise a file's functions and size",
         usage="explain file <name>", group="project",
         arg_pattern=_PATH_ARGUMENT)
def handle_explain_file(user_input):
    if not DEV_MODE or not _match_prefix(user_input, "explain file "):
        return False

    filename = user_input[len("explain file "):].strip()

    # file_analyzer was renamed to project_analyzer; the old call
    # still used the pre-rename name.
    analyze = getattr(project_analyzer, "analyze_file", None)

    if analyze is None:
        return "project_analyzer has no analyze_file() function."

    info = analyze(filename)

    if info is None:
        return f"File not found: {filename}"

    if "error" in info:
        return f"Analysis failed: {info['error']}"

    out = [
        "FILE ANALYSIS",
        "=" * 58,
        f"File:  {info.get('file', filename)}",
        f"Lines: {info.get('lines', '?')}",
        f"Size:  {info.get('size', '?')} characters",
        "",
        "Functions:",
    ]

    functions = info.get("functions") or []

    if functions:
        for func in functions:
            out.append(f"  - {func}")
    else:
        out.append("  - none detected")

    return "\n".join(out)


# ============================================================
# EDITING
# ============================================================

@command("modify plan", "Step 1 of 4: describe a code change you want made",
         usage="modify plan <file> <change>", group="editing",
         # The first argument is a file, so "modify plan for dinner" is
         # chat rather than a malformed invocation.
         arg_pattern=_PATH_ARGUMENT)
def handle_modify_plan(user_input):
    if not DEV_MODE or not _match_prefix(user_input, "modify plan "):
        return False

    request = user_input[len("modify plan "):].strip()
    parts = request.split(" ", 1)

    filename = parts[0]
    change = parts[1] if len(parts) > 1 else "No change description provided"

    steps = [
        f"Open {filename}",
        "Analyze current structure",
        f"Apply requested change: {change}",
        "Check for syntax errors",
        "Create backup before writing",
        "Save modified version",
    ]

    plan = change_planner.save_plan(filename, change, steps)

    return (
        "CHANGE PLAN CREATED\n" + "=" * 58 + "\n\n"
        f"Target: {filename}\n"
        f"Saved:  {plan}\n\n"
        "Review the plan before allowing edits."
    )


@command("approve plan", "Step 2 of 4: approve the change described in 'modify plan'",
         group="editing")
def handle_approve_plan(user_input):
    if not DEV_MODE or not _match_exact(user_input, "approve plan"):
        return False

    plans_folder = os.path.join(PROJECT_ROOT, "memory", "change_plans")

    if not os.path.exists(plans_folder):
        return "No plans exist."

    plans = sorted(os.listdir(plans_folder))

    if not plans:
        return "No plans exist."

    path = os.path.join(plans_folder, plans[-1])
    approval_manager.approve_plan(path)

    return (
        "PLAN APPROVED\n" + "=" * 58 + "\n\n"
        f"Approved: {path}\n\n"
        "Edit permission granted."
    )


@command("plan status", "Show which change (if any) is currently approved",
         group="editing")
def handle_plan_status(user_input):
    if not DEV_MODE or not _match_exact(user_input, "plan status"):
        return False

    plan = approval_manager.get_approved_plan()

    if plan:
        return f"APPROVED PLAN:\n{plan}"

    return "No approved plan."


@command("preview plan", "Step 3 of 4: generate the edit and show a diff before anything is written",
         group="editing")
def handle_preview_plan(user_input):
    if not DEV_MODE or not _match_exact(user_input, "preview plan"):
        return False

    return _run_with_activity(
        "Opening change preview",
        edit_engine.preview_plan,
    )


@command("confirm edit", "Step 4 of 4: write the previewed edit and reload", group="editing")
def handle_confirm_edit(user_input):
    if not DEV_MODE or not _match_exact(user_input, "confirm edit"):
        return False

    return _run_with_activity(
        "Applying confirmed code edit",
        edit_engine.confirm_edit,
    )


@command("cancel edit", "Throw away the previewed edit without writing anything", group="editing")
def handle_cancel_edit(user_input):
    if not DEV_MODE or not _match_exact(user_input, "cancel edit"):
        return False

    return edit_engine.cancel_edit()


@command("rollback", "Undo the most recent applied edit (or a specific one by backup name)",
         usage="rollback [backup]", group="editing",
         # A backup name, not a sentence -- "rollback that thought" is chat.
         arg_pattern=r"^\S+$")
def handle_rollback(user_input):
    if not DEV_MODE or not (
        _match_exact(user_input, "rollback")
        or _match_prefix(user_input, "rollback ")
    ):
        return False

    rest = user_input[len("rollback"):].strip()

    return _run_with_activity(
        "Preparing code rollback",
        lambda: edit_engine.rollback(rest or None),
    )


@command("list backups", "List saved backups, most recent first", group="editing")
def handle_list_backups(user_input):
    if not DEV_MODE or not _match_exact(user_input, "list backups"):
        return False

    return edit_engine.list_backups()


@command("suggest", "Get a few ideas for things worth improving (then use 'do <n>')",
         group="editing")
def handle_suggest(user_input):
    if not DEV_MODE or not _match_exact(user_input, "suggest"):
        return False

    suggestions, error = _run_with_activity(
        "Inspecting code for improvement ideas",
        suggestion_engine.generate,
    )

    if error:
        return f"COULD NOT SUGGEST ANYTHING\n{'=' * 58}\n\n{error}"

    lines = ["HERE'S WHAT I COULD DO\n" + "=" * 58]

    for i, s in enumerate(suggestions, start=1):
        lines.append(f"{i}. {s['title']}  ({s['file']})")

    lines.append("")
    lines.append("Say 'do 1' (or 2/3) to preview it as an edit. Nothing is written yet.")

    return "\n".join(lines)


@command("do", "Turn a numbered idea from 'suggest' into a previewed edit",
         usage="do <number>", group="editing",
         # "do" opens a great many ordinary sentences. Without this the
         # gate met "do it again" and "do you like music" with a
         # developer-mode refusal instead of a conversation.
         arg_pattern=r"^\d+$")
def handle_do_suggestion(user_input):
    if not DEV_MODE or not _match_prefix(user_input, "do "):
        return False

    arg = user_input[len("do "):].strip()

    try:
        index = int(arg)
    except ValueError:
        # Not "do <number>" -- most likely ordinary chat starting with
        # "do", e.g. "do you...". Let it fall through instead of
        # claiming input this command doesn't actually understand.
        return False

    suggestion = suggestion_engine.get(index)

    if not suggestion:
        return f"No suggestion #{index}. Run 'suggest' first."

    return _run_with_activity(
        f"Preparing suggested edit for {suggestion['file']}",
        lambda: edit_engine.propose(
            suggestion["file"],
            suggestion["change"],
        ),
    )


# ============================================================
# MUSIC
# ============================================================

_spotify = None
_spotify_desktop = None
_spotify_pending_selection = None
SPOTIFY_SELECTION_SECONDS = 120


def _get_spotify():
    global _spotify

    if _spotify is None:
        from visualizer.spotify_control import SpotifyControl
        _spotify = SpotifyControl()

    return _spotify


def _get_spotify_desktop():
    global _spotify_desktop

    if _spotify_desktop is None:
        from visualizer.spotify_control import SpotifyDesktop
        _spotify_desktop = SpotifyDesktop()

    return _spotify_desktop


def _spotify_action(operation):
    """Run a Spotify call, turning its errors into readable output."""
    from visualizer.spotify_control import SpotifyError

    try:
        return _run_with_activity("Talking to Spotify", operation)
    except SpotifyError as error:
        return f"SPOTIFY\n{'=' * 58}\n\n{error}"
    except Exception as error:
        return f"SPOTIFY FAILED\n{'=' * 58}\n\n{error}"


def _spotify_desktop_action(operation):
    """Run a local-client action without asking Spotify's Web API for access."""
    from visualizer.spotify_control import SpotifyError

    try:
        return _run_with_activity("Opening local Spotify", operation)
    except SpotifyError as error:
        return f"SPOTIFY (LOCAL)\n{'=' * 58}\n\n{error}"
    except Exception as error:
        return f"SPOTIFY (LOCAL) FAILED\n{'=' * 58}\n\n{error}"


def _get_local_player():
    from visualizer import local_player

    return local_player


def _clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _clear_spotify_selection():
    global _spotify_pending_selection
    existed = _spotify_pending_selection is not None
    _spotify_pending_selection = None
    return existed


def _spotify_track_label(track):
    title = str(track.get("title") or track.get("name") or "unknown track")
    artist = str(track.get("artist") or track.get("artists") or "unknown artist")
    return f"{title} - {artist}"


def _format_spotify_results(query, tracks):
    lines = [f"MUSIC RESULTS: {query}\n{'=' * 58}\n"]
    lines.append("Source: MusicBrainz metadata; selection opens Spotify search.\n")

    for number, track in enumerate(tracks, start=1):
        label = _spotify_track_label(track)
        album = str(track.get("release") or track.get("album") or "")
        duration_ms = track.get("length_ms") or track.get("duration_ms") or 0
        duration = _clock(float(duration_ms) / 1000) if duration_ms else "?"
        year = str(track.get("year") or "")

        lines.append(f"  [{number}] {label}")
        lines.append(f"      {album or 'unknown release'}"
                     f"{f' ({year})' if year else ''} - {duration}")

    lines.append(
        "\nReply with a number to open that result in Spotify, or type "
        "'spotify cancel'."
    )
    return "\n".join(lines)


def _search_spotify_picker(query):
    """Return five no-login metadata results for a local Spotify search."""
    from visualizer import music_metadata

    try:
        tracks = _run_with_activity(
            "Searching music metadata",
            lambda: music_metadata.search_recordings(query, limit=5),
        )
    except music_metadata.MusicMetadataError as error:
        return f"MUSIC SEARCH\n{'=' * 58}\n\n{error}"
    except Exception as error:
        return f"MUSIC SEARCH FAILED\n{'=' * 58}\n\n{error}"

    if not tracks:
        return f"MUSIC RESULTS\n{'=' * 58}\n\nNo tracks found for: {query}"

    global _spotify_pending_selection
    _spotify_pending_selection = {
        "query": query,
        "tracks": tracks[:5],
        "expires_at": time.monotonic() + SPOTIFY_SELECTION_SECONDS,
    }
    ui.set_music_status("Music search: choose a result"[:70])
    return _format_spotify_results(query, tracks[:5])


def _handle_spotify_selection(user_input):
    """Consume only clear picker replies; everything else remains normal chat."""
    global _spotify_pending_selection

    selection = _spotify_pending_selection
    if selection is None:
        return None

    text = (user_input or "").strip()
    lower = text.lower()

    if time.monotonic() >= selection["expires_at"]:
        _spotify_pending_selection = None
        if text.isdigit():
            return "That Spotify selection expired. Run 'spotify search <query>' again."
        return None

    if lower in ("spotify cancel", "cancel spotify", "cancel"):
        _spotify_pending_selection = None
        ui.set_music_status("")
        return "Spotify selection cancelled."

    if not text.isdigit():
        return None

    number = int(text)
    tracks = selection["tracks"]

    if not 1 <= number <= len(tracks):
        return (
            f"Choose a Spotify result from 1 to {len(tracks)}, or type "
            "'spotify cancel'."
        )

    track = tracks[number - 1]
    _spotify_pending_selection = None
    spotify_query = _spotify_track_label(track)
    result = _spotify_desktop_action(
        lambda: _get_spotify_desktop().search(spotify_query)
    )

    if result.startswith("SPOTIFY"):
        return result

    ui.set_music_status(f"Spotify selected: {spotify_query}"[:70])
    return (
        f"{result}\n\nSelected: {spotify_query}\n"
        "Spotify now has the exact title-and-artist search. Choose the matching "
        "result there to begin playback."
    )


def _play_local_track(query):
    """
    Play a file from the local library.

    Returns the message to show, or None to mean "no local track by that
    name" so the caller can fall back to Spotify. An ambiguous name is
    reported rather than guessed -- picking one silently would make the
    same command do different things as the folder grows.
    """
    player = _get_local_player()
    match, ambiguous = player.find_track(query)

    if ambiguous:
        listed = "\n".join(f"  {name}" for name in ambiguous)
        return (
            f"MUSIC\n{'=' * 58}\n\n"
            f"'{query}' matches more than one local track:\n\n{listed}\n\n"
            "Type more of the name."
        )

    if match is None:
        return None

    name, path = match

    try:
        player.get_player().play(name, path)
    except player.LocalPlaybackError as error:
        return f"MUSIC FAILED\n{'=' * 58}\n\n{error}"

    visualizer_result = ui.enter_music_mode()
    _, total = player.get_player().position()
    status = f"Playing {name} (local)"
    hud_status = status
    if "capture failed" in visualizer_result.lower():
        hud_status += " | visualizer idle: capture unavailable"
    ui.set_music_status(hud_status[:70])

    # Playback has already started. Speaking this confirmation now would talk
    # over the opening of the song, so audio mode displays it silently. Text
    # mode still receives an ordinary string-compatible result.
    if visualizer_result == "Music mode already on.":
        visualizer_note = "Visualizer is already open. Press Ctrl+B to leave it."
    elif visualizer_result.startswith("Music mode unavailable"):
        visualizer_note = visualizer_result
    else:
        visualizer_note = (
            "Visualizer opened automatically. Press Ctrl+B to leave it."
        )
    return voice_session.silent_reply(
        f"MUSIC\n{'=' * 58}\n\n{status} - {_clock(total)}\n\n"
        f"{visualizer_note}"
    )


@command("music mode", f"Toggle the audio-reactive visualizer "
                       f"(or press {ui.MUSIC_TOGGLE_LABEL})",
         dev_only=False, group="music")
def handle_music_mode(user_input):
    if not _match_exact(user_input, "music mode"):
        return False

    return ui.toggle_music_mode()


@command("volume", "Set the volume for local music playback",
         usage="volume <0-100>", dev_only=False, group="music")
def handle_local_music_volume(user_input):
    """Control only TORMENT_NEXUS's local player, never system/Spotify volume."""
    normalized = (user_input or "").strip()
    lower = normalized.lower()

    if lower == "volume":
        return (
            f"Local music volume: {ui.music_volume_percent()}%\n\n"
            "Use 'volume <0-100>'. This controls files played from the local "
            "music library; Spotify and browser audio keep their own controls."
        )

    if not lower.startswith("volume "):
        return False

    argument = normalized[len("volume"):].strip().rstrip("%")
    if argument.lower() == "up":
        value = ui.cycle_music_volume(5)
    elif argument.lower() == "down":
        value = ui.cycle_music_volume(-5)
    else:
        try:
            value = int(argument)
        except ValueError:
            return "Usage: volume <0-100>"
        if not 0 <= value <= 100:
            return "Volume must be from 0 to 100."
        value = ui.set_music_volume(value)

    return (
        f"Local music volume: {value}%\n\n"
        "This affects local files played through TORMENT_NEXUS. Spotify and "
        "browser audio retain their own volume controls."
    )


@command("spotify", "Open Spotify or search its catalogue from the terminal",
         usage="spotify [search <query>]", dev_only=False, group="music")
def handle_spotify_desktop(user_input):
    normalized = (user_input or "").strip()
    lower = normalized.lower()

    if lower == "spotify":
        return _spotify_desktop_action(lambda: _get_spotify_desktop().launch())

    if not lower.startswith("spotify "):
        return False

    argument = normalized[len("spotify"):].strip()
    lowered_argument = argument.lower()

    if lowered_argument in ("open", "launch", "start"):
        return _spotify_desktop_action(lambda: _get_spotify_desktop().launch())

    if lowered_argument in ("setup", "configure"):
        return (
            f"SPOTIFY PICKER\n{'=' * 58}\n\n"
            "No Spotify developer app, Premium account, or account token is "
            "needed. 'spotify search <song>' looks up five public music-metadata "
            "matches, then opens your numeric choice in the installed Spotify "
            "client.\n\n"
            "The lookup is online: the search text is sent to MusicBrainz. "
            "Spotify's own client remains responsible for playback."
        )

    if lowered_argument == "cancel":
        return (
            "Spotify selection cancelled."
            if _clear_spotify_selection()
            else "No Spotify selection is waiting."
        )

    if lowered_argument in ("help", "?"):
        return (
            f"SPOTIFY (LOCAL)\n{'=' * 58}\n\n"
            "spotify                    Open the installed desktop app.\n"
            "spotify search <query>     Show five no-login terminal results.\n"
            "spotify <query>            Same as a search.\n"
            "spotify cancel              Clear a numbered result picker.\n"
            "spotify setup               Explain the optional picker setup.\n\n"
            "No Spotify developer setup is needed. Search text goes to "
            "MusicBrainz for metadata; TORMENT_NEXUS then opens your chosen "
            "title-and-artist search in Spotify without reading its profile."
        )

    if lowered_argument == "search":
        return "Usage: spotify search <query>"

    query = argument[len("search"):].strip() \
        if lowered_argument.startswith("search ") else argument

    _clear_spotify_selection()
    return _search_spotify_picker(query)


@command("play playlist", "Start a Spotify playlist by name",
         usage="play playlist <name>", dev_only=False, group="music")
def handle_play_playlist(user_input):
    if not _match_prefix(user_input, "play playlist "):
        return False

    name = user_input[len("play playlist "):].strip()

    if not name:
        return "Usage: play playlist <name>"

    result = _spotify_action(lambda: _get_spotify().play_playlist(name))
    ui.set_music_status(result.splitlines()[0][:70])
    return result


@command("play", "Play a local track and open its visualizer, or use Spotify",
         usage="play <track>", dev_only=False, group="music")
def handle_play_track(user_input):
    if not _match_prefix(user_input, "play "):
        return False

    # "play playlist ..." belongs to the handler above; registration order
    # already favours it, but this keeps the two from tangling if the
    # command list is ever reordered.
    if _match_prefix(user_input, "play playlist "):
        return False

    query = user_input[len("play "):].strip()

    if not query:
        return "Usage: play <track>"

    # The local library is checked first on purpose. It is the only half
    # of this command that works with no network, so an offline Pi should
    # never have a local file lose a race to an account it cannot reach.
    local = _play_local_track(query)

    if local is not None:
        return local

    result = _spotify_action(lambda: _get_spotify().play_track(query))
    ui.set_music_status(result.splitlines()[0][:70])
    return result


@command("music library", "List the local tracks that play offline",
         dev_only=False, group="music")
def handle_music_library(user_input):
    if not _match_exact(user_input, "music library"):
        return False

    player = _get_local_player()
    tracks = player.available_tracks()

    if not tracks:
        return (
            f"MUSIC LIBRARY\n{'=' * 58}\n\n"
            "No local tracks yet.\n\n"
            f"Drop .mp3/.flac/.ogg/.wav files into:\n  {player.library_dir()}\n\n"
            "Each one becomes playable as: play <filename>"
        )

    lines = [f"MUSIC LIBRARY\n{'=' * 58}\n"]
    lines.append(f"{len(tracks)} track(s) in {player.library_dir()}\n")
    lines.extend(f"  play {name}" for name, _ in tracks)

    return "\n".join(lines)


@command("stop music", "Stop the local track that is playing",
         dev_only=False, group="music")
def handle_stop_music(user_input):
    if not _match_exact(user_input, "stop music"):
        return False

    player = _get_local_player().get_player()
    name = player.current_track()

    if not player.stop():
        return "Nothing is playing locally."

    ui.set_music_status("")
    return f"Stopped {name}."


@command("stop", "Stop an active local track without leaving the current mode",
         dev_only=False, group="music")
def handle_stop_active_local_music(user_input):
    """Reserve plain ``stop`` only while the offline player is genuinely live."""
    if not _match_exact(user_input, "stop"):
        return False

    player = _get_local_player().get_player()

    # Outside an active local playback session, ``stop`` is ordinary language
    # and should reach the conversation instead of pretending a command ran.
    if not player.is_loaded():
        return False

    name = player.current_track()

    if not player.stop():
        return False

    ui.set_music_status("")
    return f"Stopped {name}."


def _local_pause():
    """Pause local playback, or None when there is nothing to pause."""
    player = _get_local_player().get_player()
    name = player.current_track()

    if not player.pause():
        return None

    elapsed, total = player.position()
    ui.set_music_status(f"Paused {name}"[:70])

    return f"Paused {name} at {_clock(elapsed)} / {_clock(total)}."


def _local_resume():
    """Resume local playback, or None when nothing is paused."""
    player = _get_local_player().get_player()

    if not player.resume():
        return None

    name = player.current_track()
    ui.set_music_status(f"Playing {name} (local)"[:70])

    return f"Resumed {name}."


@command("pause local", "Pause the local track specifically",
         dev_only=False, group="music")
def handle_pause_local(user_input):
    if not _match_exact(user_input, "pause local"):
        return False

    # An explicit target never falls back to the other source. Saying
    # "local" and getting Spotify would be worse than being told nothing
    # was playing.
    return _local_pause() or "Nothing is playing locally."


@command("pause spotify", "Pause Spotify specifically",
         dev_only=False, group="music")
def handle_pause_spotify(user_input):
    if not _match_exact(user_input, "pause spotify"):
        return False

    return _spotify_action(lambda: _get_spotify().pause())


@command("resume local", "Resume the local track specifically",
         dev_only=False, group="music")
def handle_resume_local(user_input):
    if not _match_exact(user_input, "resume local"):
        return False

    return _local_resume() or "No local track is paused."


@command("resume spotify", "Resume Spotify specifically",
         dev_only=False, group="music")
def handle_resume_spotify(user_input):
    if not _match_exact(user_input, "resume spotify"):
        return False

    return _spotify_action(lambda: _get_spotify().resume())


@command("pause", "Pause the local track, or Spotify",
         dev_only=False, group="music")
def handle_pause(user_input):
    if not _match_exact(user_input, "pause"):
        return False

    # Bare "pause" still prefers local, which is the right guess when only
    # one thing is playing. "pause spotify" is there for when it is not.
    return _local_pause() or _spotify_action(lambda: _get_spotify().pause())


@command("resume", "Resume the local track, or Spotify",
         dev_only=False, group="music")
def handle_resume(user_input):
    if not _match_exact(user_input, "resume"):
        return False

    return _local_resume() or _spotify_action(lambda: _get_spotify().resume())


@command("skip", "Skip to the next track", dev_only=False, group="music")
def handle_skip(user_input):
    if not _match_exact(user_input, "skip"):
        return False

    return _spotify_action(lambda: _get_spotify().next_track())


@command("now playing", "Show the current local track, or Spotify's",
         dev_only=False, group="music")
def handle_now_playing(user_input):
    if not _match_exact(user_input, "now playing"):
        return False

    player = _get_local_player().get_player()

    if player.is_loaded():
        elapsed, total = player.position()
        state = "Playing" if player.is_playing() else "Paused"
        line = f"{state} {player.current_track()} (local)"
        ui.set_music_status(line[:70])
        return (
            f"NOW PLAYING\n{'=' * 58}\n\n"
            f"{line}\n{_clock(elapsed)} / {_clock(total)}"
        )

    result = _spotify_action(lambda: _get_spotify().now_playing())
    ui.set_music_status(result.splitlines()[0][:70])
    return result


@command("search", "Search the web directly and show the raw results",
         usage="search <query>", dev_only=False, group="web")
def handle_search(user_input):
    if not _match_prefix(user_input, "search "):
        return False

    # Keep the developer-only local-code command from being silently
    # reinterpreted as a web query while developer mode is off.
    if _match_prefix(user_input, "search code "):
        return "Type 'dev mode' before using: search code <term>"

    query = user_input[len("search "):].strip()

    if not query:
        return "Usage: search <query>"

    results, error = _run_with_activity(
        "Searching the web",
        lambda: search_engine.search(query),
    )

    if error:
        return f"SEARCH FAILED\n{'=' * 58}\n\n{error}"

    if not results:
        return f"No results for: {query}"

    lines = [f"SEARCH: {query}\n" + "=" * 58]

    for r in results:
        lines.append(f"\n{r['title']}\n{r['url']}\n{r['snippet']}")

    return "\n".join(lines)


def _goal_action(operation):
    """Run a goal-engine call, turning its errors into readable output."""
    from editing.goal_engine import GoalError

    try:
        return _run_with_activity("Working on goals", operation)
    except GoalError as error:
        return f"GOALS\n{'=' * 58}\n\n{error}"
    except Exception as error:
        return f"GOALS FAILED\n{'=' * 58}\n\n{error}"


@command("goals", "Show the sub-goals it set for itself",
         dev_only=False, group="editing")
def handle_show_goals(user_input):
    if not _match_exact(user_input, "goals"):
        return False

    from editing import goal_engine

    if not goal_engine.ENABLED:
        return (
            f"GOALS\n{'=' * 58}\n\n"
            "Self-directed goals are off.\n\n"
            "Set TORMENT_NEXUS_GOALS=1 to enable them. When on, it can choose\n"
            "its own sub-goals and write notes toward them into the\n"
            "workshop/ folder -- text files only, nothing executable, and\n"
            "nothing outside that folder."
        )

    goals = goal_engine.all_goals()

    if not goals:
        return (
            f"GOALS\n{'=' * 58}\n\n"
            "None yet. 'set goals' asks it to choose some."
        )

    lines = [f"GOALS\n{'=' * 58}\n"]
    legacy_indices = []

    for index, goal in enumerate(goals):
        mark = "done" if goal.get("done") else f"{goal.get('notes', 0)} steps"
        if (
            not goal.get("done")
            and not goal_engine._goal_is_project_relevant(
                goal.get("goal"), goal.get("why")
            )
        ):
            legacy_indices.append(str(index))
        lines.append(f"  [{index}] {goal['goal']}")
        if goal.get("why"):
            lines.append(f"       why: {goal['why']}")
        lines.append(f"       {mark}, set {goal.get('created', '?')}")
        lines.append("")

    if legacy_indices:
        lines.append(
            "Blocked legacy goal(s): " + ", ".join(legacy_indices) + ". "
            "They are unrelated to TORMENT_NEXUS; use 'goal done <n>' "
            "to close them before setting new goals."
        )
        lines.append("")

    lines.append(f"Workshop: {goal_engine.WORKSHOP}")
    lines.append("'work on goals' takes one step. 'goal done <n>' closes one.")

    return "\n".join(lines)


@command("set goals", "Let it choose new sub-goals for itself",
         group="editing")
def handle_set_goals(user_input):
    if not DEV_MODE or not _match_exact(user_input, "set goals"):
        return False

    from editing import goal_engine

    if not goal_engine.ENABLED:
        return "Self-directed goals are off. Set TORMENT_NEXUS_GOALS=1 first."

    result = _goal_action(goal_engine.propose_goals)

    if isinstance(result, str):
        return result

    lines = [f"NEW GOALS\n{'=' * 58}\n"]
    for item in result:
        lines.append(f"  {item['goal']}")
        if item["why"]:
            lines.append(f"    {item['why']}")
    lines.append("\n'work on goals' to start.")

    return "\n".join(lines)


@command("work on goals", "Take one step toward a self-chosen goal",
         group="editing")
def handle_work_on_goals(user_input):
    if not DEV_MODE or not _match_exact(user_input, "work on goals"):
        return False

    from editing import goal_engine

    if not goal_engine.ENABLED:
        return "Self-directed goals are off. Set TORMENT_NEXUS_GOALS=1 first."

    result = _goal_action(goal_engine.act)

    if isinstance(result, str):
        return result

    return (
        f"GOAL STEP {result['step']}\n{'=' * 58}\n\n"
        f"{result['goal']}\n\n"
        f"{result['mode']} {result['bytes']} bytes to {result['path']}"
    )


@command("goal done", "Close one of its goals",
         usage="goal done <number>", group="editing",
         arg_pattern=r"^\d+$")
def handle_goal_done(user_input):
    if not DEV_MODE or not _match_prefix(user_input, "goal done "):
        return False

    argument = user_input[len("goal done "):].strip()

    if not argument.isdigit():
        return "Usage: goal done <number>"

    from editing import goal_engine

    result = _goal_action(lambda: goal_engine.complete(int(argument)))

    if isinstance(result, str):
        return result

    return f"Closed: {result['goal']}"


@command("run autonomous cycle",
         "Trigger one guarded, no-approval self-improvement attempt",
         group="editing")
def handle_run_autonomous_cycle(user_input):
    if not DEV_MODE or not _match_exact(user_input, "run autonomous cycle"):
        return False

    # This command deliberately occupies the local model while it
    # proposes and validates an edit. Make that work visible instead
    # of presenting another apparently frozen prompt.
    ui.set_generating(True)
    serial = AUTONOMOUS_SERIAL_MODE
    ui.set_status("Observed serial self-repair" if serial else "self-improvement")

    try:
        result = (
            autonomous_engine.run_observed_serial()
            if serial else autonomous_engine.run_cycle()
        )
    finally:
        ui.finish_activity(
            "Observed serial repair completed" if serial
            else "Autonomous cycle completed"
        )

    summaries = result if serial else ([result] if result else [])

    if not summaries:
        return (
            "Nothing applied this run. Either the current budget is spent, "
            f"or check {autonomous_engine.LOG_FILE} for why every candidate "
            "was skipped."
        )

    # run_cycle() only ever returns a non-None value from its one
    # success path, so reaching here means a write actually happened.
    edit_engine.mark_restart_pending()

    if serial:
        completed = len(summaries)
        details = "\n".join(f"  {index}. {summary}"
                            for index, summary in enumerate(summaries, start=1))
        reward_note = ""

        # Three successful watched edits earn exactly one post-restart bonus
        # attempt. Persist only the backup references needed to verify and, if
        # necessary, restore this batch; it is a finite authorization, not a
        # durable autonomous setting.
        if completed == autonomous_engine.OBSERVED_SERIAL_LIMIT:
            from editing import self_heal_state

            records = autonomous_engine.last_observed_serial_records()
            if len(records) == completed and all(record.get("backup")
                                                 for record in records):
                try:
                    self_heal_state.begin_batch_reward(records)
                    reward_note = (
                        "\n\nA single bonus repair has been earned. After the "
                        "restart, TORMENT_NEXUS will run its fixed health and "
                        "regression checks before it may use that credit."
                    )
                except Exception as error:
                    reward_note = (
                        "\n\nThe batch is applied, but the bonus credit could "
                        f"not be recorded: {error}"
                    )

        return (
            f"OBSERVED SERIAL REPAIR\n{'=' * 58}\n\n"
            f"Applied {completed} guarded edit{'s' if completed != 1 else ''} "
            f"(maximum {autonomous_engine.OBSERVED_SERIAL_LIMIT}).\n\n"
            f"{details}{reward_note}\n\n"
            "Reloading once so the accepted changes take effect."
        )

    return f"{summaries[0]}\n\nReloading so the change takes effect."


@command("autonomous serial",
         "Toggle watched batches of up to three guarded self-repairs",
         usage="autonomous serial [on|off|status]", group="editing")
def handle_autonomous_serial(user_input):
    """Keep serial mode explicit and memory-only for the current dev session."""
    global AUTONOMOUS_SERIAL_MODE

    if not DEV_MODE or not _match_prefix(user_input, "autonomous serial"):
        return False

    argument = user_input[len("autonomous serial"):].strip().lower()

    if argument in ("", "status"):
        state = "ON" if AUTONOMOUS_SERIAL_MODE else "OFF"
        return (
            f"OBSERVED SERIAL MODE: {state}\n{'=' * 58}\n\n"
            "When ON, 'run autonomous cycle' can apply up to "
            f"{autonomous_engine.OBSERVED_SERIAL_LIMIT} small guarded edits "
            "while this developer-mode session stays open. Each edit is backed "
            "up and import-tested; the assistant reloads once after the batch."
        )

    if argument == "on":
        AUTONOMOUS_SERIAL_MODE = True
        return (
            "Observed serial mode: ON\n\n"
            f"The next 'run autonomous cycle' may apply up to "
            f"{autonomous_engine.OBSERVED_SERIAL_LIMIT} small, allowlisted "
            "edits. It remains limited to this developer-mode session and "
            "turns off when developer mode closes or expires."
        )

    if argument == "off":
        AUTONOMOUS_SERIAL_MODE = False
        return "Observed serial mode: OFF. The next cycle is limited to one edit."

    return "Usage: autonomous serial [on|off|status]"


# ============================================================
# DISPATCH
# ============================================================

def _matches_registered_syntax(user_input, entry):
    """
    Does this text look like a complete invocation of this entry?

    The argument has to look like an argument, not merely be present.
    Without that check any sentence opening with a command word was read
    as an attempted invocation and refused: "do you like music" answered
    "Developer mode is required for: do <number>", and six other ordinary
    phrases behaved the same way. Handlers already fall through on input
    they cannot parse, but this gate runs first, so it has to be at least
    as careful as they are.
    """
    lower = user_input.lower().strip()
    name = entry["name"].lower()

    if lower == name:
        return "<" not in entry["usage"]

    if not lower.startswith(name + " "):
        return False

    if "<" not in entry["usage"] and "[" not in entry["usage"]:
        return False

    argument = lower[len(name):].strip()

    if not argument:
        return False

    pattern = entry.get("arg_pattern")

    if pattern is not None:
        return re.match(pattern, argument, re.IGNORECASE) is not None

    return True


def try_handle_command(user_input):
    """Return the command's response, or None if nothing matched."""
    if not user_input or not user_input.strip():
        return None

    _expire_dev_mode()
    user_input = user_input.strip()

    spotify_selection = _handle_spotify_selection(user_input)
    if spotify_selection is not None:
        return spotify_selection

    # Enforce the registry's developer boundary in one place before any
    # handler runs. Individual handlers retain their own DEV_MODE checks as
    # defense in depth, but a forgotten check can no longer expose a new tool.
    for entry in sorted(COMMANDS, key=lambda item: len(item["name"]), reverse=True):
        if (
            entry["dev_only"]
            and entry["name"] != "exit dev mode"
            and not DEV_MODE
            and _matches_registered_syntax(user_input, entry)
        ):
            return (
                f"Developer mode is required for: {entry['usage']}\n\n"
                "Type 'dev mode' first."
            )

    for entry in COMMANDS:
        result = entry["handler"](user_input)

        # False means "not mine". A command that legitimately returns
        # an empty string still counts as handled.
        if result is not False and result is not None:
            return result

    return None
