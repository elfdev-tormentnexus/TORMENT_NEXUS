"""Render the project logo: SABLE, recovered from a vector projection.

The mark is the system's retrieval space, not a picture of one, and the
word is not painted on. Each glyph pixel becomes a high-dimensional vector
whose position is carried by two fixed orthonormal directions; the same
project() the panel runs at runtime finds those directions as the leading
principal components and the letterforms fall out of the flattening. Change
the seed and the noise moves, but the word is what the geometry actually
contains.

A sparse cloud shares the frame with more of its magnitude off that plane.
project() reports how much of each vector survived flattening as fidelity,
so those points come out dim without being told to -- the word resolves out
of a haze that is genuinely less well represented, which is the panel's own
semantics rather than a drop shadow.

Seeded, so an identical rebuild produces an identical PNG. Synthetic, so no
part of the maintainer's real memory geometry reaches a public image; the
release builder refuses to ship that file and a logo is not an exception.

The smiley stays the launcher and shortcut icon. It is a good application
icon and a poor page header.

No Pillow. This tree has stayed stdlib and a logo is not a reason to change
that.
"""

import colorsys
import math
import os
import random
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "assistant"))

from ui import vector_panel  # noqa: E402

ASSETS = os.path.join(ROOT, "assets")
SEED = 20260728
DIM = 48

LIGHT = (255, 255, 255)
DARK = (13, 17, 23)
MIN_CONTRAST = 3.0

# 5x7. Hand-set rather than loaded, because a font file would be a
# dependency and a licence question for five letters.
GLYPHS = {
    "S": ("01110", "10001", "10000", "01110", "00001", "10001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
}
WORD = "SABLE"
GAP = 1

# How far the haze reaches past the wordmark, as a multiple of its extent.
# The lattice is sized from this so a glyph pixel lands on close to one
# cell: below that the letters turn to blobs, and the whole point of the
# mark is that the projection resolves into something readable.
HAZE_EXTENT = 1.32
GLYPH_COLS = len(WORD) * 5 + (len(WORD) - 1) * GAP
GLYPH_ROWS = 7

# Per-dimension off-plane noise. This number is load-bearing and the first
# two attempts got it wrong in a way worth recording: at 0.62 across 48
# dimensions the off-plane variance is about 48 x 0.62^2 = 18.4, while the
# planted in-plane variance is about 0.67. Principal components follow
# variance, so project() found the noise and the wordmark never survived
# the flattening -- the render came out as an unreadable blob twice.
#
# The plane has to dominate the covariance for the letters to be what the
# projection recovers. At 0.05 the off-plane variance is about 0.12,
# comfortably under the signal.
NOISE = 0.05


# ============================================================
# PNG
# ============================================================

def _chunk(kind, body):
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    )


def write_png(path, width, height, pixels):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for r, g, b, a in pixels[y * width:(y + 1) * width]:
            raw += bytes((r, g, b, a))

    body = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as handle:
        handle.write(body)
    return len(body)


# ============================================================
# COLOUR
# ============================================================

def _lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# Solving contrast >= 3.0 against both backgrounds gives a luminance band,
# not a brightness preference:
#
#   vs white   (1.05) / (L + 0.05) >= 3   ->  L <= 0.300
#   vs #0d1117 (L + 0.05) / 0.0606 >= 3   ->  L >= 0.132
#
# Everything legible on both themes lives between those two numbers. The
# first attempt at this picked HSV values by eye and produced haze at
# 1.70:1 on dark -- the band is narrow enough that guessing does not reach
# it, and narrow enough that hue changes alone can leave it.
SAFE_MIN_LUM = 0.132
SAFE_MAX_LUM = 0.300


def _at_luminance(hue, sat, target):
    """The lightest-to-darkest scaling of one hue that hits a luminance."""
    low, high = 0.0, 1.0
    for _ in range(40):
        mid = (low + high) / 2
        r, g, b = colorsys.hsv_to_rgb(hue % 1.0, sat, mid)
        if _lum((r * 255, g * 255, b * 255)) < target:
            low = mid
        else:
            high = mid

    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, sat, (low + high) / 2)
    return int(r * 255), int(g * 255), int(b * 255)


def _dual_safe(hue, weight):
    """
    A colour clearing 3:1 on white and on GitHub's dark, both.

    The panel's palette is chosen against a terminal, which is always dark,
    so its bright end runs to white and vanishes on a light page. Rather
    than pick a value and hope, this solves for a luminance inside the band
    where both backgrounds are satisfied, and lets weight move the point
    within that band. Saturation carries the rest of the separation, since
    it is free at fixed luminance.
    """
    span = SAFE_MAX_LUM - SAFE_MIN_LUM
    # A margin inside each edge: anti-aliasing and PNG rounding should not
    # be what pushes a cell across the floor.
    target = SAFE_MIN_LUM + 0.10 * span + weight * 0.80 * span
    sat = 0.55 + 0.35 * weight
    return _at_luminance(hue, sat, target)


# ============================================================
# GEOMETRY
# ============================================================

def _word_points():
    """Glyph pixels as (x, y) in 0..1, y up."""
    width = len(WORD) * 5 + (len(WORD) - 1) * GAP
    height = 7
    points = []

    cursor = 0
    for letter in WORD:
        rows = GLYPHS[letter]
        for row_index, row in enumerate(rows):
            for col_index, cell in enumerate(row):
                if cell == "1":
                    x = (cursor + col_index + 0.5) / width
                    y = 1.0 - (row_index + 0.5) / height
                    points.append((x, y))
        cursor += 5 + GAP

    return points


def _orthonormal_pair(rng):
    a = [rng.gauss(0, 1) for _ in range(DIM)]
    b = [rng.gauss(0, 1) for _ in range(DIM)]
    a = vector_panel._unit(a)
    overlap = vector_panel._dot(b, a)
    b = vector_panel._unit([b[i] - overlap * a[i] for i in range(DIM)])
    return a, b


def _vectors(haze):
    """
    Build vectors whose leading components carry the wordmark.

    In-plane spread is large and off-plane noise small for glyph points, so
    the two planted directions dominate the covariance and project() finds
    them. Haze points sit in the same frame with far more of their length
    off that plane, which is what makes them arrive with low fidelity.
    """
    rng = random.Random(SEED)
    axis_x, axis_y = _orthonormal_pair(rng)

    vectors = []
    kinds = []

    for x, y in _word_points():
        # Centre so the planted directions carry variance, not mean offset.
        sx = (x - 0.5) * 2.0
        sy = (y - 0.5) * 2.0
        vector = [
            sx * axis_x[i] + sy * axis_y[i] + rng.gauss(0, NOISE)
            for i in range(DIM)
        ]
        vectors.append(vector)
        kinds.append("word")

    for _ in range(haze):
        # Kept close to the word's own extent. project() normalises each
        # axis over every point, so haze reaching further than the glyphs
        # does not surround the word -- it shrinks it, which is what the
        # first render did.
        sx = rng.uniform(-HAZE_EXTENT, HAZE_EXTENT)
        sy = rng.uniform(-HAZE_EXTENT, HAZE_EXTENT)
        vector = [
            sx * axis_x[i] + sy * axis_y[i] + rng.gauss(0, NOISE)
            for i in range(DIM)
        ]
        vectors.append(vector)
        kinds.append("haze")

    return vectors, kinds


# ============================================================
# RENDER
# ============================================================

def render(width, height, haze):
    vectors, kinds = _vectors(haze)
    coords, _ = vector_panel.project(vectors)

    # Size the lattice from the geometry rather than from a chosen pixel
    # count, so one glyph pixel is one cell whatever the output size is.
    cols = int(round(GLYPH_COLS * HAZE_EXTENT))
    rows = int(round(GLYPH_ROWS * HAZE_EXTENT))
    cell = min(width // (cols + 2), height // (rows + 2))
    margin_x = (width - cols * cell) // 2
    margin_y = (height - rows * cell) // 2

    pixels = [(0, 0, 0, 0)] * (width * height)

    grid = {}
    for (x, y, _hue, fidelity), kind in zip(coords, kinds):
        cx = min(cols - 1, max(0, int(x * cols)))
        cy = min(rows - 1, max(0, int((1.0 - y) * rows)))
        slot = grid.setdefault((cx, cy), {"word": False, "fid": 0.0, "n": 0})
        slot["word"] = slot["word"] or kind == "word"
        slot["fid"] += fidelity
        slot["n"] += 1

    drawn = []
    for (cx, cy), slot in grid.items():
        fidelity = slot["fid"] / slot["n"]
        if slot["word"]:
            hue, weight = 0.88, min(1.0, fidelity)
        else:
            # Haze keeps its distance in hue as well as in brightness, so
            # the word reads first even in a single-colour reproduction.
            hue, weight = 0.74, min(1.0, fidelity) * 0.45

        colour = _dual_safe(hue, weight)
        drawn.append(colour)

        # Haze draws as a smaller dot in the same cell. Equal-sized cells
        # made the word compete with its own background for attention.
        inset = 1 if slot["word"] else max(1, cell // 3)
        size = cell - 2 * inset + 1

        x0 = margin_x + cx * cell + inset
        y0 = margin_y + cy * cell + inset
        for dy in range(max(1, size)):
            row = (y0 + dy) * width
            for dx in range(max(1, size)):
                index = row + x0 + dx
                if 0 <= index < len(pixels):
                    pixels[index] = colour + (255,)

    return pixels, drawn


def _report(name, drawn):
    worst_light = min(contrast(c, LIGHT) for c in drawn)
    worst_dark = min(contrast(c, DARK) for c in drawn)
    print(f"  cells drawn      {len(drawn)}")
    print(f"  worst vs light   {worst_light:.2f}:1")
    print(f"  worst vs dark    {worst_dark:.2f}:1")
    ok = worst_light >= MIN_CONTRAST and worst_dark >= MIN_CONTRAST
    print(f"  clears {MIN_CONTRAST}:1 both  {'YES' if ok else 'NO'}")
    if not ok:
        raise SystemExit(
            f"{name}: palette fails the dual-theme floor -- widen the band "
            "in _dual_safe rather than shipping a mark that disappears"
        )


def build():
    if not os.path.isdir(ASSETS):
        raise SystemExit(f"missing {ASSETS}")

    targets = [
        ("logo_sable.png", 1160, 320, 150),
        ("logo_sable_small.png", 580, 160, 150),
        ("social_preview.png", 1280, 640, 150),
    ]

    for name, w, h, haze in targets:
        pixels, drawn = render(w, h, haze)
        path = os.path.join(ASSETS, name)
        size = write_png(path, w, h, pixels)
        print(f"wrote {path}")
        print(f"  {w}x{h}, {size} bytes")
        _report(name, drawn)
        print()


if __name__ == "__main__":
    build()
