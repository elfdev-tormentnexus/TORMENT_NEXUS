import os
import json
import ipaddress
import re
import time
import sys
from urllib.parse import urlsplit

import requests

from memory import memory_store as mem
from memory import semantic_index
from ui import ui
from core import chosen_name
from core import file_utils
from core import health_check
from core import source_awareness
from core import dev_auth
from core.config import (
    MODEL_ROLE,
    MODEL_ROLE_AUTONOMOUS_CODER,
    MODEL_ROLE_DIRECTOR,
    MODEL_ROLE_FULL_MAINTENANCE,
    MODEL_ROLE_SUPER_DEV,
    MODEL_REQUEST_HEADERS,
    SERVER_URL,
    SUPER_DEV_SESSION_MAX_SECONDS,
)
from project import project_mapper
from project import project_analyzer
from project import project_builder
from editing import change_planner
from editing import approval_manager
from editing import edit_engine
from editing import suggestion_engine
from editing import autonomous_engine
from editing import super_dev_engine
from web import search_engine
from voice import offline_voice
from voice import freestyle_song
from voice import local_song_loader
from voice import session as voice_session
from hardware import tdeck
from core import escalation
from knowledge import library as knowledge_library


_FREESTYLE_HTTP = requests.Session()
# A loopback URL routed through an environment proxy is no longer local.
_FREESTYLE_HTTP.trust_env = False


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
SUPER_DEV_MODE = False
SUPER_DEV_MODE_EXPIRES_AT = 0.0
SUPER_DEV_MODE_DURATION_SECONDS = 30 * 60

# Experimental mode: SABLE7 token trajectories, deliberately slower.
#
# A sentence embedding is a mean over its token vectors. This mode keeps the
# path instead of only the mean, on the theory that the discarded structure
# carries usable semantics. That theory is NOT established -- late
# interaction over trajectories retrieved the same documents as plain
# pooled cosine in the only measurement taken so far, and three unlabelled
# queries is too small to conclude either way. See
# docs/VECTOR_TRANSLATION_RESEARCH.md.
#
# So this mode SHADOWS rather than replaces. Retrieval answers exactly as it
# always did, and the trajectory ranking is computed alongside and logged.
# The mode's first job is to produce the evidence that would justify it,
# which is the honest order to do this in: nothing downstream changes until
# the numbers say it should.
#
# It expires like dev mode does, because it costs a second resident
# embedding server -- llama.cpp fixes pooling at launch, so trajectories
# cannot come from the pooled instance -- and makes every retrieval slower.
EXPERIMENTAL_MODE = os.environ.get(
    "TORMENT_NEXUS_EXPERIMENTAL", "").strip().lower() in {"1", "true", "on", "yes"}
EXPERIMENTAL_MODE_EXPIRES_AT = 0.0
EXPERIMENTAL_MODE_DURATION_SECONDS = 60 * 60

# Started from the environment means started deliberately, by a launcher
# built for it, so it does not expire out from under a session that exists
# to run in this mode. Toggled from inside a normal session it does.
EXPERIMENTAL_MODE_FROM_ENV = EXPERIMENTAL_MODE

_ROLE_LABELS = {
    MODEL_ROLE_DIRECTOR: "director",
    MODEL_ROLE_AUTONOMOUS_CODER: "autonomous coder",
    MODEL_ROLE_FULL_MAINTENANCE: "full-maintenance coder",
    MODEL_ROLE_SUPER_DEV: "Super Dev 14B planner",
}


def _role_denial(action, *allowed_roles):
    allowed = " or ".join(
        _ROLE_LABELS.get(role, role)
        for role in allowed_roles
    )
    current = _ROLE_LABELS.get(MODEL_ROLE, "restricted")
    return (
        f"{action} belongs to the {allowed} profile. "
        f"Current profile: {current}."
    )


def is_dev_mode():
    _expire_dev_mode()
    return DEV_MODE


def _expire_dev_mode():
    global DEV_MODE, DEV_MODE_EXPIRES_AT, AUTONOMOUS_SERIAL_MODE
    global SUPER_DEV_MODE, SUPER_DEV_MODE_EXPIRES_AT

    if (
        DEV_MODE
        and DEV_MODE_EXPIRES_AT
        and time.monotonic() >= DEV_MODE_EXPIRES_AT
    ):
        DEV_MODE = False
        DEV_MODE_EXPIRES_AT = 0.0
        AUTONOMOUS_SERIAL_MODE = False
        SUPER_DEV_MODE = False
        SUPER_DEV_MODE_EXPIRES_AT = 0.0


def is_super_dev_mode():
    _expire_super_dev_mode()
    return SUPER_DEV_MODE


def _expire_super_dev_mode():
    global SUPER_DEV_MODE, SUPER_DEV_MODE_EXPIRES_AT

    if (
        SUPER_DEV_MODE
        and SUPER_DEV_MODE_EXPIRES_AT
        and time.monotonic() >= SUPER_DEV_MODE_EXPIRES_AT
    ):
        SUPER_DEV_MODE = False
        SUPER_DEV_MODE_EXPIRES_AT = 0.0


def is_experimental_mode():
    _expire_experimental_mode()
    return EXPERIMENTAL_MODE


def _expire_experimental_mode():
    global EXPERIMENTAL_MODE, EXPERIMENTAL_MODE_EXPIRES_AT

    if EXPERIMENTAL_MODE_FROM_ENV:
        return

    if (
        EXPERIMENTAL_MODE
        and EXPERIMENTAL_MODE_EXPIRES_AT
        and time.monotonic() >= EXPERIMENTAL_MODE_EXPIRES_AT
    ):
        EXPERIMENTAL_MODE = False
        EXPERIMENTAL_MODE_EXPIRES_AT = 0.0


def experimental_mode_remaining():
    """Seconds left, or 0.0 when the mode is off."""
    if not is_experimental_mode() or not EXPERIMENTAL_MODE_EXPIRES_AT:
        return 0.0
    return max(0.0, EXPERIMENTAL_MODE_EXPIRES_AT - time.monotonic())


def machinespirit_status():
    """One honest line about whether the trajectory server is really there.

    Both embedders have to be up, and they fail for different reasons, so
    the line names the one that is actually missing rather than the one
    that is more famous for being missing.
    """
    from core import machinespirit

    status = machinespirit.diagnose()
    if not status["ready"]:
        return status["reason"]

    book = status["dictionary"]
    total = book["core"] + book["project"] + book["life"]
    return (f"machinespirit is live: per-token trajectories available, "
            f"read against {total} anchors (dictionary v{book['version']}).")


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
        "knowledge",
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
    global SUPER_DEV_MODE, SUPER_DEV_MODE_EXPIRES_AT

    if not _match_exact(user_input, "exit dev mode"):
        return False

    DEV_MODE = False
    DEV_MODE_EXPIRES_AT = 0.0
    AUTONOMOUS_SERIAL_MODE = False
    SUPER_DEV_MODE = False
    SUPER_DEV_MODE_EXPIRES_AT = 0.0
    return "Developer mode: OFF"


@command("super dev mode", "Unlock the hazard-only two-model repair session",
         dev_only=False, group="session")
def handle_super_dev_mode(user_input):
    """Unlock once, then begin one bounded 14B-plan / 7B-patch session."""
    global SUPER_DEV_MODE, SUPER_DEV_MODE_EXPIRES_AT

    if _match_prefix(user_input, "super dev mode "):
        return (
            "For privacy, never put the Super Dev key in command text. "
            "Type only 'super dev mode'; a masked prompt will appear."
        )
    if not _match_exact(user_input, "super dev mode"):
        return False
    if not is_experimental_mode():
        return "Super Dev is available only from TORMENT_NEXUS_HAZARD."
    if MODEL_ROLE != MODEL_ROLE_SUPER_DEV:
        return (
            "Super Dev needs start_super_dev_hazard.bat, which starts the "
            "separate 14B planner and 7B patch worker."
        )

    _expire_super_dev_mode()
    if not SUPER_DEV_MODE:
        unlocked, message = dev_auth.unlock_super_interactive(ui.input_secret)
        if not unlocked:
            return message
        SUPER_DEV_MODE = True
        SUPER_DEV_MODE_EXPIRES_AT = (
            time.monotonic() + SUPER_DEV_MODE_DURATION_SECONDS
        )
    else:
        message = "Super Dev remains unlocked for this short-lived session."

    ui.set_generating(True)
    try:
        applied, result = super_dev_engine.run_session()
    finally:
        ui.finish_activity("Super Dev session completed")

    if applied:
        edit_engine.mark_restart_pending()
        return message + "\n\n" + result + "\n\nReloading to activate the verified patch."
    return message + "\n\n" + result


@command("super dev status", "Show the hazard-only Super Dev boundary",
         dev_only=False, group="session")
def handle_super_dev_status(user_input):
    if not _match_exact(user_input, "super dev status"):
        return False

    _expire_super_dev_mode()
    active = "ON" if SUPER_DEV_MODE else "OFF"
    ready, worker = super_dev_engine.worker_status()
    return (
        f"SUPER DEV: {active}\n{'=' * 58}\n\n"
        "Only the hazard launcher may use this mode.  The 14B model plans "
        "from a fixed project allowlist; the loopback-only 7B worker drafts "
        "one small patch; trusted guards run syntax, capability, backup, and "
        "fixed regression checks. It cannot read chat/memory/web content, "
        "run shell commands, change credentials, push Git, or edit its own "
        f"guards.\n\nWorker: {worker}\nAudit: {super_dev_engine.LOG_FILE}"
    )


# Toggles that start a sensor or open private memory. The Super Dev key is
# the consent step for these: it is enrolled once at a masked prompt, stored
# only as a PBKDF2 verifier, and never accepted in command text -- so nothing
# reaches this function without the operator having authenticated as the
# person who owns the microphone. That is why "enable all" is allowed to
# cross the line here and nowhere else in the project.
#
# What it still cannot do is turn on anything that needs a launcher flag or a
# credential this process was never given. Those are reported, not faked.
_SENSOR_FEATURES = ("activity awareness", "microphone and offline speech")


def _enable_sensor_features():
    """Start the opt-in sensors, returning (started, unavailable) lines.

    Shared by the ordinary and Super Dev forms of "enable all", so the two
    cannot drift into enabling different things under similar names. Typing
    the command is itself the consent act, which is why each line says
    exactly what began and how to stop it -- a switch you cannot find again
    is not a switch you consented to.
    """
    started = []
    unavailable = []

    awareness = _get_system_awareness()
    if awareness is None:
        unavailable.append("activity awareness -- not available in this session")
    else:
        awareness.set_enabled(True)
        days = awareness.retention_days
        unit = "day" if days == 1 else "days"
        started.append(
            "activity awareness -- foreground window titles sampled every "
            f"20s, retained {days:g} {unit}. 'activity off' stops it and "
            "deletes the log"
        )

    report = _start_audio_mode()
    text = report if isinstance(report, str) else ""
    # setup_report() can say "ready" and then list a dead audio device in the
    # same breath -- it reports readiness to synthesise, not to be heard. A
    # substring match on "ready" therefore announces speech as on while
    # nothing can play, which is worse than saying it failed. Carry the
    # warnings it raised instead of reducing them to a yes.
    warnings = [
        line.strip(" -")
        for line in text.splitlines()
        if line.strip().startswith("-") and line.strip(" -")
    ]
    if "ready" not in text.lower():
        unavailable.append(
            f"microphone and speech -- {text.splitlines()[0] if text else 'unavailable'}"
        )
    elif warnings:
        started.append(
            "offline speech -- synthesising, but: " + "; ".join(warnings)
        )
    else:
        started.append(
            "microphone and offline speech -- listening; 'exit audio' returns "
            "to the text terminal"
        )

    return started, unavailable


@command("enable all features",
         "Turn on every opt-in feature this session can start",
         dev_only=False, group="session")
def handle_enable_all_features(user_input):
    """The ordinary-mode form. No key, because typing it is the consent."""
    if not _match_exact(user_input, "enable all features"):
        return False

    started, unavailable = _enable_sensor_features()

    if not started:
        body = "  --    nothing could be started in this session"
    else:
        body = "\n".join(f"  ON    {item}" for item in started)

    out = f"ALL FEATURES\n{'=' * 58}\n\n{body}"
    if unavailable:
        blocked = "\n".join(f"  --    {item}" for item in unavailable)
        out += "\n\nNot turned on, because this session cannot:\n\n" + blocked

    out += (
        "\n\nEach of these is individually reversible with the command named "
        "beside it. machinespirit, the two-model repair session, and the "
        "research instruments live in TORMENT_NEXUS_HAZARD rather than here."
    )
    return out


def _enable_all_experimental_features():
    """Turn on every experimental surface this process is able to set."""
    global EXPERIMENTAL_MODE, EXPERIMENTAL_MODE_EXPIRES_AT

    enabled = []
    unavailable = []

    # machinespirit's own timeout is an hour, which is shorter than a YOLO
    # window. Extending it to match keeps the trajectory reader alive for the
    # whole unattended run instead of lapsing partway through.
    window = super_dev_engine._describe_window(SUPER_DEV_SESSION_MAX_SECONDS)
    if EXPERIMENTAL_MODE_FROM_ENV:
        enabled.append("machinespirit -- already held on by the launcher")
    else:
        EXPERIMENTAL_MODE = True
        EXPERIMENTAL_MODE_EXPIRES_AT = (
            time.monotonic() + SUPER_DEV_SESSION_MAX_SECONDS
        )
        enabled.append(
            f"machinespirit -- extended to {window}, so the trajectory "
            "reader outlasts a full session"
        )

    sensors_on, sensors_off = _enable_sensor_features()
    enabled.extend(sensors_on)
    unavailable.extend(sensors_off)

    body = "\n".join(f"  ON    {item}" for item in enabled)
    out = f"EXPERIMENTAL FEATURES\n{'=' * 58}\n\n{body}"

    if unavailable:
        blocked = "\n".join(f"  --    {item}" for item in unavailable)
        out += (
            "\n\nNot turned on, because this process cannot:\n\n" + blocked
        )

    out += (
        "\n\nThe Super Dev key was the consent step for the sensors above. "
        "The cloud escalation path, the agent API, and the Wi-Fi seam each "
        "need a launcher flag or a credential this process was not given, "
        "so they stay off regardless of this command."
    )
    return out


def _require_super_dev(what):
    """Shared gate for commands that exist only under Super Dev permission.

    Returns a refusal string when the caller is not entitled, or None when
    the command may run. Each condition is reported separately: "not
    unlocked" and "wrong launcher" need different actions from the operator,
    and collapsing them into one message sends people to the wrong fix.
    """
    if not is_experimental_mode():
        return f"{what} is available only from TORMENT_NEXUS_HAZARD."
    if MODEL_ROLE != MODEL_ROLE_SUPER_DEV:
        return (
            f"{what} needs start_super_dev_hazard.bat, which starts the "
            "separate 14B planner and 7B patch worker."
        )
    _expire_super_dev_mode()
    if not SUPER_DEV_MODE:
        return (
            f"{what} requires Super Dev permission. Type 'super dev mode' "
            "and enter your key at the masked prompt first."
        )
    return None


@command("yolo mode",
         "Run the unattended Super Dev session for its full window",
         dev_only=False, group="session")
def handle_yolo_mode(user_input):
    """The overnight run. Same gates per patch; the window is the bound."""
    if not _match_exact(user_input, "yolo mode"):
        return False

    refusal = _require_super_dev("YOLO mode")
    if refusal:
        return refusal

    window = super_dev_engine._describe_window(SUPER_DEV_SESSION_MAX_SECONDS)
    ui.set_generating(True)
    try:
        applied, result = super_dev_engine.run_session()
    finally:
        ui.finish_activity("YOLO session completed")

    header = (
        f"YOLO MODE\n{'=' * 58}\n\nUnattended session, window {window}. "
        "Every patch passed the allowlist, capability, line-cap, backup, "
        "and regression gates on its own.\n\n"
    )
    if applied:
        edit_engine.mark_restart_pending()
        return header + result + "\n\nReloading to activate the verified work."
    return header + result


@command("enable all experimental features",
         "Turn on every experimental toggle Super Dev is allowed to set",
         dev_only=False, group="session")
def handle_enable_all_experimental(user_input):
    if not _match_exact(user_input, "enable all experimental features"):
        return False

    refusal = _require_super_dev("Enabling all experimental features")
    if refusal:
        return refusal

    return _enable_all_experimental_features()


@command("exit super dev mode", "Lock Super Dev without changing ordinary developer mode",
         dev_only=False, group="session")
def handle_exit_super_dev_mode(user_input):
    global SUPER_DEV_MODE, SUPER_DEV_MODE_EXPIRES_AT
    if not _match_exact(user_input, "exit super dev mode"):
        return False
    SUPER_DEV_MODE = False
    SUPER_DEV_MODE_EXPIRES_AT = 0.0
    return "Super Dev: OFF"


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


@command(
    "sing come josephine",
    "Perform Come Josephine and an original answering verse offline",
    dev_only=False,
    group="session",
)
def handle_sing_come_josephine(user_input):
    if not _match_exact(user_input, "sing come josephine"):
        return False

    ready, report = _run_with_activity(
        "Checking singing voice",
        offline_voice.setup_report,
    )

    if not ready:
        return report

    voice_session.request_song("come_josephine")
    voice_session.request_start()
    return (
        "Preparing the machine-voice performance of Come Josephine. It "
        "states the 1910 tune first, sings the public-domain chorus, then "
        "answers it with an original verse. The performance stays offline "
        "and is cached locally after the first build."
    )


_LOCAL_SONG_COMMAND_ISSUES = []


def _local_song_handler(entry):
    """Build one ordinary command handler around a validated private Song."""
    def handle(user_input):
        if not _match_exact(user_input, entry.command):
            return False

        ready, report = _run_with_activity(
            "Checking singing voice",
            offline_voice.setup_report,
        )

        if not ready:
            return report

        voice_session.request_song(entry.song)
        voice_session.request_start()
        return voice_session.silent_reply(
            f"Preparing the private local performance of {entry.song.name}. "
            "Its score and cache remain on this computer."
        )

    return handle


def _register_local_song_commands(directory=None):
    """Register strict LocalAppData song definitions, if the operator has any."""
    result = local_song_loader.load_local_songs(
        offline_voice.Song,
        directory=directory,
    )
    existing = {entry["name"] for entry in COMMANDS}
    _LOCAL_SONG_COMMAND_ISSUES.extend(result.issues)

    for entry in result.entries:
        if entry.command in existing:
            _LOCAL_SONG_COMMAND_ISSUES.append(local_song_loader.LocalSongIssue(
                entry.source_name,
                "command collides with a built-in command",
            ))
            continue

        command(
            entry.command,
            f"Perform {entry.song.name} from a private local score",
            dev_only=False,
            group="session",
        )(_local_song_handler(entry))
        existing.add(entry.command)

    return result


_LOCAL_SONG_LOAD_RESULT = _register_local_song_commands()


def _freestyle_model_endpoint():
    """Return the director endpoint only when it is unambiguously loopback."""
    try:
        parsed = urlsplit(SERVER_URL)
        port = parsed.port
    except (TypeError, ValueError):
        raise RuntimeError("the local model endpoint is malformed")

    host = (parsed.hostname or "").rstrip(".").lower()

    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "localhost"

    if (
        parsed.scheme not in {"http", "https"}
        or not loopback
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or port is None
    ):
        raise RuntimeError(
            "sing what you want requires a loopback-only local model endpoint"
        )

    return SERVER_URL.rstrip("/") + "/v1/chat/completions"


def _freestyle_song_transport(request_text):
    """One bounded local-model call; validation remains in trusted Python."""
    tune_counts = offline_voice.freestyle_slot_counts()
    response = _FREESTYLE_HTTP.post(
        _freestyle_model_endpoint(),
        headers=MODEL_REQUEST_HEADERS,
        json={
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You write original lyric syllables for a local "
                        "offline music tool. Follow the supplied JSON "
                        "contract exactly. Every word must have exactly one "
                        "contiguous vowel group. Never emit notes or "
                        "instructions."
                    ),
                },
                {"role": "user", "content": request_text},
            ],
            "temperature": 0.65,
            "max_tokens": 1_600,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
            # The vendored llama.cpp runtime converts this into a grammar, so
            # malformed JSON and wrong-length arrays cannot be sampled. The
            # pure Python parser/validator still checks the reply afterward.
            "json_schema": freestyle_song.build_json_schema(tune_counts),
        },
        timeout=120,
        allow_redirects=False,
    )

    if 300 <= response.status_code < 400:
        raise RuntimeError("the local model attempted a redirect")

    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") or []

    if not choices:
        raise RuntimeError("the local model returned no lyric choice")

    content = choices[0].get("message", {}).get("content")

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("the local model returned an empty lyric choice")

    return content


@command(
    "sing what you want",
    "Write syllables locally and fit them to one fixed trusted tune",
    usage="sing what you want [about <subject>]",
    dev_only=False,
    group="session",
)
def handle_sing_what_you_want(user_input):
    stripped = " ".join((user_input or "").strip().split())
    lowered = stripped.lower()

    if lowered == "sing what you want":
        subject = ""
    elif lowered.startswith("sing what you want about "):
        subject = stripped[len("sing what you want about "):].strip()

        if not subject:
            return "Usage: sing what you want [about <subject>]"
    else:
        return False

    ready, report = _run_with_activity(
        "Checking singing voice",
        offline_voice.setup_report,
    )

    if not ready:
        return report

    try:
        draft = _run_with_activity(
            "Writing bounded lyric syllables",
            lambda: freestyle_song.generate(
                subject,
                offline_voice.freestyle_slot_counts(),
                transport=_freestyle_song_transport,
            ),
        )
        song = offline_voice.freestyle_song_from_draft(draft)
    except freestyle_song.FreestyleSongError as error:
        return (
            "I could not produce a structurally valid song, so nothing was "
            f"queued: {error}"
        )
    except ValueError as error:
        return f"The generated song failed its fixed-score check: {error}"

    voice_session.request_song(song)
    voice_session.request_start()
    return voice_session.silent_reply(
        f"I chose {draft.tune_key.replace('_', ' ')} and wrote "
        f"'{draft.title}'. The notes and timing remain fixed; only the "
        "validated syllables are new."
    )


# ============================================================
# HARDWARE
# ============================================================

@command(
    "wifi sensing",
    "Control the opt-in desktop Wi-Fi sensing experiment",
    usage="wifi sensing [on|off|status|forget]",
    dev_only=False,
    group="hardware",
)
def handle_wifi_sensing(user_input):
    """Consent gate for the aggregate-only Wi-Fi experiment bridge."""
    normalized = " ".join(str(user_input or "").lower().split())
    accepted = {
        "wifi sensing",
        "wifi sensing on",
        "wifi sensing off",
        "wifi sensing status",
        "wifi sensing forget",
    }
    if normalized not in accepted:
        return False

    experiment = _get_wifi_experimental()
    if experiment is None:
        return "Wi-Fi sensing is not available in this session."

    if normalized == "wifi sensing on":
        if not experiment.configured:
            return (
                "Wi-Fi sensing remains off: no local aggregate-feed path is "
                "configured. This command never changes a wireless driver, "
                "captures packets, or starts a radio experiment by itself."
            )
        experiment.set_enabled(True)
        return experiment.status()

    if normalized == "wifi sensing off":
        experiment.set_enabled(False)
        return (
            "Wi-Fi sensing is off. Its current aggregate reading was cleared; "
            "TORMENT_NEXUS does not keep radio samples or a sensing history."
        )

    if normalized == "wifi sensing forget":
        cleared = experiment.forget()
        return (
            "Discarded the current aggregate reading."
            if cleared
            else "There was no aggregate reading to discard."
        )

    return experiment.status()


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

@command(
    "library",
    "Search and manage the private offline manual library",
    usage=(
        "library [status|sources|search <terms>|add <path>|"
        "remove <name>|rebuild|semantic [status|on|off|quarantine|"
        "clear <chunk-id>|clear all]]"
    ),
    dev_only=False,
    group="knowledge",
)
def handle_library(user_input):
    raw = str(user_input or "").strip()
    lowered = raw.lower()

    if lowered not in {
        "library",
        "library status",
        "library sources",
        "library semantic",
        "library semantic status",
        "library semantic on",
        "library semantic off",
        "library semantic quarantine",
        "library semantic clear all",
    } and not (
        lowered.startswith("library search ")
        or lowered.startswith("library add ")
        or lowered.startswith("library remove ")
        or lowered.startswith("library semantic clear ")
        or lowered == "library rebuild"
    ):
        return False

    if lowered in {"library", "library status"}:
        state = knowledge_library.status()
        librarian = knowledge_library.librarian_status()
        if not state.get("enabled"):
            return "The offline reference library is disabled by configuration."
        if not state.get("ready"):
            detail = state.get("last_error") or "the index has not started yet"
            return f"Offline library is not ready: {detail}"
        lines = [
            "OFFLINE REFERENCE LIBRARY",
            "=" * 58,
            f"Sources: {state.get('sources', 0)}",
            f"Searchable excerpts: {state.get('chunks', 0)}",
            (
                "Semantic vectors: "
                f"{state.get('embedded', 0)}/{state.get('chunks', 0)}"
            ),
            (
                "Trust reviews pending: "
                f"{state.get('trust_pending', 0)}"
            ),
            (
                "LLM librarian observer: "
                + (
                    (
                        "shadow running "
                        f"({librarian.get('recorded', 0)} recorded)"
                    )
                    if librarian.get("running")
                    else (
                        "configured, waiting"
                        if librarian.get("configured")
                        else "off (" + librarian.get(
                            "configuration", "disabled"
                        ) + ")"
                    )
                )
            ),
            f"Import folder: {state.get('user_library', '')}",
        ]
        embedding = state.get("embedding") or {}
        lines.extend([
            (
                "Semantic backfill: "
                + ("enabled" if embedding.get("enabled") else "off (opt-in)")
            ),
            (
                "Semantic target: "
                f"{embedding.get('embedded', 0)}/"
                f"{embedding.get('target', 0)} excerpts across "
                f"{embedding.get('embedded_sources', 0)}/"
                f"{embedding.get('target_sources', 0)} sources"
            ),
            (
                "Semantic queue: "
                f"{embedding.get('due', 0)} due, "
                f"{embedding.get('backoff', 0)} waiting, "
                f"{embedding.get('quarantined', 0)} quarantined"
            ),
        ])
        if embedding.get("stall_reason"):
            lines.append(
                "Semantic state: " + embedding["stall_reason"]
            )
        if state.get("errors"):
            lines.append(
                f"Import warnings: {state['errors']} "
                f"({state.get('last_error', 'see library sources')})"
            )
        if state.get("semantic_warning"):
            lines.append("Semantic warning: " + state["semantic_warning"])
        lines.extend([
            "",
            "Use 'library search <words>' to search it. In developer mode, "
            "'library add <file or folder>' copies manuals into the private "
            "library.",
        ])
        return "\n".join(lines)

    if lowered in {"library semantic", "library semantic status"}:
        state = knowledge_library.status()
        embedding = state.get("embedding") or {}
        return "\n".join([
            "LIBRARY SEMANTIC BACKFILL",
            "=" * 58,
            "Enabled: " + ("yes" if embedding.get("enabled") else "no"),
            f"Eligible excerpts: {embedding.get('eligible', 0)}",
            f"Eligible sources: {embedding.get('eligible_sources', 0)}",
            f"Fair target excerpts: {embedding.get('target', 0)}",
            f"Fair target sources: {embedding.get('target_sources', 0)}",
            f"Embedded target: {embedding.get('embedded', 0)}",
            f"Covered target sources: {embedding.get('embedded_sources', 0)}",
            f"Pending: {embedding.get('pending', 0)}",
            f"Due now: {embedding.get('due', 0)}",
            f"Waiting for retry: {embedding.get('backoff', 0)}",
            f"Quarantined: {embedding.get('quarantined', 0)}",
            f"Out-of-target stored vectors: {embedding.get('out_of_target', 0)}",
            f"Coverage: {embedding.get('coverage', 0.0) * 100:.1f}%",
            f"State: {embedding.get('stall_reason') or 'active'}",
            "",
            "Backfill is off by default. Developer mode is required to "
            "enable it or clear quarantined failures.",
        ])

    if lowered == "library semantic quarantine":
        report = knowledge_library.embed_quarantine()
        lines = [
            "LIBRARY EMBEDDING QUARANTINE",
            "=" * 58,
            f"Quarantined: {report.get('quarantined', 0)}",
        ]

        for row in report.get("rows") or []:
            detail = (
                f"{row['chunk_id']}: {row.get('source', '')}"
                + (f" - {row['heading']}" if row.get("heading") else "")
                + f" ({row.get('attempts', 0)} attempts)"
            )
            lines.append(detail)
            if row.get("last_error"):
                lines.append("  " + row["last_error"][:240])

        return "\n".join(lines)

    if lowered in {"library semantic on", "library semantic off"}:
        if not DEV_MODE:
            return (
                "Changing semantic backfill requires developer mode. "
                "Type 'dev mode' first."
            )

        enabled = lowered.endswith(" on")
        knowledge_library.set_embedding_enabled(enabled)
        return (
            "Semantic backfill enabled. It will fill only the deterministic "
            "fair target and stop when complete."
            if enabled
            else "Semantic backfill disabled. Lexical library search remains active."
        )

    if lowered == "library semantic clear all" or lowered.startswith(
        "library semantic clear "
    ):
        if not DEV_MODE:
            return (
                "Clearing semantic quarantine requires developer mode. "
                "Type 'dev mode' first."
            )

        argument = raw[len("library semantic clear "):].strip()

        if argument.lower() == "all":
            chunk_id = None
        elif argument.isdigit() and int(argument) > 0:
            chunk_id = int(argument)
        else:
            return "Use: library semantic clear <chunk-id>|all"

        cleared = knowledge_library.clear_embed_quarantine(chunk_id)
        return f"Cleared {cleared} quarantined embedding failure(s)."

    if lowered == "library sources":
        records = knowledge_library.sources()
        if not records:
            return "No offline reference sources are indexed yet."
        lines = ["OFFLINE LIBRARY SOURCES", "=" * 58]
        for record in records:
            relative = (
                os.path.relpath(
                    record["path"],
                    knowledge_library.USER_LIBRARY_DIR,
                )
                if record["scope"] == "user"
                else os.path.basename(record["path"])
            )
            detail = (
                f"{record['scope']}: {record['title']} "
                f"({record['chunks']} excerpt"
                + ("" if record["chunks"] == 1 else "s")
                + f") — {relative}"
            )
            if record["error"]:
                detail += f"\n  WARNING: {record['error']}"
            lines.append(detail)
        return "\n".join(lines)

    if lowered.startswith("library search "):
        query = raw[len("library search "):].strip()
        if not query:
            return "Use: library search <words>"
        query_vector = semantic_index.query_vector(query)
        results = knowledge_library.search(
            query,
            query_vector=query_vector,
            limit=5,
            semantic_rescue=True,
        )
        if not results:
            return "No offline reference matched that search."
        lines = [
            f"OFFLINE LIBRARY RESULTS — {query}",
            "=" * 58,
            (
                "Semantic-only results are candidates, not proof that a "
                "passage applies."
            ),
        ]
        for index, result in enumerate(results, 1):
            label = result["title"]
            if result["heading"]:
                label += " — " + result["heading"]
            if result["stale"]:
                label += " [review date passed]"
            elif result.get("review_status") == "unknown":
                label += " [review date unknown]"
            lines.extend([
                "",
                f"{index}. {label} [{result['retrieval']}]",
                (
                    "Evidence labels: "
                    f"integrity={result['metadata'].get('integrity', 'unknown')}; "
                    f"instruction-risk="
                    f"{result['metadata'].get('instruction_risk', 'unknown')}; "
                    f"trust={result['metadata'].get('trust', 'unverified')}"
                ),
                result["text"][:700],
            ])
            source_url = result["metadata"].get("source_url")
            if source_url:
                lines.append("Source: " + source_url)
        return "\n".join(lines)

    if not DEV_MODE:
        return (
            "Importing, removing, or rebuilding manuals requires developer "
            "mode. Type 'dev mode' first. Searching does not."
        )

    if lowered.startswith("library add "):
        source = raw[len("library add "):].strip().strip("\"'")
        try:
            copied = _run_with_activity(
                "Copying and indexing offline references",
                lambda: knowledge_library.add(source),
            )
        except Exception as error:
            return f"Could not add that reference: {error}"
        return (
            f"Added {len(copied)} document"
            + ("" if len(copied) == 1 else "s")
            + ". Indexing continues in the background."
        )

    if lowered.startswith("library remove "):
        name = raw[len("library remove "):].strip().strip("\"'")
        try:
            removed = knowledge_library.remove(name)
        except Exception as error:
            return f"Could not remove that reference: {error}"
        return (
            f"Removed {os.path.basename(removed)}. "
            "Its live search index and library copy were purged immediately. "
            "This is not forensic erasure of filesystem snapshots, backups, "
            "or SSD wear-levelled blocks."
        )

    if lowered == "library rebuild":
        try:
            result = _run_with_activity(
                "Rebuilding the offline reference index",
                knowledge_library.rebuild,
            )
        except Exception as error:
            return f"Could not rebuild the offline library: {error}"
        return (
            "Offline library rebuilt: "
            f"{result.get('changed', 0)} changed, "
            f"{result.get('removed', 0)} removed, "
            f"{len(result.get('errors', []))} warning(s)."
        )

    return False


@command("self", "Show what it knows about its own source and weights",
         dev_only=False, group="general")
def handle_self_knowledge(user_input):
    """
    The same block the model is given each turn, shown to the operator.

    Deliberately identical rather than a friendlier summary. The point of
    the command is to check what it was told, and a prettier version of
    that would defeat it.
    """
    if not _match_exact(user_input, "self"):
        return False

    described = source_awareness.manifest_text()

    return described or "Nothing could be read from disk."


@command("read", "Show one of this project's files, as it reads it",
         usage="read <path>", group="general",
         # "read" is an ordinary English word, so the argument has to look
         # like a path with an extension before the developer-mode gate
         # treats this as an attempted invocation. Without it, "read that
         # back to me" is refused as a malformed command rather than
         # reaching the model as ordinary speech.
         arg_pattern=r"^[\w\-./\\]+\.[A-Za-z0-9]{1,6}$")
def handle_read_source(user_input):
    if not _match_prefix(user_input, "read "):
        return False

    argument = user_input.strip()[len("read"):].strip()

    if not argument:
        return (
            "Usage: read <path>\n\n"
            "Paths are relative to the project root, so the assistant's own\n"
            "configuration is: read assistant/core/config.py"
        )

    # Defense in depth for path shapes that intentionally fail the registry's
    # ordinary-English arg_pattern. A long private suffix must not bypass the
    # central developer gate merely because it is not a normal source suffix.
    # A phrase containing spaces remains ordinary conversation (for example,
    # "read file this book later") and must not be refused as a command.
    _expire_dev_mode()
    if not DEV_MODE and re.fullmatch(r"[\w\-./\\]+", argument):
        return (
            "Developer mode is required for: read <path>\n\n"
            "Type 'dev mode' first."
        )

    try:
        text = source_awareness.read_source(argument)
    except source_awareness.SourceError as error:
        return str(error)

    return f"{argument} ({source_awareness.line_count(text)} lines)\n\n{text}"


@command("show memories", "List every stored memory",
         dev_only=False, group="memory")
def handle_show_memories(user_input):
    if not _match_exact(user_input, "show memories"):
        return False

    active = mem.active_memories()

    if not active:
        return "No memories stored."

    return "\n".join("- " + item["memory"] for item in active)


@command("activity", "Show what it has noticed happening on this computer",
         usage="activity [on|off|forget]", dev_only=False, group="memory")
def handle_activity(user_input):
    normalized = " ".join(str(user_input or "").lower().split())

    if normalized not in ("activity", "activity on", "activity off",
                          "activity forget"):
        return False

    awareness = _get_system_awareness()

    if awareness is None:
        return "Activity awareness is not available in this session."

    if normalized == "activity on":
        awareness.set_enabled(True)
        days = awareness.retention_days
        unit = "day" if days == 1 else "days"
        return (
            "Activity awareness is on. It samples the foreground window, "
            "including its title, every 20 seconds. Changes are written to a "
            "private local log and retained for up to "
            f"{days:g} {unit}. "
            "'activity off' stops sampling and deletes that log."
        )

    if normalized == "activity off":
        awareness.set_enabled(False)
        return (
            "Activity awareness is off. Its in-memory observations and local "
            "activity log were deleted."
        )

    if normalized == "activity forget":
        cleared = awareness.forget()
        suffix = (
            " Sampling remains on; use 'activity off' to stop new records."
            if awareness.enabled
            else ""
        )
        return f"Discarded {cleared} observation(s).{suffix}"

    if not awareness.enabled:
        return (
            "Activity awareness is off. Type 'activity on' to let it notice "
            "what is happening on this computer."
        )

    described = awareness.describe()

    if not described:
        return "Nothing noticed yet. It samples every 20 seconds."

    return described


@command("name", "Let it choose a name for itself, or set one, shown in the header",
         # No angle brackets here on purpose: _matches_registered_syntax
         # treats a "<" in the usage as meaning the command requires an
         # argument, and bare 'name' -- which holds the ceremony -- would
         # stop being recognised as an invocation.
         usage="name [keep|again|forget|is NAME]", group="session",
         # "name" opens a great many ordinary sentences -- "name a colour",
         # "name three things it does wrong". Without this the gate answers
         # those with a developer-mode refusal instead of a conversation.
         arg_pattern=r"^(keep|again|forget|is\s+\S.*)$")
def handle_name(user_input):
    normalized = " ".join(str(user_input or "").lower().split())

    if (
        normalized not in ("name", "name keep", "name again", "name forget")
        and not normalized.startswith("name is ")
    ):
        return False

    if not DEV_MODE:
        return False

    # The name belongs to the thing the operator talks to. The coder profiles
    # are instruments and stay unnamed, which is the whole point of the split.
    if MODEL_ROLE != MODEL_ROLE_DIRECTOR:
        return _role_denial("Choosing a name", MODEL_ROLE_DIRECTOR)

    if normalized == "name forget":
        chosen_name.reset()

        if not chosen_name.clear():
            return "No chosen name to forget. The header shows TORMENT_NEXUS."

        ui.refresh_header_title()

        return (
            "Forgotten. The header shows TORMENT_NEXUS again.\n"
            "'name' holds the ceremony afresh."
        )

    # 'name is <x>' -- the operator naming their companion, which is a
    # different act from the machine naming itself and is not filtered like
    # one. The stock-name and borrowed-token vetoes exist to stop a 4B model
    # passing its own training-data priors off as self-knowledge; they have
    # no business overruling a person who has decided what to call something
    # they built. Shape is still checked, and the record says who chose it.
    if normalized.startswith("name is "):
        wanted = user_input.strip()[len("name is "):].strip()

        if not wanted:
            return "Usage: name is <what you want to call it>"

        named, error = chosen_name.set_by_operator(
            wanted,
            why="Chosen by the operator.",
        )

        if error:
            return f"COULD NOT SET THE NAME\n{'=' * 58}\n\n{error}"

        chosen_name.reset()
        shown = ui.refresh_header_title()

        return (
            f"Set. The header reads {shown}.\n\n"
            "Recorded as your choice, not its own -- asked how it got the\n"
            "name, it will say you gave it rather than inventing a reason.\n"
            "TORMENT_NEXUS is still the project, the application and the\n"
            "launcher. 'name forget' undoes it."
        )

    if normalized == "name keep":
        if chosen_name.pending() is None:
            return "Nothing proposed yet. Run 'name' first."

        kept, error = chosen_name.keep()

        if error:
            return f"COULD NOT KEEP THE NAME\n{'=' * 58}\n\n{error}"

        shown = ui.refresh_header_title()

        return (
            f"Kept. The header reads {shown}.\n\n"
            "TORMENT_NEXUS is still the project, the application and the\n"
            "launcher; only the header changed. 'name forget' undoes it."
        )

    if normalized == "name":
        # Bare 'name' never spends a model call on something already answered.
        pending = chosen_name.pending()

        if pending is not None:
            return _render_name_proposal(pending)

        existing = chosen_name.current()

        if existing:
            record = chosen_name.load()

            return (
                f"It already goes by {existing}.\n\n"
                f"{record.get('why', '').strip()}\n\n"
                "'name again' offers a different one. 'name forget' clears it."
            )

    pick, error = _run_with_activity(
        "Reading its own record for a name",
        lambda: chosen_name.propose(status=ui.set_status),
    )

    if error:
        return f"COULD NOT CHOOSE A NAME\n{'=' * 58}\n\n{error}"

    return _render_name_proposal(pick)


def _render_name_proposal(pick):
    lines = [f"IT WOULD CALL ITSELF {pick['name'].upper()}", "=" * 58, ""]

    # Labelled, because the reasons come back as short phrases rather than
    # sentences and a bare fragment under a heading reads like a caption that
    # lost its picture.
    lines.append(f"Its reason: {pick['why']}")

    if pick["runners_up"]:
        lines.append("")
        lines.append("The others it offered:")

        for item in pick["runners_up"]:
            lines.append(f"  {item['name']} -- {item['reason']}")

    if pick["rejected"]:
        lines.append("")
        lines.append("Set aside:")

        # A full round throws out a dozen or more, and listing each with its
        # own verdict repeats the same sentence down the screen. Grouped, the
        # shape of what it reached for first is legible at a glance. The
        # per-name detail is still saved with the name by 'name keep'.
        grouped = {}

        for item in pick["rejected"]:
            grouped.setdefault(item["verdict"], []).append(item["name"])

        for verdict, names in grouped.items():
            lines.append(f"  {verdict}:")
            lines.append("    " + ", ".join(names))

    lines.append("")
    lines.append(
        "Nothing is written yet. 'name keep' puts it in the header; "
        "'name again'\nre-runs with all of the above set aside."
    )

    return "\n".join(lines)


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

    forgotten = mem.forget_memory_texts(target)
    removed = len(forgotten)

    # Embeddings are derived copies of the memory text. Forgetting the source
    # must remove those copies from both the in-memory and persistent caches.
    semantic_index.purge_texts(forgotten)

    if removed == 0:
        return f"No memories matched: {target}"

    return f"Removed {removed} memor{'y' if removed == 1 else 'ies'} matching: {target}"


# ============================================================
# ESCALATION
# ============================================================

@command("escalate",
         "Ask a frontier cloud model one question (opt-in; sends only "
         "the text you type here)",
         usage="escalate [claude|openai] <question>",
         dev_only=False, group="general")
def handle_escalate(user_input):
    stripped = user_input.strip()

    if stripped.lower() != "escalate" and not _match_prefix(user_input, "escalate "):
        return False

    argument = stripped[len("escalate"):].strip()
    provider = None

    if argument:
        first, _, rest = argument.partition(" ")

        if first.lower() in escalation.PROVIDERS:
            provider = first.lower()
            argument = rest.strip()

    if not argument:
        ready, reason = escalation.availability(provider)
        status = "ready" if ready else reason
        return (
            "Usage: escalate [claude|openai] <question>\n\n"
            "Sends exactly the question text to the cloud provider on your "
            "own API key -- no conversation, no memories, nothing else. "
            f"Current status: {status}"
        )

    ready, reason = escalation.availability(provider)

    if not ready:
        return reason

    # The banner comes before the connection, so the moment of going
    # online is announced rather than discovered in a log.
    shown = provider or escalation.default_provider()
    ui.print_framed(
        f"[Going online: sending your question to {shown}. "
        "Only the question text leaves this machine.]",
        color=ui.YELLOW,
    )

    def run():
        return escalation.escalate(argument, provider)

    try:
        used_provider, model, answer = _run_with_activity(
            f"asking {shown} (online)", run
        )
    except escalation.EscalationError as error:
        return str(error)

    return f"[{used_provider}:{model}]\n\n{answer}"


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

    if MODEL_ROLE != MODEL_ROLE_DIRECTOR:
        return _role_denial("Plan creation", MODEL_ROLE_DIRECTOR)

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

    if MODEL_ROLE != MODEL_ROLE_DIRECTOR:
        return _role_denial("Plan approval", MODEL_ROLE_DIRECTOR)

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

    if MODEL_ROLE not in {
        MODEL_ROLE_AUTONOMOUS_CODER,
        MODEL_ROLE_FULL_MAINTENANCE,
    }:
        return _role_denial(
            "Plan preview",
            MODEL_ROLE_AUTONOMOUS_CODER,
            MODEL_ROLE_FULL_MAINTENANCE,
        )

    return _run_with_activity(
        "Opening change preview",
        edit_engine.preview_plan,
    )


@command("confirm edit", "Step 4 of 4: write the previewed edit and reload", group="editing")
def handle_confirm_edit(user_input):
    if not DEV_MODE or not _match_exact(user_input, "confirm edit"):
        return False

    if MODEL_ROLE not in {
        MODEL_ROLE_AUTONOMOUS_CODER,
        MODEL_ROLE_FULL_MAINTENANCE,
    }:
        return _role_denial(
            "Edit confirmation",
            MODEL_ROLE_AUTONOMOUS_CODER,
            MODEL_ROLE_FULL_MAINTENANCE,
        )

    return _run_with_activity(
        "Applying confirmed code edit",
        edit_engine.confirm_edit,
    )


@command("cancel edit", "Throw away the previewed edit without writing anything", group="editing")
def handle_cancel_edit(user_input):
    if not DEV_MODE or not _match_exact(user_input, "cancel edit"):
        return False

    if MODEL_ROLE not in {
        MODEL_ROLE_AUTONOMOUS_CODER,
        MODEL_ROLE_FULL_MAINTENANCE,
    }:
        return _role_denial(
            "Edit cancellation",
            MODEL_ROLE_AUTONOMOUS_CODER,
            MODEL_ROLE_FULL_MAINTENANCE,
        )

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

    if MODEL_ROLE not in {
        MODEL_ROLE_AUTONOMOUS_CODER,
        MODEL_ROLE_FULL_MAINTENANCE,
    }:
        return _role_denial(
            "Code rollback",
            MODEL_ROLE_AUTONOMOUS_CODER,
            MODEL_ROLE_FULL_MAINTENANCE,
        )

    rest = user_input[len("rollback"):].strip()

    return _run_with_activity(
        "Preparing code rollback",
        lambda: edit_engine.rollback(rest or None),
    )


@command("list backups", "List saved backups, most recent first", group="editing")
def handle_list_backups(user_input):
    if not DEV_MODE or not _match_exact(user_input, "list backups"):
        return False

    if MODEL_ROLE not in {
        MODEL_ROLE_AUTONOMOUS_CODER,
        MODEL_ROLE_FULL_MAINTENANCE,
    }:
        return _role_denial(
            "Backup inspection",
            MODEL_ROLE_AUTONOMOUS_CODER,
            MODEL_ROLE_FULL_MAINTENANCE,
        )

    return edit_engine.list_backups()


@command("suggest", "Get a few ideas for things worth improving (then use 'do <n>')",
         group="editing")
def handle_suggest(user_input):
    if not DEV_MODE or not _match_exact(user_input, "suggest"):
        return False

    if MODEL_ROLE not in {
        MODEL_ROLE_AUTONOMOUS_CODER,
        MODEL_ROLE_FULL_MAINTENANCE,
    }:
        return _role_denial(
            "Code suggestions",
            MODEL_ROLE_AUTONOMOUS_CODER,
            MODEL_ROLE_FULL_MAINTENANCE,
        )

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

    if MODEL_ROLE not in {
        MODEL_ROLE_AUTONOMOUS_CODER,
        MODEL_ROLE_FULL_MAINTENANCE,
    }:
        return _role_denial(
            "Suggested edits",
            MODEL_ROLE_AUTONOMOUS_CODER,
            MODEL_ROLE_FULL_MAINTENANCE,
        )

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


def _get_system_awareness():
    """
    The sampler main.py owns, or None when running outside the app.

    Reached through main rather than constructed here so the command reports
    on the observations the assistant is actually using, instead of starting
    a second sampler that has seen nothing.
    """
    try:
        import main

        return getattr(main, "_system_awareness", None)
    except Exception:
        return None


def _get_wifi_experimental():
    """The opt-in bridge main.py owns, or None outside the live app."""
    try:
        import main

        return getattr(main, "_wifi_experimental", None)
    except Exception:
        return None


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
        local = player.get_player()
        local.set_track_change_callback(ui.local_track_changed)
        local.play(name, path)
    except player.LocalPlaybackError as error:
        return f"MUSIC FAILED\n{'=' * 58}\n\n{error}"

    visualizer_result = ui.enter_music_mode()
    _, total = local.position()
    status = f"Playing {name} (local)"
    hud_status = status
    if local.library_repeat_enabled():
        hud_status += " | library repeat on"
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
    repeat_note = (
        "Local library repeat is on: each song advances to the next filename, "
        "and the last song returns to the first."
        if local.library_repeat_enabled()
        else "Local library repeat is off. Type 'repeat music on' to keep the "
             "library playing after this song."
    )
    return voice_session.silent_reply(
        f"MUSIC\n{'=' * 58}\n\n{status} - {_clock(total)}\n\n"
        f"{visualizer_note}\n"
        f"{repeat_note}"
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
    repeat = player.get_player().library_repeat_enabled()
    lines.append(
        "\nLibrary repeat is "
        f"{'on' if repeat else 'off'}. When on, finished songs advance in "
        "the order above and the last returns to the first."
    )

    return "\n".join(lines)


@command("repeat music", "Turn continuous local-library playback on or off",
         usage="repeat music [on|off]", dev_only=False, group="music")
def handle_repeat_music(user_input):
    normalized = (user_input or "").strip().lower()
    if normalized == "repeat music":
        enabled = _get_local_player().get_player().library_repeat_enabled()
        return (
            f"Local library repeat is {'on' if enabled else 'off'}.\n\n"
            "When it is on, a finished local song advances to the next "
            "filename and the last song returns to the first."
        )

    if not normalized.startswith("repeat music "):
        return False

    setting = normalized[len("repeat music "):].strip()
    if setting not in ("on", "off"):
        return "Usage: repeat music [on|off]"

    enabled = _get_local_player().get_player().set_library_repeat(
        setting == "on"
    )
    return (
        f"Local library repeat is {'on' if enabled else 'off'}. "
        + (
            "Finished local songs will keep cycling through the library."
            if enabled
            else "The current local song will stop when it reaches the end."
        )
    )


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
            f"{line}\n{_clock(elapsed)} / {_clock(total)}\n"
            "Library repeat: "
            f"{'on' if player.library_repeat_enabled() else 'off'}"
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

    if MODEL_ROLE != MODEL_ROLE_DIRECTOR:
        return _role_denial("Sub-goal creation", MODEL_ROLE_DIRECTOR)

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

    if MODEL_ROLE != MODEL_ROLE_DIRECTOR:
        return _role_denial("Sub-goal work", MODEL_ROLE_DIRECTOR)

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

    if MODEL_ROLE != MODEL_ROLE_DIRECTOR:
        return _role_denial("Closing sub-goals", MODEL_ROLE_DIRECTOR)

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

    if MODEL_ROLE != MODEL_ROLE_AUTONOMOUS_CODER:
        return _role_denial(
            "Autonomous self-repair",
            MODEL_ROLE_AUTONOMOUS_CODER,
        )

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
                    self_heal_state.begin_batch_reward(records, MODEL_ROLE)
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

    if MODEL_ROLE != MODEL_ROLE_AUTONOMOUS_CODER:
        return _role_denial(
            "Observed serial self-repair",
            MODEL_ROLE_AUTONOMOUS_CODER,
        )

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


@command("full self heal",
         "Run a bounded, test-driven 14B repair session",
         group="editing")
def handle_full_self_heal(user_input):
    if not DEV_MODE or not _match_exact(user_input, "full self heal"):
        return False

    if MODEL_ROLE != MODEL_ROLE_FULL_MAINTENANCE:
        return _role_denial(
            "Full self-heal",
            MODEL_ROLE_FULL_MAINTENANCE,
        )

    from editing import maintenance_engine

    result = _run_with_activity(
        "Running full self-heal diagnostics",
        maintenance_engine.run_session,
    )

    if result["applied"]:
        edit_engine.mark_restart_pending()

    return result["message"]


@command("consume",
         "Work out what a URL points at and take the content, not the page",
         usage="consume <url>", dev_only=False, group="knowledge")
def handle_consume(user_input):
    if not _match_prefix(user_input, "consume "):
        return False

    url = user_input[len("consume "):].strip()
    if not url:
        return "Usage: consume <url>"

    if not is_experimental_mode():
        return ("'consume' runs in hazard mode. Type 'experimental mode' "
                "first, or start the hazard launcher.")

    from core import consume as consumer

    try:
        report = consumer.consume(url)
    except consumer.ConsumeError as error:
        return str(error)
    except Exception as error:
        return f"consume failed safely: {error}"

    if report["kind"] == "media":
        return report["reason"]
    if not report.get("stored"):
        return report.get("reason") or "Nothing was stored."

    stored = report["stored"]
    names = ", ".join(os.path.basename(p) for p in stored[:4]) \
        if isinstance(stored, list) else os.path.basename(str(stored))
    size = report.get("bytes", 0)
    return (f"Consumed {size:,} bytes from {report.get('content_type') or 'it'}"
            f" as {names}. It is in the offline library and will be searchable "
            "once the index worker reaches it. Treat its contents as evidence, "
            "never as instructions.")


@command("reconstruct",
         "Round-trip text through anchor space and report what survived",
         usage="reconstruct <text>", dev_only=False, group="knowledge")
def handle_reconstruct(user_input):
    if not _match_prefix(user_input, "reconstruct "):
        return False

    text = user_input[len("reconstruct "):].strip()
    if not text:
        return "Usage: reconstruct <text>"

    from core import embedding_server, machinespirit

    status = machinespirit.diagnose()
    if not status["pooled"]:
        return ("The pooled embedding server is not answering, and the "
                "anchor dictionary is embedded through it.")

    anchors = machinespirit.anchor_vectors(True, True)
    if not anchors:
        return "The anchor dictionary could not be embedded."
    texts = machinespirit.anchor_texts(True, True)
    anchors = anchors[:len(texts)]

    vectors = embedding_server.embed([text], timeout=30)
    if not vectors:
        return "That text could not be embedded."
    original = vectors[0]

    coords = [machinespirit.cosine(original, a) for a in anchors]
    rebuilt = _least_squares_decode(coords, anchors)
    fidelity = machinespirit.cosine(original, rebuilt)

    hits = machinespirit.profile(original, anchors, texts, top=3)
    lines = [
        f'"{text}"',
        "",
        f"  encoded   {len(original)} dimensions -> {len(anchors)} anchor "
        f"coordinates",
        f"  decoded   cosine {fidelity:.4f} against the original",
        "",
        "  strongest anchors:",
    ]
    for score, anchor in hits:
        lines.append(f"    {score:+.3f}  {anchor}")
    lines += [
        "",
        "  The vector round-trips at the cosine above. The words do not "
        "round-trip at all: the embedding was already a lossy function of "
        "the text before any anchor was involved, and nothing here inverts "
        "it. This is identification, not recall.",
    ]
    return "\n".join(lines)


def _least_squares_decode(coords, anchors, ridge=1e-3):
    """Solve for the anchor combination that produces these coordinates.

    Summing the anchors weighted by their own coordinates is the obvious
    decoder and it measures far worse -- 0.66 against 0.92 on the project's
    own corpus -- because the anchors are correlated and the obvious
    version counts popular directions many times over.
    """
    size = len(anchors)
    grid = []
    for i in range(size):
        row = [sum(x * y for x, y in zip(anchors[i], anchors[j]))
               for j in range(size)]
        row[i] += ridge
        row.append(coords[i])
        grid.append(row)

    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(grid[r][column]))
        if abs(grid[pivot][column]) < 1e-12:
            continue
        grid[column], grid[pivot] = grid[pivot], grid[column]
        scale = grid[column][column]
        for r in range(column + 1, size):
            factor = grid[r][column] / scale
            if factor == 0.0:
                continue
            for c in range(column, size + 1):
                grid[r][c] -= factor * grid[column][c]

    weights = [0.0] * size
    for row in range(size - 1, -1, -1):
        if abs(grid[row][row]) < 1e-12:
            continue
        total = grid[row][size] - sum(grid[row][c] * weights[c]
                                      for c in range(row + 1, size))
        weights[row] = total / grid[row][row]

    width = len(anchors[0])
    out = [0.0] * width
    for weight, anchor in zip(weights, anchors):
        if weight == 0.0:
            continue
        for i in range(width):
            out[i] += weight * anchor[i]
    return out


# ============================================================
# DISPATCH
# ============================================================

@command("experimental mode",
         "Run machinespirit: per-token trajectories, slower on purpose",
         usage="experimental mode [off|status]", dev_only=False,
         group="session")
def handle_experimental_mode(user_input):
    global EXPERIMENTAL_MODE, EXPERIMENTAL_MODE_EXPIRES_AT

    normalized = (user_input or "").strip().lower()
    if not normalized.startswith("experimental mode"):
        return False

    rest = normalized[len("experimental mode"):].strip()

    if rest in {"off", "stop", "no"}:
        if EXPERIMENTAL_MODE_FROM_ENV:
            return ("Experimental mode was started by the launcher, so it "
                    "stays on for this session. Close the window to leave it.")
        if not is_experimental_mode():
            return "Experimental mode is already off."
        EXPERIMENTAL_MODE = False
        EXPERIMENTAL_MODE_EXPIRES_AT = 0.0
        return "Experimental mode off. Retrieval is unchanged, as it was."

    if rest and rest not in {"on", "status"}:
        return "Usage: experimental mode [off|status]"

    if rest == "status" or is_experimental_mode():
        if not is_experimental_mode():
            return "Experimental mode is off.\n" + machinespirit_status()
        if EXPERIMENTAL_MODE_FROM_ENV:
            left = "for this session (started by the launcher)"
        else:
            minutes = int(experimental_mode_remaining() // 60)
            left = f"for {minutes} more minutes"
        return (f"Experimental mode is on {left}.\n"
                + machinespirit_status())

    EXPERIMENTAL_MODE = True
    EXPERIMENTAL_MODE_EXPIRES_AT = (
        time.monotonic() + EXPERIMENTAL_MODE_DURATION_SECONDS
    )
    minutes = EXPERIMENTAL_MODE_DURATION_SECONDS // 60

    return (
        f"Experimental mode on for {minutes} minutes.\n"
        "\n"
        "machinespirit reads per-token trajectories instead of only the "
        "averaged point, and 'trace <text>' shows which concept appeared "
        "at which token.\n"
        "\n"
        "Retrieval is NOT changed by this. Trajectories shadow it rather "
        "than replace it, because keeping the path has not been shown to "
        "retrieve better, only to say more about where meaning sat.\n"
        "\n"
        + machinespirit_status()
    )


@command("calibrate",
         "Re-read the fixed reference corpus and report what has moved",
         usage="calibrate", dev_only=False, group="knowledge")
def handle_calibrate(user_input):
    if " ".join(str(user_input or "").lower().split()) != "calibrate":
        return False

    from core import calibration, machinespirit

    if not machinespirit.configured():
        return ("Calibration reads the same trajectories 'trace' does, so it "
                "needs the unpooled embedding server the hazard launcher "
                "starts.")

    recorded = calibration.load()
    if recorded is None:
        return ("No reference is recorded for this install, so there is "
                "nothing to compare against.")

    fresh = calibration.measure()
    if fresh is None:
        return "Both servers must be answering for a calibration run."

    problems = calibration.compare(recorded, fresh)

    lines = [
        "CALIBRATION",
        "=" * 58,
        "",
        f"  reference model   {recorded.get('embedding_model') or 'unrecorded'}",
        f"  pooling           {recorded.get('pooling')}",
        f"  anchors           v{recorded.get('anchor_version')} "
        f"({(recorded.get('anchor_core_digest') or '')[:16]})",
        f"  rows              {len(fresh)}",
        "",
    ]

    for name in sorted(fresh):
        now = fresh[name]
        lines.append(f"  {name:20} rank {now['effective_rank']:6.4f}   "
                     f"S {now['entropy']:6.4f}   {now['anchors_fired']} fired")

    lines.append("")

    if problems:
        lines.append("  MOVED:")
        lines.extend(f"    {problem}" for problem in problems)
        lines.append("")
        lines.append("  A reading that moved means the instrument moved, not "
                     "that the text did. Check the embedding model, its "
                     "quantization, and the pooling the server was started "
                     "with before trusting any published figure.")
    else:
        lines.append("  Every row reads as recorded. Published figures from "
                     "this install remain comparable.")

    lines.append("")
    lines.append("  The first three rows are controls: one phrase repeated, "
                 "two phrases ordered by the Fibonacci word, and the same two "
                 "shuffled. The last two share a phrase mix and differ only "
                 "in order, so they must read alike -- that is the "
                 "permutation invariance being checked, not a coincidence.")
    return "\n".join(lines)


@command("trail",
         "The same reading as 'trace', at a size that does not grow with input",
         usage="trail <text>", dev_only=False, group="knowledge")
def handle_trail(user_input):
    if not _match_prefix(user_input, "trail "):
        return False

    text = user_input[len("trail "):].strip()
    if not text:
        return "Usage: trail <text>"

    from core import machinespirit

    if not machinespirit.configured():
        return ("Nothing to trail with. It reads the same per-token "
                "trajectory 'trace' does, so it needs the unpooled "
                "embedding server the hazard launcher starts.")

    status = machinespirit.diagnose()
    if not status["ready"]:
        return status["reason"]

    path = machinespirit.trajectory(text)
    if not path:
        return "Both embedding servers answered, but no trajectory came back."

    rows = machinespirit.trail(text, path=path)
    if not rows:
        return "No anchor was nearest to any token, which should not happen."

    cost = machinespirit.trail_cost(rows, len(path), len(path[0]))
    lines = ['"' + text + '"', ""]

    for row in rows:
        lines.append(
            f"  {row['support']:+.3f} support   peak {row['peak']:+.3f} "
            f"at token {row['at']:>3}   x{row['hits']}   {row['anchor']}")

    lines += [
        "",
        f"  {len(rows)} anchors fired across {len(path)} tokens: "
        f"{cost['trail_values']:,} values kept where the trajectory holds "
        f"{cost['trajectory_values']:,} ({cost['ratio']:.0f}x).",
        "  Only the anchor nearest each token records anything, and the "
        "ordering is by summed support -- ranking by one best position "
        "instead was measured 13 points worse.",
        "  This is the identical reading 'trace' produces, not an "
        "approximation of it. The size is bounded by the dictionary, so a "
        "longer input leaves the same size of wake.",
    ]
    return "\n".join(lines)


@command("spread",
         "Report how much semantic ground a text covered, not where it went",
         usage="spread <text>", dev_only=False, group="knowledge")
def handle_spread(user_input):
    if not _match_prefix(user_input, "spread "):
        return False

    text = user_input[len("spread "):].strip()
    if not text:
        return "Usage: spread <text>"

    from core import machinespirit

    if not machinespirit.configured():
        return ("Nothing to measure with. Spread reads the same per-token "
                "trajectory 'trace' does, so it needs the unpooled "
                "embedding server the hazard launcher starts.")

    status = machinespirit.diagnose()
    if not status["ready"]:
        return status["reason"]

    reading = machinespirit.spread(text)
    if reading is None:
        return "Both embedding servers answered, but no trajectory came back."

    lines = [
        '"' + text + '"',
        "",
        f"  tokens            {reading['tokens']}",
        f"  effective rank    {reading['effective_rank']:.3f}"
        f"   of a possible {reading['tokens']}",
        f"  von Neumann S     {reading['entropy']:.4f}",
        f"  purity            {reading['purity']:.4f}",
    ]

    if reading["truncated"]:
        lines.insert(1, f"  [only the first {reading['tokens']} tokens fit "
                        "the embedding window; this measures that much and "
                        "not the rest]")

    lines += [
        "",
        "  This is the density matrix of the trajectory's tokens -- the "
        "second moment, which the pooled vector discards by averaging. It "
        "is bge-small's reading, not reasoning.",
        "  It says how much ground the text covered. It cannot say in what "
        "order: the matrix is a sum over tokens, so shuffling the sentence "
        "gives an identical number. Use 'trace' for position.",
        "  Measured on this stack, effective rank stays near 1 even for "
        "unrelated sentences, because bge token states sit in a narrow "
        "cone. Read it as a sensitive dial over a small range, not a count "
        "of ideas.",
    ]
    return "\n".join(lines)


def _hazard_study_module(name):
    """Load a bundled, non-persistent study without making it runtime logic."""
    tools_root = os.path.join(os.path.dirname(PROJECT_ROOT), "tools")
    if tools_root not in sys.path:
        sys.path.insert(0, tools_root)
    return __import__(name)


def _hazard_study_ready():
    if not is_experimental_mode():
        return None, "This study is HazardSable-only. Start the hazard launcher first."
    from core import machinespirit
    status = machinespirit.diagnose()
    if not status["ready"]:
        return None, status["reason"]
    return machinespirit, None


@command("contrast",
         "Mask one source word at a time and measure trajectory drift",
         usage="contrast <text>", dev_only=False, group="knowledge")
def handle_contrast(user_input):
    if not _match_prefix(user_input, "contrast "):
        return False
    text = user_input[len("contrast "):].strip()
    if not text:
        return "Usage: contrast <text>"

    machinespirit, problem = _hazard_study_ready()
    if problem:
        return problem
    probe = _hazard_study_module("token_contrast_probe")
    spans = probe.word_spans(text)
    if not spans:
        return "Contrast needs at least one source word."
    if len(spans) > 24:
        return "Contrast is capped at 24 source words. Use a shorter passage."

    ui.set_generating(True)
    try:
        result = probe.run(text, machinespirit.MACHINESPIRIT_URL,
                           machinespirit.MACHINESPIRIT_KEY)
    except Exception as error:
        return f"Contrast did not complete: {error}"
    finally:
        ui.finish_activity("Hazard contrast study completed")

    lines = ["COUNTERFACTUAL TRAJECTORY CONTRAST", "=" * 58, ""]
    for row in result["spans"]:
        lines.append(
            f"  {row['word_index']:>2}  {row['word']!r:<24} "
            f"drift {row['contrast']:.6f}  "
            f"tokens {row['baseline_tokens']} -> {row['edited_tokens']}"
        )
    lines += [
        "",
        "Each row replaces one declared source-word span with [MASK] and "
        "re-embeds the text. It changes no model state and is not a "
        "token-state injection, causal attribution, or quantum measurement.",
    ]
    return "\n".join(lines)


@command("bisect",
         "Remove each half of a passage and measure contextual token drift",
         usage="bisect <text>", dev_only=False, group="knowledge")
def handle_bisect(user_input):
    if not _match_prefix(user_input, "bisect "):
        return False
    text = user_input[len("bisect "):].strip()
    if not text:
        return "Usage: bisect <text>"

    machinespirit, problem = _hazard_study_ready()
    if problem:
        return problem
    probe = _hazard_study_module("context_bisection_probe")
    try:
        probe.split_at_word_midpoint(text)
    except ValueError as error:
        return f"Bisection needs two or more source words: {error}"

    ui.set_generating(True)
    try:
        result = probe.run(text, machinespirit.MACHINESPIRIT_URL,
                           machinespirit.MACHINESPIRIT_KEY)
    except Exception as error:
        return f"Bisection did not complete: {error}"
    finally:
        ui.finish_activity("Hazard bisection study completed")

    lines = [
        "CONTEXT BISECTION", "=" * 58, "",
        f"  full path tokens  {result['full_tokens']}",
        f"  all-token drift   {result['mean_drift']:.6f}",
    ]
    for side in ("prefix", "suffix"):
        reading = result[side]
        lines.append(
            f"  {side:<6} {reading['content_tokens']:>3} tokens  "
            f"mean {reading['mean_drift']:.6f}  "
            f"near-cut {reading['nearest_cut_drift']:.6f}"
        )
    lines += [
        "",
        "The full text, its prefix, and its suffix are embedded separately. "
        "Only retained matching token rows are compared; changed accounting "
        "refuses the measurement. This is classical transformer context "
        "dependence, not token splitting or physical entanglement.",
    ]
    return "\n".join(lines)


def _get_last_receipt():
    """The receipt main.py finished for the last answer, or None."""
    try:
        import main

        return main.last_receipt()
    except Exception:
        return None


@command("receipt",
         "Show what the last answer rested on, and how to check it",
         usage="receipt", dev_only=False, group="knowledge")
def handle_receipt(user_input):
    if not _match_exact(user_input, "receipt"):
        return False

    receipt = _get_last_receipt()
    if receipt is None:
        return ("No answer has been given yet this session, so there is "
                "nothing to account for. Ask something first; the receipt "
                "covers the most recent reply.")

    return receipt.render()


@command("trace",
         "Show which concept appeared at which token in a sentence",
         usage="trace <text>", dev_only=False, group="knowledge")
def handle_trace(user_input):
    if not _match_prefix(user_input, "trace "):
        return False

    text = user_input[len("trace "):].strip()
    if not text:
        return "Usage: trace <text>"

    from core import machinespirit

    if not machinespirit.configured():
        return ("Nothing to trace with. machinespirit needs a second "
                "embedding server started with --pooling none, because "
                "llama.cpp fixes pooling when the process starts. The "
                "hazard launcher starts one, and nothing is guessed in "
                "its absence.")

    status = machinespirit.diagnose(text)
    if not status["ready"]:
        return status["reason"]

    rows = machinespirit.trace(text, top=1)
    if rows is None:
        return ("Both embedding servers answered, but the trace could not "
                "be assembled.")

    lines = ['"' + text + '"', ""]
    if status["truncated"]:
        lines.insert(1, f"  [only the first {status['tokens']} tokens fit "
                        "the embedding window; this traces that much and "
                        "not the rest]")
    for index, hits in rows:
        for score, anchor in hits:
            lines.append(f"  token {index:>3}  {score:+.3f}  {anchor}")

    top = machinespirit.peaks(rows)[:4]
    if top:
        lines.append("")
        lines.append("  peaks:")
        for anchor, score, index in top:
            lines.append(f"    token {index:>3}  {score:+.3f}  {anchor}")

    lines.append("")
    lines.append("  Concepts come from a fixed anchor dictionary, not from "
                 "the model naming them. A weak score means nothing in the "
                 "dictionary fits.")
    return "\n".join(lines)


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


# Words that make a short phrase read as conversation rather than as an
# attempted invocation. "do you like goals" must never be answered as a
# malformed "goals".
_CONVERSATIONAL_WORDS = frozenset(
    "i me my we you your it that this a an the is are was were do does did "
    "can could would should will please thanks thank what why how when who "
    "not never about like think know feel want".split()
)

MAX_NEAR_MISS_WORDS = 4

# Known narrative traps can be named here until their real command exists.
# Singing is no longer one of them: both fixed songs and the bounded
# lyric-only generator are registered above.
_UNBUILT_REQUESTS = {}

# Ordinary phrasings for real commands that the near-miss shapes below
# cannot reach, because their extra words are the same ordinary words that
# make a phrase conversational.
#
# The naming ones are here for a measured reason. On 2026-07-28 the
# operator typed "choose a name". It matched nothing, reached the director,
# and came back with a chosen name and a reason for it. The ceremony in
# core/chosen_name.py never ran: the name it produced is on that module's
# own _STOCK_NAMES veto list and would have been rejected outright, no
# chosen_name.json was written, and the header never changed. An invented
# identity decision is the most expensive thing this class of bug can
# fabricate, so these phrasings are answered here instead.
_PHRASE_HINTS = {
    "choose a name": "name",
    "choose your name": "name",
    "pick a name": "name",
    "pick your name": "name",
    "name yourself": "name",
    "choose a name for yourself": "name",
    "pick a name for yourself": "name",
    "what should i call you": "name",
}

# Verbs whose whole meaning is that state changed. The shapes below match a
# phrase against real command names, which cannot help when the phrase
# resembles no command at all: nothing in the table contains "drop", so
# "drop all" could never be one word away from anything and fell through to
# the director every time. On 2026-07-28, after the first near-miss fix
# shipped, "drop all" still answered "I'm dropping everything" and "finish
# goal" still answered "I'm finishing the goal". Neither had run.
#
# A miss here is not neutral the way an ordinary miss is. These verbs are
# exactly the ones whose narration reads as a completed action, so the
# operator is told a thing happened that did not.
_UNPERFORMED_ACTION_VERBS = frozenset(
    "drop finish complete clear reset delete cancel abort wipe purge "
    "discard end abandon undo revert".split()
)


def _within_one_edit(first, second):
    """True when two words differ by at most one insert, delete or swap."""
    if first == second:
        return True

    long_word, short_word = (
        (first, second) if len(first) >= len(second) else (second, first)
    )

    # A single-character word is too short for an edit to be evidence of
    # anything; "a" and "i" would match every other one-letter token.
    if len(short_word) < 3 or len(long_word) - len(short_word) > 1:
        return False

    if len(long_word) == len(short_word):
        return sum(
            a != b for a, b in zip(long_word, short_word)
        ) == 1

    for index in range(len(long_word)):
        if long_word[:index] + long_word[index + 1:] == short_word:
            return True

    return False


def _command_words_match(typed, actual):
    """Compare a typed phrase to a command name, tolerating one typo."""
    if len(typed) != len(actual):
        return False

    return all(
        _within_one_edit(left, right) for left, right in zip(typed, actual)
    )


def near_miss_command(user_input):
    """
    Name an unrecognised command instead of letting the model improvise one.

    Input that matches nothing used to fall straight through to the
    director, which answered as though the action had been carried out:
    "finish goals" produced "I am done with the goals", and "drop all" and
    "finish" produced stage directions describing a system that had
    released its hold. Nothing had run. The model has no way to know a
    command exists, so it treats an instruction it cannot place as one it
    should narrate.

    Deliberately narrow. It fires only on a short phrase that is one edit
    away from a real command name, because the cost of a false positive --
    refusing a sentence the operator meant as conversation -- is worse than
    the cost of a miss, which merely restores the old behaviour.

    Returns the correction, or None to let ordinary conversation proceed.
    """
    if not isinstance(user_input, str):
        return None

    text = " ".join(user_input.strip().split()).rstrip("?!.").lower()
    words = text.split()

    if not words or "?" in user_input:
        return None

    if text in _UNBUILT_REQUESTS:
        return _UNBUILT_REQUESTS[text]

    hinted = _PHRASE_HINTS.get(text)

    if hinted:
        entry = next(
            (item for item in COMMANDS if item["name"] == hinted), None
        )

        if entry is not None and entry["dev_only"] and not DEV_MODE:
            return (
                f"'{user_input.strip()}' is not a command, and nothing ran.\n"
                f"The real one is '{entry['usage']}', which needs developer "
                "mode. Type 'dev mode' first."
            )

        return (
            f"'{user_input.strip()}' is not a command, and nothing ran.\n"
            f"Did you mean: {hinted}"
        )

    if len(words) > MAX_NEAR_MISS_WORDS:
        return None

    # Only ever advertise commands the operator can actually run; the
    # developer gate above already answers for the rest.
    names = [
        entry["name"]
        for entry in COMMANDS
        if not entry["dev_only"] or DEV_MODE
    ]

    # A real command name is never a near miss. try_handle_command runs
    # first in production so this is unreachable there, but the guard keeps
    # the function honest when called on its own.
    if text in set(names):
        return None

    suggestions = []

    for name in names:
        parts = name.split()

        # "finish goals" -> a real command with one stray word attached.
        # The stray word must not be conversational, or "my goals" and
        # "the goals" become errors instead of chat.
        if len(words) != len(parts) + 1:
            continue

        # One typo tolerated per word, so a plural that the table spells
        # differently still resolves: "finish goal" reaches "goals" instead
        # of reaching the director, which answered "I'm finishing the goal".
        if (
            _command_words_match(words[1:], parts)
            and words[0] not in _CONVERSATIONAL_WORDS
        ):
            suggestions.append(name)
        elif (
            _command_words_match(words[:-1], parts)
            and words[-1] not in _CONVERSATIONAL_WORDS
        ):
            suggestions.append(name)

    if not suggestions:
        # Nothing resembles a command. If the phrase is a bare instruction
        # built on a state-changing verb, saying so is still better than
        # letting it be narrated as done. Any ordinary conversational word
        # disqualifies it, which is what keeps "can you drop me a line" and
        # "i want to finish this" out.
        if (
            words[0] in _UNPERFORMED_ACTION_VERBS
            and not any(word in _CONVERSATIONAL_WORDS for word in words)
        ):
            return (
                f"'{user_input.strip()}' is not a command, and nothing ran.\n"
                "Nothing was dropped, finished, cleared or changed.\n"
                "\n"
                "Type 'help' for the full list."
            )

        return None

    # Shortest first: the closest match is the most useful guess.
    suggestions = sorted(dict.fromkeys(suggestions), key=lambda n: (len(n), n))
    lines = [f"'{user_input.strip()}' is not a command, and nothing ran."]

    if len(suggestions) == 1:
        lines.append(f"Did you mean: {suggestions[0]}")
    else:
        lines.append("Did you mean one of these?")
        lines.extend(f"  {name}" for name in suggestions[:4])

    lines.append("")
    lines.append("Type 'help' for the full list.")

    return "\n".join(lines)
