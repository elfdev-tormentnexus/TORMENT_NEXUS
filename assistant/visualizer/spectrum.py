"""
Psychedelic spectrum cathedral for the terminal visualizer.

This is deliberately closer to a turn-of-the-millennium media-player
visualizer than a conventional equalizer: gel-glass towers, a luminous
portal, an aurora ceiling, a receding cyber grid, and a white waveform
thread all occupy the same impossible chrome space.
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


class SpectrumVisualizer:
    """A liquid equalizer temple floating above a perspective grid."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.pulse = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self._np = None
        self._grid_key = None
        self._grid = None

    def step(self, dt, features, _width, _height):
        dt = max(0.0, float(dt))
        response = min(1.0, dt * 7.5)
        bass = self._clamp(features.get("bass", 0.0))
        mid = self._clamp(features.get("mid", 0.0))
        treble = self._clamp(features.get("treble", 0.0))
        beat = self._clamp(features.get("beat", 0.0))

        self.bass += (bass - self.bass) * response
        self.mid += (mid - self.mid) * response
        self.treble += (treble - self.treble) * response
        self.time += dt * (0.52 + self.mid * 1.65)
        self.pulse = max(beat, self.pulse * math.exp(-dt * 4.0))

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
        intensity = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        highlight = np.zeros((pixel_h, pixel_w), dtype=bool)

        level = self._clamp(features.get("level", 0.0))
        spectrum = np.asarray(
            features.get("spectrum", ()),
            dtype=np.float32,
        )
        if spectrum.size < 2:
            spectrum = np.zeros(48, dtype=np.float32)

        # A scalloped portal sits behind the towers. Multiple close shells
        # produce the pearlescent, airbrushed depth of old media players.
        portal_y = yy + 0.13
        portal_radius = np.sqrt((xx * 0.72) ** 2 + (portal_y * 1.08) ** 2)
        portal_phase = (
            portal_radius * (18.0 + self.bass * 4.0)
            - self.time * 2.8
            + np.sin(xx * 3.5 - self.time) * 0.8
        )
        portal = np.exp(
            -(
                np.abs(np.sin(portal_phase))
                / (0.10 + self.mid * 0.10)
            ) ** 2
        )
        portal *= np.clip((1.08 - portal_radius) / 0.22, 0.0, 1.0)
        portal *= np.clip((portal_radius - 0.15) / 0.18, 0.0, 1.0)
        intensity = np.maximum(
            intensity,
            portal * (0.14 + level * 0.25),
        )

        # Two fluid ribbons make a synthetic aurora across the upper half.
        ribbon_axis = (
            yy
            + 0.50
            + np.sin(xx * 2.4 - self.time * 1.4) * 0.13
            + np.sin(xx * 6.1 + self.time * 0.8) * 0.045
        )
        aurora = np.exp(
            -(np.abs(ribbon_axis) / (0.035 + self.treble * 0.025)) ** 2
        )
        second_axis = (
            yy
            + 0.68
            - np.sin(xx * 3.2 + self.time) * 0.08
        )
        aurora += np.exp(-(np.abs(second_axis) / 0.026) ** 2) * 0.55
        aurora *= np.clip((-yy + 0.16) / 0.32, 0.0, 1.0)
        intensity = np.maximum(
            intensity,
            aurora * (0.20 + self.treble * 0.42),
        )

        horizon = max(2, min(pixel_h - 2, int(pixel_h * 0.58)))
        self._draw_gel_towers(
            intensity,
            highlight,
            spectrum,
            horizon,
            level,
        )
        self._draw_cyber_grid(intensity, xx, yy)
        self._draw_waveform(
            intensity,
            highlight,
            features,
            horizon,
            level,
        )

        # Deterministic glints hang in the "sky". They shimmer instead of
        # jumping randomly between frames.
        glint_noise = (
            np.sin(xx * 83.0 + yy * 47.0 + self.time * 2.0)
            * np.sin(xx * 31.0 - yy * 101.0 - self.time * 1.3)
        )
        glints = (glint_noise > 0.985 - self.treble * 0.045) & (yy < 0.12)
        intensity[glints] = np.maximum(
            intensity[glints],
            0.55 + self.treble * 0.4,
        )
        highlight |= glints & (glint_noise > 0.995 - self.pulse * 0.02)

        # A beat creates the familiar overexposed horizontal lens flare.
        if self.pulse > 0.02:
            flare = np.exp(
                -((np.arange(pixel_h)[:, None] - horizon)
                  / (1.1 + self.pulse * 4.5)) ** 2
            )
            intensity = np.maximum(
                intensity,
                flare * self.pulse * 0.48,
            )

        intensity = np.clip(intensity, 0.0, 1.0)
        bayer = np.asarray(_BAYER, dtype=np.float32) / 15.0
        threshold = np.tile(
            bayer,
            ((pixel_h + 3) // 4, (pixel_w + 3) // 4),
        )[:pixel_h, :pixel_w]
        dots = intensity > (0.15 + threshold * 0.66)
        dots |= highlight
        return self._to_cells(
            dots,
            intensity,
            highlight,
            width,
            height,
        )

    def _draw_gel_towers(
        self,
        intensity,
        highlight,
        spectrum,
        horizon,
        level,
    ):
        """Draw rounded translucent pillars with short mirrored tails."""
        np = self._np
        pixel_h, pixel_w = intensity.shape
        bars = max(7, min(30, pixel_w // 4))
        positions = np.linspace(0, spectrum.size - 1, bars)
        energies = np.interp(positions, np.arange(spectrum.size), spectrum)
        spacing = pixel_w / bars

        for index, raw_energy in enumerate(energies):
            energy = self._clamp(raw_energy)
            centre = int((index + 0.5) * spacing)
            half = max(1, int(spacing * 0.31))
            height_px = max(
                3,
                int(
                    (0.10 + energy * 0.72 + self.bass * 0.12)
                    * max(4, horizon - 2)
                ),
            )
            top = max(1, horizon - height_px)
            left = max(0, centre - half)
            right = min(pixel_w, centre + half + 1)

            # Dim glass body, brighter chrome edges, and a rounded gel cap.
            body = 0.15 + energy * 0.46 + level * 0.10
            intensity[top:horizon, left:right] = np.maximum(
                intensity[top:horizon, left:right],
                body,
            )
            intensity[top:horizon, left:left + 1] = np.maximum(
                intensity[top:horizon, left:left + 1],
                0.58 + energy * 0.32,
            )
            intensity[top:horizon, max(left, right - 1):right] = np.maximum(
                intensity[top:horizon, max(left, right - 1):right],
                0.48 + energy * 0.28,
            )

            cap_y = min(pixel_h - 1, top)
            cap_radius = max(1, half)
            for offset_y in range(-cap_radius, cap_radius + 1):
                row = cap_y + offset_y
                if not 0 <= row < pixel_h:
                    continue
                span = int(
                    cap_radius
                    * math.sqrt(
                        max(
                            0.0,
                            1.0 - (offset_y / max(1, cap_radius)) ** 2,
                        )
                    )
                )
                cap_left = max(0, centre - span)
                cap_right = min(pixel_w, centre + span + 1)
                intensity[row, cap_left:cap_right] = np.maximum(
                    intensity[row, cap_left:cap_right],
                    0.34 + energy * 0.52,
                )

            if energy > 0.58:
                highlight[
                    max(0, cap_y - 1):min(pixel_h, cap_y + 1),
                    max(0, centre - 1):min(pixel_w, centre + 1),
                ] = True

            reflected = min(
                pixel_h,
                horizon + max(2, int(height_px * 0.27)),
            )
            if reflected > horizon:
                fade = np.linspace(
                    0.35 + energy * 0.34,
                    0.06,
                    reflected - horizon,
                    dtype=np.float32,
                )[:, None]
                intensity[horizon:reflected, left:right] = np.maximum(
                    intensity[horizon:reflected, left:right],
                    fade,
                )

    def _draw_cyber_grid(self, intensity, xx, yy):
        """A curved perspective floor converging beneath the cathedral."""
        np = self._np
        floor = np.clip((yy - 0.15) / 0.85, 0.0, 1.0)
        mask = floor > 0.0
        depth = 0.07 + floor
        vertical = np.exp(
            -(
                np.abs(np.sin((xx / depth) * math.pi * 1.35))
                / 0.085
            ) ** 2
        )
        horizontal = np.exp(
            -(
                np.abs(np.sin(6.0 / depth - self.time * 2.2))
                / 0.11
            ) ** 2
        )
        grid = np.maximum(vertical * 0.72, horizontal)
        grid *= mask * (0.12 + floor * 0.34)
        intensity[:] = np.maximum(intensity, grid)

    def _draw_waveform(
        self,
        intensity,
        highlight,
        features,
        horizon,
        level,
    ):
        np = self._np
        pixel_h, pixel_w = intensity.shape
        waveform = np.asarray(
            features.get("waveform", ()),
            dtype=np.float32,
        )
        if waveform.size < 2:
            waveform = np.sin(
                np.linspace(0.0, math.pi * 5.0, 64, dtype=np.float32)
                + self.time
            ) * 0.04

        xs = np.linspace(1, max(1, pixel_w - 2), waveform.size)
        xs = xs.astype(np.int32)
        amplitude = pixel_h * (0.035 + level * 0.095)
        ys = np.rint(
            horizon
            - np.clip(waveform, -1.0, 1.0) * amplitude
        ).astype(np.int32)
        ys = np.clip(ys, 0, pixel_h - 1)

        for index in range(len(xs) - 1):
            self._line(
                intensity,
                xs[index],
                ys[index],
                xs[index + 1],
                ys[index + 1],
                1.0,
            )
            self._line(
                highlight,
                xs[index],
                ys[index],
                xs[index + 1],
                ys[index + 1],
                True,
            )

    def _coordinates(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)
        if self._grid_key == key:
            return self._grid

        np = self._np
        x = np.linspace(-1.28, 1.28, pixel_w, dtype=np.float32)
        y = np.linspace(-0.94, 0.94, pixel_h, dtype=np.float32)
        self._grid = np.meshgrid(x, y)
        self._grid_key = key
        return self._grid

    def _line(self, target, x0, y0, x1, y1, value):
        np = self._np
        height, width = target.shape
        count = int(max(abs(x1 - x0), abs(y1 - y0))) + 2
        xs = np.linspace(x0, x1, count).astype(np.int32)
        ys = np.linspace(y0, y1, count).astype(np.int32)
        keep = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        target[ys[keep], xs[keep]] = value

    def _to_cells(
        self,
        dots,
        intensity,
        highlight,
        width,
        height,
    ):
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

        for y in range(height):
            row = []
            for x in range(width):
                packed = int(bits[y, x])
                if not packed:
                    row.append(None)
                    continue
                if bright[y, x]:
                    colour = top
                else:
                    colour = min(
                        max(0, top - 1),
                        max(0, int(strength[y, x] * top)),
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
