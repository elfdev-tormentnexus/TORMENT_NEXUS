"""
Neon horizon grid for the terminal visualizer.

This is the perspective half of the Y2K vocabulary the other scenes leave
untouched: a wireframe floor rushing away to a hard horizon, a banded sun
sitting on that horizon, and a spectrum-shaped skyline cut out in front of
it. The radial tunnel owns polar space and the cathedral owns vertical
bars, so this one is built entirely out of depth instead.

The floor is not a projected mesh. Each pixel below the horizon is turned
back into a ground coordinate -- depth is one over the distance below the
horizon -- which gives true perspective for the price of two divisions and
costs nothing per grid line.
"""

import math


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

# The horizon sits above centre so the floor gets most of the viewport.
# Terminal cells are tall, and an even split leaves the grid looking squat.
_HORIZON = -0.18

# Ground lines further away than this fade out completely. Without it the
# floor turns into a solid bright wash where the lines converge.
_DEPTH_FADE = 26.0

# How far the camera floats above the plane, and how wide a ground unit is.
# Together these decide how many grid squares are visible at the bottom of
# the viewport; too small and the whole floor sits inside one square.
_CAMERA = 2.0
_GROUND_SPREAD = 1.6

# Ground units per pixel at which a family of lines stops being resolvable.
_RESOLVE = 0.55


class GridVisualizer:
    """Wireframe ground plane running to a banded sun on the horizon."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.travel = 0.0
        self.pulse = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self._np = None
        self._grid_key = None
        self._grid = None

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

        # Travel is what sells the perspective, so bass drives distance
        # covered rather than a colour or a size.
        self.travel += dt * (1.05 + self.bass * 2.70 + self.pulse * 1.30)
        self.time += dt * (0.55 + self.mid * 1.20)
        self.pulse = max(beat, self.pulse * math.exp(-dt * 3.8))

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        pixel_w = width * CELL_W
        pixel_h = height * CELL_H
        xx, yy = self._coordinates(pixel_w, pixel_h)

        level = self._clamp(features.get("level", 0.0))
        spectrum = np.asarray(features.get("spectrum", ()), dtype=np.float32)

        if spectrum.size < 2:
            spectrum = np.zeros(48, dtype=np.float32)

        intensity = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        highlight = np.zeros((pixel_h, pixel_w), dtype=bool)

        self._draw_sun(intensity, highlight, xx, yy, level)
        self._draw_skyline(intensity, highlight, xx, yy, spectrum, level)
        self._draw_floor(intensity, xx, yy, level)
        self._draw_horizon(intensity, highlight, yy, level)

        intensity = np.clip(intensity, 0.0, 1.0)
        bayer = np.asarray(_BAYER, dtype=np.float32) / 15.0
        threshold = np.tile(
            bayer,
            ((pixel_h + 3) // 4, (pixel_w + 3) // 4),
        )[:pixel_h, :pixel_w]
        dots = intensity > (0.17 + threshold * 0.62)
        dots |= highlight

        return self._to_cells(dots, intensity, highlight, width, height)

    def _draw_sun(self, intensity, highlight, xx, yy, level):
        """A banded disc bisected by the horizon, in the usual chrome idiom."""
        np = self._np
        centre_y = _HORIZON - 0.30
        offset_y = yy - centre_y
        radius = np.sqrt((xx * 0.62) ** 2 + offset_y ** 2)
        size = 0.30 + self.bass * 0.055 + self.pulse * 0.045

        disc = np.clip((size - radius) / 0.045, 0.0, 1.0)

        # Bands widen toward the bottom of the disc, which is the detail
        # that reads as "sunset" rather than "striped circle".
        depth = np.clip((offset_y + size) / max(2.0 * size, 1e-3), 0.0, 1.0)
        bands = 0.5 + 0.5 * np.cos(offset_y * 44.0 + self.time * 1.1)
        bands = np.where(bands > (0.12 + depth * 0.74), 1.0, 0.12)

        body = disc * bands
        intensity[:] = np.maximum(intensity, body * (0.50 + level * 0.38))

        rim = np.exp(-(np.abs(radius - size) / 0.014) ** 2)
        rim *= yy < _HORIZON
        intensity[:] = np.maximum(intensity, rim * (0.85 + level * 0.15))
        highlight |= rim > 0.55

    def _draw_skyline(self, intensity, highlight, xx, yy, spectrum, level):
        """Spectrum-shaped ridge that genuinely occludes the sun behind it."""
        np = self._np
        x_axis = xx[0]

        # Mirroring about the centre keeps the ridge symmetrical, which
        # stops it reading as a bar chart that happens to be pointy.
        position = np.clip(np.abs(x_axis) / 1.42, 0.0, 1.0)
        position = position * (spectrum.size - 1)
        profile = np.interp(
            position,
            np.arange(spectrum.size, dtype=np.float32),
            spectrum,
        )

        ridge = profile * (0.15 + self.bass * 0.17) + 0.030
        ridge = ridge + 0.020 * np.sin(x_axis * 8.5 + self.time * 0.7)
        crest = _HORIZON - np.clip(ridge, 0.0, 0.55)

        body = (yy >= crest[None, :]) & (yy <= _HORIZON)
        edge = np.exp(-(np.abs(yy - crest[None, :]) / 0.013) ** 2)
        edge *= body | (yy < _HORIZON)

        # Overwrite rather than max, so the ridge blocks the sun instead of
        # letting it glow straight through the mountain.
        intensity[:] = np.where(body, 0.05 + level * 0.06, intensity)
        intensity[:] = np.maximum(intensity, edge * (0.72 + self.treble * 0.28))
        highlight |= edge > 0.62

    def _draw_floor(self, intensity, xx, yy, level):
        """Turn each pixel below the horizon back into a ground coordinate."""
        np = self._np
        below = yy > _HORIZON
        drop = np.maximum(yy - _HORIZON, 1e-3)
        depth = _CAMERA / drop
        ground_x = xx * depth * _GROUND_SPREAD
        ground_z = depth + self.travel

        # Line width is held roughly constant on screen by widening it in
        # ground units as the surface recedes. Too narrow and a line falls
        # below one pixel and dithers away to nothing.
        across = np.abs(ground_x - np.round(ground_x))
        along = np.abs(ground_z - np.round(ground_z))

        # How far a single pixel travels in ground units, per axis. Both
        # the aliasing fade and the line width are expressed against this,
        # because both failures are really the same failure: drawing detail
        # finer than the raster can carry.
        pixel_h, pixel_w = xx.shape
        span_y = (_CAMERA / drop ** 2) * (2.0 / max(pixel_h - 1, 1))
        span_x = depth * _GROUND_SPREAD * (2.84 / max(pixel_w - 1, 1))

        # Near the horizon successive lines land closer together than one
        # pixel, and sampling them yields moire rather than a grid. Fade
        # each family as its own spacing approaches the raster.
        along_visible = np.clip(1.0 - span_y / _RESOLVE, 0.0, 1.0)
        across_visible = np.clip(1.0 - span_x / _RESOLVE, 0.0, 1.0)

        # Hold each family at least a pixel and a half wide, or the peak
        # falls between two samples and the line renders as broken dashes.
        nominal = np.clip(depth * 0.045, 0.045, 0.90)
        along_w = np.maximum(nominal, span_y * 1.4)
        across_w = np.maximum(nominal, span_x * 1.4)

        lines = np.maximum(
            np.exp(-(across / across_w) ** 2) * across_visible,
            np.exp(-(along / along_w) ** 2) * along_visible,
        )
        lines *= np.clip(1.0 - depth / _DEPTH_FADE, 0.0, 1.0) * below

        # Depth cueing already lives in the fade factors above, so the near
        # cores are driven clear of the dither ceiling rather than left to
        # straddle it, where every other subpixel drops out.
        intensity[:] = np.maximum(
            intensity,
            lines * (0.90 + level * 0.10 + self.pulse * 0.15),
        )

    def _draw_horizon(self, intensity, highlight, yy, level):
        np = self._np
        distance = np.abs(yy - _HORIZON)
        glow = np.exp(-(distance / 0.055) ** 2)
        intensity[:] = np.maximum(intensity, glow * (0.22 + level * 0.30))

        # A line thinner than one pixel row cannot render solid, so widen it
        # to the raster instead of letting it break into dashes.
        step_y = 2.0 / max(yy.shape[0] - 1, 1)
        line = np.exp(-(distance / max(0.007, step_y * 1.15)) ** 2)
        intensity[:] = np.maximum(intensity, line)
        highlight |= line > 0.5

    def _coordinates(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)

        if self._grid_key == key:
            return self._grid

        np = self._np
        x = np.linspace(-1.42, 1.42, pixel_w, dtype=np.float32)
        y = np.linspace(-1.0, 1.0, pixel_h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        self._grid_key = key
        self._grid = (xx, yy)
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
