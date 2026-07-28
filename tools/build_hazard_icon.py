"""Hazard stripes, for the launcher that starts in experimental mode.

Diagonal caution stripes. The register is the point: this launcher starts a
mode that is deliberately slower, keeps a second embedding server resident,
and runs an unproven retrieval path alongside the real one. It should not
look like the ordinary launcher.

Writes a PNG and a Windows .ico. The .ico is PNG-in-ICO, which every
Windows since Vista reads, so no BMP encoder is needed.

    python tools/build_hazard_icon.py
"""
import math
import os
import struct
import sys
import zlib

YELLOW = (250, 204, 21)
BLACK = (17, 17, 17)
STRIPE = 34          # px, measured perpendicular to the diagonal
SIZES = (256, 128, 64, 48, 32, 16)


def _png_bytes(size, rgba_rows):
    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + bytes(r) for r in rgba_rows)
    return b"".join([
        b"\x89PNG\r\n\x1a\n",
        chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)),
        chunk(b"IDAT", zlib.compress(raw, 9)),
        chunk(b"IEND", b""),
    ])


def stripes(size):
    """Diagonal stripes with a rounded-square mask and a thin dark edge."""
    rows = []
    radius = size * 0.16
    inset = max(1.0, size * 0.02)
    scale = size / 256.0
    period = max(2.0, STRIPE * scale * 2)

    for y in range(size):
        row = bytearray()
        for x in range(size):
            # Rounded-square distance, so the icon reads as a plate rather
            # than a full-bleed square at small sizes.
            dx = max(inset - x, 0, x - (size - 1 - inset))
            dy = max(inset - y, 0, y - (size - 1 - inset))
            cx = min(max(x, radius), size - 1 - radius)
            cy = min(max(y, radius), size - 1 - radius)
            corner = math.hypot(x - cx, y - cy)

            outside = corner - radius
            if dx or dy:
                outside = max(outside, math.hypot(dx, dy))

            alpha = 255
            if outside > 0:
                alpha = int(max(0.0, 255 * (1.0 - outside)))

            phase = ((x + y) % period) / period
            r, g, b = YELLOW if phase < 0.5 else BLACK

            # Dark rim: reads as a border at every size, and keeps the
            # yellow from bleeding into a light page.
            edge = radius - corner if corner > 0 else radius
            if outside > -1.5 * scale - 0.5:
                r, g, b = BLACK

            row += bytes((r, g, b, alpha))
        rows.append(row)
    return rows


def write_ico(path, pngs):
    """ICONDIR + one ICONDIRENTRY per image, each holding a whole PNG."""
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, blob in pngs:
        entries += struct.pack("<BBBBHHII",
                               0 if size >= 256 else size,
                               0 if size >= 256 else size,
                               0, 0, 1, 32, len(blob), offset)
        blobs += blob
        offset += len(blob)
    open(path, "wb").write(head + entries + blobs)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets = os.path.join(root, "assets")
    pngs = []
    for size in SIZES:
        blob = _png_bytes(size, stripes(size))
        pngs.append((size, blob))
        if size == 256:
            out = os.path.join(assets, "hazard_icon.png")
            open(out, "wb").write(blob)
            print(f"  {out}  {len(blob):,} bytes")

    ico = os.path.join(assets, "hazard_icon.ico")
    write_ico(ico, pngs)
    print(f"  {ico}  {os.path.getsize(ico):,} bytes  "
          f"({len(SIZES)} sizes: {', '.join(str(s) for s in SIZES)})")


if __name__ == "__main__":
    sys.exit(main() or 0)
