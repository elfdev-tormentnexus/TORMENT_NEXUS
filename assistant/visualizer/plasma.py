"""
Liquid plasma field for the terminal visualizer.

Every other scene in this folder is built from hard edges -- tunnel rings,
equalizer towers, orbital traces, cube facets. This one is deliberately the
opposite: soft metaball blobs that swell, drift and merge, so the rotation
has something that breathes between the sharper scenes.

The blobs are a genuine metaball field rather than drawn circles. Each one
contributes an inverse-square falloff to a shared surface, and the surface
is squashed into view range afterwards, which is what makes two blobs bulge
toward each other and fuse as they pass instead of simply overlapping.
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

# Enough blobs to keep the field busy, few enough that the whole thing does
# not saturate into one shapeless bright mass.
_BLOBS = 6

# Softening term in the falloff. Without it a blob centre divides by zero
# and the surface blows out to a single hard dot.
_SOFTEN = 0.006

# Where the blob surface is considered to start, and where its surrounding
# glow fades in. Both are cuts through the same summed field.
_SURFACE_LEVEL = 0.46
_HALO_LEVEL = 0.30


class PlasmaVisualizer:
    """Merging metaball blobs over a slow interference wash."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.drift = 0.0
        self.pulse = 0.0
        self.ripple = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self._np = None
        self._grid_key = None
        self._grid = None

    def step(self, dt, features, _width, _height):
        dt = max(0.0, float(dt))
        response = min(1.0, dt * 6.0)
        bass = self._clamp(features.get("bass", 0.0))
        mid = self._clamp(features.get("mid", 0.0))
        treble = self._clamp(features.get("treble", 0.0))
        beat = self._clamp(features.get("beat", 0.0))

        self.bass += (bass - self.bass) * response
        self.mid += (mid - self.mid) * response
        self.treble += (treble - self.treble) * response

        # A clear rise over the decaying envelope is a new transient, so the
        # shock ring restarts from the centre. The margin matters: a loud
        # sustained passage holds beat high every frame, and testing against
        # the envelope alone would retrigger continuously and pin the ring
        # at radius zero instead of ever letting it travel.
        decayed = self.pulse * math.exp(-dt * 3.2)
        if beat > decayed * 1.15 + 0.05:
            self.ripple = 0.0
        self.pulse = max(beat, decayed)

        self.time += dt * (0.32 + self.mid * 1.10)
        self.drift += dt * (0.20 + self.bass * 0.72)
        self.ripple += dt * (0.85 + self.pulse * 1.35)

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

        field = np.zeros((pixel_h, pixel_w), dtype=np.float32)

        for index in range(_BLOBS):
            phase = self.drift + index * 1.71
            centre_x = math.sin(phase * (0.70 + index * 0.11)) * 0.86
            centre_y = math.cos(phase * (0.53 + index * 0.09)) * 0.64
            size = (
                0.21
                + self.bass * 0.15
                + 0.045 * math.sin(self.time * 1.3 + index * 2.1)
            )
            distance = (xx - centre_x) ** 2 + (yy - centre_y) ** 2
            field += (size * size) / (distance + _SOFTEN)

        # The raw field is unbounded near a centre, so fold it into 0..1.
        # This is also what gives the blobs their soft shoulders.
        surface = field / (1.0 + field)

        # Six overlapping falloffs never actually reach zero, so drawing the
        # surface directly floods the whole viewport. Cutting at an
        # isosurface is what makes these blobs with empty space around them
        # rather than one continuous gradient.
        body = np.clip(
            (surface - _SURFACE_LEVEL) / (1.0 - _SURFACE_LEVEL),
            0.0,
            1.0,
        )
        halo = np.clip((surface - _HALO_LEVEL) / 0.16, 0.0, 1.0)

        wash = (
            np.sin(xx * 3.1 + self.time * 1.3)
            + np.sin(yy * 2.7 - self.time * 0.9)
            + np.sin((xx + yy) * 2.2 + self.time * 0.6)
            + np.sin(np.sqrt(xx * xx + yy * yy) * 5.0 - self.time * 1.7)
        ) * 0.25

        # The interference wash rides on the blobs instead of the whole
        # frame, so it reads as motion within the liquid.
        intensity = (
            body * (0.56 + level * 0.36)
            + halo * (0.5 + 0.5 * wash) * (0.16 + self.treble * 0.22)
        )

        if self.pulse > 0.02:
            radius = np.sqrt(xx * xx + yy * yy)
            ring = np.exp(
                -(
                    np.abs(radius - self.ripple)
                    / (0.05 + self.pulse * 0.055)
                ) ** 2
            )
            intensity = intensity + ring * self.pulse * 0.55

        intensity = np.clip(intensity, 0.0, 1.0)

        # The hot cores are the one hard feature the scene keeps, so they
        # read as molten rather than as a uniformly lit blob.
        highlight = surface > (0.80 - self.pulse * 0.08)

        bayer = np.asarray(_BAYER, dtype=np.float32) / 15.0
        threshold = np.tile(
            bayer,
            ((pixel_h + 3) // 4, (pixel_w + 3) // 4),
        )[:pixel_h, :pixel_w]
        dots = intensity > (0.16 + threshold * 0.60)
        dots |= highlight

        return self._to_cells(dots, intensity, highlight, width, height)

    def _coordinates(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)

        if self._grid_key == key:
            return self._grid

        np = self._np
        x = np.linspace(-1.30, 1.30, pixel_w, dtype=np.float32)
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
