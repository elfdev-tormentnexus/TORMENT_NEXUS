"""Build the one-door launcher icon: the Sable mark under a hazard strip.

TORMENT_NEXUS.bat is the way into every mode, including the two that can
write to your files. The icon says both halves of that: the ordinary mark, so
it is recognisably the same program, and a caution strip, so nobody reaches
the self-editing surface believing they opened a chat window.

Deliberately the yellow-and-black hazard colours rather than Super Dev's blue
and red. Those two exist to be told apart from each other on a taskbar; this
one is the front door and should read as the project's own.

The stripes frame the mark rather than crossing it. A bottom band was tried
first and it took the chin off the face, which made the icon read as a hazard
sign with a picture above it instead of as Sable behind caution tape. A border
keeps the mark whole, which is the half of the meaning that says this is still
the same program. At 16x16 the border is two pixels and still reads.

Unlike build_super_dev_icon.py, which draws from nothing, this composites
artwork that already exists -- so it has to decode PNG. It borrows
machinesoul's decoder rather than carrying a second one: that module is a
PNG codec this project already owns and tests, and a private copy here would
be the thing that disagrees with it later.

    python tools/build_launcher_icon.py
"""

import os
import struct
import sys
import zlib

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, "tools"))

import machinesoul  # noqa: E402

SOURCE = os.path.join(PROJECT, "assets", "assistant_icon.ico")
OUT = os.path.join(PROJECT, "assets", "torment_nexus_icon.ico")

# Caution yellow and the near-black the other icons edge with, so the three
# launcher icons look like a set rather than three separate decisions.
YELLOW = (250, 198, 20)
BLACK = (18, 18, 22)

# Fractions of the icon's smaller side.
BORDER = 0.12            # how far the striped frame reaches in from the edge
RULE = 0.02              # dark line on the frame's inside, separating it
STRIPE = 0.17            # diagonal stripe width, as a fraction of the size


def _frames(path):
    """Every frame in an ICO, as (size, rgba_bytes)."""
    with open(path, "rb") as handle:
        blob = handle.read()

    reserved, kind, count = struct.unpack("<HHH", blob[:6])
    if reserved or kind != 1:
        raise SystemExit(f"{path} is not an ICO file.")

    out = []
    for index in range(count):
        entry = 6 + index * 16
        width = blob[entry] or 256
        height = blob[entry + 1] or 256
        length, offset = struct.unpack("<II", blob[entry + 8:entry + 16])
        body = blob[offset:offset + length]

        if body[:8] != b"\x89PNG\r\n\x1a\n":
            raise SystemExit(
                f"{path} frame {width}x{height} is a BMP frame; this tool "
                "only reads the PNG-framed icons this project ships."
            )

        out.append((width, height, _decode(body, width, height)))
    return out


def _decode(png, width, height):
    """PNG bytes to RGBA, through machinesoul's own unfilter."""
    position = 8
    idat = bytearray()
    depth = colour = None

    while position < len(png):
        length, name = struct.unpack(">I4s", png[position:position + 8])
        body = png[position + 8:position + 8 + length]
        if name == b"IHDR":
            depth, colour = body[8], body[9]
        elif name == b"IDAT":
            idat += body
        elif name == b"IEND":
            break
        position += 12 + length

    if (depth, colour) != (8, 6):
        raise SystemExit(
            f"frame {width}x{height} is depth {depth} colour type {colour}; "
            "this tool expects 8-bit RGBA, which is what the shipped icon is."
        )

    return machinesoul._unfilter(zlib.decompress(bytes(idat)), width, height)


def _striped(x, y, size):
    """Which hazard colour a pixel in the strip takes."""
    stripe = max(2, int(size * STRIPE))
    # Diagonal, leaning the way the other hazard art leans.
    return YELLOW if ((x + (size - y)) // stripe) % 2 == 0 else BLACK


def _compose(width, height, rgba):
    """Striped frame around the edge; the mark inside it is untouched."""
    out = bytearray(rgba)
    side = min(width, height)
    edge = max(2, int(side * BORDER))
    rule = max(1, int(side * RULE))

    for y in range(height):
        for x in range(width):
            # How far this pixel is from whichever edge is nearest.
            depth = min(x, y, width - 1 - x, height - 1 - y)

            if depth >= edge:
                continue

            if depth >= edge - rule:
                # A dark line on the inside of the frame, so the stripes stop
                # against something rather than bleeding into the artwork.
                red, green, blue = BLACK
            else:
                red, green, blue = _striped(x, y, max(width, height))

            index = (y * width + x) * 4
            out[index] = red
            out[index + 1] = green
            out[index + 2] = blue
            out[index + 3] = 255

    return bytes(out)


def _encode(width, height, rgba):
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)                      # filter: none
        raw += rgba[y * stride:(y + 1) * stride]

    return b"".join((
        b"\x89PNG\r\n\x1a\n",
        machinesoul._chunk(
            b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
        machinesoul._chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
        machinesoul._chunk(b"IEND", b""),
    ))


def build(source=SOURCE, out=OUT):
    frames = _frames(source)
    encoded = [
        (width, height, _encode(width, height, _compose(width, height, rgba)))
        for width, height, rgba in frames
    ]

    header = struct.pack("<HHH", 0, 1, len(encoded))
    offset = len(header) + 16 * len(encoded)
    directory = bytearray()
    body = bytearray()

    for width, height, png in encoded:
        directory += struct.pack(
            "<BBBBHHII",
            0 if width == 256 else width,
            0 if height == 256 else height,
            0, 0, 1, 32, len(png), offset,
        )
        body += png
        offset += len(png)

    with open(out, "wb") as handle:
        handle.write(header + bytes(directory) + bytes(body))

    return out, [(w, h) for w, h, _ in encoded]


if __name__ == "__main__":
    path, sizes = build()
    print(f"wrote {path}")
    for width, height in sizes:
        print(f"  {width}x{height}")
