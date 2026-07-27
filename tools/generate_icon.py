"""
Renders the assistant's own default idle face (ui.py's emotion 0 --
the neutral face FACE_EMOTION_SEQUENCE always returns to) into a
Windows .ico file for the desktop shortcut.

Reuses the real pixel-generation code in ui.py rather than
reimplementing the face shape by hand, so the icon always matches
whatever the face actually looks like on screen -- if the face design
in ui.py ever changes, rerunning this script picks up the change.

Run from the project root: python generate_icon.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "assistant"))

from PIL import Image

from ui.ui import LayeredDisplayEngine, FACE_PIXEL_W, FACE_PIXEL_H


SCALE = 8  # each face pixel becomes an SCALE x SCALE block before downsampling
OUT_PATH = os.path.join(os.path.dirname(__file__), "assistant_icon.ico")

# The pixel buffer is 40x32 (wider than tall); pad to a square canvas
# so the icon isn't squished when Windows scales it.
PAD_TOP = (FACE_PIXEL_W - FACE_PIXEL_H) // 2


def main():
    engine = LayeredDisplayEngine()
    pixels = engine._build_face_pixels(0, 0.0)  # emotion 0, no reactive wave

    canvas_size = FACE_PIXEL_W * SCALE
    img = Image.new("RGBA", (canvas_size, canvas_size), (13, 13, 15, 255))
    px = img.load()

    for y, row in enumerate(pixels):
        for x, on in enumerate(row):
            if not on:
                continue

            out_y = y + PAD_TOP

            for dy in range(SCALE):
                for dx in range(SCALE):
                    px[x * SCALE + dx, out_y * SCALE + dy] = (240, 240, 245, 255)

    img.save(
        OUT_PATH,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
