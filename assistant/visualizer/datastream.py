"""
Reactive digital-rain scene for the terminal music visualizer.

This is a deliberately dense, cinematic replacement for the older independent
glyph columns.  A layered code curtain now has slow foreground strands, fast
background sparks, a spectrum-shaped data horizon, and a brief scan-line fault
on a real beat.  It remains plain terminal text rather than imitation logos or
video frames, so it stays legible in the project's supported console fonts.
"""

import math


# Keep the alphabet to single-cell glyphs that render reliably in Windows
# terminals. Unicode escapes prevent an editor or shell codepage from turning
# the shaded blocks into mojibake.
_GLYPHS = (
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "<>[]{}/\\|=+*#%@$&?!:;~^"
    "\u2591\u2592\u2593\u2588\u2580\u2584\u258c\u2590"
)

_HEAD_SPAN = 0.82


class DatastreamVisualizer:
    """A perspective-like, audio-reactive curtain of falling terminal code."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.pulse = 0.0
        self.glitch = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self._previous_beat = 0.0
        self._np = None
        self._rng = None
        self._shape = None
        self._heads = None
        self._speeds = None
        self._lengths = None
        self._depths = None
        self._drift = None
        self._glyphs = None

    def step(self, dt, features, _width, _height):
        """Advance independent strands and short beat-driven data faults."""
        try:
            dt = max(0.0, min(0.25, float(dt)))
        except (TypeError, ValueError):
            dt = 0.0

        features = features or {}
        response = 1.0 - math.exp(-dt * 8.0)
        bass = self._feature(features, "bass")
        mid = self._feature(features, "mid")
        treble = self._feature(features, "treble")
        beat = self._feature(features, "beat")

        self.bass += (bass - self.bass) * response
        self.mid += (mid - self.mid) * response
        self.treble += (treble - self.treble) * response
        self.time += dt * (0.60 + self.mid * 0.95 + self.treble * 0.35)
        self.pulse = max(beat, self.pulse * math.exp(-dt * 4.8))

        if beat > 0.14 and beat > self._previous_beat + 0.045:
            self.glitch = 1.0
        self.glitch *= math.exp(-dt * 7.2)
        self._previous_beat = beat

        if self._heads is None:
            return

        np = self._np
        rows = self._shape[0]
        # Treble provides the obvious speed change, while bass makes the
        # heavier foreground strands land with the kick rather than merely
        # randomizing glyphs.
        flow = 3.0 + self.treble * 18.0 + self.mid * 4.5 + self.bass * 5.0
        self._heads += self._speeds * dt * flow

        gone = self._heads - self._lengths > rows
        if bool(np.any(gone)):
            count = int(np.count_nonzero(gone))
            self._heads[gone] = -self._rng.random(count) * rows * 0.28
            self._speeds[gone] = 0.36 + self._rng.random(count) * 1.24
            self._lengths[gone] = 4.0 + self._rng.random(count) * (
                max(rows, 4) * 0.92
            )
            self._depths[gone] = 0.25 + self._rng.random(count) * 0.75
            self._drift[gone] = self._rng.random(count) * math.tau

        # A beat briefly reseeds a handful of the nearest strands at the top
        # of the display. It creates a visible arrival without the whole rain
        # jumping or becoming a noisy television effect.
        if self.glitch > 0.55:
            struck = self._rng.random(self._heads.size) < (
                0.025 + self.glitch * 0.11
            )
            self._heads[struck] = np.minimum(
                self._heads[struck],
                self._rng.random(int(np.count_nonzero(struck))) * rows * 0.25,
            )

    def render(self, width, height, features):
        """Return palette-coloured, one-cell glyph rain for the UI canvas."""
        if self._np is None:
            import numpy as np
            self._np = np
            self._rng = np.random.default_rng(0x5EEDC0DE)

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        self._ensure_columns(width, height)

        features = features or {}
        level = self._feature(features, "level")
        spectrum = self._spectrum(features)
        columns = np.linspace(0.0, spectrum.size - 1, width)
        band = np.interp(
            columns,
            np.arange(spectrum.size, dtype=np.float32),
            spectrum,
        ).astype(np.float32)

        rows = np.arange(height, dtype=np.float32)[:, None]
        x = np.linspace(-1.0, 1.0, width, dtype=np.float32)[None, :]

        # Slow sinusoidal curvature makes the strands feel like a deep sheet
        # of data, rather than a row of unrelated columns. Audio mids widen
        # it, while foreground columns bend more than distant sparks.
        bend = (
            np.sin(x * (6.5 + self.mid * 6.0) + self.time * 1.6 + self._drift)
            * (0.16 + self.mid * 0.95)
            * self._depths
        )
        bend += np.sin(x * 18.0 - self.time * 2.1) * self.glitch * 0.42
        behind = (self._heads[None, :] + bend) - rows
        inside = (behind >= 0.0) & (behind < self._lengths[None, :])
        trail = np.clip(
            1.0 - behind / np.maximum(self._lengths[None, :], 1.0),
            0.0,
            1.0,
        )

        column_gain = (
            0.30
            + band[None, :] * 0.56
            + level * 0.25
            + self._depths[None, :] * 0.18
        )
        strength = np.where(inside, trail * column_gain, 0.0)

        # A low data horizon turns the live spectrum into a dense city of code
        # below the rain. It is subtle until music is present, then expands
        # strongly with bass and beats.
        floor = int(round(height * 0.79))
        horizon_height = np.maximum(
            1,
            np.rint(
                1.0
                + band * height * (0.11 + self.mid * 0.07)
                + self.bass * height * 0.12
                + self.pulse * height * 0.08
            ),
        ).astype(np.int32)
        horizon = (rows >= floor - horizon_height[None, :]) & (rows <= floor)
        horizon_strength = 0.14 + band[None, :] * 0.40 + level * 0.16
        strength = np.maximum(
            strength,
            np.where(horizon, horizon_strength, 0.0),
        )

        # A narrow scan-lane is the actual "corruption" event: it sweeps the
        # code field on a transient and fades immediately, rather than hiding
        # the rain behind a permanent static overlay.
        scan_y = (
            (self.time * (5.0 + self.bass * 8.0) + self.glitch * height * 0.18)
            % (height + 5.0)
        ) - 2.5
        scan = np.exp(-((rows - scan_y) / (0.55 + self.glitch * 1.7)) ** 2)
        scan_strength = scan * (0.035 + self.glitch * 0.55 + self.pulse * 0.08)
        strength = np.maximum(strength, scan_strength)
        heads = inside & (behind < _HEAD_SPAN)
        scan_heads = scan > (0.72 - self.glitch * 0.22)

        self._churn_glyphs(width, height)
        return self._to_cells(strength, heads | scan_heads, width, height)

    def _ensure_columns(self, width, height):
        """Allocate a stable, full field for the current terminal geometry."""
        if self._shape == (height, width):
            return

        np = self._np
        rng = self._rng
        self._shape = (height, width)
        self._heads = (rng.random(width) * (height + 3.0)).astype(np.float32)
        self._speeds = (0.36 + rng.random(width) * 1.24).astype(np.float32)
        self._lengths = (
            4.0 + rng.random(width) * (max(height, 4) * 0.92)
        ).astype(np.float32)
        self._depths = (0.25 + rng.random(width) * 0.75).astype(np.float32)
        self._drift = (rng.random(width) * math.tau).astype(np.float32)
        self._glyphs = rng.integers(
            0,
            len(_GLYPHS),
            size=(height, width),
            dtype=np.int16,
        )

    def _churn_glyphs(self, width, height):
        """Keep readable strings, with a brief beat-driven code mutation."""
        np = self._np
        churn = 0.006 + self.treble * 0.045 + self.glitch * 0.43
        mask = self._rng.random((height, width)) < churn

        if not bool(np.any(mask)):
            return

        replacement = self._rng.integers(
            0,
            len(_GLYPHS),
            size=(height, width),
        )
        self._glyphs = np.where(mask, replacement, self._glyphs).astype(np.int16)

    def _to_cells(self, strength, heads, width, height):
        top = len(self.palette) - 1
        palette = self.palette or ("",)
        rows = []

        for row_index in range(height):
            row = []
            for col_index in range(width):
                value = float(strength[row_index, col_index])
                if value <= 0.065:
                    row.append(None)
                    continue

                glyph = _GLYPHS[int(self._glyphs[row_index, col_index])]
                if heads[row_index, col_index]:
                    colour = top
                elif top <= 0:
                    colour = 0
                else:
                    colour = min(top - 1, max(0, int(value * top)))
                row.append((glyph, palette[colour]))
            rows.append(row)

        return rows

    def _spectrum(self, features):
        np = self._np
        try:
            spectrum = np.asarray(features.get("spectrum", ()), dtype=np.float32)
        except (AttributeError, TypeError, ValueError):
            spectrum = np.empty(0, dtype=np.float32)
        if spectrum.size < 2:
            return np.zeros(48, dtype=np.float32)
        return np.clip(
            np.nan_to_num(spectrum.reshape(-1), nan=0.0, posinf=1.0),
            0.0,
            1.0,
        )

    @staticmethod
    def _feature(features, name):
        try:
            return max(0.0, min(1.0, float(features.get(name, 0.0))))
        except (AttributeError, TypeError, ValueError):
            return 0.0
