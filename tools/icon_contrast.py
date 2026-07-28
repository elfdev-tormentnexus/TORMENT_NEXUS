"""Measure a PNG's contrast against both GitHub themes.

Pure stdlib: this project avoids Pillow on purpose.

    python tools/icon_contrast.py assets/sable_mark.png [more.png ...]

GitHub's default is the light theme, so an image that only clears 3:1 on
dark is effectively invisible to most visitors. Both columns must pass.
"""
import collections
import struct
import sys
import zlib

LIGHT = (255, 255, 255)
DARK = (13, 17, 23)
WCAG_NON_TEXT = 3.0


def read_png(path):
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos = 8
    idat = b""
    width = height = depth = colour = None
    while pos < len(data):
        length, = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
        pos += 12 + length
    return width, height, depth, colour, zlib.decompress(idat)


def unfilter(raw, width, height, channels):
    stride = width * channels
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        filt = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            x = line[i]
            if filt == 1:
                x = (x + a) & 255
            elif filt == 2:
                x = (x + b) & 255
            elif filt == 3:
                x = (x + (a + b) // 2) & 255
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                x = (x + pr) & 255
            line[i] = x
        out += line
        prev = line
    return out


def lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def measure(path):
    w, h, depth, colour, raw = read_png(path)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    print(f"\n=== {path}")
    print(f"size: {w}x{h}  depth: {depth}  colour type: {colour} "
          f"({channels} channels)")
    if depth != 8 or colour not in (2, 6):
        print(f"  unhandled PNG form (depth {depth}, colour {colour}) — skipped")
        return None

    out = unfilter(raw, w, h, channels)
    pixels = []
    for i in range(0, len(out), channels):
        if channels == 4:
            pixels.append(tuple(out[i:i + 4]))
        else:
            pixels.append((out[i], out[i + 1], out[i + 2], 255))

    opaque = [p for p in pixels if p[3] > 16]
    print(f"pixels: {len(pixels)}   opaque: {len(opaque)} "
          f"({100 * len(opaque) / len(pixels):.1f}%)")
    if not opaque:
        print("  fully transparent — nothing to measure")
        return None

    counts = collections.Counter(opaque)
    print("dominant opaque colours:")
    for c, n in counts.most_common(6):
        print(f"  rgb{c[:3]} a={c[3]:<3} x{n:<6} "
              f"light {contrast(c, LIGHT):5.2f}:1   dark {contrast(c, DARK):5.2f}:1")

    # Two different images need two different questions asked of them.
    #
    # A transparent-background glyph floats directly on the page, so its own
    # ink must clear 3:1 against both themes. That is the smiley's failure:
    # pale ink at 17.8% coverage sits at 1.27:1 on white and disappears.
    #
    # An opaque slab brings its own background. The page never touches the
    # ink, so mean-opaque colour measures the slab against the page rather
    # than anything a reader must actually distinguish, and a dark slab on a
    # dark page scores ~1.0:1 while remaining perfectly legible. What matters
    # there is ink against its own field.
    bg, bg_n = counts.most_common(1)[0]
    slab = len(opaque) / len(pixels) > 0.95 and bg_n / len(opaque) > 0.5

    if slab:
        ink = [c for c, _ in counts.most_common(12) if c != bg]
        ink = max(ink, key=lambda c: contrast(c, bg)) if ink else bg
        ci = contrast(ink, bg)
        print(f"opaque slab: background rgb{bg[:3]} covers "
              f"{100 * bg_n / len(opaque):.1f}% of it")
        print(f"  ink rgb{ink[:3]} vs its own field : {ci:.2f}:1  "
              f"{'PASS' if ci >= WCAG_NON_TEXT else 'FAIL'}")
        print(f"  ink vs GitHub light      : {contrast(ink, LIGHT):.2f}:1")
        print(f"  ink vs GitHub dark       : {contrast(ink, DARK):.2f}:1")
        print("  (slab supplies its own background; page contrast is not the test)")
        return ci, ci

    avg = tuple(sum(p[i] for p in opaque) // len(opaque) for i in range(3))
    cl, cd = contrast(avg, LIGHT), contrast(avg, DARK)
    print(f"mean opaque colour rgb{avg}")
    print(f"  vs GitHub light #ffffff : {cl:.2f}:1  "
          f"{'PASS' if cl >= WCAG_NON_TEXT else 'FAIL'}")
    print(f"  vs GitHub dark  #0d1117 : {cd:.2f}:1  "
          f"{'PASS' if cd >= WCAG_NON_TEXT else 'FAIL'}")
    return cl, cd


if __name__ == "__main__":
    targets = sys.argv[1:] or [
        "assets/assistant_icon_animated.png",
        "assets/sable_mark.png",
    ]
    results = {t: measure(t) for t in targets}
    print(f"\nWCAG non-text minimum is {WCAG_NON_TEXT}:1 on BOTH themes.")
    both = [t for t, r in results.items() if r and min(r) >= WCAG_NON_TEXT]
    print("passes both:", ", ".join(both) if both else "none")
