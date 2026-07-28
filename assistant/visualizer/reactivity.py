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
    # Travel and terrain are both bass-driven, and the skyline is cut
    # straight from the spectrum, so both are pushed hardest here.
    "neon horizon": {
        "bass": (1.52, 0.62),
        "mid": (1.24, 0.76),
        "treble": (1.30, 0.72),
        "level": (1.40, 0.70),
        "beat": (1.72, 0.74),
        "stereo_width": (1.22, 0.80),
        "spectrum": (1.50, 0.60),
        "waveform": 1.40,
        "pan": 1.24,
    },
    # The softest profile of the set. Blob drift follows mids, and an
    # aggressive beat gain would put a hard edge on a deliberately
    # edgeless scene.
    "plasma flow": {
        "bass": (1.36, 0.70),
        "mid": (1.54, 0.60),
        "treble": (1.22, 0.78),
        "level": (1.50, 0.66),
        "beat": (1.58, 0.78),
        "stereo_width": (1.30, 0.74),
        "spectrum": (1.24, 0.74),
        "waveform": 1.30,
        "pan": 1.30,
    },
    # The data curtain now uses bass for its low horizon, mids for the sheet's
    # curvature, treble for rain speed, and beats for its brief scan fault.
    "datastream rain": {
        "bass": (1.46, 0.64),
        "mid": (1.48, 0.62),
        "treble": (1.62, 0.56),
        "level": (1.40, 0.70),
        "beat": (2.20, 0.64),
        "stereo_width": (1.24, 0.78),
        "spectrum": (1.54, 0.58),
        "waveform": 1.38,
        "pan": 1.22,
    },
    # The most transient-driven scene there is: a beat throws the whole
    # starfield forward, so this carries the strongest beat gain.
    "wormhole": {
        "bass": (1.60, 0.58),
        "mid": (1.28, 0.74),
        "treble": (1.36, 0.70),
        "level": (1.44, 0.68),
        "beat": (2.25, 0.64),
        "stereo_width": (1.32, 0.72),
        "spectrum": (1.30, 0.70),
        "waveform": 1.42,
        "pan": 1.38,
    },
    # A harsh, skeletal scene: bass pulls its void upward, mid/treble grow
    # the triangular field, and onsets alone release its short hard-cut burst.
    "acid lattice": {
        "bass": (1.66, 0.57),
        "mid": (1.56, 0.60),
        "treble": (1.64, 0.57),
        "level": (1.44, 0.68),
        "beat": (2.32, 0.62),
        "stereo_width": (1.42, 0.68),
        "spectrum": (1.48, 0.62),
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
    bass expands the tunnel and reactor, mids and treble push the cube's
    motion and corruption, and onsets alone fracture the lattice.
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
