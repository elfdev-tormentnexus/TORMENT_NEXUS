"""Audio-reactive spectrum cathedral for the terminal visualizer."""

import math


CELL_W = 2
CELL_H = 4
_BRAILLE_WEIGHTS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


class SpectrumVisualizer:
    """A mirrored equalizer wall with a live centre trace."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.pulse = 0.0
        self._np = None

    def step(self, dt, features, _width, _height):
        self.time += max(0.0, dt) * (0.7 + float(features.get("mid", 0.0)) * 1.7)
        self.pulse = max(
            float(features.get("beat", 0.0)),
            self.pulse * math.exp(-max(0.0, dt) * 3.8),
        )

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np
        width, height = max(1, int(width)), max(1, int(height))
        pixel_w, pixel_h = width * CELL_W, height * CELL_H
        intensity = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        spectrum = np.asarray(features.get("spectrum", ()), dtype=np.float32)

        if spectrum.size < 2:
            spectrum = np.zeros(48, dtype=np.float32)

        level = max(0.0, min(1.0, float(features.get("level", 0.0))))
        bass = max(0.0, min(1.0, float(features.get("bass", 0.0))))
        treble = max(0.0, min(1.0, float(features.get("treble", 0.0))))
        bars = max(5, min(26, pixel_w // 4))
        sample_positions = np.linspace(0, spectrum.size - 1, bars)
        energies = np.interp(sample_positions, np.arange(spectrum.size), spectrum)
        floor = pixel_h - 3
        spacing = pixel_w / bars

        for index, energy in enumerate(energies):
            centre = int((index + 0.5) * spacing)
            half = max(1, int(spacing * 0.27))
            height_px = max(2, int((0.10 + energy * 0.82 + bass * 0.09) * (pixel_h - 4)))
            top = max(1, floor - height_px)
            left, right = max(0, centre - half), min(pixel_w, centre + half + 1)
            intensity[top:floor, left:right] = np.maximum(
                intensity[top:floor, left:right],
                0.25 + energy * 0.75,
            )
            # Reflected lower bars make the whole field read as a cathedral
            # rather than a conventional tiny equalizer.
            reflected = min(pixel_h - 1, floor + max(1, height_px // 4))
            intensity[floor:reflected, left:right] = np.maximum(
                intensity[floor:reflected, left:right], 0.18 + energy * 0.5,
            )

        x = np.arange(pixel_w, dtype=np.float32)
        horizon = int(pixel_h * 0.50 + math.sin(self.time * 0.8) * pixel_h * 0.025)
        wave = np.sin(x * (0.10 + treble * 0.09) + self.time * 6.0)
        y = np.rint(horizon + wave * (1.0 + level * pixel_h * 0.095)).astype(np.int32)
        y = np.clip(y, 0, pixel_h - 1)
        intensity[y, np.arange(pixel_w)] = 1.0

        if self.pulse > 0.02:
            glow = np.exp(-((np.arange(pixel_h)[:, None] - horizon) / (1.5 + self.pulse * 5.0)) ** 2)
            intensity = np.maximum(intensity, glow * self.pulse * 0.44)

        bayer = np.asarray(_BAYER, dtype=np.float32) / 15.0
        threshold = np.tile(bayer, ((pixel_h + 3) // 4, (pixel_w + 3) // 4))[:pixel_h, :pixel_w]
        dots = intensity > (0.16 + threshold * 0.70)
        return self._to_cells(dots, intensity, width, height)

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
