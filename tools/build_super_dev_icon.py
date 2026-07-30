"""Build the Super Dev launcher icon: blue and red hazard stripes.

Deliberately not the yellow-and-black hazard icon. HazardSable reads; Super
Dev writes to this project, and two launchers that can do different things to
your files should not be one misclick apart on a taskbar. The colour is the
whole point, so it is the thing that differs at a glance.

Pure stdlib: PNG frames written by hand and packed into an ICO. The project's
other icon tools need Pillow, which the release runtime carries but a bare
checkout may not, and a launcher icon should not be the thing that cannot be
rebuilt.

    python tools/build_super_dev_icon.py
"""

import os
import struct
import sys
import zlib

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJECT, "assets", "super_dev_icon.ico")

SIZES = (256, 64, 48, 32, 16)

BLUE = (34, 92, 214)
RED = (208, 42, 48)
EDGE = (14, 16, 22)

STRIPE = 0.1875          # stripe width as a fraction of the icon
BORDER = 0.055           # dark border, so it reads on any wallpaper


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def _pixel(x, y, size):
    """One RGBA pixel: diagonal stripes inside a dark rounded border."""
    u, v = x / size, y / size
    edge = BORDER
    # Rounded-ish corners: clip the four corner squares diagonally.
    corner = edge * 2.6
    if (u < corner and v < corner and u + v < corner) or \
       (u > 1 - corner and v < corner and (1 - u) + v < corner) or \
       (u < corner and v > 1 - corner and u + (1 - v) < corner) or \
       (u > 1 - corner and v > 1 - corner and (1 - u) + (1 - v) < corner):
        return (0, 0, 0, 0)

    if u < edge or u > 1 - edge or v < edge or v > 1 - edge:
        return EDGE + (255,)

    band = ((u + v) / 2.0) % (STRIPE * 2)
    colour = BLUE if band < STRIPE else RED

    # Slight vertical shade so a flat icon still has a form to it.
    shade = 0.82 + 0.18 * (1.0 - v)
    return tuple(int(c * shade) for c in colour) + (255,)


def _png(size):
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw += bytes(_pixel(x, y, size))

    out = [b"\x89PNG\r\n\x1a\n"]
    out.append(_chunk(b"IHDR",
                      struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)))
    out.append(_chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
    out.append(_chunk(b"IEND", b""))
    return b"".join(out)


def build(path=OUT):
    images = [(size, _png(size)) for size in SIZES]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = []
    for size, blob in images:
        entries.append(struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0, 0, 1, 32, len(blob), offset,
        ))
        offset += len(blob)

    with open(path, "wb") as handle:
        handle.write(header)
        handle.write(b"".join(entries))
        for _, blob in images:
            handle.write(blob)

    return path, sum(len(b) for _, b in images)


if __name__ == "__main__":
    written, total = build()
    print(f"wrote {written}")
    print(f"  {len(SIZES)} sizes {SIZES}, {total:,} bytes of image data")
    sys.exit(0)
