"""
Falling glyph columns for the terminal visualizer.

The other scenes paint with braille subpixels and treat the terminal as a
dot matrix. This one does the opposite and uses the character cell as the
character cell, because a scene made of readable glyphs is the one that
looks like the machine is spilling its contents -- which is the joke the
whole project is named after.

Columns fall at a speed set by treble, so busy passages accelerate the
rain, and beats scramble glyphs in place rather than moving anything, so a
transient reads as corruption instead of as a jolt.
"""

import math


# Deliberately restricted to characters already proven to render in the
# Windows terminals this ships to: ASCII plus the block set the cube scene
# uses. Anything wider risks tofu boxes on a default console font.
_GLYPHS = (
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "<>[]{}/\\|=+*#%@$&?!:;~^"
    "░▒▓█▀▄▌▐"
)

# Fraction of a column's length that renders as the bright leading head.
_HEAD_SPAN = 1.0


class DatastreamVisualizer:
    """Glyph rain whose speed tracks treble and whose glyphs rot on beats."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.pulse = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self._np = None
        self._rng = None
        self._shape = None
        self._heads = None
        self._speeds = None
        self._lengths = None
        self._glyphs = None

    def step(self, dt, features, _width, _height):
        dt = max(0.0, float(dt))
        response = min(1.0, dt * 7.0)
        bass = self._clamp(features.get("bass", 0.0))
        mid = self._clamp(features.get("mid", 0.0))
        treble = self._clamp(features.get("treble", 0.0))
        beat = self._clamp(features.get("beat", 0.0))

        self.bass += (bass - self.bass) * response
        self.mid += (mid - self.mid) * response
        self.treble += (treble - self.treble) * response
        self.time += dt
        self.pulse = max(beat, self.pulse * math.exp(-dt * 4.2))

        if self._heads is None:
            return

        np = self._np
        rows = self._shape[0]
        # Advance is in cells per second. Each column keeps its own base
        # speed so the rain never marches in lockstep.
        self._heads += (
            self._speeds
            * dt
            * (4.0 + self.treble * 16.0 + self.bass * 4.0)
        )

        # A column that has fully left the bottom re-enters above the top
        # with a fresh speed and length, so the field keeps reshuffling.
        gone = self._heads - self._lengths > rows
        if bool(np.any(gone)):
            count = int(np.count_nonzero(gone))
            # Re-entering only just above the top matters: a deeper offset
            # lets neighbouring columns sit off-screen together and opens
            # visible dead patches across the field.
            self._heads[gone] = -self._rng.random(count) * rows * 0.22
            self._speeds[gone] = 0.45 + self._rng.random(count) * 0.95
            self._lengths[gone] = 5.0 + self._rng.random(count) * (
                max(rows, 4) * 0.85
            )

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np
            self._rng = np.random.default_rng(0xC0FFEE)

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        self._ensure_columns(width, height)

        level = self._clamp(features.get("level", 0.0))
        spectrum = np.asarray(features.get("spectrum", ()), dtype=np.float32)

        if spectrum.size < 2:
            spectrum = np.zeros(48, dtype=np.float32)

        # Each column samples its own spectrum band, so a bright column
        # corresponds to a frequency that is actually loud.
        band = np.interp(
            np.linspace(0.0, spectrum.size - 1, width),
            np.arange(spectrum.size, dtype=np.float32),
            spectrum,
        ).astype(np.float32)

        rows = np.arange(height, dtype=np.float32)[:, None]
        behind = self._heads[None, :] - rows
        inside = (behind >= 0.0) & (behind < self._lengths[None, :])

        # Brightness falls off along the tail, so each column reads as a
        # comet rather than a uniform bar.
        trail = np.clip(
            1.0 - behind / np.maximum(self._lengths[None, :], 1.0),
            0.0,
            1.0,
        )
        strength = np.where(inside, trail, 0.0).astype(np.float32)
        strength *= 0.45 + band[None, :] * 0.40 + level * 0.25
        strength = np.clip(strength + self.pulse * 0.10 * (strength > 0.0), 0.0, 1.0)

        heads = inside & (behind < _HEAD_SPAN)

        self._churn_glyphs(width, height)

        return self._to_cells(strength, heads, width, height)

    def _ensure_columns(self, width, height):
        """Reallocate column state when the terminal changes shape."""
        if self._shape == (height, width):
            return

        np = self._np
        rng = self._rng
        self._shape = (height, width)
        # Heads start spread across the viewport rather than above it, so
        # the scene is already full on its very first frame.
        self._heads = (rng.random(width) * height).astype(np.float32)
        self._speeds = (0.45 + rng.random(width) * 0.95).astype(np.float32)
        self._lengths = (
            5.0 + rng.random(width) * (max(height, 4) * 0.85)
        ).astype(np.float32)
        self._glyphs = rng.integers(
            0,
            len(_GLYPHS),
            size=(height, width),
        ).astype(np.int16)

    def _churn_glyphs(self, width, height):
        """Rot a share of the glyphs in place; beats rot far more of them."""
        np = self._np
        churn = 0.02 + self.treble * 0.10 + self.pulse * 0.38
        mask = self._rng.random((height, width)) < churn

        if not bool(np.any(mask)):
            return

        replacement = self._rng.integers(0, len(_GLYPHS), size=(height, width))
        self._glyphs = np.where(mask, replacement, self._glyphs).astype(np.int16)

    def _to_cells(self, strength, heads, width, height):
        top = len(self.palette) - 1
        rows = []

        for row_index in range(height):
            row = []

            for col_index in range(width):
                value = float(strength[row_index, col_index])

                if value <= 0.06:
                    row.append(None)
                    continue

                glyph = _GLYPHS[int(self._glyphs[row_index, col_index])]

                if heads[row_index, col_index]:
                    colour = top
                else:
                    colour = min(
                        max(0, top - 1),
                        max(0, int(value * top)),
                    )

                row.append((glyph, self.palette[colour]))

            rows.append(row)

        return rows

    @staticmethod
    def _clamp(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0
