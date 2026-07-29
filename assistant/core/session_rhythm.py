"""How long a session ran, and how it compares to the ones before it.

`time_awareness` answers "what time is it" and "how long was I closed".
This answers a different question: "is this session unusual". Both are
counted rather than felt.

The distinction that keeps this honest is not whether the assistant says
"I". It is whether the fact underneath is real and checkable. "Six hours,
the longest session I have a record of" is first person, and every part of
it can be verified against the file this module writes. "I felt every
minute of that" cannot be verified against anything, and this module gives
no ground for saying it.

So: durations, gaps, counts, and comparisons. No claim about what happened
during a gap, because nothing was running to have anything happen to it,
and no claim that a long session was experienced as long.

Only timings are recorded -- never text, never window titles, never what was
discussed. A pause length is still behavioural data, so recording is opt-in
and the file is plain JSON the operator can read and delete.
"""
import json
import os
import time

from core.config import ASSISTANT_ROOT

RHYTHM_FILE = os.path.join(ASSISTANT_ROOT, "memory", "session_rhythm.json")

# A pause longer than this is a break rather than a slow reply, and mixing
# the two makes a median meaningless.
BREAK_SECONDS = 20 * 60

# Keep the file small and readable by hand. This is a rhythm, not a log.
MAX_SESSIONS = 200


class Session:
    """One run, measured from construction."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self.started = clock()
        self.turns = []
        self._last_turn = None

    def note_turn(self):
        """Record that an exchange completed, and the pause before it."""
        now = self._clock()
        gap = None if self._last_turn is None else now - self._last_turn
        self.turns.append({"at": now, "gap": gap})
        self._last_turn = now
        return gap

    def seconds(self):
        return max(0.0, self._clock() - self.started)

    def pauses(self):
        """Gaps between consecutive turns, breaks excluded."""
        return [t["gap"] for t in self.turns
                if t["gap"] is not None and t["gap"] < BREAK_SECONDS]

    def breaks(self):
        return [t["gap"] for t in self.turns
                if t["gap"] is not None and t["gap"] >= BREAK_SECONDS]

    def summary(self):
        pauses = self.pauses()
        return {
            "started": self.started,
            "seconds": self.seconds(),
            "turns": len(self.turns),
            "median_pause": _median(pauses),
            "longest_pause": max(pauses) if pauses else None,
            "breaks": len(self.breaks()),
        }


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def load(path=None):
    """Past session summaries, oldest first. Missing or damaged reads empty.

    A damaged rhythm file must not stop the assistant starting. Losing a
    comparison is a small thing; refusing to run over it is not.
    """
    target = path or RHYTHM_FILE
    try:
        with open(target, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    sessions = data.get("sessions") if isinstance(data, dict) else None
    return sessions if isinstance(sessions, list) else []


def record(summary, path=None):
    """Append one session summary, keeping the file bounded."""
    target = path or RHYTHM_FILE
    sessions = load(target)
    sessions.append(summary)
    sessions = sessions[-MAX_SESSIONS:]
    folder = os.path.dirname(target)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump({"sessions": sessions}, handle, indent=1)
    os.replace(tmp, target)
    return len(sessions)


def rank(seconds, history):
    """Where this duration sits among past ones. (position, total).

    Position 1 is the longest. Returns (None, 0) with no history, because
    "the longest session so far" is not a fact when there is nothing to
    compare against -- it is just the only one.
    """
    durations = [s.get("seconds") for s in history
                 if isinstance(s.get("seconds"), (int, float))]
    if not durations:
        return None, 0
    longer = sum(1 for d in durations if d > seconds)
    return longer + 1, len(durations)


# Pacing anything visual at a fixed speed is a guess about the viewer.
# Rhythm is a measured alternative: someone who answers in eight seconds
# and someone who answers in ninety are not reading at the same rate, and
# the difference has been counted rather than assumed.
#
# Bounded hard, because a single unusual session should not make an
# animation unwatchable in either direction, and because a multiplier
# derived from two data points is barely evidence.
PACE_MIN = 0.6
PACE_MAX = 1.8
PACE_REFERENCE_SECONDS = 25.0
PACE_MIN_SESSIONS = 3


def typical_pause(history=None):
    """Median of past sessions' median pauses, or None when unknown."""
    past = load() if history is None else history
    medians = [s.get("median_pause") for s in past
               if isinstance(s.get("median_pause"), (int, float))
               and s.get("median_pause") > 0]
    if len(medians) < PACE_MIN_SESSIONS:
        return None
    return _median(medians)


def viewing_pace(history=None):
    """A duration multiplier for rendered animations.

    Above 1.0 means hold frames longer, for an operator who takes their
    time. Returns exactly 1.0 when there is not enough history to have
    measured anything, rather than inventing a preference.
    """
    pause = typical_pause(history)
    if pause is None:
        return 1.0
    ratio = pause / PACE_REFERENCE_SECONDS
    return max(PACE_MIN, min(PACE_MAX, ratio))


def describe(session, history=None, describe_duration=None):
    """A checkable sentence or two about this session's shape.

    Every clause here corresponds to a number in the rhythm file. Nothing
    is inferred about how the time felt, because nothing measured that.
    """
    if describe_duration is None:
        from core.time_awareness import describe_duration as _dd
        describe_duration = _dd

    past = load() if history is None else history
    summary = session.summary()
    seconds = summary["seconds"]
    lines = [f"This session has run {describe_duration(seconds)}"]

    if summary["turns"]:
        lines[0] += f" across {summary['turns']} exchanges"
    lines[0] += "."

    position, total = rank(seconds, past)
    if position == 1 and total >= 1:
        lines.append(
            f"That is the longest of the {total + 1} sessions I have a record "
            "of."
        )
    elif position is not None and total >= 3:
        lines.append(
            f"That places it {position} of {total + 1} by length."
        )

    median = summary["median_pause"]
    if median is not None and summary["turns"] >= 4:
        lines.append(
            f"Typical gap between exchanges: {describe_duration(median)}."
        )

    if summary["breaks"]:
        count = summary["breaks"]
        word = "break" if count == 1 else "breaks"
        lines.append(
            f"{count} {word} of twenty minutes or more, which I noticed only "
            "by the clock -- nothing ran in between."
        )

    return " ".join(lines)
