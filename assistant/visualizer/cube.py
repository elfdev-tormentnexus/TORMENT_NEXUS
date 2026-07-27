"""
Audio-reactive wireframe cube, rendered as braille pixels in the terminal.

A 3-axis rotating cube that drifts around the screen and bounces off the
edges, DVD-screensaver style, and comes apart under the music: bass
inflates it, mids spin it, treble shreds it.

Corruption is strictly pixel-based -- braille dot fields and solid block
glyphs. No letters, digits, or punctuation are ever used as "damage",
because those read as text that failed to render rather than as an image
breaking up, which is the opposite of the intended effect.

Rendering is braille (U+2800..U+28FF): every character cell carries a
2x4 dot matrix, so the effective resolution is eight times the terminal's
character grid.
"""

import math
import random


# Braille dot bit layout inside one cell:
#   1 4
#   2 5
#   3 6
#   7 8
_BRAILLE_WEIGHTS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)

CELL_W = 2
CELL_H = 4

# Solid-block material for heavy corruption. Deliberately pixel-like:
# fills and half-blocks, nothing that could be mistaken for a character.
_BLOCKS = ("░", "▒", "▓", "█", "▀", "▄", "▌", "▐")

_VERTICES = (
    (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
    (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
)

_EDGES = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
)


class CubeVisualizer:
    def __init__(self, palette):
        """palette: ordered dim -> bright ANSI colour strings."""
        self.palette = palette
        self.angle = [0.35, 0.6, 0.1]
        self.spin = [0.9, 1.3, 0.5]

        # Position and velocity in character cells. Velocity is in cells
        # per second so motion is frame-rate independent.
        self.x = 12.0
        self.y = 6.0
        self.vx = 11.0
        self.vy = 5.0

        self.flash = 0.0
        self.bounces = 0
        self._np = None

    # -- geometry --------------------------------------------------------

    @staticmethod
    def _rotate(point, angle):
        """Rotate about X, then Y, then Z -- the three axes, in order."""
        x, y, z = point
        ax, ay, az = angle

        cos, sin = math.cos(ax), math.sin(ax)
        y, z = y * cos - z * sin, y * sin + z * cos

        cos, sin = math.cos(ay), math.sin(ay)
        x, z = x * cos + z * sin, -x * sin + z * cos

        cos, sin = math.cos(az), math.sin(az)
        x, y = x * cos - y * sin, x * sin + y * cos

        return x, y, z

    def _project(self, point, scale_x, scale_y):
        x, y, z = point
        # Perspective divide. The camera sits back far enough that the
        # cube never turns inside out at the near corners.
        depth = 3.4
        factor = depth / (depth + z)
        return x * factor * scale_x, y * factor * scale_y

    # -- frame -----------------------------------------------------------

    def step(self, dt, features, width, height):
        """Advance rotation and DVD-style travel by dt seconds."""
        bass = features.get("bass", 0.0)
        mid = features.get("mid", 0.0)
        beat = features.get("beat", 0.0)

        # Mids drive spin, so busier passages visibly tumble faster.
        rate = 1.0 + mid * 2.2 + beat * 1.5

        for axis in range(3):
            self.angle[axis] += self.spin[axis] * rate * dt

        speed = 1.0 + bass * 0.8
        self.x += self.vx * speed * dt
        self.y += self.vy * speed * dt

        half_w = max(6.0, min(width, height * 2.2) * 0.18)
        half_h = half_w * 0.5

        if self.x - half_w < 0:
            self.x = half_w
            self.vx = abs(self.vx)
            self._bounce()
        elif self.x + half_w > width:
            self.x = width - half_w
            self.vx = -abs(self.vx)
            self._bounce()

        if self.y - half_h < 0:
            self.y = half_h
            self.vy = abs(self.vy)
            self._bounce()
        elif self.y + half_h > height:
            self.y = height - half_h
            self.vy = -abs(self.vy)
            self._bounce()

        self.flash = max(0.0, self.flash - dt * 2.4)

    def _bounce(self):
        self.bounces += 1
        self.flash = 1.0

    def render(self, width, height, features):
        """
        Returns rows of (char, colour) tuples, or None per cell where
        nothing should be drawn so the background shows through.
        """
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np

        bass = features.get("bass", 0.0)
        treble = features.get("treble", 0.0)
        level = features.get("level", 0.0)
        beat = features.get("beat", 0.0)

        pixel_w = max(8, width * CELL_W)
        pixel_h = max(8, height * CELL_H)
        buffer = np.zeros((pixel_h, pixel_w), dtype=bool)

        # Bass inflates the cube; level stretches it out of square. The
        # axes are driven separately so loud passages visibly deform it
        # rather than just scaling it up.
        base = min(pixel_w, pixel_h * 2) * 0.14
        scale_x = base * (1.0 + bass * 0.75 + level * 0.35)
        scale_y = base * 0.5 * (1.0 + level * 0.9 - bass * 0.2)

        centre_x = self.x * CELL_W
        centre_y = self.y * CELL_H

        points = [
            self._project(self._rotate(v, self.angle), scale_x, scale_y)
            for v in _VERTICES
        ]

        for a, b in _EDGES:
            x0, y0 = points[a]
            x1, y1 = points[b]
            self._line(
                buffer,
                centre_x + x0, centre_y + y0,
                centre_x + x1, centre_y + y1,
            )

        if treble > 0.05 or beat > 0.05:
            self._corrupt_pixels(buffer, treble, beat)

        return self._to_cells(buffer, width, height, bass, treble, beat, level)

    # -- drawing ---------------------------------------------------------

    def _line(self, buffer, x0, y0, x1, y1):
        np = self._np
        height, width = buffer.shape

        span = max(abs(x1 - x0), abs(y1 - y0))
        count = int(span) + 2

        if count < 2:
            return

        xs = np.linspace(x0, x1, count).astype(np.int32)
        ys = np.linspace(y0, y1, count).astype(np.int32)
        keep = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        buffer[ys[keep], xs[keep]] = True

    def _corrupt_pixels(self, buffer, treble, beat):
        """
        Tear the raster apart. Pixels only: rows slide sideways, dots drop
        out, and bands of the image smear downward. Nothing here inserts a
        glyph -- this stage operates purely on the dot field.
        """
        np = self._np
        height, width = buffer.shape

        # Horizontal row displacement -- the classic broken-scanline slip.
        shear_rows = int(height * min(0.5, treble * 0.55 + beat * 0.35))

        for _ in range(shear_rows):
            row = random.randrange(height)
            shift = random.randint(-6, 6) * max(1, int(1 + treble * 4))
            buffer[row] = np.roll(buffer[row], shift)

        # Dot dropout, strongest on transients.
        drop = treble * 0.18 + beat * 0.25

        if drop > 0.01:
            mask = np.random.random(buffer.shape) < drop
            buffer &= ~mask

        # Vertical smear: a band of the image bleeds down over itself.
        if beat > 0.4:
            top = random.randrange(0, max(1, height - 4))
            depth = random.randint(2, max(3, int(height * 0.12)))
            band = buffer[top:top + depth]

            if band.size:
                buffer[top:top + depth] |= np.roll(band, 1, axis=0)

    def _to_cells(self, buffer, width, height, bass, treble, beat, level):
        np = self._np
        pixel_h, pixel_w = buffer.shape

        rows = pixel_h // CELL_H
        cols = pixel_w // CELL_W
        trimmed = buffer[:rows * CELL_H, :cols * CELL_W]

        # Vectorised braille pack: fold the dot field into (row, 4, col, 2)
        # and weight each dot by its bit.
        grid = trimmed.reshape(rows, CELL_H, cols, CELL_W)
        weights = np.array(_BRAILLE_WEIGHTS, dtype=np.uint16)
        bits = (grid * weights[None, :, None, :]).sum(axis=(1, 3)).astype(np.int32)

        palette = self.palette
        top = len(palette) - 1

        # Intensity picks the palette entry; a bounce or a beat pushes the
        # whole cube brighter for a moment.
        heat = min(1.0, bass * 0.5 + level * 0.4 + beat * 0.6 + self.flash)
        base_index = int(round(heat * top))

        block_chance = beat * 0.22 + treble * 0.10

        out = []

        for row in range(min(rows, height)):
            line = []
            bit_row = bits[row]

            for col in range(min(cols, width)):
                value = int(bit_row[col])

                if not value:
                    line.append(None)
                    continue

                # Occasional solid-block fragments read as overexposed
                # raster cells. Still pixels, never text.
                if block_chance > 0 and random.random() < block_chance:
                    char = random.choice(_BLOCKS)
                    index = min(top, base_index + 1)
                else:
                    char = chr(0x2800 + value)
                    index = base_index

                    # Sparse cells sit dimmer, which gives the wireframe
                    # some depth instead of a flat single-colour outline.
                    if bin(value).count("1") <= 2:
                        index = max(0, index - 1)

                line.append((char, palette[index]))

            out.append(line)

        return out
