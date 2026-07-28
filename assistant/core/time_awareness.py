"""
Grounded awareness of local clock time and conversational gaps.

This is intentionally clock awareness, not a simulation of hidden activity.
TORMENT_NEXUS can know that time passed while it was closed because the
previous completed turn carries a timestamp. It cannot claim to have watched,
waited, thought, or felt anything during that interval.
"""

import re
from datetime import datetime


_HISTORY_STAMP = re.compile(r"^\[([^\]\r\n]+)\]$", re.MULTILINE)


def _localize(value):
    """Return a timezone-aware local datetime without changing the instant."""
    if value.tzinfo is None:
        return value.astimezone()
    return value.astimezone()


def _history_last_interaction(history):
    """Read the newest valid conversation timestamp from the audit history."""
    matches = _HISTORY_STAMP.findall(str(history or ""))

    for raw in reversed(matches):
        try:
            return _localize(datetime.fromisoformat(raw.strip()))
        except (TypeError, ValueError):
            continue

    return None


def describe_duration(seconds):
    """Compact, human-readable elapsed time without false precision."""
    try:
        total = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        total = 0

    if total < 10:
        return "a few seconds"
    if total < 60:
        return f"{total} seconds"

    minutes, seconds = divmod(total, 60)
    if minutes < 60:
        if minutes == 1:
            return "about 1 minute"
        return f"about {minutes} minutes"

    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        pieces = [f"{hours} hour" + ("" if hours == 1 else "s")]
        if minutes:
            pieces.append(
                f"{minutes} minute" + ("" if minutes == 1 else "s")
            )
        return ", ".join(pieces)

    days, hours = divmod(hours, 24)
    pieces = [f"{days} day" + ("" if days == 1 else "s")]
    if hours:
        pieces.append(f"{hours} hour" + ("" if hours == 1 else "s"))
    return ", ".join(pieces)


def _display_time(value):
    return value.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z").replace(
        " 0",
        " ",
    )


class TimeAwareness:
    """Session clock plus the timestamp of the previous completed turn."""

    def __init__(self, history="", session_started=None):
        started = session_started or datetime.now().astimezone()
        self.session_started_at = _localize(started)
        self.last_interaction_at = _history_last_interaction(history)

    def note_interaction(self, when=None):
        """Remember a completed turn for the next prompt in this process."""
        self.last_interaction_at = _localize(
            when or datetime.now().astimezone()
        )

    def context(self, now=None):
        """Trusted local-clock facts for one model turn."""
        current = _localize(now or datetime.now().astimezone())
        session_seconds = (
            current - self.session_started_at
        ).total_seconds()
        lines = [
            f"- Current local date and time: {_display_time(current)}",
            (
                "- Current session has been open for: "
                f"{describe_duration(session_seconds)}"
            ),
        ]

        if self.last_interaction_at is None:
            lines.append(
                "- Previous recorded conversation: none; this appears to be "
                "a fresh conversational history."
            )
            return "\n".join(lines)

        elapsed = (current - self.last_interaction_at).total_seconds()
        lines.append(
            "- Previous recorded conversation turn: "
            f"{_display_time(self.last_interaction_at)}"
        )

        if elapsed < 0:
            lines.append(
                "- Time since that turn: unavailable because the local system "
                "clock is earlier than the saved timestamp."
            )
        else:
            lines.append(
                "- Time since that turn: "
                f"{describe_duration(elapsed)}"
            )

        return "\n".join(lines)
