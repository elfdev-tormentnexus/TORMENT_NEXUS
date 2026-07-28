"""
Audio-reactive cyber-dream cube rendered with terminal braille pixels.

The moving cube remains a nod to old screensavers, but the scene now has
the visual language around it that makes that reference land: recursive
chrome geometry, spectral afterimages, a warped wireframe floor, orbital
glints, and controlled scanline corruption on treble hits.
"""

import math


CELL_W = 2
CELL_H = 4

# How far a unit cube's furthest vertex reaches, as a multiple of the
# projection scale, taken over the whole rotation space. Measured rather
# than derived: the perspective factor depth/(depth + z) is part of it, so
# the reach is not simply the sqrt(3) of the cube's own diagonal.
PROJECTION_REACH = 2.0
_BRAILLE_WEIGHTS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)

_VERTICES = (
    (-1, -1, -1),
    (1, -1, -1),
    (1, 1, -1),
    (-1, 1, -1),
    (-1, -1, 1),
    (1, -1, 1),
    (1, 1, 1),
    (-1, 1, 1),
)

_EDGES = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
)

# All are single-cell pixel glyphs. High transients can briefly replace a
# dense braille cell with one of these overexposed fragments.
_BLOCKS = ("░", "▒", "▓", "█", "▀", "▄", "▌", "▐")


class CubeVisualizer:
    """A recursive chrome cube drifting through a warped cyberspace grid."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.angle = [0.35, 0.60, 0.10]
        self.spin = [0.72, 1.08, 0.42]
        self.x = 12.0
        self.y = 6.0
        self.vx = 8.5
        self.vy = 3.8
        self.time = 0.0
        self.flash = 0.0
        self.pulse = 0.0
        self.bounces = 0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self._np = None

    @staticmethod
    def _rotate(point, angle):
        x, y, z = point
        ax, ay, az = angle

        cosine, sine = math.cos(ax), math.sin(ax)
        y, z = y * cosine - z * sine, y * sine + z * cosine

        cosine, sine = math.cos(ay), math.sin(ay)
        x, z = x * cosine + z * sine, -x * sine + z * cosine

        cosine, sine = math.cos(az), math.sin(az)
        x, y = x * cosine - y * sine, x * sine + y * cosine
        return x, y, z

    @staticmethod
    def _project(point, scale_x, scale_y):
        x, y, z = point
        depth = 3.55
        factor = depth / (depth + z)
        return x * factor * scale_x, y * factor * scale_y

    def step(self, dt, features, width, height):
        """Advance the object with smooth music-driven rotation and travel."""
        dt = max(0.0, float(dt))
        response = min(1.0, dt * 7.0)
        bass = self._clamp(features.get("bass", 0.0))
        mid = self._clamp(features.get("mid", 0.0))
        treble = self._clamp(features.get("treble", 0.0))
        beat = self._clamp(features.get("beat", 0.0))
        level = self._clamp(features.get("level", 0.0))

        self.bass += (bass - self.bass) * response
        self.mid += (mid - self.mid) * response
        self.treble += (treble - self.treble) * response
        self.pulse = max(beat, self.pulse * math.exp(-dt * 4.2))
        self.time += dt * (0.58 + self.mid * 1.55)

        rate = 0.72 + self.mid * 1.8 + self.pulse * 0.75
        for axis in range(3):
            self.angle[axis] += self.spin[axis] * rate * dt

        width = max(1, int(width))
        height = max(1, int(height))
        half_w, half_h = self._half_extents(width, height, level)

        if width <= half_w * 2.0:
            self.x = width * 0.5
        else:
            self.x += self.vx * (0.62 + self.bass * 0.55) * dt
            if self.x - half_w < 0:
                self.x = half_w
                self.vx = abs(self.vx)
                self._bounce()
            elif self.x + half_w > width:
                self.x = width - half_w
                self.vx = -abs(self.vx)
                self._bounce()

        if height <= half_h * 2.0:
            self.y = height * 0.42
        else:
            self.y += self.vy * (0.68 + self.bass * 0.42) * dt
            if self.y - half_h < 0:
                self.y = half_h
                self.vy = abs(self.vy)
                self._bounce()
            elif self.y + half_h > height:
                self.y = height - half_h
                self.vy = -abs(self.vy)
                self._bounce()

        self.flash = max(0.0, self.flash - dt * 2.2)

    def _scales(self, width, height, level):
        """The projection scales render() will use, from the same numbers."""
        pixel_w = max(1, int(width)) * CELL_W
        pixel_h = max(1, int(height)) * CELL_H
        base = max(1.5, min(pixel_w, pixel_h * 2.0) * 0.145)

        return (
            base * (1.0 + self.bass * 0.58 + level * 0.20),
            base * 0.50 * (1.0 + level * 0.58 - self.bass * 0.10),
        )

    def _half_extents(self, width, height, level):
        """
        How far the drawn cube actually reaches, in cells.

        The bounce box used to be its own invention -- fractions of the
        terminal size with no relation to the projection -- while the shape
        was sized in pixels by an unrelated formula that also grows with
        bass and level. The cube therefore turned around when its CENTRE
        came within about 40 pixels of the edge while the shape itself
        reached two to four times that, and _line() clips out-of-bounds
        pixels silently, so it slid off the screen rather than complaining.
        """
        scale_x, scale_y = self._scales(width, height, level)

        half_w = scale_x * PROJECTION_REACH / CELL_W
        half_h = scale_y * PROJECTION_REACH / CELL_H

        # Never claim more than this much of the field. At once-maximal bass
        # and level the cube is genuinely wider than the terminal, and an
        # honest box would leave it nowhere to travel and freeze it
        # mid-screen. It clips a little there instead, and keeps moving.
        return (
            max(2.0, min(half_w, width * 0.45)),
            max(1.0, min(half_h, height * 0.45)),
        )

    def _bounce(self):
        self.bounces += 1
        self.flash = 1.0

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        pixel_w = width * CELL_W
        pixel_h = height * CELL_H
        intensity = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        highlight = np.zeros((pixel_h, pixel_w), dtype=bool)
        level = self._clamp(features.get("level", 0.0))

        self._draw_starfield(intensity)
        self._draw_grid(intensity)

        centre_x = min(pixel_w - 1, max(0, int(self.x * CELL_W)))
        centre_y = min(pixel_h - 1, max(0, int(self.y * CELL_H)))
        # Shared with the bounce box in step(), which is the whole point:
        # the two were separate formulas and disagreed by a factor of four.
        scale_x, scale_y = self._scales(width, height, level)

        # Two restrained afterimages turn movement into a translucent trail
        # instead of a single screensaver object crossing an empty field.
        speed = max(1.0, math.hypot(self.vx, self.vy))
        trail_x = self.vx / speed
        trail_y = self.vy / speed
        for distance, strength in ((9.0, 0.14), (4.5, 0.24)):
            self._draw_cube(
                intensity,
                highlight,
                centre_x - trail_x * distance,
                centre_y - trail_y * distance * 1.4,
                scale_x,
                scale_y,
                tuple(value - distance * 0.006 for value in self.angle),
                strength,
                False,
            )

        # Nested frames resemble a chrome software logo opening inward.
        self._draw_cube(
            intensity,
            highlight,
            centre_x,
            centre_y,
            scale_x,
            scale_y,
            tuple(self.angle),
            0.72 + level * 0.22,
            True,
        )
        self._draw_cube(
            intensity,
            highlight,
            centre_x,
            centre_y,
            scale_x * 0.55,
            scale_y * 0.55,
            (
                -self.angle[1],
                self.angle[2] + self.time * 0.35,
                self.angle[0],
            ),
            0.46 + self.mid * 0.30,
            self.pulse > 0.35,
        )

        self._draw_orbit(
            intensity,
            highlight,
            centre_x,
            centre_y,
            scale_x * 1.55,
            scale_y * 1.18,
        )
        self._apply_scanline_bend(intensity, highlight)

        intensity = np.clip(intensity, 0.0, 1.0)
        return self._to_cells(
            intensity,
            highlight,
            width,
            height,
        )

    def _draw_starfield(self, intensity):
        """Sparse deterministic pixels drift like a synthetic star field."""
        np = self._np
        pixel_h, pixel_w = intensity.shape
        yy, xx = np.indices((pixel_h, pixel_w), dtype=np.float32)
        field = (
            np.sin(xx * 37.7 + yy * 73.1 + self.time * 1.7)
            * np.sin(xx * 91.3 - yy * 29.9 - self.time)
        )
        stars = field > 0.992 - self.treble * 0.025
        intensity[stars] = np.maximum(
            intensity[stars],
            0.28 + self.treble * 0.34,
        )

    def _draw_grid(self, intensity):
        """Warped perspective wireframe floor with a low vanishing point."""
        np = self._np
        pixel_h, pixel_w = intensity.shape
        x = np.linspace(-1.2, 1.2, pixel_w, dtype=np.float32)
        y = np.linspace(-0.9, 0.9, pixel_h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        floor = np.clip((yy - 0.12) / 0.78, 0.0, 1.0)
        depth = floor + 0.06
        wobble = np.sin(self.time * 0.7 + yy * 4.0) * 0.045
        vertical = np.exp(
            -(
                np.abs(
                    np.sin(((xx + wobble) / depth) * math.pi * 1.4)
                )
                / 0.075
            ) ** 2
        )
        horizontal = np.exp(
            -(
                np.abs(np.sin(5.4 / depth - self.time * 1.9))
                / 0.095
            ) ** 2
        )
        grid = np.maximum(vertical * 0.64, horizontal)
        grid *= (floor > 0.0) * (0.09 + floor * 0.31)
        intensity[:] = np.maximum(intensity, grid)

    def _draw_cube(
        self,
        intensity,
        highlight,
        centre_x,
        centre_y,
        scale_x,
        scale_y,
        angle,
        strength,
        bright_vertices,
    ):
        points = [
            self._project(self._rotate(vertex, angle), scale_x, scale_y)
            for vertex in _VERTICES
        ]

        for start, end in _EDGES:
            x0, y0 = points[start]
            x1, y1 = points[end]
            self._line(
                intensity,
                centre_x + x0,
                centre_y + y0,
                centre_x + x1,
                centre_y + y1,
                strength,
            )

        if bright_vertices:
            height, width = highlight.shape
            for point_x, point_y in points:
                x = int(round(centre_x + point_x))
                y = int(round(centre_y + point_y))
                if 0 <= x < width and 0 <= y < height:
                    highlight[y, x] = True
                    intensity[y, x] = 1.0

    def _draw_orbit(
        self,
        intensity,
        highlight,
        centre_x,
        centre_y,
        radius_x,
        radius_y,
    ):
        np = self._np
        samples = max(32, int(radius_x * 5.0))
        phase = np.linspace(0.0, math.tau, samples, dtype=np.float32)
        tilt = self.angle[2] * 0.45
        local_x = np.cos(phase) * radius_x
        local_y = np.sin(phase) * radius_y
        cosine = math.cos(tilt)
        sine = math.sin(tilt)
        xs = centre_x + local_x * cosine - local_y * sine
        ys = centre_y + local_x * sine * 0.45 + local_y * cosine

        for index in range(samples - 1):
            self._line(
                intensity,
                xs[index],
                ys[index],
                xs[index + 1],
                ys[index + 1],
                0.28 + self.mid * 0.30,
            )

        for offset in (0.0, math.pi):
            bead_phase = self.time * (1.4 + self.treble) + offset
            local_x = math.cos(bead_phase) * radius_x
            local_y = math.sin(bead_phase) * radius_y
            x = int(round(
                centre_x + local_x * cosine - local_y * sine
            ))
            y = int(round(
                centre_y + local_x * sine * 0.45 + local_y * cosine
            ))
            if 0 <= y < intensity.shape[0] and 0 <= x < intensity.shape[1]:
                intensity[y, x] = 1.0
                highlight[y, x] = True

    def _apply_scanline_bend(self, intensity, highlight):
        """Treble bends selected raster lines; beats briefly smear them."""
        np = self._np
        height, _width = intensity.shape
        bends = int(height * (self.treble * 0.08 + self.pulse * 0.05))

        for index in range(bends):
            row = int(
                (self.time * 17.0 + index * 13.0)
                % max(1, height)
            )
            direction = -1 if index % 2 else 1
            shift = direction * max(
                1,
                int(1 + self.treble * 4.0),
            )
            intensity[row] = np.roll(intensity[row], shift)
            highlight[row] = np.roll(highlight[row], shift)

        if self.pulse > 0.45 and height > 2:
            row = int(self.time * 11.0) % (height - 1)
            intensity[row + 1] = np.maximum(
                intensity[row + 1],
                intensity[row] * self.pulse * 0.72,
            )

    def _line(self, target, x0, y0, x1, y1, value):
        np = self._np
        height, width = target.shape
        count = int(max(abs(x1 - x0), abs(y1 - y0))) + 2
        if count < 2:
            return
        xs = np.linspace(x0, x1, count).astype(np.int32)
        ys = np.linspace(y0, y1, count).astype(np.int32)
        keep = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        target[ys[keep], xs[keep]] = np.maximum(
            target[ys[keep], xs[keep]],
            value,
        )

    def _to_cells(self, intensity, highlight, width, height):
        np = self._np
        threshold = 0.16
        dots = intensity > threshold
        dots |= highlight
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

                cell_strength = float(strength[y, x])
                if (
                    self.pulse > 0.55
                    and cell_strength > 0.72
                    and (x + y + int(self.time * 10.0)) % 11 == 0
                ):
                    glyph = _BLOCKS[(x * 3 + y) % len(_BLOCKS)]
                else:
                    glyph = chr(0x2800 + packed)

                if bright[y, x]:
                    colour = top
                else:
                    colour = min(
                        max(0, top - 1),
                        max(0, int(cell_strength * top)),
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
