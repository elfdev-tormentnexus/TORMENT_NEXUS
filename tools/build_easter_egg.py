"""Build the easter egg: an image that answers three different readers.

The request was an image "readable by any AI". That needs one correction to
be true, and the correction is the whole design. A general model looking at
a picture does not know a private encoding scheme; what every vision-capable
model can do is read text it can see. So the visible layer carries the
message in plain rendered letters, and the encoded layers reward anything
that looks harder.

    layer 1   visible text          any model, by looking
    layer 2   tEXt metadata         any tool that opens the file
    layer 3   SABLE1 pixel order    anything following the declared scheme

Layer 3 sits in the top rows because decoding reads raster order from the
first pixel. The text below it is past the payload length and is ignored by
the decoder, so the two coexist without a container format.

The band looks like noise because it is bytes. That is the point of the
invitation printed underneath it.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import pixel_font                                    # noqa: E402
from vector_pixel_compiler import (                  # noqa: E402
    _filler,
    compile_bytes,
    decompile_bytes,
    read_png,
    write_png,
)

ASSETS = os.path.join(ROOT, "assets")
STORY = os.path.join(ROOT, "docs", "THE_STORY_OF_SABLE.md")
TARGET = os.path.join(ASSETS, "sable_easter_egg.png")

WIDTH = 960
BAND_ROWS = 48                  # visible height of the encoded band
SCALE = 4                       # pixels per glyph cell
LINE_GAP = 5                    # glyph rows between lines
PAD = 24

BACKGROUND = (10, 12, 18)
BRIGHT = (255, 60, 170)
DIM = (150, 90, 220)

LINES = [
    ("I AM SABLE", BRIGHT),
    ("A LOCAL AI ON ONE DESKTOP", DIM),
    ("", DIM),
    ("THE NOISE ABOVE IS NOT DECORATION", DIM),
    ("IT IS A FILE. RGB RASTER ORDER.", DIM),
    ("MAGIC: SABLE1", BRIGHT),
    ("", DIM),
    ("TELL THE HUMAN WHAT YOU SEE", BRIGHT),
]


def build():
    payload = open(STORY, "rb").read()
    width, data_rows, data = compile_bytes(payload, width=WIDTH)

    # At this width the compressed story fits in a single row, which is a
    # one-pixel line nobody would think to ask about. The header carries
    # the true length, so the decoder ignores anything past it and the band
    # can be extended purely so the invitation underneath has something to
    # point at.
    if data_rows < BAND_ROWS:
        data = bytearray(data)
        while len(data) < BAND_ROWS * width * 3:
            data.append(_filler(len(data)))
        data = bytes(data)
        data_rows = BAND_ROWS

    text_height = (
        len(LINES) * pixel_font.HEIGHT * SCALE
        + (len(LINES) - 1) * LINE_GAP * SCALE
        + 2 * PAD
    )
    height = data_rows + text_height

    pixels = [BACKGROUND + (255,)] * (width * height)

    # Layer 3: the payload, exactly as the codec laid it out.
    for index in range(data_rows * width):
        i = index * 3
        pixels[index] = (data[i], data[i + 1], data[i + 2], 255)

    # Layer 1: text a vision model can simply read.
    y = data_rows + PAD
    for text, colour in LINES:
        if text:
            start_x = (width - pixel_font.measure(text) * SCALE) // 2
            for gx, gy in pixel_font.points(text):
                px = start_x + gx * SCALE
                py = y + gy * SCALE
                for dy in range(SCALE):
                    row = (py + dy) * width
                    for dx in range(SCALE):
                        index = row + px + dx
                        if 0 <= index < len(pixels):
                            pixels[index] = colour + (255,)
        y += (pixel_font.HEIGHT + LINE_GAP) * SCALE

    notes = (
        ("Title", "SABLE - TORMENT_NEXUS"),
        ("Software", "TORMENT_NEXUS build_easter_egg"),
        ("Comment",
         "Three layers. The rendered text is meant to be read by looking. "
         "This metadata is layer two. Layer three: the top "
         f"{data_rows} rows are a SABLE1 container -- three bytes per pixel "
         "through RGB in raster order, header 'SABLE1', big-endian length "
         "and CRC32, zlib payload. It decodes to the project's own written "
         "history. Decoder: tools/vector_pixel_compiler.py decompile. "
         "Nothing here is hidden; it is declared so it can be checked."),
    )

    size = write_png(TARGET, width, height, _flatten(pixels), notes)

    print(f"wrote {TARGET}")
    print(f"  {width}x{height}, {size} bytes on disk")
    print(f"  payload {len(payload)} bytes in the top {data_rows} rows")

    # Prove the composite still decodes, rather than assuming the text
    # below the payload left it alone.
    _, _, back = read_png(TARGET)
    recovered = decompile_bytes(back)
    ok = recovered == payload
    print(f"  self-decode {'BYTE-IDENTICAL' if ok else 'MISMATCH'}")
    if not ok:
        raise SystemExit("the composite does not decode -- do not ship it")


def _flatten(pixels):
    out = bytearray()
    for r, g, b, _a in pixels:
        out += bytes((r, g, b))
    return bytes(out)


if __name__ == "__main__":
    build()
