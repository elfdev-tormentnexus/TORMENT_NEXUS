"""
Renders the inverted-colour icon that marks an interface-mode window.

Interface mode opens a listening socket and an authentication boundary, so
the operator needs to be able to tell at a glance which window it is. The
shape stays identical -- the same idle face as the normal icon, taken from
the same code in ui.py -- and only the two colours swap: dark face on a
light field instead of light face on a dark one. Same system, visibly
different state, which is what an inverted icon should say.

Unlike tools/generate_icon.py this uses no Pillow. The face is two solid
colours on a flat field, so writing the PNG entries directly with zlib
costs about forty lines and keeps a build-time-only dependency out of the
curated release pins. Nearest-neighbour is deliberate as well: the source
is a small boolean grid, and sampling it per target size keeps 16x16 crisp
where downsampling a large canvas would smear it.

Run from the project root:  python tools/generate_interface_icon.py
"""

import os
import struct
import sys
import zlib

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, "assistant"))

from ui.ui import LayeredDisplayEngine, FACE_PIXEL_W, FACE_PIXEL_H  # noqa: E402

OUT_PATH = os.path.join(PROJECT, "assets", "assistant_icon_interface.ico")

# The normal icon is (240,240,245) on (13,13,15). These are those two,
# swapped, and nothing else changes.
BACKGROUND = (240, 240, 245, 255)
FOREGROUND = (13, 13, 15, 255)

SIZES = (16, 32, 48, 64, 128, 256)

# The face buffer is wider than tall; pad to a square so Windows does not
# stretch it. Same padding as the normal icon, so the two register exactly.
PAD_TOP = (FACE_PIXEL_W - FACE_PIXEL_H) // 2


def _face_grid():
    engine = LayeredDisplayEngine()
    # Emotion 0, no reactive wave: the neutral face the sequence returns to.
    return engine._build_face_pixels(0, 0.0)


def _render(grid, size):
    """Nearest-neighbour sample the face grid into a square RGBA buffer."""
    rows = []

    for y in range(size):
        source_y = y * FACE_PIXEL_W // size - PAD_TOP
        row = bytearray()

        for x in range(size):
            source_x = x * FACE_PIXEL_W // size
            lit = (
                0 <= source_y < FACE_PIXEL_H
                and 0 <= source_x < FACE_PIXEL_W
                and grid[source_y][source_x]
            )
            row.extend(FOREGROUND if lit else BACKGROUND)

        rows.append(bytes(row))

    return rows


def _chunk(tag, payload):
    body = tag + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(
        ">I", zlib.crc32(body) & 0xFFFFFFFF
    )


def _png(rows, size):
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    # Filter byte 0 (None) per scanline: the image is flat colour, so a
    # predictor would buy nothing over zlib's own matching.
    raw = b"".join(b"\x00" + row for row in rows)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def _ico(images):
    count = len(images)
    directory = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = []

    for size, payload in images:
        entries.append(struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,               # palette entries: none, this is 32-bit
            0,               # reserved
            1,               # colour planes
            32,              # bits per pixel
            len(payload),
            offset,
        ))
        offset += len(payload)

    return directory + b"".join(entries) + b"".join(p for _s, p in images)


def main():
    grid = _face_grid()
    images = [(size, _png(_render(grid, size), size)) for size in SIZES]
    blob = _ico(images)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    with open(OUT_PATH, "wb") as handle:
        handle.write(blob)

    print(f"Wrote {OUT_PATH} ({len(blob)} bytes, {len(images)} sizes)")


if __name__ == "__main__":
    main()
