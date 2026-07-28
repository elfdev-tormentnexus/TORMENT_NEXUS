"""
Half-duplex, fully offline speech input and output.

Listening uses Sherpa-ONNX, a small quantized Moonshine English model, and
Silero VAD. A dedicated feminine Piper voice supplies ordinary speech, whose
vocal tract is retained while a dry chromatic carrier supplies the deliberately
constrained machine pitch. A fixed carrier also gives songs their exact notes.
Optional packages are imported only when audio mode is requested, so normal
text chat has no voice dependency or startup cost.
"""

import copy
from dataclasses import dataclass
import hashlib
import io
import os
import re
import threading
import time
import wave

from core.config import (
    VOICE_ASR_DIR,
    VOICE_CADENCE_STRENGTH,
    VOICE_DAISY_ACCOMPANIMENT_GAIN,
    VOICE_DAISY_CACHE,
    VOICE_INPUT_CHANNELS,
    VOICE_INPUT_DEVICE,
    VOICE_NUM_THREADS,
    VOICE_OUTPUT_DEVICE,
    VOICE_PITCH_SEMITONES,
    VOICE_ROBOT_ENABLED,
    VOICE_ROBOT_FORMANT_SHIFT,
    VOICE_ROBOT_STRENGTH,
    VOICE_SAMPLE_RATE,
    VOICE_SPEECH_LENGTH_SCALE,
    VOICE_SPEECH_NOISE_SCALE,
    VOICE_SPEECH_NOISE_W_SCALE,
    VOICE_SPEECH_PAUSE_SECONDS,
    VOICE_SPEECH_CLAUSE_PAUSE_SECONDS,
    VOICE_VOWEL_STRETCH,
    VOICE_PITCH_FLATTEN,
    VOICE_SPEECH_VOCODER,
    VOICE_SPEECH_CARRIER_HZ,
    VOICE_TTS_NAME,
    VOICE_TTS_MODEL,
    VOICE_TTS_SPEAKER,
    VOICE_VAD_MODEL,
)


class VoiceSetupError(RuntimeError):
    pass


class VoiceRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Song:
    """The musical material and cache identity for one offline performance."""

    name: str
    score: tuple
    eighth_seconds: float
    harmony: dict
    chords: tuple
    intro_melody: tuple
    cache_path: str
    accompaniment_gain: float


_ASR_FILES = {
    "preprocessor": "preprocess.onnx",
    "encoder": "encode.int8.onnx",
    "uncached_decoder": "uncached_decode.int8.onnx",
    "cached_decoder": "cached_decode.int8.onnx",
    "tokens": "tokens.txt",
}


def _device_value(value):
    if value is None or value == "":
        return None

    text = str(value).strip()
    return int(text) if text.isdigit() else text


def _dependency_error(require_microphone=True):
    missing = []

    modules = [
        ("numpy", "numpy"),
        ("sounddevice", "sounddevice"),
    ]

    if require_microphone:
        modules.append(("sherpa_onnx", "sherpa-onnx"))

    for module_name, display_name in modules:
        try:
            __import__(module_name)
        except (ImportError, OSError):
            missing.append(display_name)

    try:
        from piper import PiperVoice as _PiperVoice  # noqa: F401
    except (ImportError, OSError):
        # A separate, unrelated package also uses the top-level name "piper".
        # Checking the actual class prevents that package from producing a
        # false "ready" report.
        missing.append("piper-tts")

    if missing:
        return "Missing voice packages: " + ", ".join(missing)

    return None


def setup_issues(check_devices=True, require_microphone=False):
    """Return reasons typed-to-spoken audio mode cannot start."""
    issues = []
    dependency_issue = _dependency_error(require_microphone=require_microphone)

    if dependency_issue:
        issues.append(dependency_issue)

    required = [VOICE_TTS_MODEL, VOICE_TTS_MODEL + ".json"]

    if require_microphone:
        required.append(VOICE_VAD_MODEL)
        required.extend(
            os.path.join(VOICE_ASR_DIR, name)
            for name in _ASR_FILES.values()
        )

    missing_files = [path for path in required if not os.path.isfile(path)]

    if missing_files:
        issues.append(
            "Missing offline speech models under models/voice "
            f"({len(missing_files)} file{'s' if len(missing_files) != 1 else ''})"
        )

    if check_devices and not dependency_issue:
        try:
            import sounddevice as sd

            sd.query_devices(_device_value(VOICE_OUTPUT_DEVICE), "output")

            if require_microphone:
                sd.query_devices(_device_value(VOICE_INPUT_DEVICE), "input")
                sd.check_input_settings(
                    device=_device_value(VOICE_INPUT_DEVICE),
                    channels=VOICE_INPUT_CHANNELS,
                    dtype="float32",
                    samplerate=VOICE_SAMPLE_RATE,
                )
        except Exception as error:
            issues.append(f"Audio device unavailable: {error}")

    return issues


# Runtime overrides for things that were previously environment-only.
#
# A beta tester asked for reading speed and a way to choose the
# microphone. Both already existed as environment variables, which means
# restarting to change them -- fine for a developer, useless for someone
# adjusting by ear mid-conversation.
_pace_override = None
_input_override = None
_output_override = None


def speech_pace():
    """Current length_scale. Higher is slower."""
    return _pace_override if _pace_override is not None else VOICE_SPEECH_LENGTH_SCALE


def set_speech_pace(value):
    """
    Set reading speed. Returns the value actually applied.

    Bounded because Piper degrades badly outside this range -- far below
    0.6 the words run together, far above 3.0 it stops sounding like
    speech and starts sounding like a fault.
    """
    global _pace_override

    _pace_override = max(0.5, min(3.0, float(value)))
    return _pace_override


def input_device():
    return _input_override if _input_override is not None else VOICE_INPUT_DEVICE


def output_device():
    return _output_override if _output_override is not None else VOICE_OUTPUT_DEVICE


def set_input_device(value):
    global _input_override
    _input_override = value
    return value


def set_output_device(value):
    global _output_override
    _output_override = value
    return value


def audio_devices():
    """
    Every input and output the machine reports.

    Returns (inputs, outputs, error). Each entry is (index, name,
    channels, is_default). Errors are returned rather than raised: a
    listing that cannot be produced should say so, not take the command
    down.
    """
    try:
        import sounddevice as sd
    except ImportError as error:
        return [], [], f"sounddevice is not installed: {error}"

    try:
        devices = sd.query_devices()
        default_in, default_out = sd.default.device
    except Exception as error:
        return [], [], f"could not list audio devices: {error}"

    inputs, outputs = [], []

    for index, device in enumerate(devices):
        name = device.get("name", "?")

        if device.get("max_input_channels", 0) > 0:
            inputs.append((index, name, device["max_input_channels"],
                           index == default_in))

        if device.get("max_output_channels", 0) > 0:
            outputs.append((index, name, device["max_output_channels"],
                            index == default_out))

    return inputs, outputs, None


def microphone_issues(check_device=True):
    """Return microphone/recognizer issues without blocking speech output."""
    return setup_issues(
        check_devices=check_device,
        require_microphone=True,
    )


def setup_report():
    issues = setup_issues(require_microphone=False)

    if not issues:
        input_issues = microphone_issues()
        effect = (
            f" Clean feminine machine voice ({VOICE_TTS_NAME}) is enabled at "
            f"{round(VOICE_ROBOT_STRENGTH * 100)}% strength "
            f"with {round(VOICE_CADENCE_STRENGTH * 100)}% stepped cadence."
            if VOICE_ROBOT_ENABLED
            else " The robotic voice effect is disabled."
        )

        if input_issues:
            return (
                True,
                "Audio mode is ready for typed messages and offline speech "
                "output. Microphone input is unavailable, so type into the "
                "audio-mode prompt instead."
                + effect
                + "\n\n"
                + "\n".join("- " + issue for issue in input_issues),
            )

        return (
            True,
            "Audio mode is ready: typed messages, offline microphone "
            "recognition, and Piper speech output are available."
            + effect,
        )

    lines = ["Voice is not ready yet:"]
    lines.extend("- " + issue for issue in issues)
    lines.append("")
    lines.append("Run setup\\setup_voice.bat once, then restart the assistant.")
    lines.append(
        "On the Raspberry Pi, see assistant/voice/README.md for the one-time "
        "audio setup."
    )
    return False, "\n".join(lines)


def _speech_chunks(text, limit=260):
    cleaned = _prepare_for_speech(text)

    if not cleaned:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks = []

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        # Keep sentence boundaries visible to the playback loop. This permits
        # an intentional, cancelable pause instead of relying on a long block
        # of text whose punctuation timing varies by Piper voice.
        while len(sentence) > limit:
            split_at = sentence.rfind(" ", 0, limit + 1)

            if split_at < limit // 2:
                split_at = limit

            chunks.append(sentence[:split_at].strip())
            sentence = sentence[split_at:].strip()

        if sentence:
            chunks.append(sentence)

    return chunks


# Brief lines need more room than a paragraph. At the normal synthesis pace a
# two- to eight-word answer is often over before its deliberately mechanical
# cadence has time to register, while applying the same slowdown to a long
# reply makes it drag. These multipliers are applied by Piper at synthesis
# time, so text streaming and audio playback remain naturally synchronized.
_VERY_SHORT_SPEECH_WORD_LIMIT = 4
_SHORT_SPEECH_WORD_LIMIT = 8
_VERY_SHORT_SPEECH_PACE_MULTIPLIER = 1.20
_SHORT_SPEECH_PACE_MULTIPLIER = 1.11
_MAX_SPEECH_LENGTH_SCALE = 2.30


def _speech_length_scale_for_chunk(text, base_scale=None):
    """Return a more deliberate Piper pace for brief spoken replies."""
    if base_scale is None:
        base_scale = VOICE_SPEECH_LENGTH_SCALE

    words = re.findall(r"[A-Za-z0-9']+", str(text or ""))

    if len(words) <= _VERY_SHORT_SPEECH_WORD_LIMIT:
        multiplier = _VERY_SHORT_SPEECH_PACE_MULTIPLIER
    elif len(words) <= _SHORT_SPEECH_WORD_LIMIT:
        multiplier = _SHORT_SPEECH_PACE_MULTIPLIER
    else:
        multiplier = 1.0

    return min(
        _MAX_SPEECH_LENGTH_SCALE,
        max(0.5, float(base_scale) * multiplier),
    )


def _prepare_for_speech(text):
    """Make terminal/Markdown output pleasant and bounded when read aloud."""
    value = str(text or "")
    value = re.sub(r"```.*?```", " Code details are shown on screen. ", value, flags=re.DOTALL)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"https?://\S+", "link", value)
    value = re.sub(r"[`*_#>|]", " ", value)

    # Give list items terminal punctuation while the line structure still
    # exists -- the whitespace collapse below destroys it.
    #
    # A numbered item has punctuation only on its number, so the sentence
    # splitter ends the sentence THERE and the number joins the previous
    # item: "13. Connected hardware" was spoken as "...searching the web,
    # thirteen." then a pause, then "connected hardware, fourteen." Every
    # pause landed one item late. Turning the number's full stop into a
    # comma and ending the item properly puts the break where the item
    # actually ends.
    def _close_item(match):
        number, body = match.group(1), match.group(2).rstrip()
        tail = "" if body.endswith((".", ":", ";", ",")) else "."
        return f"{number}, {body}{tail}"

    def _close_bullet(match):
        body = match.group(1).rstrip()
        tail = "" if body.endswith((".", ":", ";", ",")) else "."
        return f"{body}{tail}"

    value = re.sub(r"(?m)^[ \t>]*(\d+)[.)]\s+(.+?)[ \t]*$", _close_item, value)
    value = re.sub(r"(?m)^[ \t>]*[-•–]\s+(.+?)[ \t]*$",
                   _close_bullet, value)

    # The displayed answer keeps its punctuation; only the spoken rendering
    # flattens excited and questioning marks so Piper does not inject a
    # cheerful or inquisitive upswing before clinical shaping is applied.
    value = re.sub(r"[!?]+", ".", value)
    value = re.sub(r"\s+", " ", value).strip()

    if len(value) <= 1_200:
        return value

    shortened = value[:1_170].rsplit(" ", 1)[0].rstrip(" ,;:")
    return shortened + ". The rest is shown on screen."


def _resize_matrix(np, matrix, target_samples):
    """Resize only the time axis while retaining the existing channel layout."""
    if len(matrix) == target_samples:
        return matrix

    if not len(matrix):
        return np.zeros((target_samples, matrix.shape[1]), dtype=np.float32)

    source_positions = np.linspace(0.0, 1.0, len(matrix))
    target_positions = np.linspace(0.0, 1.0, target_samples)
    return np.stack(
        [
            np.interp(
                target_positions,
                source_positions,
                matrix[:, channel],
            )
            for channel in range(matrix.shape[1])
        ],
        axis=1,
    ).astype(np.float32)


def _tuned_float(name, default, low, high):
    """Read a clamped tuning override, as core.config does for voice settings."""
    try:
        return max(low, min(high, float(os.environ.get(name, default))))
    except (TypeError, ValueError):
        return default


# Deliberately constrained, downward-biased steps.  The one restrained lift is
# placed before a deeper fall: it creates a dry, skeptical emphasis without
# turning the sentence into a melody.  The rest of the pattern settles down,
# which reads as controlled and faintly sardonic rather than eager or warm.
_CADENCE_SEMITONE_PATTERN = (0.0, -0.75, -0.15, 1.40, -1.10, -0.45, -1.30)

# Measured against 14 minutes of Portal 2 dialogue. The reference delivery
# carries about 2.4 semitones of inflection inside a phrase; this voice was
# measured at 0.64, which is why it read as a dead monotone rather than as a
# cold one. The pattern above keeps its shape -- downward-biased, one
# restrained lift -- and is scaled bodily instead, so more motion does not
# become a different motion.
#
# Deliberately short of the full 2.4: the reference includes lines played for
# emphasis, and matching those exactly makes an assistant that sounds amused.
_CADENCE_DEPTH = _tuned_float("TORMENT_NEXUS_CADENCE_DEPTH", 3.80, 0.0, 8.0)

# Ceiling on upward steps, in semitones. Falls are left unbounded.
_CADENCE_LIFT_CEILING = _tuned_float(
    "TORMENT_NEXUS_CADENCE_LIFT", 2.20, 0.0, 8.0
)

# How far the voice falls from the start of a phrase to the end.
#
# Real speech drifts downward across a phrase; exaggerating that drift is
# what makes a line land as final and uninterested, where a rising contour
# reads as engaged, questioning, or pleased. _speech_chunks splits replies
# into sentences that are synthesized separately, so each sentence gets its
# own descent: it opens near the resting pitch and settles a few semitones
# under it.
#
# This is the dominant pitch motion now. The stepped pattern above is only a
# small jitter riding on top, which is the intended balance -- the direction
# should be audible, the wobble should not.
# A modestly stronger sentence fall makes the final thought land with dry
# certainty. It is still far below a sung contour.
# Raised from 1.10. The reference falls 1.1-1.3 semitones from the first half
# of a phrase to the second; this voice managed 0.18, so sentences ended at
# the pitch they started and nothing ever landed. Each spoken chunk carries
# its own ramp, so this is the fall across one sentence, not one reply.
# Interacts with _CADENCE_DEPTH: the step pattern is downward-biased, so
# deepening it steepens the sentence fall too. Tune the pair together and
# measure, rather than either alone.
_CADENCE_DECLINATION_SEMITONES = _tuned_float(
    "TORMENT_NEXUS_CADENCE_FALL", 0.60, 0.0, 6.0
)

# The final 120ms gets one small additional fall. This is the equivalent of a
# spoken deadpan full stop: it gives sentence endings bite without changing
# duration or inserting an echo/reverb effect.
_CADENCE_TAIL_DROP_SEMITONES = 0.90

# Every utterance previously started on the same carrier, so consecutive
# sentences had identical pitch arcs -- measured at 0.43 semitones of
# variation between phrases against 2.2-2.5 in the reference. That sameness
# is a large part of what marks a voice as synthetic in the dull sense
# rather than the intended one.
#
# The offset is derived from the text, not drawn at random: the same
# sentence is always delivered at the same pitch, which is both reproducible
# for the tests and quietly appropriate for a machine.
# Expressed as the standard deviation to produce, so it can be compared
# directly against a measurement of the reference rather than being a scale
# factor whose effect depends on the shape of the draw below.
_UTTERANCE_PITCH_SPREAD = _tuned_float(
    "TORMENT_NEXUS_PHRASE_PITCH_SPREAD", 2.30, 0.0, 6.0
)

# Standard deviation of the triangular unit draw in _utterance_pitch_bias.
_UNIT_DRAW_STD = 0.408

# However the draw falls, one sentence never leaps more than this far from
# the resting pitch. Beyond it the voice stops sounding like one speaker.
_UTTERANCE_PITCH_LIMIT = 4.5

# What counts as terse, and how far below rest such a line is delivered.
_TERSE_WORD_LIMIT = _tuned_float("TORMENT_NEXUS_TERSE_WORDS", 4, 1, 12)
_TERSE_PITCH_DROP = _tuned_float("TORMENT_NEXUS_TERSE_DROP", 2.10, 0.0, 5.0)


def _utterance_pitch_bias(text):
    """A stable chromatic per-sentence pitch offset in semitones."""
    if not text or _UTTERANCE_PITCH_SPREAD <= 0.0:
        return 0.0

    digest = hashlib.blake2b(
        text.strip().lower().encode("utf-8", "ignore"),
        digest_size=8,
    ).digest()
    # Two independent bytes averaged: a flat draw puts as much weight at the
    # extremes as at the centre, which reads as the voice lurching between
    # two registers rather than varying around one.
    unit = ((digest[0] + digest[1]) / 510.0) * 2.0 - 1.0
    semitones = unit / _UNIT_DRAW_STD * _UTTERANCE_PITCH_SPREAD

    # A short flat statement -- "You're right." "I guess so." -- is the
    # coldest thing this voice says, and it must never be handed an upward
    # offset. Drawing from the hash alone did exactly that: "You are right."
    # landed at +4 semitones, the top of the range, which reads as pert
    # rather than indifferent. Terse lines are pinned below rest, keeping
    # enough of the draw that they do not all sound like one recording.
    if len(re.findall(r"[A-Za-z0-9']+", text)) <= _TERSE_WORD_LIMIT:
        semitones = -_TERSE_PITCH_DROP - abs(semitones) * 0.35

    bounded = max(
        -_UTTERANCE_PITCH_LIMIT,
        min(_UTTERANCE_PITCH_LIMIT, semitones),
    )
    # Keep phrase-to-phrase movement on the same chromatic grid as the
    # carrier. The text-derived choice still gives different sentences their
    # own stable placement, but it never leaves the voice between notes.
    return float(round(bounded))

def _cadence_semitone_curve(
    np,
    frame_energy,
    sample_rate,
    hop,
    strength,
):
    """
    Place asymmetric two-way pitch-offset plateaus at low-energy speech seams.

    The deliberately uneven pattern avoids a musical up/down wobble. Plateau
    boundaries seek local energy minima, so inflections tend to change between
    syllable groups instead of halfway through a vowel. Its plateau duration
    and jump depth are derived from the supplied reference recording.
    """
    curve = np.zeros(len(frame_energy), dtype=np.float32)
    strength = max(0.0, min(1.0, float(strength)))

    if not len(frame_energy) or strength <= 0:
        return curve

    peak = float(np.max(frame_energy))

    if peak <= 1e-7:
        return curve

    active = np.flatnonzero(frame_energy > max(peak * 0.055, 1e-6))

    if not active.size:
        return curve

    active_start = int(active[0])
    active_end = int(active[-1]) + 1
    # Let each pitch decision survive long enough to read as an intentional
    # thought. Faster cycling measured as a generic vocoder pattern, whereas
    # these longer phraselets produce the dry, deliberate timing we want.
    plateau_frames = max(
        3,
        int(round(0.26 * sample_rate / hop)),
    )
    search_frames = max(
        1,
        int(round(0.095 * sample_rate / hop)),
    )
    minimum_frames = max(
        2,
        int(round(0.13 * sample_rate / hop)),
    )
    boundaries = [active_start]
    target = active_start + plateau_frames

    while target < active_end - minimum_frames:
        lower = max(
            boundaries[-1] + minimum_frames,
            target - search_frames,
        )
        upper = min(
            active_end - minimum_frames,
            target + search_frames,
        )

        if upper <= lower:
            break

        local_energy = frame_energy[lower:upper + 1]
        boundary = lower + int(np.argmin(local_energy))
        boundaries.append(boundary)
        target = boundary + plateau_frames

    boundaries.append(active_end)
    pattern = np.asarray(
        _CADENCE_SEMITONE_PATTERN,
        dtype=np.float32,
    ) * strength * _CADENCE_DEPTH

    # Deliberately asymmetric. Scaling the pattern bodily scaled its one
    # lift too, up to nearly five semitones, which is a leap a cold voice
    # does not make -- it starts to sound interested. Falls keep the full
    # depth; rises are capped. The delivery should be able to drop further
    # than it can climb.
    pattern = np.minimum(pattern, _CADENCE_LIFT_CEILING)

    values = [
        float(pattern[index % len(pattern)])
        for index in range(len(boundaries) - 1)
    ]

    # The pattern's one lift is fine mid-phrase -- it is what keeps the line
    # from being a flat slide -- but it must never be the last thing heard.
    # A short sentence covers only two or three plateaus, so the lift can
    # land on or near the final one and the phrase rises into its own full
    # stop: "It's you." was measured climbing 2.19 semitones.
    #
    # Merely rejecting a positive final value was not enough. A lift on the
    # penultimate plateau still left the ending above the opening, because
    # the declination has barely accumulated that early. The last plateau is
    # therefore pinned to the bottom of the pattern outright: every phrase
    # lands cold, and the variety between phrases comes from the per-
    # sentence pitch offset instead.
    if values:
        values[-1] = float(np.min(pattern))

    for index, (start, end) in enumerate(
        zip(boundaries[:-1], boundaries[1:])
    ):
        curve[start:end] = values[index]

    # Thirty-to-fifty milliseconds is enough to prevent zippering without
    # blurring the characteristic step from one plateau to the next.
    transition_frames = max(
        1,
        int(round(0.032 * sample_rate / hop)),
    )

    for index, boundary in enumerate(boundaries[1:-1], start=1):
        start = max(active_start, boundary - transition_frames)
        end = min(active_end, boundary + transition_frames + 1)
        # Read back the assigned values, not the raw pattern, or the ramp
        # into a corrected final plateau would still aim at the lift.
        previous_value = values[index - 1]
        next_value = values[index]
        curve[start:end] = np.linspace(
            previous_value,
            next_value,
            end - start,
            dtype=np.float32,
        )

    fade_frames = min(
        max(1, transition_frames),
        max(1, (active_end - active_start) // 3),
    )
    # Easing in from the resting pitch is right: the phrase should arrive,
    # not start mid-thought.
    curve[active_start:active_start + fade_frames] *= np.linspace(
        0.25,
        1.0,
        fade_frames,
        dtype=np.float32,
    )

    # Easing *out* is not. Scaling a plateau toward zero moves a negative
    # value upward, so the symmetric fade that used to sit here lifted the
    # end of every phrase by three quarters of its own depth -- a rise into
    # the full stop, precisely the delivery this curve exists to avoid. It
    # went unnoticed while the pattern was shallow enough for the lift to be
    # under a semitone. Nothing follows active_end but silence, so there is
    # no discontinuity worth buying it back for.
    # Declination, added after the fade so the descent is present for the
    # whole phrase rather than being tapered away exactly where it matters
    # most -- the final words are the ones that have to land cold.
    span = active_end - active_start

    if _CADENCE_DECLINATION_SEMITONES and span > 1:
        # Descends from the resting pitch, never above it. Centring this
        # ramp on zero lifted the opening of every phrase (measured 197Hz
        # -> 207Hz at the same setting), and a high phrase-onset is exactly
        # what reads as pleased rather than indifferent. The line has to
        # *settle* into cold, not climb first.
        drop = _CADENCE_DECLINATION_SEMITONES * strength
        curve[active_start:active_end] += np.linspace(
            0.0,
            -drop,
            span,
            dtype=np.float32,
        )

    if _CADENCE_TAIL_DROP_SEMITONES and span > 1:
        tail_frames = min(
            span,
            max(2, int(round(0.12 * sample_rate / hop))),
        )
        curve[active_end - tail_frames:active_end] += np.linspace(
            0.0,
            -_CADENCE_TAIL_DROP_SEMITONES * strength,
            tail_frames,
            dtype=np.float32,
        )

    return curve


def _estimate_period(np, frame, sample_rate, fmin=70.0, fmax=400.0):
    """
    Length of one pitch period in samples, or 0 when the frame is unvoiced.

    Plain normalised autocorrelation. Nothing clever is needed here: the
    input is clean single-speaker synthesis, not a noisy recording.
    """
    frame = frame - frame.mean()
    energy = float(np.dot(frame, frame))

    if energy < 1e-8:
        return 0

    correlation = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
    min_lag = max(1, int(sample_rate / fmax))
    max_lag = min(len(correlation) - 1, int(sample_rate / fmin))

    if max_lag <= min_lag:
        return 0

    window = correlation[min_lag:max_lag]
    lag = int(np.argmax(window)) + min_lag

    # A voiced frame repeats itself strongly. Anything weaker is a
    # fricative or silence, where imposing a pitch period would only
    # smear the consonant.
    if correlation[lag] < 0.32 * correlation[0]:
        return 0

    return lag


def _psola_pitch_shift(np, source, sample_rate, semitones, vowel_stretch=1.0,
                       pitch_flatten=1.0):
    """
    Shift pitch while leaving formants where they are.

    Resampling -- which is what _clean_pitch_cadence does -- moves pitch
    and formants together, so lowering a voice with it produces a
    physically larger speaker rather than the same speaker pitched down.
    That is fine for a cadence wobble of well under a semitone, and wrong
    for the several semitones of register change this project needs: the
    target voice is a female vocal tract driven at a low, constrained
    pitch, a combination resampling cannot produce.

    TD-PSOLA gets there by never touching the spectrum at all. The signal
    is cut into grains centred on successive pitch periods, and those
    grains are simply laid back down at a different spacing. Each grain
    keeps its own spectral content -- so the vocal tract is untouched --
    while the rate at which grains repeat, which is the perceived pitch,
    changes. Duration is preserved by mapping output time back to input
    time one-to-one and reusing whichever grain sits nearest.

    vowel_stretch elongates only the voiced parts -- the vowels -- while
    leaving consonants at their original speed. Piper's length_scale
    cannot do this: it slows everything equally, which reads as a person
    talking slowly rather than as a machine. Holding vowels while keeping
    consonants crisp is what makes speech sound synthesised instead of
    spoken, and it is a different lever from pitch entirely. 1.0 disables
    it; 1.6 makes vowels roughly half again as long.

    pitch_flatten compresses the pitch contour toward its own median:
    1.0 leaves it alone, 0.0 makes the voice perfectly monotone. This is
    the piece the stepped cadence could never provide -- that layer only
    *added* small steps on top of whatever contour Piper produced, so the
    underlying expressiveness always survived. Measured against the
    reference recording, GLaDOS holds pitch static for 82% of frames at
    2.43st deviation, where untouched Piper runs 5-6st. Squeezing the
    contour is the only way to close that, and PSOLA can do it because
    grain spacing is already how pitch is produced here.

    Known limit: for shifts approaching an octave down the output grains
    are spaced further apart than the grains are wide, so their overlap
    thins and the result gets rougher. Within a few semitones -- the
    range this is used in -- the overlap stays healthy. Raising pitch has
    the opposite, benign behaviour: grains pack closer and overlap more.
    """
    vowel_stretch = max(1.0, float(vowel_stretch))

    # Normalise shape before any early return, so every path hands back the
    # same rank. The no-op branch used to return the caller's original
    # array untouched, which was 1-D for mono input while the processed
    # branches always returned 2-D.
    if source.ndim == 1:
        source = source[:, None]

    source = source.astype(np.float32, copy=False)

    if (
        abs(semitones) < 0.01
        and vowel_stretch <= 1.001
        and pitch_flatten >= 0.999
    ):
        return source.copy()
    samples, channels = source.shape
    ratio = 2.0 ** (semitones / 12.0)
    mono = source.mean(axis=1)

    # --- period contour -------------------------------------------------
    frame_size = int(0.040 * sample_rate)
    hop = int(0.010 * sample_rate)

    if samples < frame_size * 2:
        return source.copy()

    default_period = max(2, int(sample_rate / 170.0))
    period_at = np.zeros(samples, dtype=np.int32)
    centres, values = [], []

    for start in range(0, samples - frame_size, hop):
        centres.append(start + frame_size // 2)
        values.append(_estimate_period(np, mono[start:start + frame_size], sample_rate))

    if not centres:
        return source.copy()

    # Unvoiced frames inherit the nearest voiced period so grain spacing
    # stays continuous across consonants instead of jumping.
    values = np.asarray(values, dtype=np.float32)
    voiced = values > 0

    if not voiced.any():
        return source.copy()

    values = np.interp(
        np.arange(len(values)),
        np.flatnonzero(voiced),
        values[voiced],
    )
    period_at = np.interp(
        np.arange(samples),
        np.asarray(centres, dtype=np.float64),
        values,
    ).astype(np.int32)
    period_at = np.clip(period_at, 2, default_period * 4)

    # --- pitch-contour compression --------------------------------------
    # Grain width keeps following the real input period; only the spacing
    # between grains is compressed, since spacing is what sets pitch.
    # Geometric interpolation toward the median means a uniform pull in
    # semitones rather than in Hz.
    pitch_flatten = max(0.0, min(1.0, float(pitch_flatten)))
    spacing_at = period_at.astype(np.float64)

    if pitch_flatten < 0.999:
        voiced_samples = np.interp(
            np.arange(samples),
            np.asarray(centres, dtype=np.float64),
            voiced.astype(np.float32),
        ) > 0.5

        if voiced_samples.any():
            median_period = float(np.median(spacing_at[voiced_samples]))

            if median_period > 1.0:
                spacing_at = median_period * np.power(
                    spacing_at / median_period,
                    pitch_flatten,
                )
                spacing_at = np.clip(
                    spacing_at, 2.0, float(default_period * 4)
                )

    # --- output-to-input time map ---------------------------------------
    # Identity when nothing is being stretched, so duration is preserved.
    # With vowel_stretch, voiced samples emit more than one output sample
    # each while consonants stay 1:1 -- the vowels lengthen and the
    # consonants keep their attack.
    if vowel_stretch > 1.001:
        voiced_at = np.interp(
            np.arange(samples),
            np.asarray(centres, dtype=np.float64),
            voiced.astype(np.float32),
        )
        # Smooth the voiced/unvoiced boundary so the stretch ramps in
        # rather than stepping, which would click at the transition.
        emitted = 1.0 + (vowel_stretch - 1.0) * np.clip(voiced_at, 0.0, 1.0)
        output_clock = np.cumsum(emitted)
        total_out = max(4, int(output_clock[-1]))
        input_of_output = np.interp(
            np.arange(total_out, dtype=np.float64),
            output_clock,
            np.arange(samples, dtype=np.float64),
        )
    else:
        total_out = samples
        input_of_output = np.arange(samples, dtype=np.float64)

    # --- analysis marks -------------------------------------------------
    marks = []
    position = 0

    while position < samples:
        marks.append(position)
        position += int(period_at[position])

    if len(marks) < 3:
        return source.copy()

    marks = np.asarray(marks, dtype=np.int64)

    # --- synthesis ------------------------------------------------------
    margin = default_period * 4
    output = np.zeros((total_out + margin, channels), dtype=np.float32)
    weights = np.zeros(total_out + margin, dtype=np.float32)
    out_position = 0.0

    while out_position < total_out:
        centre = int(out_position)
        # Output time is mapped back to input time through
        # input_of_output, which is identity unless vowels are being
        # stretched. Reading the same input region across several output
        # positions is what lengthens a vowel.
        source_centre = int(input_of_output[min(centre, total_out - 1)])
        nearest = int(np.searchsorted(marks, source_centre))
        nearest = min(max(nearest, 0), len(marks) - 1)
        mark = int(marks[nearest])
        period = int(period_at[min(mark, samples - 1)])
        advance = float(spacing_at[min(mark, samples - 1)])
        half = max(2, period)

        start = mark - half
        end = mark + half
        clipped_start = max(0, start)
        clipped_end = min(samples, end)

        if clipped_end - clipped_start < 4:
            out_position += max(1.0, advance / ratio)
            continue

        grain = source[clipped_start:clipped_end]
        window = np.hanning(len(grain)).astype(np.float32)

        write_at = centre - (mark - clipped_start)

        if write_at < 0:
            trim = -write_at
            grain = grain[trim:]
            window = window[trim:]
            write_at = 0

        if len(grain) < 4:
            out_position += max(1.0, advance / ratio)
            continue

        room = len(output) - write_at

        if room < 4:
            break

        grain = grain[:room]
        window = window[:len(grain)]

        output[write_at:write_at + len(grain)] += grain * window[:, None]
        weights[write_at:write_at + len(grain)] += window

        # Wider spacing than the input period means fewer repetitions per
        # second, which is a lower pitch.
        out_position += max(1.0, advance / ratio)

    usable = weights[:total_out] > 1e-6
    result = output[:total_out]
    result[usable] /= weights[:total_out][usable, None]

    source_rms = float(np.sqrt(np.mean(source * source)))
    result_rms = float(np.sqrt(np.mean(result * result)))

    if source_rms and result_rms:
        result *= source_rms / result_rms

    return result


def _clean_pitch_cadence(
    np,
    source,
    sample_rate,
    strength,
    pitch_offset=0.0,
):
    """
    Add two-way pitch-offset steps through clean variable-speed resampling.

    Unlike a phase vocoder, this never decomposes or reconstructs the voice.
    Each low-energy-delimited speech group is simply read at a slightly
    different rate. Pitch and formants rise together, retaining a feminine
    source timbre and producing intentionally uneven machine timing.

    pitch_offset is a constant semitone shift applied on top of the stepped
    cadence, so the whole voice can be dropped into a colder register without
    introducing a carrier or a phase vocoder. It rides the same resampler,
    which means formants move with pitch -- the voice reads as a physically
    larger, flatter speaker rather than a pitched-down small one. Because
    reading slower is what lowers the pitch, a negative offset also
    stretches the audio, which is why the pacing gets more deliberate as it
    gets deeper.
    """
    if source.ndim == 1:
        source = source[:, None]

    source = source.astype(np.float32, copy=False)
    strength = max(0.0, min(1.0, float(strength)))
    pitch_offset = float(pitch_offset)

    no_cadence = strength <= 0
    no_shift = abs(pitch_offset) < 1e-3

    if (no_cadence and no_shift) or len(source) < 2:
        return source.copy()

    frame_size = 512 if sample_rate >= 16_000 else 256
    hop = frame_size // 4
    window = np.hanning(frame_size).astype(np.float32)
    mono = source.mean(axis=1)
    starts = np.arange(0, len(source), hop, dtype=np.int64)
    frame_energy = np.zeros(len(starts), dtype=np.float32)

    for index, start in enumerate(starts):
        frame = np.zeros(frame_size, dtype=np.float32)
        section = mono[start:min(len(mono), start + frame_size)]
        frame[:len(section)] = section
        frame_energy[index] = np.sqrt(
            np.mean((frame * window) ** 2)
        )

    semitone_frames = _cadence_semitone_curve(
        np,
        frame_energy,
        sample_rate,
        hop,
        strength,
    )
    frame_centers = (
        starts.astype(np.float64) + frame_size * 0.5
    )
    input_positions = np.arange(len(source), dtype=np.float64)
    semitone_samples = np.interp(
        input_positions,
        frame_centers,
        semitone_frames,
        left=0.0,
        right=0.0,
    )
    # The stepped cadence rides on top of the constant register shift, so a
    # single resampling pass produces both.
    playback_rates = np.power(
        2.0,
        (semitone_samples + pitch_offset) / 12.0,
    )
    output_clock = np.zeros(len(source), dtype=np.float64)
    output_clock[1:] = np.cumsum(
        1.0 / playback_rates[:-1],
        dtype=np.float64,
    )
    output_count = max(1, int(np.floor(output_clock[-1])) + 1)
    output_positions = np.arange(output_count, dtype=np.float64)
    read_positions = np.interp(
        output_positions,
        output_clock,
        input_positions,
    )
    output = np.stack(
        [
            np.interp(
                read_positions,
                input_positions,
                source[:, channel],
            )
            for channel in range(source.shape[1])
        ],
        axis=1,
    ).astype(np.float32)
    source_rms = float(np.sqrt(np.mean(source * source)))
    output_rms = float(np.sqrt(np.mean(output * output)))

    if source_rms and output_rms:
        output *= (source_rms / output_rms) * 0.99

    return output


# onnxruntime reports an out-of-memory condition as a wall of internal
# arena detail -- a build path, a source line, and a byte count -- with no
# hint that the machine simply has nothing left to give. The byte count is
# usually small, which reads like a bug in the voice rather than a full
# system, and sends you looking in the wrong place entirely.
_ALLOCATION_FAILURE_MARKERS = (
    "failed to allocate memory",
    "bfc_arena",
    "bad_alloc",
    "out of memory",
    "cannot allocate memory",
    "memoryerror",
)


def _load_failure_hint(error):
    """Add a plain-language cause when a load failed for want of memory."""
    text = str(error)

    if not any(m in text.lower() for m in _ALLOCATION_FAILURE_MARKERS):
        return text

    return (
        f"{text}\n\n"
        "This is the machine running out of memory, not a problem with the "
        "voice model -- the size it asked for is small, and it fails only "
        "because there is nothing left to give. Close some applications and "
        "try again. If it keeps happening, restart: on Windows this is "
        "usually the commit charge filling up over days of uptime, which a "
        "reboot clears."
    )


# Frame length for the envelope the voice-mode face reacts to. Short enough
# to catch individual syllables, long enough that the face is not strobing.
SPEECH_ENVELOPE_HOP = 0.025


def _speech_envelope(np, audio, sample_rate, hop_seconds):
    """
    Reduce an utterance to a loudness and a brightness track.

    Two dimensions rather than one: loudness alone cannot tell a vowel from a
    sibilant, and the face reads as reacting to speech, not just to volume,
    when consonants push it differently from open vowels.

    Both are returned as plain lists so the renderer, which has no numpy
    dependency of its own, can index them directly.
    """
    samples = np.asarray(audio, dtype=np.float32)

    if samples.ndim > 1:
        samples = samples.mean(axis=1)

    if samples.size == 0:
        return [], []

    peak = float(np.max(np.abs(samples)))

    if peak <= 0.0:
        return [], []

    samples = samples / peak
    hop = max(1, int(round(hop_seconds * sample_rate)))
    usable = (samples.size // hop) * hop

    if usable < hop:
        return [], []

    frames = samples[:usable].reshape(-1, hop)
    levels = np.sqrt((frames ** 2).mean(axis=1))

    # Loudness is compressed, but only mildly: speech sits well below its
    # peak most of the time, so a linear map leaves the face nearly still,
    # while a hard compression lifts the quiet frames so far that the face
    # never settles and stops reading as reactive at all.
    loudness = np.clip(levels / max(float(levels.max()), 1e-6), 0.0, 1.0)
    loudness = loudness ** 0.75

    # Zero-crossing rate stands in for brightness. It separates fricatives
    # from vowels for a fraction of the cost of a spectrum per frame.
    crossings = np.abs(np.diff(np.signbit(frames).astype(np.int8), axis=1))
    brightness = crossings.mean(axis=1) if crossings.size else levels * 0.0
    brightness = np.clip(brightness / 0.35, 0.0, 1.0)

    return (
        [float(value) for value in loudness],
        [float(value) for value in brightness],
    )


# A consonant lasts about as long as it lasts. Sung vowels do not.
_SUSTAIN_ONSET_SECONDS = 0.070
_SUSTAIN_CODA_SECONDS = 0.055

# Below this much stretch there is no audible smear to correct, and speech
# rendered at its own length must not be reshaped at all.
_SUSTAIN_MIN_RATIO = 1.25


def _sustain_warp(
    np,
    source_samples,
    output_samples,
    source_span,
    output_span,
    sample_rate,
):
    """
    Map output position to source position, holding the vowel, not the word.

    Stretching a syllable uniformly to fill a long note stretches its
    consonants too, so a held "day" arrives as "d-d-d-ay-y-y" -- the slip
    audible on the opening notes, where a 0.34s syllable is asked to cover
    1.26s. Singers do not do this: the onset and release keep roughly their
    spoken length and the vowel absorbs the whole surplus.

    The decision is made on the raw sample counts, not the frame spans. The
    two spans are offset by different amounts (hop against frame_size), so a
    1:1 render still shows output_span a few hundred samples the larger, and
    testing those would quietly reshape ordinary speech as well.

    Returns a pair of breakpoint arrays for np.interp, or (None, None) when
    the note is too close to spoken length to be worth reshaping.
    """
    if source_span <= 0 or output_span <= source_span:
        return None, None

    if output_samples <= source_samples * _SUSTAIN_MIN_RATIO:
        return None, None

    onset = min(
        int(sample_rate * _SUSTAIN_ONSET_SECONDS),
        max(1, int(source_span * 0.30)),
    )
    coda = min(
        int(sample_rate * _SUSTAIN_CODA_SECONDS),
        max(1, int(source_span * 0.25)),
    )

    # Nothing left in the middle to spend the surplus on.
    if onset + coda >= source_span:
        return None, None

    return (
        np.asarray(
            [0.0, onset, output_span - coda, output_span],
            dtype=np.float64,
        ),
        np.asarray(
            [0.0, onset, source_span - coda, source_span],
            dtype=np.float64,
        ),
    )


# The reference voice sits about 8dB lower above 4kHz than this one did.
# That excess is what made the vocoder read as buzz rather than as a smooth
# synthetic voice: the carrier's upper harmonics survive the envelope intact,
# where a real vocal tract would have damped them.
_TILT_CORNER_HZ = _tuned_float("TORMENT_NEXUS_TILT_CORNER_HZ", 1900.0,
                               200.0, 12_000.0)
_TILT_DB_PER_OCTAVE = _tuned_float("TORMENT_NEXUS_TILT_DB_OCTAVE", 3.4,
                                   0.0, 18.0)


def _spectral_tilt(np, signal, sample_rate, corner_hz, db_per_octave):
    """Roll the top end off at a fixed slope above a corner frequency."""
    if db_per_octave <= 0.0 or signal.size == 0:
        return signal

    was_mono = signal.ndim == 1
    matrix = signal[:, None] if was_mono else signal
    spectrum = np.fft.rfft(matrix, axis=0)
    freqs = np.fft.rfftfreq(matrix.shape[0], 1.0 / sample_rate)
    octaves = np.log2(np.maximum(freqs, corner_hz) / corner_hz)
    gain = (10.0 ** (-(db_per_octave * octaves) / 20.0)).astype(np.float32)
    shaped = np.fft.irfft(
        spectrum * gain[:, None],
        n=matrix.shape[0],
        axis=0,
    ).astype(np.float32)

    return shaped[:, 0] if was_mono else shaped


def _chromatic_carrier_frequencies(np, carrier_hz, semitone_offsets):
    """Snap offsets from a carrier's reference note to the chromatic grid.

    This is the digital equivalent of a chromatic pitch-correction pass: the
    carrier can change between phraselets, but it cannot glide or retain
    within-syllable vibrato.  The spectral envelope remains untouched, so it
    does not make Piper's articulation sound sung.
    """
    offsets = np.asarray(semitone_offsets, dtype=np.float32)
    return (
        max(1e-6, float(carrier_hz))
        * np.power(2.0, np.rint(offsets) / 12.0)
    ).astype(np.float32)


def _machine_vocoder(
    np,
    source,
    sample_rate,
    carrier_hz=172.0,
    formant_shift=1.0,
    output_samples=None,
    cadence_strength=0.0,
):
    """
    Replace Piper's vocal cords with a dry, fixed-pitch machine carrier.

    Only the changing spectral envelope is retained, which carries the actual
    consonants and vowels. Source pitch and most natural-human timbre are
    discarded. Supplying output_samples stretches that envelope without
    changing its frequencies, which is also what lets Daisy Bell hold notes.
    """
    if source.ndim == 1:
        source = source[:, None]

    source_samples, channels = source.shape
    output_samples = max(1, int(output_samples or source_samples))
    frame_size = 512 if sample_rate >= 16_000 else 256
    hop = frame_size // 4
    window = np.hanning(frame_size).astype(np.float32)
    output = np.zeros(
        (output_samples + frame_size, channels),
        dtype=np.float32,
    )
    weights = np.zeros(output_samples + frame_size, dtype=np.float32)

    carrier_hz = max(45.0, float(carrier_hz))
    formant_shift = max(0.75, min(1.35, float(formant_shift)))
    carrier_count = output_samples + frame_size
    cadence_strength = max(0.0, min(1.0, float(cadence_strength)))
    semitone_samples = np.zeros(carrier_count, dtype=np.float32)

    if cadence_strength and source_samples > 1:
        # Ordinary speech needs the phrase-level stepped movement that makes
        # the delivery feel deliberately sequenced, while Daisy Bell needs
        # exact held notes.  Derive a shallow contour from voiced-energy
        # groups, then apply it to the carrier only: formants remain fixed and
        # the result never turns into a sung melody.
        analysis_size = 512 if sample_rate >= 16_000 else 256
        analysis_hop = analysis_size // 4
        analysis_window = np.hanning(analysis_size).astype(np.float32)
        mono = source.mean(axis=1)
        starts = np.arange(0, source_samples, analysis_hop, dtype=np.int64)
        energy = np.zeros(len(starts), dtype=np.float32)

        for index, start in enumerate(starts):
            frame = np.zeros(analysis_size, dtype=np.float32)
            section = mono[start:min(source_samples, start + analysis_size)]
            frame[:len(section)] = section
            energy[index] = np.sqrt(np.mean((frame * analysis_window) ** 2))

        cadence_frames = _cadence_semitone_curve(
            np,
            energy,
            sample_rate,
            analysis_hop,
            cadence_strength,
        )
        frame_centres = starts.astype(np.float64) + analysis_size * 0.5
        positions = np.arange(carrier_count, dtype=np.float64)
        source_positions = np.clip(positions, 0, source_samples - 1)
        semitone_samples = np.interp(
            source_positions,
            frame_centres,
            cadence_frames,
            left=0.0,
            right=0.0,
        ).astype(np.float32)

    # Constrain the complete carrier after sentence bias, cadence, and
    # declination have been applied. The sentence carrier itself is already
    # on that grid, so this gives spoken syllable groups the same discrete
    # chromatic placement as a manual pitch-correction pass while retaining
    # a reference tuning that can be measured against the target voice.
    carrier_frequencies = _chromatic_carrier_frequencies(
        np,
        carrier_hz,
        semitone_samples,
    )
    carrier_phase = np.cumsum(
        (2.0 * np.pi * carrier_frequencies) / float(sample_rate),
        dtype=np.float64,
    ).astype(np.float32)
    carrier = np.zeros(carrier_count, dtype=np.float32)
    # One phase-locked oscillator bank stays deliberately stationary. The
    # former detuned second bank and phase drift produced shimmer/chorusing
    # that sounded synth-like and spatial; a stable carrier is drier, flatter,
    # and more clinical.
    harmonic_count = max(
        6,
        min(24, int((sample_rate * 0.45) / carrier_hz)),
    )

    for harmonic in range(1, harmonic_count + 1):
        harmonic_level = (
            (1.0 if harmonic == 1 else 0.82 if harmonic % 2 else 0.58)
            / (harmonic ** 1.12)
        )
        carrier += (
            harmonic_level
            * np.sin(carrier_phase * harmonic + harmonic * 0.09)
        ).astype(np.float32)

    carrier_peak = float(np.max(np.abs(carrier)))

    if carrier_peak:
        carrier /= carrier_peak

    smooth_kernel = np.ones(11, dtype=np.float32) / 11.0
    frequencies = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)
    consonant_mask = np.clip(
        (frequencies - 2_000.0) / 2_000.0,
        0.0,
        1.0,
    )
    source_span = max(0, source_samples - frame_size)
    output_span = max(1, output_samples - hop)
    warp_output, warp_source = _sustain_warp(
        np,
        source_samples,
        output_samples,
        source_span,
        output_span,
        sample_rate,
    )

    for output_start in range(0, output_samples, hop):
        if warp_output is None:
            progress = min(1.0, output_start / output_span)
            source_start = int(round(progress * source_span))
        else:
            source_start = int(round(float(np.interp(
                min(output_start, output_span),
                warp_output,
                warp_source,
            ))))
        source_frame = np.zeros(
            (frame_size, channels),
            dtype=np.float32,
        )
        source_slice = source[
            source_start:min(source_samples, source_start + frame_size)
        ]
        source_frame[:len(source_slice)] = source_slice

        carrier_frame = carrier[
            output_start:output_start + frame_size
        ] * window
        carrier_spectrum = np.fft.rfft(carrier_frame)
        carrier_magnitude = np.abs(carrier_spectrum)
        carrier_envelope = np.convolve(
            carrier_magnitude,
            smooth_kernel,
            mode="same",
        )
        carrier_shape = np.clip(
            carrier_magnitude / (carrier_envelope + 1e-6),
            0.0,
            4.0,
        )
        carrier_phase = carrier_spectrum / (carrier_magnitude + 1e-6)

        for channel in range(channels):
            speech_spectrum = np.fft.rfft(
                source_frame[:, channel] * window
            )
            speech_envelope = np.convolve(
                np.abs(speech_spectrum),
                smooth_kernel,
                mode="same",
            )

            if abs(formant_shift - 1.0) > 1e-4:
                bins = np.arange(
                    len(speech_envelope),
                    dtype=np.float32,
                )
                speech_envelope = np.interp(
                    bins / formant_shift,
                    bins,
                    speech_envelope,
                    left=float(speech_envelope[0]),
                    right=0.0,
                ).astype(np.float32)

            machine_spectrum = (
                speech_envelope * carrier_shape * carrier_phase
            )
            # A narrow unvoiced band keeps S/F/T sounds readable. It carries
            # no vocal pitch and is the only direct source-spectrum remnant.
            machine_spectrum += (
                speech_spectrum * consonant_mask * 0.14
            )
            rendered = np.fft.irfft(
                machine_spectrum,
                n=frame_size,
            ).real
            output[
                output_start:output_start + frame_size,
                channel,
            ] += (rendered * window).astype(np.float32)

        weights[
            output_start:output_start + frame_size
        ] += window * window

    usable = weights[:output_samples] > 1e-6
    output = output[:output_samples]
    output[usable] /= weights[:output_samples][usable, None]

    source_rms = float(np.sqrt(np.mean(source * source))) if source.size else 0.0
    output_rms = float(np.sqrt(np.mean(output * output))) if output.size else 0.0

    if source_rms and output_rms:
        output *= (source_rms / output_rms) * 0.92

    return output


_SPEECH_DIGITAL_EDGE = 0.022
_SUNG_DIGITAL_EDGE = 0.035


def _digital_voice_texture(
    np,
    audio,
    strength,
    *,
    edge_strength,
    drive,
):
    """Add a small, time-aligned digital finish to a machine voice.

    The carrier vocoder already supplies the characteristic synthetic pitch.
    This final pass supplies the restrained quantisation and clock-like
    transients that make the sung voice feel deliberately rendered rather than
    merely filtered.  It never resamples, delays, or mixes a second copy of
    the signal, so consonants remain aligned and ordinary replies stay clear.
    """
    if audio.size == 0:
        return audio

    strength = max(0.0, min(1.0, float(strength)))
    edge_strength = max(0.0, min(0.08, float(edge_strength))) * strength
    drive = max(0.90, min(1.20, float(drive)))
    textured = audio.astype(np.float32, copy=False)

    # The levels are intentionally modest: this is a controlled digital
    # texture, not audible bit-crushing.  Stronger machine treatment makes
    # the stepping a little more apparent, like the sung rendering.
    levels = max(128, int(round(512 - 256 * strength)))
    textured = np.round(textured * levels) / levels

    if edge_strength and len(textured) > 1:
        edge = np.zeros_like(textured)
        edge[1:] = textured[1:] - textured[:-1]
        textured = textured + edge * edge_strength

    return np.tanh(textured * drive).astype(np.float32)


def _encoded_robot_effect(
    np,
    audio,
    sample_rate,
    strength,
    carrier_hz=172.0,
    formant_shift=1.0,
    output_samples=None,
    pitch_lock=False,
    cadence_strength=0.0,
    pitch_offset=0.0,
    vowel_stretch=1.0,
    pitch_flatten=1.0,
):
    """Shape dry speech, or lock it to a carrier when singing exact notes."""
    if audio.size == 0:
        return audio

    strength = max(0.0, min(1.0, float(strength)))
    source = audio.astype(np.float32) / 32768.0
    was_mono = source.ndim == 1
    matrix = source[:, None] if was_mono else source
    target_samples = max(1, int(output_samples or len(matrix)))

    if strength <= 0:
        clean = _resize_matrix(np, matrix, target_samples)
        result = (np.clip(clean, -1.0, 1.0) * 32767.0).astype(np.int16)
        return result[:, 0] if was_mono else result

    if pitch_lock:
        hold = max(1, int(round(sample_rate / 11_000)))
        held = np.repeat(matrix[::hold], hold, axis=0)[:len(matrix)]
        robot = _machine_vocoder(
            np,
            held,
            sample_rate,
            carrier_hz=carrier_hz,
            formant_shift=formant_shift,
            output_samples=target_samples,
        )
    elif VOICE_SPEECH_VOCODER:
        # The same engine sing_daisy_bell uses, minus the note-following.
        #
        # This is the only path here that fully separates pitch from
        # formants: the oscillator bank supplies the excitation while the
        # spectral envelope -- the vocal tract, and therefore the voice's
        # apparent gender -- is taken from Piper's output. A low carrier
        # under a feminine envelope is exactly the combination the target
        # voice has, and the one that resampling and PSOLA cannot make,
        # because both move pitch and formants together.
        #
        # Flatness comes free: a fixed carrier has no pitch deviation at
        # all, so there is nothing left for the cadence layer to suppress.
        robot = _machine_vocoder(
            np,
            matrix,
            sample_rate,
            carrier_hz=carrier_hz,
            formant_shift=formant_shift,
            output_samples=len(matrix),
            cadence_strength=cadence_strength * strength,
        )
        target_samples = len(robot)

        # Damp the carrier's surviving upper harmonics. Applied before the
        # quantisation below, so the digital edge is added to a voice that
        # already has a plausible spectral slope rather than being smoothed
        # away along with the buzz.
        robot = _spectral_tilt(
            np,
            robot,
            sample_rate,
            _TILT_CORNER_HZ,
            _TILT_DB_PER_OCTAVE,
        )

    else:
        # Register shift and cadence wobble are deliberately handled by
        # different tools. PSOLA does the multi-semitone drop because it
        # preserves formants and duration; the resampler keeps the
        # sub-semitone stepped cadence, where its pitch/formant coupling
        # is far too small to hear. Doing the register shift with the
        # resampler was what produced both the "large male" timbre
        # (formants down 25%) and the slow-motion delivery (time
        # stretched 35%).
        shifted = _psola_pitch_shift(
            np,
            matrix,
            sample_rate,
            pitch_offset * strength,
            vowel_stretch=1.0 + (vowel_stretch - 1.0) * strength,
            pitch_flatten=1.0 - (1.0 - pitch_flatten) * strength,
        )
        robot = _clean_pitch_cadence(
            np,
            shifted,
            sample_rate,
            cadence_strength * strength,
        )
        target_samples = len(robot)

    if pitch_lock:
        clean = _resize_matrix(np, matrix, target_samples)
        encoded = clean * (1.0 - strength) + robot * strength
        encoded = _digital_voice_texture(
            np,
            encoded,
            strength,
            edge_strength=_SUNG_DIGITAL_EDGE,
            drive=1.08,
        )
    else:
        # Do not mix a time-warped voice against its original. Even a quiet
        # dry copy would create comb filtering and a cheap chorus/vocoder tone.
        encoded = robot

        if VOICE_SPEECH_VOCODER:
            # Give normal replies the same restrained rendered edge as Daisy
            # Bell, just below the song's setting so sibilants stay clean.
            encoded = _digital_voice_texture(
                np,
                encoded,
                strength,
                edge_strength=_SPEECH_DIGITAL_EDGE,
                drive=1.06,
            )

    peak = float(np.max(np.abs(encoded)))

    if peak > 0.96:
        encoded *= 0.96 / peak

    result = (np.clip(encoded, -1.0, 1.0) * 32767.0).astype(np.int16)
    return result[:, 0] if was_mono else result


# Chorus melody transcribed from the public-domain 1892 score. Durations are
# eighth-note units; pronunciation spellings make isolated Piper syllables
# connect more naturally after vocoding.
DAISY_EIGHTH_SECONDS = 0.21
DAISY_CHORUS = (
    ("day", 62, 6), ("zee", 59, 6),
    ("day", 55, 6), ("zee", 50, 6),
    ("give", 52, 2), ("me", 54, 2), ("your", 55, 2),
    ("an", 52, 4), ("sir", 55, 2), ("do", 50, 8),
    (None, None, 2),
    ("I'm", 57, 6), ("half", 62, 6),
    ("cray", 59, 6), ("zee", 55, 6),
    ("all", 52, 2), ("for", 54, 2), ("the", 55, 2),
    ("love", 57, 4), ("of", 59, 2), ("you", 57, 8),
    (None, None, 2), ("it", 59, 2),
    ("won't", 60, 2), ("be", 59, 2), ("a", 57, 2),
    ("style", 62, 4), ("ish", 59, 2),
    ("mare", 57, 2), ("ridge", 55, 6),
    (None, None, 2), ("eye", 57, 2),
    ("can't", 59, 4), ("af", 55, 2),
    ("ford", 52, 4), ("a", 55, 2),
    ("care", 52, 2), ("ridge", 50, 6),
    (None, None, 2), ("but", 50, 2),
    ("you'll", 55, 4), ("look", 59, 2),
    ("sweet", 57, 2), (None, None, 4),
    ("on", 55, 4), ("the", 59, 2),
    ("seat", 57, 2), (None, None, 2),
    ("of", 59, 1), ("a", 60, 1),
    ("buy", 62, 2), ("sick", 59, 2), ("ull", 55, 2),
    ("built", 57, 4), ("for", 50, 2), ("two", 55, 8),
    (None, None, 4),
)

# Original answering continuation written for this project:
#
# Dear one, dear one, here is my answer true.
# I'm half dreaming, thinking the whole night through.
# It need not be a grand marriage,
# nor a fine horse and carriage.
# But we can ride, side by side,
# on a bright machine built for two.
#
# Its syllables deliberately use the same notes and durations as the familiar
# chorus. Phonetic spellings keep isolated Piper syllables connected.
DAISY_QWEN_CONTINUATION = (
    ("dear", 62, 6), ("one", 59, 6),
    ("dear", 55, 6), ("one", 50, 6),
    ("here", 52, 2), ("is", 54, 2), ("my", 55, 2),
    ("an", 52, 4), ("sir", 55, 2), ("true", 50, 8),
    (None, None, 2),
    ("I'm", 57, 6), ("half", 62, 6),
    ("dream", 59, 6), ("ing", 55, 6),
    ("think", 52, 2), ("ing", 54, 2), ("the", 55, 2),
    ("whole", 57, 4), ("night", 59, 2), ("through", 57, 8),
    (None, None, 2), ("it", 59, 2),
    ("need", 60, 2), ("not", 59, 2), ("be", 57, 2),
    ("a", 62, 4), ("grand", 59, 2),
    ("mare", 57, 2), ("ridge", 55, 6),
    (None, None, 2), ("nor", 57, 2),
    ("a", 59, 4), ("fine", 55, 2),
    ("horse", 52, 4), ("and", 55, 2),
    ("care", 52, 2), ("ridge", 50, 6),
    (None, None, 2), ("but", 50, 2),
    ("we", 55, 4), ("can", 59, 2),
    ("ride", 57, 2), (None, None, 4),
    ("side", 55, 4), ("by", 59, 2),
    ("side", 57, 2), (None, None, 2),
    ("on", 59, 1), ("a", 60, 1),
    ("bright", 62, 2), ("ma", 59, 2), ("sheen", 55, 2),
    ("built", 57, 4), ("for", 50, 2), ("two", 55, 8),
    (None, None, 4),
)

# The 1961 IBM 704 demonstration does not open on the voice. The machine
# states the tune by itself first, and the singing arrives over an
# accompaniment already running -- which is most of why that recording is
# unsettling rather than merely quaint. This is the opening phrase, "Daisy,
# Daisy, give me your answer do", played on the oscillators alone.
# Timed from the reference recording, where the vocal enters at 1:06.
DAISY_INTRO_TARGET_SECONDS = 66.0

# The introduction plays the chorus itself with the words taken away, so the
# machine states the tune before it sings it, and repeats until the entry.
_DAISY_INTRO_SOURCE = tuple(
    (note, units) for _text, note, units in DAISY_CHORUS
)


def _build_daisy_intro(target_seconds, eighth_seconds):
    """Repeat the tune up to the vocal's entry, rounded to whole measures."""
    measures = max(1, int(round(target_seconds / (eighth_seconds * 6))))
    wanted = measures * 6
    melody = []
    total = 0

    while total < wanted:
        for note, units in _DAISY_INTRO_SOURCE:
            if total >= wanted:
                break
            # A note is clipped rather than allowed to overrun, so the
            # introduction ends exactly on a bar line and the chorus does
            # not start half a beat into a measure.
            units = min(units, wanted - total)
            melody.append((note, units))
            total += units

    return tuple(melody)


DAISY_INTRO_MELODY = _build_daisy_intro(
    DAISY_INTRO_TARGET_SECONDS,
    DAISY_EIGHTH_SECONDS,
)
DAISY_INTRO_EIGHTHS = sum(units for _note, units in DAISY_INTRO_MELODY)
DAISY_INTRO_MEASURES = DAISY_INTRO_EIGHTHS // 6

# Fourteen eighth notes complete the first 32 measures and leave a two-measure
# instrumental bridge before Qwen's continuation. The final two eighths make
# the complete performance exactly 66 measures after the introduction.
DAISY_PERFORMANCE = (
    ((None, None, DAISY_INTRO_EIGHTHS),)
    + DAISY_CHORUS
    + ((None, None, 14),)
    + DAISY_QWEN_CONTINUATION
    + ((None, None, 2),)
)

# One chord per three-beat measure. This is the traditional public-domain
# chorus harmony in G, voiced for a sparse MUSIC-IV-era electronic ensemble.
DAISY_HARMONY = {
    "G": (43, 55, 59, 62),
    "G7": (43, 55, 59, 62, 65),
    "C": (48, 55, 60, 64),
    "D7": (50, 57, 60, 66),
    "Em": (40, 55, 59, 64, 67),
    "A7": (45, 55, 61, 64),
}
DAISY_CHORD_PROGRESSION = (
    "G", "G", "G", "G7",
    "C", "C", "G", "G",
    "D7", "D7", "G", "Em",
    "A7", "A7", "D7", "D7",
    "D7", "D7", "G", "G",
    "G", "C", "G", "G",
    "G", "D7", "G", "D7",
    "G", "D7", "G", "G",
)
DAISY_PERFORMANCE_CHORDS = (
    # The introduction can outrun one pass of the progression, so it cycles
    # rather than being sliced -- a short slice would leave later measures
    # with no chord at all and the accompaniment would simply stop.
    tuple(
        DAISY_CHORD_PROGRESSION[index % len(DAISY_CHORD_PROGRESSION)]
        for index in range(DAISY_INTRO_MEASURES)
    )
    + DAISY_CHORD_PROGRESSION
    + ("G", "D7")
    + DAISY_CHORD_PROGRESSION
)

DAISY_SONG = Song(
    name="Daisy Bell",
    score=DAISY_PERFORMANCE,
    eighth_seconds=DAISY_EIGHTH_SECONDS,
    harmony=DAISY_HARMONY,
    chords=DAISY_PERFORMANCE_CHORDS,
    intro_melody=DAISY_INTRO_MELODY,
    cache_path=VOICE_DAISY_CACHE,
    accompaniment_gain=VOICE_DAISY_ACCOMPANIMENT_GAIN,
)


def _midi_frequency(note):
    return 440.0 * (2.0 ** ((float(note) - 69.0) / 12.0))


def _add_daisy_tone(
    np,
    destination,
    sample_rate,
    start_sample,
    duration_samples,
    midi_note,
    level,
    brightness=1.0,
):
    """Add one deliberately primitive additive-synthesis instrument note."""
    start = max(0, int(start_sample))
    end = min(len(destination), start + max(1, int(duration_samples)))
    sample_count = end - start

    if sample_count <= 0:
        return

    timeline = np.arange(sample_count, dtype=np.float32) / float(sample_rate)
    phase = (
        2.0
        * np.pi
        * _midi_frequency(midi_note)
        * timeline
    )
    tone = (
        np.sin(phase)
        + 0.34 * brightness * np.sin(phase * 2.0 + 0.13)
        + 0.16 * brightness * np.sin(phase * 3.0 + 0.31)
        + 0.07 * brightness * np.sin(phase * 5.0 + 0.08)
    ) / (1.0 + 0.57 * brightness)

    # The hard, short envelope and low-resolution amplitude steps produce a
    # small early-digital "computer organ" rather than a modern soft synth.
    attack = min(
        sample_count // 3,
        max(1, int(sample_rate * 0.007)),
    )
    release = min(
        sample_count // 2,
        max(1, int(sample_rate * 0.055)),
    )
    envelope = np.ones(sample_count, dtype=np.float32)

    if attack:
        envelope[:attack] = np.linspace(
            0.0,
            1.0,
            attack,
            endpoint=False,
            dtype=np.float32,
        )

    if release:
        envelope[-release:] *= np.linspace(
            1.0,
            0.0,
            release,
            dtype=np.float32,
        )

    destination[start:end] += (
        tone.astype(np.float32) * envelope * float(level)
    )


def _song_computer_accompaniment(song, np, sample_rate, output_samples):
    """
    Render synchronized bass-and-chord waltz accompaniment from oscillators.

    It recreates the sparse, visibly synthetic character of early computer
    music without embedding or sampling the historical recording.
    """
    output_samples = max(1, int(output_samples))
    accompaniment = np.zeros(output_samples, dtype=np.float32)
    eighth_samples = max(
        1,
        int(round(song.eighth_seconds * sample_rate)),
    )
    beat_samples = eighth_samples * 2
    measure_samples = eighth_samples * 6
    short_note = max(1, int(round(beat_samples * 0.68)))
    bass_note = max(1, int(round(beat_samples * 0.78)))
    stagger = max(1, int(round(sample_rate * 0.006)))

    for measure_index, chord_name in enumerate(song.chords):
        measure_start = measure_index * measure_samples

        if measure_start >= output_samples:
            break

        voicing = song.harmony[chord_name]
        bass, upper = voicing[0], voicing[1:]
        _add_daisy_tone(
            np,
            accompaniment,
            sample_rate,
            measure_start,
            bass_note,
            bass,
            0.22,
            brightness=0.62,
        )

        # A clockwork "oom-pah-pah": the upper voices enter a few milliseconds
        # apart, exposing the individual oscillators instead of forming a
        # polished modern pad.
        for beat_index in (1, 2):
            beat_start = measure_start + beat_index * beat_samples

            for voice_index, midi_note in enumerate(upper):
                _add_daisy_tone(
                    np,
                    accompaniment,
                    sample_rate,
                    beat_start + voice_index * stagger,
                    short_note,
                    midi_note,
                    0.052,
                    brightness=1.0,
                )

        # A very short high pulse acts like the timing tick audible in early
        # digital demonstrations and gives each measure a mechanical edge.
        _add_daisy_tone(
            np,
            accompaniment,
            sample_rate,
            measure_start,
            int(sample_rate * 0.045),
            bass + 24,
            0.026,
            brightness=1.18,
        )

    # The tune itself, stated before the voice arrives. It is louder than the
    # chord voices so it reads as the melody rather than as part of the
    # texture, and it stops exactly where the singing starts.
    position = 0

    for midi_note, units in song.intro_melody:
        duration = units * eighth_samples

        if midi_note is not None:
            _add_daisy_tone(
                np,
                accompaniment,
                sample_rate,
                position,
                max(1, int(round(duration * 0.90))),
                midi_note,
                0.20,
                brightness=0.90,
            )

        position += duration

    accompaniment = np.round(accompaniment * 512.0) / 512.0
    peak = float(np.max(np.abs(accompaniment)))

    if peak > 0.58:
        accompaniment *= 0.58 / peak

    return accompaniment.astype(np.float32)


def _daisy_computer_accompaniment(np, sample_rate, output_samples):
    """Backward-compatible Daisy Bell wrapper for the generic arranger."""
    return _song_computer_accompaniment(
        DAISY_SONG,
        np,
        sample_rate,
        output_samples,
    )


def _mix_song(song, np, vocal, sample_rate):
    """Mix the generated accompaniment below the machine-sung vocal."""
    if vocal.ndim > 1:
        vocal = vocal.mean(axis=1)

    voice = vocal.astype(np.float32) / 32768.0
    accompaniment = _song_computer_accompaniment(
        song,
        np,
        sample_rate,
        len(voice),
    )
    envelope_window = max(1, int(round(sample_rate * 0.025)))
    envelope_starts = np.arange(
        0,
        len(voice),
        envelope_window,
        dtype=np.int64,
    )
    envelope_peaks = np.maximum.reduceat(
        np.abs(voice),
        envelope_starts,
    )
    envelope_centers = (
        envelope_starts.astype(np.float32) + envelope_window * 0.5
    )
    vocal_presence = np.interp(
        np.arange(len(voice), dtype=np.float32),
        envelope_centers,
        np.clip(envelope_peaks * 4.5, 0.0, 1.0),
        left=float(np.clip(envelope_peaks[0] * 4.5, 0.0, 1.0)),
        right=float(np.clip(envelope_peaks[-1] * 4.5, 0.0, 1.0)),
    ).astype(np.float32)
    accompaniment_gain = np.maximum(
        0.12,
        song.accompaniment_gain - 0.14 * vocal_presence,
    )
    mixed = voice * 0.86 + accompaniment * accompaniment_gain
    mixed = np.tanh(mixed * 1.08)
    peak = float(np.max(np.abs(mixed)))

    if peak > 0.96:
        mixed *= 0.96 / peak

    return (
        np.clip(mixed, -1.0, 1.0) * 32767.0
    ).astype(np.int16)


def _mix_daisy_performance(np, vocal, sample_rate):
    """Backward-compatible Daisy Bell wrapper for the generic song mixer."""
    return _mix_song(DAISY_SONG, np, vocal, sample_rate)


class OfflineVoice:
    def __init__(self):
        issues = setup_issues(require_microphone=False)

        if issues:
            raise VoiceSetupError("\n".join(issues))

        import numpy as np
        import sounddevice as sd

        self.np = np
        self.sd = sd
        # Read through the accessors so a device chosen mid-session is
        # picked up by the next voice instance without a restart.
        self.input_device = _device_value(input_device())
        self.output_device = _device_value(output_device())
        input_issues = microphone_issues()
        self.microphone_available = not input_issues
        self.microphone_issue = "\n".join(input_issues)
        self.sherpa_onnx = None
        self.recognizer = None

        if self.microphone_available:
            import sherpa_onnx

            self.sherpa_onnx = sherpa_onnx
            self.recognizer = self._create_recognizer()

        self.piper_voice = None
        self.speech_syn_config = None
        self.song_syn_config = None

    def _create_recognizer(self):
        path = lambda key: os.path.join(VOICE_ASR_DIR, _ASR_FILES[key])

        try:
            return self.sherpa_onnx.OfflineRecognizer.from_moonshine(
                preprocessor=path("preprocessor"),
                encoder=path("encoder"),
                uncached_decoder=path("uncached_decoder"),
                cached_decoder=path("cached_decoder"),
                tokens=path("tokens"),
                num_threads=VOICE_NUM_THREADS,
                decoding_method="greedy_search",
                debug=False,
            )
        except Exception as error:
            raise VoiceSetupError(
                f"Could not load the offline speech recognizer: {error}"
            ) from error

    def _create_vad(self):
        config = self.sherpa_onnx.VadModelConfig()
        config.silero_vad.model = VOICE_VAD_MODEL
        config.silero_vad.min_silence_duration = 0.45
        config.silero_vad.min_speech_duration = 0.20
        config.sample_rate = VOICE_SAMPLE_RATE
        window_size = config.silero_vad.window_size

        return (
            self.sherpa_onnx.VoiceActivityDetector(
                config,
                buffer_size_in_seconds=60,
            ),
            window_size,
        )

    def listen(self, cancelled, phase_changed=None):
        """
        Wait for one complete spoken utterance.

        Returns transcript text, or None when Escape/cancel was requested.
        Input is read in 100 ms blocks so the manual exit remains responsive.
        """
        if not self.microphone_available:
            raise VoiceRuntimeError(
                "Microphone input is unavailable. Type a message in the "
                "audio-mode prompt instead."
            )

        vad, window_size = self._create_vad()
        samples_per_read = int(0.1 * VOICE_SAMPLE_RATE)
        pending = self.np.empty(0, dtype=self.np.float32)

        try:
            with self.sd.InputStream(
                channels=VOICE_INPUT_CHANNELS,
                dtype="float32",
                samplerate=VOICE_SAMPLE_RATE,
                blocksize=samples_per_read,
                device=self.input_device,
            ) as stream:
                while True:
                    if cancelled():
                        return None

                    samples, _overflowed = stream.read(samples_per_read)

                    if VOICE_INPUT_CHANNELS > 1:
                        samples = samples.mean(axis=1)
                    else:
                        samples = samples.reshape(-1)

                    pending = self.np.concatenate((pending, samples))

                    while len(pending) >= window_size:
                        vad.accept_waveform(pending[:window_size])
                        pending = pending[window_size:]

                    while not vad.empty():
                        segment = vad.front.samples
                        vad.pop()

                        if phase_changed:
                            phase_changed("transcribing")

                        recognition_stream = self.recognizer.create_stream()
                        recognition_stream.accept_waveform(
                            VOICE_SAMPLE_RATE,
                            segment,
                        )
                        self.recognizer.decode_stream(recognition_stream)
                        text = recognition_stream.result.text.strip()

                        if text:
                            return text
        except Exception as error:
            raise VoiceRuntimeError(f"Microphone listening failed: {error}") from error

    def _resolved_speaker(self):
        """
        VOICE_TTS_SPEAKER, validated against the model actually loaded.

        Returns None for single-speaker voices, so switching back to one
        does not pass a speaker_id it cannot use. An out-of-range id is
        reported rather than silently clamped -- quietly speaking as the
        wrong person is worse than refusing.
        """
        if VOICE_TTS_SPEAKER is None:
            return None

        available = getattr(self.piper_voice.config, "num_speakers", 1) or 1

        if available <= 1:
            return None

        if not 0 <= VOICE_TTS_SPEAKER < available:
            raise VoiceSetupError(
                f"{VOICE_TTS_NAME} has {available} speakers, so speaker "
                f"{VOICE_TTS_SPEAKER} does not exist. Set "
                "TORMENT_NEXUS_PIPER_SPEAKER to a valid id."
            )

        return VOICE_TTS_SPEAKER

    def _load_piper(self):
        if self.piper_voice is not None:
            return

        try:
            from piper import PiperVoice
            from piper.config import SynthesisConfig

            self.piper_voice = PiperVoice.load(VOICE_TTS_MODEL)
            self.speech_syn_config = SynthesisConfig(
                volume=0.94,
                length_scale=speech_pace(),
                noise_scale=VOICE_SPEECH_NOISE_SCALE,
                noise_w_scale=VOICE_SPEECH_NOISE_W_SCALE,
                normalize_audio=True,
            )
            self.song_syn_config = SynthesisConfig(
                volume=0.96,
                length_scale=0.86,
                noise_scale=0.08,
                noise_w_scale=0.06,
                normalize_audio=True,
            )

            # The chosen voice lives inside a 904-speaker model, so the
            # speaker has to be selected explicitly -- without this every
            # synthesis silently falls back to speaker 0, which is a
            # different person entirely and none of the measurements that
            # picked this voice would apply.
            speaker = self._resolved_speaker()

            if speaker is not None:
                self.speech_syn_config.speaker_id = speaker
                self.song_syn_config.speaker_id = speaker
        except Exception as error:
            raise VoiceSetupError(
                f"Could not load the Piper voice: {_load_failure_hint(error)}"
            ) from error

    def prepare_output(self):
        """Load speech synthesis before the first reply needs it."""
        self._load_piper()

    def _speech_config_for_chunk(self, text):
        """Copy Piper settings only when a brief reply needs slower timing."""
        config = self.speech_syn_config
        base_scale = getattr(config, "length_scale", None)

        # Keeping the original object for test doubles and unchanged longer
        # text avoids needless allocations in the normal reply path.
        if base_scale is None:
            return config

        adjusted_scale = _speech_length_scale_for_chunk(text, base_scale)

        if abs(adjusted_scale - float(base_scale)) < 1e-6:
            return config

        adjusted = copy.copy(config)
        adjusted.length_scale = adjusted_scale
        return adjusted

    def _synthesize_wav_bytes(self, text, syn_config, cancelled):
        target = io.BytesIO()
        synthesis_error = []

        def synthesize():
            try:
                with wave.open(target, "wb") as wav_file:
                    self.piper_voice.synthesize_wav(
                        text,
                        wav_file,
                        syn_config=syn_config,
                    )
            except Exception as error:
                synthesis_error.append(error)

        worker = threading.Thread(target=synthesize, daemon=True)
        worker.start()

        while worker.is_alive():
            if cancelled():
                return None

            time.sleep(0.02)

        worker.join()

        if synthesis_error:
            raise VoiceRuntimeError(
                f"Speech synthesis failed: {synthesis_error[0]}"
            ) from synthesis_error[0]

        return target.getvalue()

    def _decode_wav_bytes(self, wav_bytes):
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frames = wav_file.readframes(wav_file.getnframes())

        if sample_width != 2:
            raise VoiceRuntimeError(
                f"Unsupported Piper sample width: {sample_width * 8}-bit"
            )

        audio = self.np.frombuffer(frames, dtype=self.np.int16)

        if channels > 1:
            audio = audio.reshape(-1, channels)

        return audio, sample_rate

    def _stop_playback(self):
        """Silence the speaker, whatever state the stream is in."""
        try:
            self.sd.stop()
            return True
        except Exception:
            return False

    def _stream_is_active(self, elapsed, duration):
        """
        Is audio still playing?

        sounddevice's get_stream() raises when it cannot identify a
        current stream, and it reports on the module-level stream shared
        with every other caller. Letting that exception escape used to
        abandon the loop mid-playback, leaving audio running with nothing
        left to stop it -- the cancel key then did nothing, because the
        code that would have honoured it was already gone. Falling back to
        the clip's own duration keeps the loop -- and therefore the cancel
        check -- alive no matter what the stream query does.
        """
        try:
            stream = self.sd.get_stream()
        except Exception:
            return elapsed < duration

        if stream is None:
            return elapsed < duration

        try:
            return bool(stream.active)
        except Exception:
            return elapsed < duration

    def _play_audio(self, audio, sample_rate, cancelled, progress=None):
        duration = max(0.05, len(audio) / float(sample_rate))
        self._publish_speech_envelope(audio, sample_rate)
        started_at = time.monotonic()

        if progress:
            progress(0.0)

        self.sd.play(audio, sample_rate, device=self.output_device)

        # A hard ceiling so a stream that never reports itself finished
        # cannot pin this loop open forever.
        deadline = duration + 5.0

        while True:
            elapsed = time.monotonic() - started_at

            # Cancellation is checked before the stream state, so a stop
            # is honoured even on the last iteration.
            if cancelled():
                self._stop_playback()
                return False

            if not self._stream_is_active(elapsed, duration):
                break

            if elapsed > deadline:
                self._stop_playback()
                break

            if progress:
                progress(min(0.995, elapsed / duration))

            time.sleep(0.05)

        if progress:
            progress(1.0)

        return True

    def set_speech_envelope_callback(self, callback):
        """
        Receive the shape of each utterance just before it is played.

        The face reacts to what is actually being said, and the samples are
        already in hand here, so there is nothing to capture and no second
        audio device to contend with. Handing over the whole envelope at once
        rather than a level per tick lets the renderer interpolate at its own
        frame rate instead of stepping at this loop's 20Hz.
        """
        self._speech_envelope_callback = callback

    def _publish_speech_envelope(self, audio, sample_rate):
        callback = getattr(self, "_speech_envelope_callback", None)

        if callback is None:
            return

        try:
            levels, brightness = _speech_envelope(
                self.np,
                audio,
                sample_rate,
                SPEECH_ENVELOPE_HOP,
            )
            callback(levels, brightness, SPEECH_ENVELOPE_HOP)
        except Exception:
            # A cosmetic effect must never be able to stop the voice.
            pass

    def _play_wav_bytes(
        self,
        wav_bytes,
        cancelled,
        phase_changed=None,
        progress=None,
        pitch_bias=0.0,
    ):
        try:
            audio, sample_rate = self._decode_wav_bytes(wav_bytes)

            if VOICE_ROBOT_ENABLED and VOICE_ROBOT_STRENGTH > 0:
                if phase_changed:
                    phase_changed("shaping measured machine cadence")

                audio = _encoded_robot_effect(
                    self.np,
                    audio,
                    sample_rate,
                    VOICE_ROBOT_STRENGTH,
                    carrier_hz=(
                        VOICE_SPEECH_CARRIER_HZ
                        * (2.0 ** (pitch_bias / 12.0))
                    ),
                    # Both of these were previously left to defaults, so
                    # speech ran at 172Hz-nominal with no formant lift while
                    # the sung path got 145Hz and 1.08. The missing lift is
                    # the "drifts toward male" failure the vocoder exists to
                    # avoid, so it has to be passed here, not defaulted.
                    formant_shift=VOICE_ROBOT_FORMANT_SHIFT,
                    cadence_strength=VOICE_CADENCE_STRENGTH,
                    pitch_offset=VOICE_PITCH_SEMITONES,
                    vowel_stretch=VOICE_VOWEL_STRETCH,
                    pitch_flatten=VOICE_PITCH_FLATTEN,
                )

            if phase_changed:
                phase_changed("speaking")

            return self._play_audio(
                audio,
                sample_rate,
                cancelled,
                progress=progress,
            )
        except VoiceRuntimeError:
            raise
        except Exception as error:
            self.sd.stop()
            raise VoiceRuntimeError(f"Speaker playback failed: {error}") from error

    def _trim_speech(self, audio, sample_rate):
        """Remove isolated-token silence before fitting it to a sung note."""
        if audio.ndim > 1:
            mono = audio.mean(axis=1)
        else:
            mono = audio

        magnitude = self.np.abs(mono.astype(self.np.int32))
        peak = int(self.np.max(magnitude)) if magnitude.size else 0

        if not peak:
            return audio

        active = self.np.flatnonzero(magnitude > max(120, int(peak * 0.025)))

        if not active.size:
            return audio

        margin = int(sample_rate * 0.018)
        start = max(0, int(active[0]) - margin)
        end = min(len(audio), int(active[-1]) + margin)
        return audio[start:end]

    def _load_song_cache(self, song):
        if not os.path.isfile(song.cache_path):
            return None

        try:
            with wave.open(song.cache_path, "rb") as wav_file:
                if wav_file.getsampwidth() != 2 or wav_file.getnchannels() != 1:
                    return None

                sample_rate = wav_file.getframerate()
                frames = wav_file.readframes(wav_file.getnframes())

            return (
                self.np.frombuffer(frames, dtype=self.np.int16).copy(),
                sample_rate,
            )
        except (OSError, EOFError, wave.Error):
            return None

    def _save_song_cache(self, song, audio, sample_rate):
        folder = os.path.dirname(song.cache_path)
        os.makedirs(folder, exist_ok=True)
        temporary = song.cache_path + ".tmp"

        try:
            with wave.open(temporary, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio.astype(self.np.int16).tobytes())

            os.replace(temporary, song.cache_path)
        finally:
            if os.path.isfile(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass

    def _build_song_audio(self, song, cancelled, phase_changed=None):
        self._load_piper()
        token_cache = {}
        segments = []
        sample_rate = int(self.piper_voice.config.sample_rate)
        voiced_total = sum(
            1
            for text, _note, _units in song.score
            if text
        )
        voiced_index = 0

        for text, note, duration_units in song.score:
            if cancelled():
                return None

            target_samples = max(
                1,
                int(
                    round(
                        duration_units
                        * song.eighth_seconds
                        * sample_rate
                    )
                ),
            )

            if text is None:
                segments.append(
                    self.np.zeros(target_samples, dtype=self.np.int16)
                )
                continue

            voiced_index += 1

            if phase_changed:
                phase_changed(
                    f"building {song.name} "
                    f"{voiced_index}/{voiced_total}"
                )

            token_audio = token_cache.get(text)

            if token_audio is None:
                wav_bytes = self._synthesize_wav_bytes(
                    text,
                    self.song_syn_config,
                    cancelled,
                )

                if wav_bytes is None:
                    return None

                token_audio, token_rate = self._decode_wav_bytes(wav_bytes)

                if token_rate != sample_rate:
                    raise VoiceRuntimeError(
                        "Piper changed sample rate while building "
                        f"{song.name}."
                    )

                token_audio = self._trim_speech(token_audio, sample_rate)
                token_cache[text] = token_audio

            segment = _encoded_robot_effect(
                self.np,
                token_audio,
                sample_rate,
                1.0,
                carrier_hz=_midi_frequency(note),
                formant_shift=VOICE_ROBOT_FORMANT_SHIFT,
                output_samples=target_samples,
                pitch_lock=True,
            )

            # Tiny fades prevent note-boundary clicks without blurring lyrics.
            fade_samples = min(
                len(segment) // 3,
                max(1, int(sample_rate * 0.006)),
            )

            if fade_samples:
                fade = self.np.linspace(
                    0.0,
                    1.0,
                    fade_samples,
                    dtype=self.np.float32,
                )
                segment[:fade_samples] = (
                    segment[:fade_samples].astype(self.np.float32) * fade
                ).astype(self.np.int16)
                segment[-fade_samples:] = (
                    segment[-fade_samples:].astype(self.np.float32)
                    * fade[::-1]
                ).astype(self.np.int16)

            segments.append(segment)

        if not segments:
            return None

        vocal = self.np.concatenate(segments)

        if phase_changed:
            phase_changed("synthesizing computer accompaniment")

        performance = _mix_song(
            song,
            self.np,
            vocal,
            sample_rate,
        )
        self._save_song_cache(song, performance, sample_rate)
        return performance, sample_rate

    def sing(self, song, cancelled, phase_changed=None):
        """Build once, cache, and perform one public-domain song."""
        cached = self._load_song_cache(song)

        if cached is None:
            if phase_changed:
                phase_changed(f"building {song.name} voice")

            cached = self._build_song_audio(song, cancelled, phase_changed)

        if cached is None or cancelled():
            return False

        audio, sample_rate = cached

        if phase_changed:
            phase_changed(f"singing {song.name}")

        try:
            return self._play_audio(audio, sample_rate, cancelled)
        except Exception as error:
            self.sd.stop()
            raise VoiceRuntimeError(
                f"{song.name} playback failed: {error}"
            ) from error

    def _load_daisy_cache(self):
        """Backward-compatible wrapper for Daisy Bell's dedicated cache."""
        return self._load_song_cache(DAISY_SONG)

    def _save_daisy_cache(self, audio, sample_rate):
        """Backward-compatible wrapper for Daisy Bell's dedicated cache."""
        self._save_song_cache(DAISY_SONG, audio, sample_rate)

    def _build_daisy_audio(self, cancelled, phase_changed=None):
        """Backward-compatible wrapper for the generic song builder."""
        return self._build_song_audio(DAISY_SONG, cancelled, phase_changed)

    def sing_daisy_bell(self, cancelled, phase_changed=None):
        """Perform Daisy Bell without changing its public voice API."""
        return self.sing(DAISY_SONG, cancelled, phase_changed)

    def speak(self, text, cancelled, phase_changed=None, progress=None):
        """Synthesize and play a reply. False means Escape interrupted it."""
        chunks = _speech_chunks(text)

        if not chunks:
            return True

        if phase_changed:
            phase_changed("loading voice")
        self._load_piper()

        for index, chunk in enumerate(chunks):
            if cancelled():
                return False

            if phase_changed:
                phase_changed(
                    "synthesizing short reply at deliberate pace"
                    if len(re.findall(r"[A-Za-z0-9']+", chunk))
                    <= _SHORT_SPEECH_WORD_LIMIT
                    else "synthesizing speech"
                )
            wav_bytes = self._synthesize_wav_bytes(
                chunk,
                self._speech_config_for_chunk(chunk),
                cancelled,
            )

            if wav_bytes is None:
                return False

            def report_progress(fraction, current=index, spoken=chunk):
                if progress:
                    progress(current, len(chunks), spoken, fraction)

            if not self._play_wav_bytes(
                wav_bytes,
                cancelled,
                phase_changed,
                progress=report_progress,
                pitch_bias=_utterance_pitch_bias(chunk),
            ):
                return False

            if index + 1 < len(chunks):
                if phase_changed:
                    phase_changed("pausing between phrases")

                # A chunk that ends on sentence punctuation really is the
                # end of a thought. One that does not is a long sentence
                # cut at a word boundary to fit the synthesiser, and
                # giving that the full stop's pause invents a sentence
                # break the text never had.
                ends_sentence = chunk.rstrip().endswith((".", "!", "?", ":"))
                gap = (
                    VOICE_SPEECH_PAUSE_SECONDS
                    if ends_sentence
                    else VOICE_SPEECH_CLAUSE_PAUSE_SECONDS
                )

                deadline = time.monotonic() + gap

                while time.monotonic() < deadline:
                    if cancelled():
                        return False

                    remaining = deadline - time.monotonic()
                    time.sleep(min(0.02, max(0.0, remaining)))

        return True
