"""
Hyperspace wormhole for the terminal visualizer.

A projected starfield inside a flexing tunnel. The radial tunnel scene next
door is a flat polar field with no depth model at all; this one carries real
per-star depth, so stars accelerate as they approach, spread away from the
vanishing point, and stretch into streaks when the music drives the speed
up. The two read very differently in motion despite both being round.

Streaks are drawn by sampling each star along the segment it covered during
the frame rather than by blurring afterwards, which keeps a fast star as one
continuous line instead of a dotted trail.
"""

import math

from visualizer import anchor


CELL_W = 2
CELL_H = 4

_BRAILLE_WEIGHTS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)

_BAYER = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)

_STARS = 340

# Samples taken along each star's per-frame path. Enough to keep a fast
# streak unbroken without turning the scatter into the dominant cost.
_STREAK_SAMPLES = 7

# Depth at which a star is recycled. Never zero: the projection divides by
# it, and a star exactly at the eye projects to infinity.
_NEAR_PLANE = 0.045

_HALF_WIDTH = 1.34

# Focal scale for the star projection. Larger spreads the field away from
# the vanishing point sooner, which is what lengthens the streaks; too
# small and every star stays bunched in the middle as a dot.
_PROJECTION = 0.42


class WormholeVisualizer:
    """Projected starfield rushing outward through a ribbed tunnel."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        # Wall-clock seconds for the slow anchor layer. Deliberately not
        # scaled by audio: a reference that speeds up with the music is
        # not a reference. See visualizer/anchor.py.
        self.slow = 0.0
        self.warp = 0.0
        self.pulse = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self._np = None
        self._rng = None
        self._grid_key = None
        self._grid = None
        self._x = None
        self._y = None
        self._z = None
        self._prev_z = None

    def _ensure_stars(self):
        if self._x is not None:
            return

        np = self._np
        rng = self._rng
        # Stars are seeded in a ring rather than a disc, so the centre of
        # the tunnel stays open and reads as distance instead of clutter.
        angle = rng.random(_STARS) * (2.0 * math.pi)
        radius = 0.22 + rng.random(_STARS) * 0.95
        self._x = (np.cos(angle) * radius).astype(np.float32)
        self._y = (np.sin(angle) * radius).astype(np.float32)
        self._z = (_NEAR_PLANE + rng.random(_STARS)).astype(np.float32)
        self._prev_z = self._z.copy()

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
        self.pulse = max(beat, self.pulse * math.exp(-dt * 4.0))

        self.time += dt * (0.60 + self.mid * 1.30)
        self.slow += dt
        self.warp += dt * (1.30 + self.bass * 2.40 + self.pulse * 3.20)

        if self._np is None or self._x is None:
            return

        np = self._np
        speed = dt * (0.42 + self.bass * 0.85 + self.pulse * 1.45)
        self._prev_z = self._z.copy()
        self._z = self._z - speed

        # Past the eye a star wraps to the far plane with a fresh angle, so
        # the field never repeats a recognisable pattern.
        passed = self._z <= _NEAR_PLANE
        if bool(np.any(passed)):
            count = int(np.count_nonzero(passed))
            angle = self._rng.random(count) * (2.0 * math.pi)
            radius = 0.22 + self._rng.random(count) * 0.95
            self._x[passed] = np.cos(angle) * radius
            self._y[passed] = np.sin(angle) * radius
            self._z[passed] = 1.0 + self._rng.random(count) * 0.35
            # Reset the trail too, or the wrap draws a streak clean across
            # the screen from the old position to the new one.
            self._prev_z[passed] = self._z[passed]

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np
            self._rng = np.random.default_rng(0x5EED)

        np = self._np
        self._ensure_stars()

        width = max(1, int(width))
        height = max(1, int(height))
        pixel_w = width * CELL_W
        pixel_h = height * CELL_H
        xx, yy, radius, angle = self._coordinates(pixel_w, pixel_h)

        level = self._clamp(features.get("level", 0.0))
        spectrum = np.asarray(features.get("spectrum", ()), dtype=np.float32)

        if spectrum.size < 2:
            spectrum = np.zeros(48, dtype=np.float32)

        intensity = self._draw_tunnel(radius, angle, spectrum, level)

        # Slow rings expanding under the starfield. Rings rather than bands
        # because this scene is built around a vanishing point, and
        # horizontal strata would fight its geometry rather than sit behind
        # it. Wall-clock only -- see visualizer/anchor.py.
        anchor.apply(
            np,
            intensity,
            anchor.rings(np, xx, yy, self.slow),
            strength=0.30,
            mid=self.mid,
        )

        highlight = np.zeros((pixel_h, pixel_w), dtype=bool)
        stars = np.zeros((pixel_h, pixel_w), dtype=bool)
        self._draw_stars(intensity, highlight, stars, pixel_w, pixel_h)

        intensity = np.clip(intensity, 0.0, 1.0)
        bayer = np.asarray(_BAYER, dtype=np.float32) / 15.0
        threshold = np.tile(
            bayer,
            ((pixel_h + 3) // 4, (pixel_w + 3) // 4),
        )[:pixel_h, :pixel_w]
        dots = intensity > (0.18 + threshold * 0.62)
        # A star is a point, and dithering a point makes it blink in and out
        # between frames. They are drawn unconditionally instead.
        dots |= stars
        dots |= highlight

        return self._to_cells(dots, intensity, highlight, width, height)

    def _draw_tunnel(self, radius, angle, spectrum, level):
        """Receding rings plus angular ribs, both flexing with the music."""
        np = self._np

        # Rings are evenly spaced in inverse radius, which is what puts the
        # vanishing point at the centre instead of at the edges.
        depth = 1.0 / np.maximum(radius, 0.055)
        rings = np.abs(np.sin(depth * 2.6 - self.warp * 1.7))
        rings = np.exp(-(rings / (0.16 + self.mid * 0.14)) ** 2)

        band = np.interp(
            (((angle + math.pi) / (2.0 * math.pi)) * (spectrum.size - 1)).ravel(),
            np.arange(spectrum.size, dtype=np.float32),
            spectrum,
        ).reshape(radius.shape)

        ribs = np.abs(
            np.sin(angle * 9.0 + self.warp * 0.9 + band * 2.4)
        ) ** (7.0 - self.treble * 3.0)

        # Everything fades toward the centre so the throat stays dark and
        # actually reads as somewhere the stars are arriving from.
        throat = np.clip((radius - 0.10) / 0.26, 0.0, 1.0)
        wall = np.clip((1.30 - radius) / 0.42, 0.0, 1.0)
        envelope = throat * wall

        # Kept deliberately dim. The tunnel is the room the stars fly
        # through; at full strength it competes with them and the scene
        # stops reading as depth at all.
        return (
            0.030
            + rings * (0.17 + band * 0.32 + level * 0.13)
            + ribs * (0.06 + band * 0.20 + self.treble * 0.11)
        ) * envelope

    def _draw_stars(self, intensity, highlight, stars, pixel_w, pixel_h):
        """Scatter each star along the path it covered during this frame."""
        np = self._np

        walk = np.linspace(0.0, 1.0, _STREAK_SAMPLES, dtype=np.float32)[None, :]
        depths = self._z[:, None] + (self._prev_z - self._z)[:, None] * walk
        depths = np.maximum(depths, _NEAR_PLANE)

        screen_x = (self._x[:, None] / depths) * _PROJECTION
        screen_y = (self._y[:, None] / depths) * _PROJECTION

        columns = (screen_x + _HALF_WIDTH) / (2.0 * _HALF_WIDTH) * (pixel_w - 1)
        rows = (screen_y + 1.0) * 0.5 * (pixel_h - 1)
        columns = np.rint(columns).astype(np.int32)
        rows = np.rint(rows).astype(np.int32)

        # Nearer samples are brighter, and the tail of the streak dims so a
        # fast star reads as travelling rather than as a static line.
        brightness = np.clip(1.0 - depths * 0.82, 0.06, 1.0)
        brightness = brightness * (0.55 + 0.45 * walk)

        keep = (
            (columns >= 0)
            & (columns < pixel_w)
            & (rows >= 0)
            & (rows < pixel_h)
        )

        flat_rows = rows[keep]
        flat_cols = columns[keep]
        flat_values = brightness[keep].astype(np.float32)

        if flat_rows.size:
            np.maximum.at(intensity, (flat_rows, flat_cols), flat_values)
            visible = flat_values > 0.22
            if bool(np.any(visible)):
                stars[flat_rows[visible], flat_cols[visible]] = True
            hot = flat_values > 0.72
            if bool(np.any(hot)):
                highlight[flat_rows[hot], flat_cols[hot]] = True

    def _coordinates(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)

        if self._grid_key == key:
            return self._grid

        np = self._np
        x = np.linspace(-_HALF_WIDTH, _HALF_WIDTH, pixel_w, dtype=np.float32)
        y = np.linspace(-1.0, 1.0, pixel_h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        # Squashed on x so the tunnel reads round in a terminal whose cells
        # are roughly twice as tall as they are wide.
        radius = np.sqrt((xx * 0.62) ** 2 + yy ** 2)
        angle = np.arctan2(yy, xx * 0.62)
        self._grid_key = key
        self._grid = (xx, yy, radius, angle)
        return self._grid

    def _to_cells(self, dots, intensity, highlight, width, height):
        np = self._np
        grid = dots.reshape(height, CELL_H, width, CELL_W)
        weights = np.asarray(_BRAILLE_WEIGHTS, dtype=np.uint16)
        bits = (grid * weights[None, :, None, :]).sum(axis=(1, 3))
        strength = intensity.reshape(
            height,
            CELL_H,
            width,
            CELL_W,
        ).max(axis=(1, 3))
        bright = highlight.reshape(
            height,
            CELL_H,
            width,
            CELL_W,
        ).any(axis=(1, 3))

        top = len(self.palette) - 1
        rows = []

        for row_index in range(height):
            row = []

            for col_index in range(width):
                packed = int(bits[row_index, col_index])

                if not packed:
                    row.append(None)
                    continue

                if bright[row_index, col_index]:
                    colour = top
                else:
                    colour = min(
                        max(0, top - 1),
                        max(0, int(strength[row_index, col_index] * top)),
                    )

                row.append((chr(0x2800 + packed), self.palette[colour]))

            rows.append(row)

        return rows

    @staticmethod
    def _clamp(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0
