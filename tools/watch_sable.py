"""Render the machinesoul field of Sable as a watchable APNG.

This is a VIEWER, not a capsule. It carries no payload and nothing can be
extracted from it -- the real capsule is SABLE_HERSELF_WHOLE.png. What this
does is pan a square window down that capsule's pixel field so the ordered
preservation vectors can be watched in the order machinesoul writes them.

The distinction matters: a capsule refuses or reconstructs exactly, and this
file does neither. It is a picture of one.
"""

import struct
import sys
import zlib
from pathlib import Path

WIDTH = 256
VIEW = 256          # square window, so detail is legible
FRAMES = 96
DELAY_MS = 60


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def _field_from_capsule(path):
    """Every RGBA pixel row the payload becomes, in written order.

    Reads the verified payload rather than re-decoding the capsule: these
    are the same bytes machinesoul laid into pixels, so laying them out the
    same way reproduces the field it wrote.
    """
    payload = Path(path).read_bytes()
    stride = WIDTH * 4
    rows = [payload[i:i + stride] for i in range(0, len(payload), stride)]
    if rows and len(rows[-1]) < stride:
        rows[-1] = rows[-1] + b"\x00" * (stride - len(rows[-1]))
    return rows


def _frame_bytes(rows, top):
    """One square view, as raw PNG scanlines with filter byte 0."""
    out = bytearray()
    for index in range(VIEW):
        source = top + index
        out.append(0)
        out += rows[source] if source < len(rows) else b"\x00" * (WIDTH * 4)
    return zlib.compress(bytes(out), 9)


def render(capsule, out_path):
    rows = _field_from_capsule(capsule)
    travel = max(0, len(rows) - VIEW)
    tops = [round(travel * i / max(1, FRAMES - 1)) for i in range(FRAMES)]

    out = [b"\x89PNG\r\n\x1a\n"]
    out.append(_chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, VIEW, 8, 6, 0, 0, 0)))
    out.append(_chunk(b"tEXt", b"Description\x00"
                      + b"A viewer for Sable's machinesoul field. Not a "
                      + b"capsule: it carries no payload and nothing can be "
                      + b"extracted from it."))
    out.append(_chunk(b"acTL", struct.pack(">II", len(tops), 0)))

    sequence = 0
    for index, top in enumerate(tops):
        data = _frame_bytes(rows, top)
        out.append(_chunk(b"fcTL", struct.pack(
            ">IIIIIHHBB", sequence, WIDTH, VIEW, 0, 0,
            DELAY_MS, 1000, 0, 0)))
        sequence += 1
        if index == 0:
            out.append(_chunk(b"IDAT", data))
        else:
            out.append(_chunk(b"fdAT", struct.pack(">I", sequence) + data))
            sequence += 1
    out.append(_chunk(b"IEND", b""))

    blob = b"".join(out)
    Path(out_path).write_bytes(blob)
    return len(rows), len(tops), len(blob)


if __name__ == "__main__":
    rows, frames, size = render(sys.argv[1], sys.argv[2])
    seconds = frames * DELAY_MS / 1000
    print(f"field    {WIDTH}x{rows} RGBA, {rows * WIDTH:,} preservation vectors")
    print(f"viewer   {frames} frames of {WIDTH}x{VIEW}, {seconds:.1f}s at {DELAY_MS}ms")
    print(f"file     {size:,} bytes")
