"""
Audio-reactive blue radial field rendered with terminal braille pixels.

The scene deliberately resembles the vivid, liquid visualisers common in
older media players: a dark central tunnel, mirrored electric-blue energy,
radial streaks, and a real white oscilloscope trace across the horizon.
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

_BAYER_4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


class RadialVisualizer:
    """Wide, music-driven tunnel field with a central oscilloscope."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.phase = 0.0
        self.pulse = 0.0
        self.pan = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self._np = None
        self._grid_key = None
        self._grid = None

    def step(self, dt, features, _width, _height):
        """Advance the field with smoothed, frame-rate-independent motion."""
        bass = self._clamp(features.get("bass", 0.0))
        mid = self._clamp(features.get("mid", 0.0))
        treble = self._clamp(features.get("treble", 0.0))
        beat = self._clamp(features.get("beat", 0.0))
        pan = max(-1.0, min(1.0, float(features.get("pan", 0.0))))

        response = min(1.0, max(0.0, dt) * 8.0)
        self.bass += (bass - self.bass) * response
        self.mid += (mid - self.mid) * response
        self.treble += (treble - self.treble) * response
        self.pan += (pan - self.pan) * response

        self.time += dt * (0.72 + self.mid * 1.45)
        self.phase += dt * (0.32 + self.mid * 0.82)
        self.pulse = max(beat, self.pulse * math.exp(-max(0.0, dt) * 4.6))

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        pixel_w = width * CELL_W
        pixel_h = height * CELL_H
        x, y, radius, angle = self._coordinate_grid(pixel_w, pixel_h)

        level = self._clamp(features.get("level", 0.0))
        stereo = self._clamp(features.get("stereo_width", 0.0))
        spectrum = np.asarray(features.get("spectrum", ()), dtype=np.float32)

        if spectrum.size < 2:
            spectrum = np.zeros(48, dtype=np.float32)

        angular_position = (
            ((angle + math.pi) / (2.0 * math.pi))
            * (spectrum.size - 1)
        )
        angular_energy = np.interp(
            angular_position.ravel(),
            np.arange(spectrum.size),
            spectrum,
        ).reshape(radius.shape)
        mirrored_position = (
            1.0 - angular_position / max(1, spectrum.size - 1)
        ) * (spectrum.size - 1)
        mirrored_energy = np.interp(
            mirrored_position.ravel(),
            np.arange(spectrum.size),
            spectrum,
        ).reshape(radius.shape)
        energy = np.clip(
            angular_energy * 0.62 + mirrored_energy * 0.38,
            0.0,
            1.0,
        )

        warp = (
            0.15 * np.sin(angle * 3.0 + self.phase * 1.7)
            + 0.08 * np.sin(angle * 7.0 - self.phase * 2.3)
            + 0.05 * np.sin(angle * 13.0 + self.time)
        )
        field_radius = radius * (
            1.0 - self.bass * 0.08 - self.pulse * 0.055
        )
        travelling = (
            field_radius * (18.0 + self.treble * 8.0)
            - self.time * (4.2 + self.mid * 3.8)
            + warp * 17.0
            + energy * 4.5
        )

        liquid_edges = np.exp(
            -(
                np.abs(np.sin(travelling))
                / (0.12 + energy * 0.16 + self.pulse * 0.09)
            ) ** 2
        )
        secondary_edges = np.exp(
            -(
                np.abs(np.sin(
                    travelling * 0.57
                    - angle * 3.0
                    + self.phase * 3.0
                ))
                / 0.18
            ) ** 2
        )
        spokes = np.abs(
            np.sin(
                angle * (7.0 + self.treble * 4.0)
                + field_radius * 7.0
                - self.phase * 5.0
            )
        ) ** (8.0 - self.treble * 3.0)

        horizon_y = (
            0.025 * np.sin(x * 10.0 - self.time * 2.0)
            + 0.014 * np.sin(x * 27.0 + self.phase * 3.0)
        )
        horizon = np.exp(
            -(np.abs(y - horizon_y) / (0.011 + level * 0.010)) ** 2
        )
        horizon *= 0.45 + 0.55 * np.abs(
            np.sin(x * 22.0 + self.time * 2.5)
        )

        inner = np.clip((radius - 0.075) / 0.16, 0.0, 1.0)
        outer = np.clip((1.22 - radius) / 0.24, 0.0, 1.0)
        envelope = inner * outer
        ambient = 0.045 + level * 0.07
        intensity = (
            ambient
            + liquid_edges * (0.20 + energy * 0.72)
            + secondary_edges * (0.08 + self.mid * 0.25)
            + spokes * (0.07 + energy * 0.42 + self.treble * 0.18)
            + horizon * (0.32 + level * 0.55)
        ) * envelope

        if self.pulse > 0.01:
            ring = np.exp(
                -(np.abs(radius - (0.22 + self.pulse * 0.18)) / 0.045) ** 2
            )
            intensity += ring * self.pulse * 0.65 * envelope

        intensity = np.clip(intensity, 0.0, 1.0)
        white = np.zeros((pixel_h, pixel_w), dtype=bool)
        glow = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        self._draw_waveform(glow, white, features, level, stereo)
        intensity = np.maximum(intensity, glow)

        bayer = np.asarray(_BAYER_4, dtype=np.float32) / 15.0
        threshold = np.tile(
            bayer,
            ((pixel_h + 3) // 4, (pixel_w + 3) // 4),
        )[:pixel_h, :pixel_w]
        dots = intensity > (0.18 + threshold * 0.64)
        dots |= white

        return self._to_cells(dots, intensity, white, width, height)

    def _coordinate_grid(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)

        if self._grid_key == key:
            return self._grid

        np = self._np
        x = np.linspace(-1.28, 1.28, pixel_w, dtype=np.float32)
        y = np.linspace(-0.82, 0.82, pixel_h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        radial_x = xx * 0.72
        radial_y = yy * 1.08
        radius = np.sqrt(radial_x ** 2 + radial_y ** 2)
        angle = np.arctan2(radial_y, radial_x)
        self._grid_key = key
        self._grid = (xx, yy, radius, angle)
        return self._grid

    def _draw_waveform(self, glow, white, features, level, stereo):
        np = self._np
        height, width = glow.shape
        waveform = np.asarray(features.get("waveform", ()), dtype=np.float32)

        if waveform.size < 2:
            waveform = np.sin(
                np.linspace(0.0, math.pi * 6.0, 64, dtype=np.float32)
                + self.time * 1.4
            ) * 0.035

        left = max(1, int(width * 0.06))
        right = max(left, min(width - 2, int(width * 0.94)))
        xs = np.linspace(left, right, waveform.size).astype(np.int32)
        centre = (height - 1) * (0.50 + self.pan * 0.018)
        amplitude = height * (0.075 + level * 0.17 + stereo * 0.025)
        ys = np.rint(centre - np.clip(waveform, -1.0, 1.0) * amplitude)
        ys = np.clip(ys, 1, height - 2).astype(np.int32)

        for index in range(len(xs) - 1):
            self._line(
                glow,
                xs[index],
                ys[index],
                xs[index + 1],
                ys[index + 1],
                1.0,
            )
            self._line(
                white,
                xs[index],
                ys[index],
                xs[index + 1],
                ys[index + 1],
                True,
            )

        glow[1:] = np.maximum(glow[1:], white[:-1] * 0.72)
        glow[:-1] = np.maximum(glow[:-1], white[1:] * 0.72)

    def _line(self, target, x0, y0, x1, y1, value):
        np = self._np
        height, width = target.shape
        count = int(max(abs(x1 - x0), abs(y1 - y0))) + 2
        xs = np.linspace(x0, x1, count).astype(np.int32)
        ys = np.linspace(y0, y1, count).astype(np.int32)
        keep = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        target[ys[keep], xs[keep]] = value

    def _to_cells(self, dots, intensity, white, width, height):
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
        white_cells = white.reshape(
            height,
            CELL_H,
            width,
            CELL_W,
        ).any(axis=(1, 3))

        palette_top = len(self.palette) - 1
        rows = []

        for row_index in range(height):
            row = []

            for col_index in range(width):
                packed = int(bits[row_index, col_index])

                if not packed:
                    row.append(None)
                    continue

                if white_cells[row_index, col_index]:
                    color_index = palette_top
                else:
                    color_index = min(
                        palette_top - 1,
                        max(
                            0,
                            int(strength[row_index, col_index] * palette_top),
                        ),
                    )

                row.append(
                    (chr(0x2800 + packed), self.palette[color_index])
                )

            rows.append(row)

        return rows

    @staticmethod
    def _clamp(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0
