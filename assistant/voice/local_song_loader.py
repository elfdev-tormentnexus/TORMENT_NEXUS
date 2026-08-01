"""Load operator-owned song scores without putting them in the source tree.

Local songs are data, not Python plugins.  Each definition is parsed from the
operator's LocalAppData folder, validated against tight structural and size
bounds, and converted with a caller-supplied ``Song`` factory.  Keeping the
factory injected avoids importing ``offline_voice`` back into this module.
"""

from dataclasses import dataclass
import json
import math
import os
import re


FORMAT_VERSION = 1
MAX_DEFINITION_BYTES = 512 * 1024
MAX_DEFINITIONS = 32
MAX_SCORE_SEGMENTS = 4096
MAX_PERFORMANCE_SECONDS = 20 * 60

_COMMAND = re.compile(r"^sing [a-z0-9]+(?: [a-z0-9]+){1,6}$")
_DISPLAY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 '&(),.\-]{0,79}$")
_CACHE_FILENAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}\.wav$")
_DEFINITION_FILENAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}\.json$")
_CHORD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9#b+()\-/]{0,23}$")
_SPOKEN_TOKEN = re.compile(r"^[A-Za-z][A-Za-z'\-]{0,39}$")

_REQUIRED_KEYS = frozenset({
    "format_version",
    "command",
    "name",
    "score",
    "eighth_seconds",
    "harmony",
    "chords",
    "intro_melody",
    "cache_filename",
    "accompaniment_gain",
})
_OPTIONAL_KEYS = frozenset({"vocal_semitones", "measure_units"})


class LocalSongError(ValueError):
    """One private definition failed the data-only song contract."""


@dataclass(frozen=True)
class LocalSongEntry:
    command: str
    song: object
    source_name: str


@dataclass(frozen=True)
class LocalSongIssue:
    source_name: str
    reason: str


@dataclass(frozen=True)
class LocalSongLoadResult:
    entries: tuple
    issues: tuple


def default_directory(environ=None):
    """Return the per-user private-song folder, or ``None`` off Windows."""
    environ = os.environ if environ is None else environ
    local_appdata = str(environ.get("LOCALAPPDATA", "")).strip()

    if not local_appdata:
        return None

    return os.path.join(
        os.path.realpath(os.path.expandvars(local_appdata)),
        "TORMENT_NEXUS",
        "private_songs",
    )


def _unique_object(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise LocalSongError(f"duplicate JSON key: {key}")
        result[key] = value

    return result


def _reject_constant(value):
    raise LocalSongError(f"non-finite JSON number: {value}")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _bounded_number(value, label, lower, upper):
    if not _is_number(value) or not math.isfinite(float(value)):
        raise LocalSongError(f"{label} must be a finite number")

    value = float(value)
    if not lower <= value <= upper:
        raise LocalSongError(f"{label} must be between {lower} and {upper}")

    return value


def _midi_note(value, label, allow_none=False):
    if value is None and allow_none:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise LocalSongError(f"{label} must be an integer MIDI note")

    if not 0 <= value <= 127:
        raise LocalSongError(f"{label} must be between 0 and 127")

    return value


def _duration(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 96:
        raise LocalSongError(f"{label} must be an integer from 1 to 96")
    return value


def _measure_units(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise LocalSongError("measure_units must be 4, 6, or 8")
    if value not in {4, 6, 8}:
        raise LocalSongError("measure_units must be 4, 6, or 8")
    return value


def _parse_score(value):
    if not isinstance(value, list) or not value:
        raise LocalSongError("score must be a non-empty array")
    if len(value) > MAX_SCORE_SEGMENTS:
        raise LocalSongError("score has too many segments")

    parsed = []
    for index, segment in enumerate(value):
        label = f"score[{index}]"
        if not isinstance(segment, list) or len(segment) != 3:
            raise LocalSongError(f"{label} must contain text, note, and duration")

        text, note, units = segment
        if text is None:
            if note is not None:
                raise LocalSongError(f"{label} silence must use a null note")
        else:
            if not isinstance(text, str) or not _SPOKEN_TOKEN.fullmatch(text):
                raise LocalSongError(f"{label} has an invalid spoken token")
            note = _midi_note(note, f"{label} note")

        parsed.append((text, note, _duration(units, f"{label} duration")))

    return tuple(parsed)


def _parse_intro(value):
    if not isinstance(value, list):
        raise LocalSongError("intro_melody must be an array")
    if len(value) > MAX_SCORE_SEGMENTS:
        raise LocalSongError("intro_melody has too many segments")

    parsed = []
    for index, segment in enumerate(value):
        label = f"intro_melody[{index}]"
        if not isinstance(segment, list) or len(segment) != 2:
            raise LocalSongError(f"{label} must contain note and duration")
        note, units = segment
        parsed.append((
            _midi_note(note, f"{label} note", allow_none=True),
            _duration(units, f"{label} duration"),
        ))

    return tuple(parsed)


def _parse_harmony(value):
    if not isinstance(value, dict) or not 1 <= len(value) <= 64:
        raise LocalSongError("harmony must contain between 1 and 64 chords")

    parsed = {}
    for name, voicing in value.items():
        if not isinstance(name, str) or not _CHORD_NAME.fullmatch(name):
            raise LocalSongError("harmony contains an invalid chord name")
        if not isinstance(voicing, list) or not 2 <= len(voicing) <= 8:
            raise LocalSongError(f"harmony[{name}] must contain 2 to 8 notes")
        parsed[name] = tuple(
            _midi_note(note, f"harmony[{name}][{index}]")
            for index, note in enumerate(voicing)
        )

    return parsed


def _parse_chords(value, harmony):
    if not isinstance(value, list) or not value:
        raise LocalSongError("chords must be a non-empty array")
    if len(value) > MAX_SCORE_SEGMENTS:
        raise LocalSongError("chords has too many measures")

    parsed = []
    for index, name in enumerate(value):
        if not isinstance(name, str) or name not in harmony:
            raise LocalSongError(f"chords[{index}] is not defined in harmony")
        parsed.append(name)

    return tuple(parsed)


def _read_document(path):
    with open(path, "rb") as handle:
        raw = handle.read(MAX_DEFINITION_BYTES + 1)

    if len(raw) > MAX_DEFINITION_BYTES:
        raise LocalSongError("definition exceeds the 512 KiB limit")

    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )


def load_song_file(path, song_factory, private_directory=None):
    """Validate one JSON definition and construct its Song-compatible value."""
    source_name = os.path.basename(path)
    if not _DEFINITION_FILENAME.fullmatch(source_name):
        raise LocalSongError("definition filename is not safe")

    data = _read_document(path)
    if not isinstance(data, dict):
        raise LocalSongError("definition root must be a JSON object")

    keys = frozenset(data)
    missing = sorted(_REQUIRED_KEYS - keys)
    unknown = sorted(keys - _REQUIRED_KEYS - _OPTIONAL_KEYS)
    if missing:
        raise LocalSongError("missing fields: " + ", ".join(missing))
    if unknown:
        raise LocalSongError("unknown fields: " + ", ".join(unknown))
    if data["format_version"] != FORMAT_VERSION:
        raise LocalSongError(f"format_version must be {FORMAT_VERSION}")

    command_text = data["command"]
    if not isinstance(command_text, str) or not _COMMAND.fullmatch(command_text):
        raise LocalSongError("command must be a lowercase 'sing ...' phrase")

    name = data["name"]
    if not isinstance(name, str) or not _DISPLAY_NAME.fullmatch(name):
        raise LocalSongError("name contains unsupported characters")

    cache_filename = data["cache_filename"]
    if not isinstance(cache_filename, str) or not _CACHE_FILENAME.fullmatch(
        cache_filename
    ):
        raise LocalSongError("cache_filename must be a simple lowercase .wav name")

    score = _parse_score(data["score"])
    intro = _parse_intro(data["intro_melody"])
    harmony = _parse_harmony(data["harmony"])
    chords = _parse_chords(data["chords"], harmony)
    eighth_seconds = _bounded_number(
        data["eighth_seconds"], "eighth_seconds", 0.04, 2.0
    )
    accompaniment_gain = _bounded_number(
        data["accompaniment_gain"], "accompaniment_gain", 0.0, 1.0
    )
    vocal_semitones = _bounded_number(
        data.get("vocal_semitones", 0.0), "vocal_semitones", -24.0, 24.0
    )
    measure_units = _measure_units(data.get("measure_units", 6))

    total_units = sum(units for _text, _note, units in score)
    if total_units % measure_units:
        raise LocalSongError(
            "score duration must end on a complete measure"
        )
    if len(chords) != total_units // measure_units:
        raise LocalSongError("chords must contain exactly one entry per score measure")
    if total_units * eighth_seconds > MAX_PERFORMANCE_SECONDS:
        raise LocalSongError("performance exceeds the 20-minute limit")

    intro_units = sum(units for _note, units in intro)
    leading_silence = 0
    for text, _note, units in score:
        if text is not None:
            break
        leading_silence += units
    if intro_units > leading_silence:
        raise LocalSongError("intro_melody extends beyond the score's leading silence")

    private_directory = private_directory or os.path.dirname(os.path.abspath(path))
    cache_path = os.path.join(
        os.path.realpath(private_directory),
        "cache",
        cache_filename,
    )

    try:
        song = song_factory(
            name=name,
            score=score,
            eighth_seconds=eighth_seconds,
            harmony=harmony,
            chords=chords,
            intro_melody=intro,
            cache_path=cache_path,
            accompaniment_gain=accompaniment_gain,
            vocal_semitones=vocal_semitones,
            measure_units=measure_units,
        )
    except TypeError as error:
        raise LocalSongError(f"song factory rejected the definition: {error}") from error

    return LocalSongEntry(command_text, song, source_name)


def load_local_songs(song_factory, directory=None):
    """Load valid local definitions; isolate a bad file from the rest."""
    directory = default_directory() if directory is None else directory
    if not directory or not os.path.isdir(directory):
        return LocalSongLoadResult((), ())

    entries = []
    issues = []
    seen_commands = set()
    seen_caches = set()

    try:
        with os.scandir(directory) as iterator:
            candidates = sorted(iterator, key=lambda item: item.name.lower())
    except OSError as error:
        return LocalSongLoadResult((), (LocalSongIssue("<directory>", str(error)),))

    json_candidates = [
        entry for entry in candidates if entry.name.lower().endswith(".json")
    ]
    if len(json_candidates) > MAX_DEFINITIONS:
        issues.append(LocalSongIssue(
            "<directory>",
            f"only the first {MAX_DEFINITIONS} JSON definitions were considered",
        ))

    for candidate in json_candidates[:MAX_DEFINITIONS]:
        try:
            if candidate.is_symlink() or not candidate.is_file(follow_symlinks=False):
                raise LocalSongError("definition must be a regular non-link file")
            entry = load_song_file(
                candidate.path,
                song_factory,
                private_directory=directory,
            )
            cache_name = os.path.normcase(os.path.basename(entry.song.cache_path))
            if entry.command in seen_commands:
                raise LocalSongError("command duplicates another local definition")
            if cache_name in seen_caches:
                raise LocalSongError("cache_filename duplicates another definition")
            seen_commands.add(entry.command)
            seen_caches.add(cache_name)
            entries.append(entry)
        except (LocalSongError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            issues.append(LocalSongIssue(candidate.name, str(error)))

    return LocalSongLoadResult(tuple(entries), tuple(issues))
