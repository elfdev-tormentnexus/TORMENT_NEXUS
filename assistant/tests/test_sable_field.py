"""Sable's own scene, held to the two things it can get wrong.

It can fail to react, which is what it was doing, and it can react by
turning everything on, which is worse than not reacting -- a field where
every cell is lit says the same thing about every passage.

The numbers here were measured on 2026-07-30 rather than chosen.
"""

import unittest

import numpy as np

from visualizer import reactivity, sable_field
from visualizer.sable_field import SableFieldVisualizer


DT = 1.0 / 30.0
W, H = 60, 18
PIXEL_W, PIXEL_H = W * sable_field.CELL_W, H * sable_field.CELL_H

# A braille cell lights if any of its eight dots clears this, which is the
# threshold render() itself uses.
DOT_THRESHOLD = 0.30

_BASE = {
    "mid": 0.55, "treble": 0.45, "beat": 0.1, "level": 0.5,
    "stereo_width": 0.3, "pan": 0.0,
    "spectrum": [0.5] * 16, "waveform": [0.2] * 16,
}


def _settle(bass, frames=40, pin=True):
    scene = SableFieldVisualizer(palette=((255, 0, 0), (0, 255, 0)))
    shaped = reactivity.shape_features(dict(_BASE, bass=bass), "sable field")
    for _ in range(frames):
        scene.step(DT, shaped, W, H)
    scene._np = np
    if pin:
        # Scroll and phase differ because bass drives them. Pinning both is
        # what makes the comparisons below about the warp and nothing else.
        scene.scroll = 4.0
        scene.time = 3.0
    return scene


def _field(scene):
    intensity = np.zeros((PIXEL_H, PIXEL_W), dtype=np.float32)
    ys = np.arange(PIXEL_H, dtype=np.float32)[:, None]
    xs = np.arange(PIXEL_W, dtype=np.float32)[None, :]
    scene._draw_field(intensity, xs / (PIXEL_W - 1), ys / (PIXEL_H - 1),
                      PIXEL_H, PIXEL_W)
    return np.clip(intensity, 0.0, 1.0)


def _shape_correlation(a, b):
    """Brightness normalised away, so only geometry is left."""
    an = (a - a.mean()) / (a.std() or 1.0)
    bn = (b - b.mean()) / (b.std() or 1.0)
    return float((an * bn).mean())


class LatticeTests(unittest.TestCase):
    def setUp(self):
        self.quiet = _settle(0.05)
        self.loud = _settle(0.9)

    def test_bass_bends_the_lattice_rather_than_only_lighting_it(self):
        """The distinction the feature exists to make.

        Measured: with the warp disabled the quiet and loud fields are 0.94
        the same shape -- bass changes brightness and nothing else. With it
        enabled the correlation falls to about -0.10, because the mesh has
        actually moved.
        """
        bent = _shape_correlation(_field(self.quiet), _field(self.loud))

        warp = sable_field._WIRE_WARP
        sable_field._WIRE_WARP = 0.0
        try:
            flat = _shape_correlation(_field(self.quiet), _field(self.loud))
        finally:
            sable_field._WIRE_WARP = warp

        self.assertGreater(flat, 0.80)
        self.assertLess(bent, 0.55)

    def test_the_lattice_is_visible_and_grows_with_bass(self):
        off = sable_field._WIRE_BASE, sable_field._WIRE_BASS
        sable_field._WIRE_BASE = sable_field._WIRE_BASS = 0.0
        try:
            without = float((_field(self.loud) > DOT_THRESHOLD).mean())
        finally:
            sable_field._WIRE_BASE, sable_field._WIRE_BASS = off

        with_lattice = float((_field(self.loud) > DOT_THRESHOLD).mean())
        self.assertGreater(with_lattice, without)

    def test_the_field_does_not_saturate_into_fog(self):
        """Everything lit says the same thing about every passage."""
        for name, scene in (("quiet", self.quiet), ("loud", self.loud)):
            with self.subTest(bass=name):
                coverage = float((_field(scene) > DOT_THRESHOLD).mean())
                self.assertLess(coverage, 0.70)

    def test_silence_leaves_the_field_dark(self):
        silent = SableFieldVisualizer(palette=((255, 0, 0), (0, 255, 0)))
        quiet_features = {key: 0.0 for key in
                          ("bass", "mid", "treble", "beat", "level")}
        quiet_features.update(spectrum=[0.0] * 16, waveform=[0.0] * 16)
        for _ in range(60):
            silent.step(DT, quiet_features, W, H)
        silent._np = np

        coverage = float((_field(silent) > DOT_THRESHOLD).mean())
        self.assertLess(coverage, 0.05)


class MotionTests(unittest.TestCase):
    def test_the_capsule_only_ever_fills_forward(self):
        """Scroll was elapsed time times a changing rate, so it jumped back."""
        scene = SableFieldVisualizer(palette=((255, 0, 0), (0, 255, 0)))
        positions = []

        for index in range(120):
            bass = 0.9 if (index // 15) % 2 else 0.05
            shaped = reactivity.shape_features(
                dict(_BASE, bass=bass), "sable field")
            scene.step(DT, shaped, W, H)
            positions.append(scene.scroll)

        for earlier, later in zip(positions, positions[1:]):
            self.assertGreaterEqual(later, earlier)

    def test_a_hit_lands_rather_than_being_followed(self):
        """Symmetric smoothing left a transient still climbing after it passed."""
        scene = SableFieldVisualizer(palette=((255, 0, 0), (0, 255, 0)))
        shaped = reactivity.shape_features(dict(_BASE, bass=0.9), "sable field")

        frames = 0
        while scene.bass < 0.6 and frames < 60:
            scene.step(DT, shaped, W, H)
            frames += 1

        # Measured at two frames; anything beyond a handful reads as lag.
        self.assertLessEqual(frames, 5)

    def test_the_gate_stays_rarer_than_the_bands(self):
        """The one damping that was deliberate and stays."""
        profile = reactivity._PROFILES["sable field"]
        lattice = reactivity._PROFILES["acid lattice"]

        self.assertLess(profile["beat"][0], lattice["beat"][0])


if __name__ == "__main__":
    unittest.main()
