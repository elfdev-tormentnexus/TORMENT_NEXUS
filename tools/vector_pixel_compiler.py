"""Compile text into pixel order, and decompile it back.

The distinction that makes this worth building: a projection is lossy and
one-way. Flattening 384 dimensions to a screen throws away everything it
could not fit, and nothing reads the original back out of the result. An
encoding is neither. Bytes go into pixel order under a stated scheme and
the same bytes come out, exactly, or the checksum says they did not.

So this is the honest version of "a machine can read it". It is not a
claim that a model can perceive meaning in a picture. It is a codec, with
a decoder in the same file, and the round trip either reproduces the input
byte for byte or reports failure.

Layout, raster order, three bytes a pixel through the RGB channels, alpha
held at 255:

    magic    6 bytes   SABLE1
    version  1 byte
    flags    1 byte    bit 0 set when the payload is zlib compressed
    length   4 bytes   big-endian, payload bytes before padding
    crc32    4 bytes   big-endian, over the payload as stored
    payload  length bytes
    padding  deterministic filler to the end of the final row

The filler is derived from position rather than random, so an identical
input produces an identical file and a rebuild can be compared.

The image looks like structured noise because it is structured noise. That
is the form data takes when every channel is carrying a byte rather than a
colour someone chose. Nothing is hidden in it and nothing is pretending to
be a picture.
"""

import argparse
import os
import struct
import sys
import zlib

MAGIC = b"SABLE1"
VERSION = 1
FLAG_COMPRESSED = 0x01
HEADER = len(MAGIC) + 1 + 1 + 4 + 4          # 16 bytes


# ============================================================
# PNG
# ============================================================

def _chunk(kind, body):
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    )


def _text_chunk(key, value):
    return _chunk(b"tEXt", key.encode("latin-1") + b"\0"
                  + value.encode("latin-1", "replace"))


def write_png(path, width, height, data, notes=()):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * width * 3
        for x in range(width):
            i = start + x * 3
            raw += bytes((data[i], data[i + 1], data[i + 2], 255))

    body = bytearray(b"\x89PNG\r\n\x1a\n")
    body += _chunk(b"IHDR",
                   struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    for key, value in notes:
        body += _text_chunk(key, value)
    body += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    body += _chunk(b"IEND", b"")

    with open(path, "wb") as handle:
        handle.write(body)
    return len(body)


def read_png(path):
    """Return (width, height, RGB bytes in raster order)."""
    blob = open(path, "rb").read()
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")

    pos = 8
    idat = b""
    width = height = None
    while pos < len(blob):
        length, = struct.unpack(">I", blob[pos:pos + 4])
        kind = blob[pos + 4:pos + 8]
        chunk = blob[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", chunk[:10])
            if depth != 8 or colour != 6:
                raise ValueError("expected 8-bit RGBA")
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
        pos += 12 + length

    raw = zlib.decompress(idat)
    stride = width * 4
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        filt = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        for i in range(stride):
            a = line[i - 4] if i >= 4 else 0
            b = prev[i]
            c = prev[i - 4] if i >= 4 else 0
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
        for i in range(0, stride, 4):
            out += line[i:i + 3]
        prev = line

    return width, height, bytes(out)


# ============================================================
# CODEC
# ============================================================

def _filler(index):
    """Deterministic padding, so an identical input rebuilds identically."""
    return (index * 37 + (index >> 8) * 101) & 0xFF


def compile_bytes(payload, width=None, compress=True):
    stored = zlib.compress(payload, 9) if compress else payload
    flags = FLAG_COMPRESSED if compress else 0

    body = (
        MAGIC
        + bytes((VERSION, flags))
        + struct.pack(">I", len(stored))
        + struct.pack(">I", zlib.crc32(stored) & 0xFFFFFFFF)
        + stored
    )

    total_px = (len(body) + 2) // 3
    if width is None:
        width = max(16, int(total_px ** 0.5) + 1)
    height = (total_px + width - 1) // width

    data = bytearray(body)
    while len(data) < width * height * 3:
        data.append(_filler(len(data)))

    return width, height, bytes(data)


def decompile_bytes(data):
    # The magic is searched for rather than required at offset zero. Pinning
    # it to the first pixel forces the payload into the top-left corner and
    # dictates the composition of anything it shares an image with; letting
    # it sit anywhere means a stripe can go where it belongs visually and
    # still decode. The header carries its own length and checksum, so a
    # false positive on six bytes fails the CRC rather than returning junk.
    start = data.find(MAGIC)
    if start < 0:
        raise ValueError("no SABLE1 magic anywhere in pixel order")

    data = data[start:]

    version = data[6]
    flags = data[7]
    length, = struct.unpack(">I", data[8:12])
    want_crc, = struct.unpack(">I", data[12:16])

    if version != VERSION:
        raise ValueError(f"unknown container version {version}")

    stored = data[HEADER:HEADER + length]
    if len(stored) != length:
        raise ValueError(
            f"truncated: header claims {length} bytes, image holds "
            f"{len(stored)}"
        )

    got_crc = zlib.crc32(stored) & 0xFFFFFFFF
    if got_crc != want_crc:
        raise ValueError(
            f"checksum mismatch: header {want_crc:08X}, payload {got_crc:08X}"
        )

    return zlib.decompress(stored) if flags & FLAG_COMPRESSED else stored


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)

    enc = sub.add_parser("compile", help="text file -> png")
    enc.add_argument("source")
    enc.add_argument("target")
    enc.add_argument("--width", type=int, default=None)

    dec = sub.add_parser("decompile", help="png -> text on stdout")
    dec.add_argument("source")

    chk = sub.add_parser("verify", help="prove a file round-trips")
    chk.add_argument("source")

    args = parser.parse_args()

    if args.mode == "compile":
        payload = open(args.source, "rb").read()
        width, height, data = compile_bytes(payload, args.width)
        notes = (
            ("Software", "TORMENT_NEXUS vector_pixel_compiler"),
            ("Comment",
             "Pixel order carries a SABLE1 container: 3 bytes per pixel "
             "through RGB, raster order. Decode with "
             "tools/vector_pixel_compiler.py decompile. This is an "
             "encoding, not a projection -- the bytes come back exactly."),
        )
        size = write_png(args.target, width, height, data, notes)
        print(f"wrote {args.target}")
        print(f"  {width}x{height}, {size} bytes on disk")
        print(f"  payload {len(payload)} bytes -> "
              f"{width * height * 3} bytes of pixel order")
        return 0

    if args.mode == "decompile":
        _, _, data = read_png(args.source)
        sys.stdout.buffer.write(decompile_bytes(data))
        return 0

    if args.mode == "verify":
        original = open(args.source, "rb").read()
        width, height, data = compile_bytes(original)
        tmp = args.source + ".roundtrip.png"
        write_png(tmp, width, height, data)
        _, _, back = read_png(tmp)
        recovered = decompile_bytes(back)
        os.remove(tmp)

        same = recovered == original
        print(f"input      {len(original)} bytes")
        print(f"image      {width}x{height}")
        print(f"recovered  {len(recovered)} bytes")
        print(f"round trip {'BYTE-IDENTICAL' if same else 'MISMATCH'}")
        return 0 if same else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
