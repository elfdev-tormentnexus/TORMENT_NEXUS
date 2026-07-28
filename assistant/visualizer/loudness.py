"""
Per-track playback gain, so the library plays at one perceived level.

The complaint this fixes is specific: a quiet track gets the volume turned
up, the next one is mastered eight decibels hotter, and it arrives at the
new setting. Album-to-album level differences are a mastering artifact, not
something the listener asked for, and the fix is to measure each file once
and scale it on the way out.

WHAT THIS MEASURES, AND WHAT IT DOES NOT
----------------------------------------
This is gated RMS, not ITU-R BS.1770 LUFS. Real loudness units apply a
K-weighting filter -- a high-pass plus a high-shelf approximating how the
ear weights frequency -- before the same kind of gated mean. Without that
filter a bass-heavy track measures louder than it sounds and gets pushed
down a little too far.

Gated RMS is nonetheless most of the benefit: the gate is what stops quiet
intros and fade-outs from dragging the average down, and it is the part
that makes a single number describe a whole song. Adding K-weighting means
biquad coefficients and a filter pass, which is a reasonable next step and
not a prerequisite. This is deliberately the version that ships without a
new dependency and without a perceptible delay before playback.

Two safeguards matter more than accuracy here:

  * Gain is capped by the file's own peak, so normalising can never clip a
    track that was already mastered near full scale. A clipped track sounds
    worse than an uneven one.
  * Gain is bounded both ways, so a near-silent recording is not amplified
    until its noise floor becomes the loudest thing in the room.

Measurements are cached by path, size and mtime under assistant/cache/,
which is gitignored and denied by the release packager. Re-encoding a file
changes its size or mtime and invalidates the entry.
"""

import json
import math
import os
import threading

from core.config import ASSISTANT_ROOT


CACHE_FILE = os.path.join(ASSISTANT_ROOT, "cache", "track_loudness.json")

# About -20 dBFS RMS. Chosen to sit below typical modern masters so the
# common case is a small attenuation rather than a boost: pulling a loud
# track down cannot clip, while pushing a quiet one up eventually can.
TARGET_RMS = 0.10

# A quiet recording is quiet for a reason often enough that unlimited
# make-up gain is the wrong default. Four times is about +12 dB.
MAX_GAIN = 4.0
MIN_GAIN = 0.20

# Never let a normalised sample exceed this. Slightly under full scale so
# intersample peaks after resampling still have somewhere to go.
PEAK_CEILING = 0.985

# Blocks quieter than this fraction of the track's own mean square are
# treated as silence and excluded. This is the gate, and it is the single
# thing that makes one number describe a song with a quiet intro.
GATE_RELATIVE = 0.10

# Reading an entire album to play one track would put a visible delay in
# front of every play. Twenty-four windows spread across the file describe
# the level well enough and cost a few tens of milliseconds.
WINDOW_COUNT = 24
WINDOW_SECONDS = 1.25

_lock = threading.Lock()
_cache = None


def _load_cache():
    global _cache

    if _cache is not None:
        return _cache

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        _cache = loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        _cache = {}

    return _cache


def _save_cache():
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

        with open(CACHE_FILE, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(_cache, handle, indent=1, sort_keys=True)
    except OSError:
        # A cache that cannot be written costs a re-measure per play, which
        # is a performance problem and not a correctness one.
        pass


def _identity(path):
    try:
        stat = os.stat(path)
    except OSError:
        return None

    return f"{os.path.abspath(path)}|{stat.st_size}|{int(stat.st_mtime)}"


def _measure(path):
    """Return (rms, peak) sampled across the file, or None if unreadable."""
    try:
        import numpy as np
        import soundfile as sf
    except ImportError:
        return None

    try:
        with sf.SoundFile(path) as handle:
            samplerate = handle.samplerate or 44100
            total = handle.frames
            window = max(1, int(samplerate * WINDOW_SECONDS))

            if total <= 0:
                return None

            if total <= window * WINDOW_COUNT:
                starts = [0]
                window = total
            else:
                stride = (total - window) / max(1, WINDOW_COUNT - 1)
                starts = [int(index * stride) for index in range(WINDOW_COUNT)]

            squares = []
            peak = 0.0

            for start in starts:
                handle.seek(start)
                block = handle.read(window, dtype="float32", always_2d=True)

                if block.size == 0:
                    continue

                mono = block.mean(axis=1)
                squares.append(float(np.mean(mono * mono)))
                peak = max(peak, float(np.max(np.abs(block))))
    except Exception:
        # An unreadable or exotic file plays at unity rather than failing.
        return None

    if not squares:
        return None

    import numpy as np

    values = np.asarray(squares, dtype=np.float64)
    mean_square = float(values.mean())

    if mean_square > 0.0:
        # The gate: drop windows far below the track's own average before
        # averaging again, so an ambient intro stops counting as the song.
        kept = values[values >= mean_square * GATE_RELATIVE]

        if kept.size:
            mean_square = float(kept.mean())

    return math.sqrt(max(mean_square, 0.0)), peak


def gain_for(path):
    """
    The playback multiplier that brings this file to the common level.

    Returns 1.0 whenever the file cannot be measured, so an unreadable or
    unusual track plays exactly as it always did.
    """
    if not path:
        return 1.0

    identity = _identity(path)

    if identity is None:
        return 1.0

    with _lock:
        cache = _load_cache()
        cached = cache.get(identity)

        if isinstance(cached, (int, float)) and cached > 0.0:
            return float(cached)

    measured = _measure(path)

    if measured is None:
        return 1.0

    rms, peak = measured

    if rms <= 0.0:
        gain = 1.0
    else:
        gain = TARGET_RMS / rms

    # The peak limit is applied after the bounds, not before: clipping is
    # the one outcome worse than an uneven library, so it wins over the
    # target level every time.
    gain = max(MIN_GAIN, min(MAX_GAIN, gain))

    if peak > 0.0:
        gain = min(gain, PEAK_CEILING / peak)

    gain = max(MIN_GAIN, gain)

    with _lock:
        _load_cache()[identity] = gain
        _save_cache()

    return gain


def forget():
    """Drop every measurement, for when the target or the gate changes."""
    global _cache

    with _lock:
        _cache = {}
        _save_cache()
