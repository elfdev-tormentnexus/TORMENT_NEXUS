"""Vector coordinates to pixels, and back, with the loss measured.

Distinct from tools/vector_pixel_compiler.py, which puts arbitrary bytes in
raster order. That is a bitmap and it costs 32% over simply compressing.
This is a different question with a different answer: an embedding is not
arbitrary bytes. It is a coordinate, it tolerates quantisation the way this
project's own Q8 models do, and neighbouring coordinates in a well-ordered
set resemble each other -- which is exactly the structure PNG's predictive
filters were built to exploit.

So the claim worth testing is not "images are a good container". It is that
a float32 embedding set is a wasteful way to store something whose useful
precision is closer to a byte, and that laying those bytes out so similar
vectors sit adjacent lets an ordinary PNG filter do real work.

Layout: one vector per row, three dimensions per pixel through RGB, so the
row is the vector and the column is the dimension. Reading across is one
memory's coordinates; reading down is how one dimension varies across the
set. Both are meaningful to look at, which is the point.

Quantisation is affine per file: a single scale and offset recorded in the
metadata, not per row, so a decoded vector can be compared against any
other without unpacking a per-row table. Cosine similarity against the
original is reported rather than asserted -- the number is the finding.
"""

import argparse
import json
import math
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vector_pixel_compiler import _chunk, _text_chunk, read_png  # noqa: E402

MAGIC = "SABLEVEC1"


# ============================================================
# CODEC
# ============================================================

def quantise(vectors):
    """Affine float -> uint8 over the whole set. Returns (bytes, scale, low)."""
    low = min(min(v) for v in vectors)
    high = max(max(v) for v in vectors)
    span = (high - low) or 1.0
    scale = span / 255.0

    out = []
    for vector in vectors:
        row = bytearray()
        for value in vector:
            q = int(round((value - low) / scale))
            row.append(max(0, min(255, q)))
        out.append(bytes(row))
    return out, scale, low


def dequantise(rows, scale, low, dims):
    return [
        [low + row[i] * scale for i in range(dims)]
        for row in rows
    ]


def encode(vectors, path, note=""):
    dims = len(vectors[0])
    rows, scale, low = quantise(vectors)

    width = (dims + 2) // 3           # three dimensions per pixel
    height = len(vectors)

    raw = bytearray()
    for row in rows:
        raw.append(0)                 # filter type 0; PNG will not re-filter
        for x in range(width):
            base = x * 3
            r = row[base] if base < dims else 0
            g = row[base + 1] if base + 1 < dims else 0
            b = row[base + 2] if base + 2 < dims else 0
            raw += bytes((r, g, b, 255))

    header = {
        "magic": MAGIC,
        "dims": dims,
        "count": len(vectors),
        "scale": scale,
        "low": low,
        "layout": "one vector per row, three dims per pixel via RGB",
    }

    body = bytearray(b"\x89PNG\r\n\x1a\n")
    body += _chunk(b"IHDR",
                   struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    body += _text_chunk("Comment", json.dumps(header))
    if note:
        body += _text_chunk("Description", note)
    body += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    body += _chunk(b"IEND", b"")

    with open(path, "wb") as handle:
        handle.write(body)

    return os.path.getsize(path), header


def decode(path):
    blob = open(path, "rb").read()
    header = None
    pos = 8
    while pos < len(blob):
        length, = struct.unpack(">I", blob[pos:pos + 4])
        kind = blob[pos + 4:pos + 8]
        chunk = blob[pos + 8:pos + 8 + length]
        if kind == b"tEXt":
            key, _, value = chunk.partition(b"\0")
            if key == b"Comment":
                candidate = json.loads(value.decode("latin-1"))
                if candidate.get("magic") == MAGIC:
                    header = candidate
        elif kind == b"IEND":
            break
        pos += 12 + length

    if header is None:
        raise ValueError("no SABLEVEC1 header")

    width, height, rgb = read_png(path)
    dims = header["dims"]

    rows = []
    for y in range(height):
        flat = rgb[y * width * 3:(y + 1) * width * 3]
        rows.append(flat[:dims])

    return dequantise(rows, header["scale"], header["low"], dims), header


# ============================================================
# MEASUREMENT
# ============================================================

def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def report(original, recovered, png_bytes):
    dims = len(original[0])
    count = len(original)

    floats = count * dims * 4
    packed = struct.pack(f">{count * dims}f",
                         *[v for row in original for v in row])
    zlibbed = len(zlib.compress(packed, 9))

    sims = [cosine(a, b) for a, b in zip(original, recovered)]
    worst = min(sims)
    mean = sum(sims) / len(sims)

    print(f"  vectors                {count} x {dims}")
    print(f"  float32 raw            {floats:>9,} bytes")
    print(f"  float32 + zlib         {zlibbed:>9,} bytes"
          f"   ({100 * zlibbed / floats:.1f}% of raw)")
    print(f"  quantised PNG          {png_bytes:>9,} bytes"
          f"   ({100 * png_bytes / floats:.1f}% of raw,"
          f" {100 * png_bytes / zlibbed:.1f}% of zlib)")
    print()
    print(f"  cosine vs original     mean {mean:.6f}   worst {worst:.6f}")
    print(f"  mean error             {1 - mean:.2e}")

    return {
        "raw": floats,
        "zlib": zlibbed,
        "png": png_bytes,
        "mean_cosine": mean,
        "worst_cosine": worst,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="JSON file: list of float lists")
    parser.add_argument("target", help="PNG to write")
    args = parser.parse_args()

    vectors = json.load(open(args.source))
    size, header = encode(vectors, args.target)
    recovered, _ = decode(args.target)

    print(f"wrote {args.target}")
    print(f"  {(header['dims'] + 2) // 3}x{header['count']}")
    print()
    report(vectors, recovered, size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
