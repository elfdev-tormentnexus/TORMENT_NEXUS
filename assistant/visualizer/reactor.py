"""Audio-reactive orbital reactor for the terminal visualizer."""

import math


CELL_W = 2
CELL_H = 4
_BRAILLE_WEIGHTS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


class ReactorVisualizer:
    """A rotating, concentric reactor with audio-driven orbit fractures."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.pulse = 0.0
        self._np = None
        self._grid_key = None
        self._grid = None

    def step(self, dt, features, _width, _height):
        mid = max(0.0, min(1.0, float(features.get("mid", 0.0))))
        self.time += max(0.0, dt) * (0.45 + mid * 1.95)
        self.pulse = max(
            float(features.get("beat", 0.0)),
            self.pulse * math.exp(-max(0.0, dt) * 4.4),
        )

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np
        width, height = max(1, int(width)), max(1, int(height))
        pixel_w, pixel_h = width * CELL_W, height * CELL_H
        x, y, radius, angle = self._coordinates(pixel_w, pixel_h)
        bass = max(0.0, min(1.0, float(features.get("bass", 0.0))))
        mid = max(0.0, min(1.0, float(features.get("mid", 0.0))))
        treble = max(0.0, min(1.0, float(features.get("treble", 0.0))))
        level = max(0.0, min(1.0, float(features.get("level", 0.0))))
        spectrum = np.asarray(features.get("spectrum", ()), dtype=np.float32)
        if spectrum.size < 2:
            spectrum = np.zeros(48, dtype=np.float32)

        sector = ((angle + math.pi) / (2.0 * math.pi) * (spectrum.size - 1))
        energy = np.interp(sector.ravel(), np.arange(spectrum.size), spectrum).reshape(radius.shape)
        spin = angle * (5.0 + treble * 8.0) + self.time * (2.0 + mid * 3.0)
        core_radius = 0.12 + bass * 0.09 + self.pulse * 0.07
        core = np.exp(-((radius / max(0.03, core_radius)) ** 2))
        rings = np.exp(-((np.sin(radius * (24.0 + bass * 12.0) - self.time * 5.0 + energy * 5.0)) / (0.11 + treble * 0.12)) ** 2)
        blades = np.abs(np.sin(spin + radius * 12.0)) ** (10.0 - treble * 5.0)
        orbit = np.exp(-((radius - (0.56 + 0.10 * np.sin(spin * 0.6))) / 0.025) ** 2)
        noise = (np.sin(x * 57.0 + y * 71.0 + self.time * 10.0) + 1.0) * 0.5
        sparks = (noise > 0.965 - treble * 0.07) * (0.20 + treble * 0.72)
        intensity = np.clip(
            core * (0.56 + level * 0.44)
            + rings * (0.12 + energy * 0.58)
            + blades * (0.05 + mid * 0.32)
            + orbit * (0.24 + self.pulse * 0.72)
            + sparks,
            0.0,
            1.0,
        )

        bayer = np.asarray(_BAYER, dtype=np.float32) / 15.0
        threshold = np.tile(bayer, ((pixel_h + 3) // 4, (pixel_w + 3) // 4))[:pixel_h, :pixel_w]
        dots = intensity > (0.17 + threshold * 0.68)
        return self._to_cells(dots, intensity, width, height)

    def _coordinates(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)
        if self._grid_key == key:
            return self._grid
        np = self._np
        x = np.linspace(-1.35, 1.35, pixel_w, dtype=np.float32)
        y = np.linspace(-0.84, 0.84, pixel_h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        radius = np.sqrt((xx * 0.73) ** 2 + (yy * 1.14) ** 2)
        self._grid_key = key
        self._grid = (xx, yy, radius, np.arctan2(yy, xx))
        return self._grid

    def _to_cells(self, dots, intensity, width, height):
        np = self._np
        grid = dots.reshape(height, CELL_H, width, CELL_W)
        weights = np.asarray(_BRAILLE_WEIGHTS, dtype=np.uint16)
        bits = (grid * weights[None, :, None, :]).sum(axis=(1, 3))
        strength = intensity.reshape(height, CELL_H, width, CELL_W).max(axis=(1, 3))
        top = len(self.palette) - 1
        rows = []
        for y in range(height):
            row = []
            for x in range(width):
                packed = int(bits[y, x])
                if not packed:
                    row.append(None)
                    continue
                colour = min(top, max(0, int(strength[y, x] * top)))
                row.append((chr(0x2800 + packed), self.palette[colour]))
            rows.append(row)
        return rows
