"""Scene-specific audio shaping for a more expressive visualizer."""


_PROFILES = {
    "radial tunnel": {
        "bass": (1.42, 0.68),
        "mid": (1.22, 0.76),
        "treble": (1.28, 0.72),
        "level": (1.38, 0.72),
        "beat": (1.65, 0.75),
        "stereo_width": (1.24, 0.78),
        "spectrum": (1.34, 0.66),
        "waveform": 1.48,
        "pan": 1.28,
    },
    "spectrum cathedral": {
        "bass": (1.28, 0.74),
        "mid": (1.30, 0.72),
        "treble": (1.48, 0.64),
        "level": (1.42, 0.70),
        "beat": (1.80, 0.72),
        "stereo_width": (1.18, 0.82),
        "spectrum": (1.58, 0.58),
        "waveform": 1.62,
        "pan": 1.18,
    },
    "orbital reactor": {
        "bass": (1.58, 0.60),
        "mid": (1.26, 0.74),
        "treble": (1.34, 0.70),
        "level": (1.46, 0.68),
        "beat": (2.00, 0.70),
        "stereo_width": (1.34, 0.72),
        "spectrum": (1.26, 0.72),
        "waveform": 1.38,
        "pan": 1.36,
    },
    "corrupt cube": {
        "bass": (1.42, 0.66),
        "mid": (1.48, 0.62),
        "treble": (1.62, 0.58),
        "level": (1.38, 0.72),
        "beat": (2.15, 0.68),
        "stereo_width": (1.28, 0.76),
        "spectrum": (1.32, 0.68),
        "waveform": 1.36,
        "pan": 1.42,
    },
}

_DEFAULT_PROFILE = _PROFILES["radial tunnel"]


def _clamp(value, low=0.0, high=1.0):
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _lift(value, gain, curve):
    """Compress the quiet end upward while retaining a hard peak ceiling."""
    value = _clamp(value)
    if value <= 0.0:
        return 0.0
    return min(1.0, (value ** curve) * gain)


def _shape_sequence(values, gain, curve, signed=False):
    try:
        iterator = iter(values)
    except TypeError:
        return ()

    shaped = []
    for value in iterator:
        if signed:
            numeric = _clamp(value, -1.0, 1.0)
            shaped.append(
                max(-1.0, min(1.0, numeric * gain))
            )
        else:
            shaped.append(_lift(value, gain, curve))
    return tuple(shaped)


def shape_features(features, scene_name):
    """
    Return a copy whose quiet details and transients are easier to see.

    Each scene emphasizes the part of the music that fits its visual language:
    bass expands the tunnel and reactor, spectrum detail raises the cathedral,
    and mids/treble push the cube's motion and corruption.
    """
    source = dict(features or {})
    profile = _PROFILES.get(scene_name, _DEFAULT_PROFILE)
    shaped = dict(source)

    for name in ("bass", "mid", "treble", "level", "beat", "stereo_width"):
        gain, curve = profile[name]
        shaped[name] = _lift(source.get(name, 0.0), gain, curve)

    shaped["pan"] = _clamp(
        _clamp(source.get("pan", 0.0), -1.0, 1.0) * profile["pan"],
        -1.0,
        1.0,
    )
    shaped["spectrum"] = _shape_sequence(
        source.get("spectrum", ()),
        profile["spectrum"][0],
        profile["spectrum"][1],
    )
    shaped["waveform"] = _shape_sequence(
        source.get("waveform", ()),
        profile["waveform"],
        1.0,
        signed=True,
    )
    return shaped
