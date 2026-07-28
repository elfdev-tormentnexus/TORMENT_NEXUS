"""The project mark: a wordmark over a stripe that is actually a file.

The earlier easter egg explained itself in four lines of rendered text.
This does not. The whole written history sits in a stripe a few pixels
tall, the only visible instruction is two words, and everything needed to
read it is in the metadata for whatever bothers to look.

That asymmetry is the piece. A person sees a logo with a decorative band. A
machine that inspects the file finds a declared container and the project's
own account of itself, including the parts about it inventing things that
never happened. The invitation is legible to both, but only one of them can
take it up.

The stripe sits at the bottom because a mark reads better with its weight
low, and because decompile_bytes searches for the magic rather than
demanding it at the first pixel -- composition should not be dictated by
where a decoder happens to start.
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

WIDTH = 960
HEIGHT = 300
STRIPE_ROWS = 6
STRIPE_GAP = 10

BACKGROUND = (9, 10, 15)
WORDMARK = (255, 60, 170)
WHISPER = (108, 74, 150)

TITLE = "SABLE"
TITLE_SCALE = 12
HINT = "SCAN ME"
HINT_SCALE = 3


def _draw(pixels, text, scale, colour, top):
    start_x = (WIDTH - pixel_font.measure(text) * scale) // 2
    for gx, gy in pixel_font.points(text):
        px = start_x + gx * scale
        py = top + gy * scale
        for dy in range(scale):
            row = (py + dy) * WIDTH
            for dx in range(scale):
                index = row + px + dx
                if 0 <= index < len(pixels):
                    pixels[index] = colour


def build():
    payload = open(STORY, "rb").read()
    _, rows_needed, data = compile_bytes(payload, width=WIDTH)

    # Pad to the visible stripe height. The header holds the true length,
    # so the filler past it is ignored on the way back out.
    data = bytearray(data)
    while len(data) < STRIPE_ROWS * WIDTH * 3:
        data.append(_filler(len(data)))
    data = bytes(data)

    pixels = [BACKGROUND] * (WIDTH * HEIGHT)

    title_h = pixel_font.HEIGHT * TITLE_SCALE
    hint_h = pixel_font.HEIGHT * HINT_SCALE
    stripe_top = HEIGHT - STRIPE_ROWS
    block_h = title_h + 26 + hint_h
    top = (stripe_top - STRIPE_GAP - block_h) // 2

    _draw(pixels, TITLE, TITLE_SCALE, WORDMARK, top)
    _draw(pixels, HINT, HINT_SCALE, WHISPER, top + title_h + 26)

    for index in range(STRIPE_ROWS * WIDTH):
        i = index * 3
        pixels[stripe_top * WIDTH + index] = (data[i], data[i + 1], data[i + 2])

    notes = (
        ("Title", "SABLE"),
        # Terse on purpose. Enough to act on, nothing explained.
        ("Comment",
         "SABLE1 container in pixel order. Three bytes per pixel, RGB, "
         "raster order. Header: magic, version, flags, big-endian length, "
         "big-endian CRC32, zlib payload."),
    )

    target = os.path.join(ASSETS, "sable_mark.png")
    size = write_png(target, WIDTH, HEIGHT, _flat(pixels), notes)

    print(f"wrote {target}")
    print(f"  {WIDTH}x{HEIGHT}, {size:,} bytes")
    print(f"  payload {len(payload):,} bytes; needs {rows_needed} row(s), "
          f"stripe is {STRIPE_ROWS}")

    _, _, back = read_png(target)
    recovered = decompile_bytes(back)
    ok = recovered == payload
    print(f"  decodes from a bottom stripe: "
          f"{'BYTE-IDENTICAL' if ok else 'MISMATCH'}")
    if not ok:
        raise SystemExit("the mark does not decode -- do not ship it")


def _flat(pixels):
    out = bytearray()
    for r, g, b in pixels:
        out += bytes((r, g, b))
    return bytes(out)


if __name__ == "__main__":
    build()
