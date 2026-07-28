"""
Audio-reactive liquid-chrome reactor for the terminal visualizer.

The scene borrows from glossy Y2K interface art: a breathing bio-orb,
pearlescent highlights, atomic rings, tiny satellite flares, and faint
cellular circuitry suspended behind it.
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


class ReactorVisualizer:
    """A chrome bio-orb crossed by elastic, music-driven atom rings."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        # Wall-clock seconds for the slow anchor layer. Deliberately not
        # scaled by audio: a reference that speeds up with the music is
        # not a reference. See visualizer/anchor.py.
        self.slow = 0.0
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
        self.time += dt * (0.42 + self.mid * 1.85)
        self.slow += dt
        self.pulse = max(
            beat,
            self.pulse * math.exp(-dt * 4.25),
        )

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        pixel_w = width * CELL_W
        pixel_h = height * CELL_H
        xx, yy, radius, angle = self._coordinates(pixel_w, pixel_h)
        intensity = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        highlight = np.zeros((pixel_h, pixel_w), dtype=bool)

        # The slow layer, drawn first so everything else sits on top
        # of it. It moves on wall-clock time alone, which is what
        # gives the audio-driven motion above it a sense of speed.
        anchor.apply(
            np,
            intensity,
            anchor.rings(np, xx, yy, self.slow),
            strength=0.26,
            mid=self.mid,
        )

        level = self._clamp(features.get("level", 0.0))
        spectrum = np.asarray(
            features.get("spectrum", ()),
            dtype=np.float32,
        )
        if spectrum.size < 2:
            spectrum = np.zeros(48, dtype=np.float32)

        sector = (
            (angle + math.pi)
            / (2.0 * math.pi)
            * (spectrum.size - 1)
        )
        angular_energy = np.interp(
            sector.ravel(),
            np.arange(spectrum.size),
            spectrum,
        ).reshape(radius.shape)

        # A quiet circuit-cell texture keeps the black background alive.
        cells = np.abs(
            np.sin(xx * 8.0 + np.sin(yy * 5.0 + self.time * 0.35))
            * np.sin(yy * 9.0 - np.sin(xx * 4.0 - self.time * 0.25))
        )
        circuitry = np.exp(-((cells - 0.72) / 0.045) ** 2)
        outside = np.clip((radius - 0.52) / 0.32, 0.0, 1.0)
        intensity = np.maximum(
            intensity,
            circuitry * outside * (0.055 + self.treble * 0.075),
        )

        # The shell is not a perfect circle: it folds like a liquid chrome
        # logo, with each angular slice responding to a spectrum band.
        shell_target = (
            0.49
            + self.bass * 0.055
            + self.pulse * 0.035
            + np.sin(angle * 5.0 + self.time * 1.5) * 0.045
            + np.sin(angle * 9.0 - self.time * 0.8) * 0.022
            + angular_energy * 0.045
        )
        shell_distance = np.abs(radius - shell_target)
        shell = np.exp(
            -(shell_distance / (0.018 + self.treble * 0.014)) ** 2
        )
        shell_glow = np.exp(
            -(shell_distance / (0.075 + self.pulse * 0.018)) ** 2
        )
        intensity = np.maximum(
            intensity,
            shell_glow * (0.10 + level * 0.20),
        )
        intensity = np.maximum(
            intensity,
            shell * (0.48 + angular_energy * 0.45),
        )

        inside = radius < shell_target
        gel = (
            0.09
            + 0.16
            * (
                np.sin(
                    radius * 18.0
                    - angle * 3.0
                    - self.time * 2.6
                )
                + 1.0
            )
            * 0.5
        )
        gel += angular_energy * 0.16
        intensity[inside] = np.maximum(
            intensity[inside],
            gel[inside],
        )

        # Chrome needs an asymmetric white reflection, not even shading.
        specular = np.exp(
            -(
                ((xx + 0.20) / 0.16) ** 2
                + ((yy + 0.22) / 0.085) ** 2
            )
        )
        specular += np.exp(
            -(
                ((xx - 0.19) / 0.07) ** 2
                + ((yy - 0.25) / 0.15) ** 2
            )
        ) * 0.70
        specular *= inside
        intensity = np.maximum(intensity, specular)
        highlight |= specular > 0.64

        # Interference petals turn the centre into a bio-digital iris.
        petals = np.exp(
            -(
                np.abs(
                    np.sin(
                        angle * (3.0 + self.treble * 2.0)
                        + radius * 9.0
                        - self.time * 2.7
                    )
                )
                / (0.09 + self.mid * 0.08)
            ) ** 2
        )
        petal_envelope = np.clip((0.47 - radius) / 0.30, 0.0, 1.0)
        intensity = np.maximum(
            intensity,
            petals * petal_envelope * (0.20 + self.mid * 0.48),
        )

        # Three differently tilted orbitals create the atomic-logo silhouette.
        orbit_a = self._orbit(xx, yy, 0.28 + self.time * 0.08, 0.78, 0.23)
        orbit_b = self._orbit(xx, yy, -0.58 - self.time * 0.05, 0.82, 0.20)
        orbit_c = self._orbit(xx, yy, 1.18 + self.time * 0.04, 0.74, 0.18)
        orbits = np.maximum(orbit_a, np.maximum(orbit_b, orbit_c))
        intensity = np.maximum(
            intensity,
            orbits * (0.26 + self.mid * 0.34 + self.pulse * 0.22),
        )

        # Bright beads travel around the orbit paths like tiny lens flares.
        bead_phase = np.cos(angle * 4.0 - self.time * 3.1)
        beads = (
            (orbits > 0.56)
            & (bead_phase > 0.965 - self.treble * 0.035)
        )
        intensity[beads] = 1.0
        highlight |= beads

        # A small pearl in the centre anchors the otherwise fluid shape.
        pearl_radius = 0.075 + self.bass * 0.035 + self.pulse * 0.025
        pearl = np.exp(-(radius / max(0.025, pearl_radius)) ** 3)
        intensity = np.maximum(
            intensity,
            pearl * (0.62 + level * 0.38),
        )
        highlight |= pearl > 0.72

        # Beat-synchronised horizontal and vertical flare: classic glossy
        # software-box art, but sparse enough not to flatten the scene.
        if self.pulse > 0.025:
            flare_x = np.exp(
                -(np.abs(xx) / (0.012 + self.pulse * 0.018)) ** 2
            )
            flare_y = np.exp(
                -(np.abs(yy) / (0.009 + self.pulse * 0.012)) ** 2
            )
            flare = np.maximum(
                flare_x * 0.58,
                flare_y,
            )
            flare *= np.clip((0.92 - radius) / 0.38, 0.0, 1.0)
            intensity = np.maximum(
                intensity,
                flare * self.pulse * 0.72,
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

    def _orbit(self, xx, yy, rotation, major, minor):
        np = self._np
        cosine = math.cos(rotation)
        sine = math.sin(rotation)
        rotated_x = xx * cosine - yy * sine
        rotated_y = xx * sine + yy * cosine
        distance = np.sqrt(
            (rotated_x / major) ** 2
            + (rotated_y / minor) ** 2
        )
        return np.exp(
            -(np.abs(distance - 1.0) / (0.022 + self.treble * 0.012)) ** 2
        )

    def _coordinates(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)
        if self._grid_key == key:
            return self._grid

        np = self._np
        x = np.linspace(-1.32, 1.32, pixel_w, dtype=np.float32)
        y = np.linspace(-0.86, 0.86, pixel_h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        radial_x = xx * 0.74
        radial_y = yy * 1.10
        radius = np.sqrt(radial_x ** 2 + radial_y ** 2)
        angle = np.arctan2(radial_y, radial_x)
        self._grid = (xx, yy, radius, angle)
        self._grid_key = key
        return self._grid

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
