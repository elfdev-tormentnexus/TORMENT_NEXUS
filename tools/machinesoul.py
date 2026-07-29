"""machinesoul: carry a payload, exactly, inside an animated capsule.

Named against machinespirit, and the pair is the point. They are the two
halves of what this project does to data, and keeping them under one name
made it possible to say "1:1" about something measured at 0.9243.

    machinespirit   the lossy half. Anchor coordinates, per-token traces,
                    consume, memory. Reads MEANING, discards the words, and
                    the loss is the subject of the research: 0.9243 cosine
                    through the codec, 90% pooled retrieval against 83% for
                    the trace, +0.380 mean profile on real entries.
    machinesoul     the lossless half. Bytes in, the same bytes out, or an
                    exception. No cosine appears anywhere in this file. A
                    release archive has no tolerance for a good enough
                    reconstruction, and the sha256 is what enforces that.

A capsule is machinesoul's container. The operator's decision to ship one
was made with the size measurement in hand rather than instead of it:
packing bytes into a PNG does not beat zipping them -- PNG
*is* DEFLATE, so the best case is a tie and the real figure is the container
overhead:

    research prose      51,066 raw   20,178 zlib   20,292 as PNG   1.01x
    already compressed  20,178       20,194        20,306          1.01x
    GGUF slice, 4 MB    4,194,304    3,156,813     3,157,802       1.00x

So this costs about 1% on small payloads and about 0.03% on large ones. It
buys nothing in bytes and it is not a way around a file-size limit: a
capsule holding an 8 GB model is an 8 GB file. What it buys is that the
release artifact is made of the release, which is the project's whole
aesthetic argument and the reason it exists.

The frames look like coloured static because they are bytes, which is the
same thing `build_easter_egg.py` says about its band and for the same
reason. Anything that re-encodes the image destroys the payload -- an
optimiser, a screenshot, a social preview. That is stated in the tEXt chunk
so a recipient who re-saves it learns why extraction then fails.

Layout, raster order from the first pixel of the first frame:

    magic     9   b"MACHINESOUL1"
    version   1   currently 1
    length    8   payload bytes, big-endian
    frames    4   frame count
    digest   32   sha256 of the payload
    payload   n
    filler        zero to the end of the last frame

    python tools/machinesoul.py build docs --out sable_research.png
    python tools/machinesoul.py extract sable_research.png --out docs.tar
"""
import argparse
import hashlib
import io
import os
import struct
import sys
import tarfile
import zlib

MAGIC = b"MACHINESOUL1"
VERSION = 1
HEADER = len(MAGIC) + 1 + 8 + 4 + 32
WIDTH = 256
CHANNELS = 4


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def _rows(blob, width):
    """Scanlines with filter 0. Filtering compresses images, not payloads."""
    stride = width * CHANNELS
    return [b"\x00" + blob[i:i + stride] for i in range(0, len(blob), stride)]


def tar_directory(folder):
    """Deterministic tar, so the same tree always makes the same capsule.

    Timestamps, uid/gid and ownership are zeroed. A capsule whose digest
    changed because of a file mtime would make the checksum cycle lie about
    what changed.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for root, folders, names in os.walk(folder):
            folders.sort()
            for name in sorted(names):
                full = os.path.join(root, name)
                info = archive.gettarinfo(full,
                                          os.path.relpath(full, folder))
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with open(full, "rb") as handle:
                    archive.addfile(info, handle)
    return buffer.getvalue()


def build(payload, out_path, frames=8, width=WIDTH, delay_ms=120, note=""):
    """Write the capsule. Returns (frames, width, height, bytes written)."""
    if frames < 1:
        raise ValueError("a capsule needs at least one frame")

    digest = hashlib.sha256(payload).digest()
    header = (MAGIC + bytes([VERSION]) + struct.pack(">Q", len(payload))
              + struct.pack(">I", frames) + digest)
    body = header + payload

    stride = width * CHANNELS
    # Every frame is the same size, because APNG frames that share IHDR
    # dimensions need no offsets and stay readable by simple decoders.
    per_frame_rows = max(1, -(-len(body) // (stride * frames)))
    height = per_frame_rows
    capacity = stride * height * frames
    body = body + b"\x00" * (capacity - len(body))

    out = [b"\x89PNG\r\n\x1a\n",
           _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))]

    text = (note or
            "MACHINESOUL1. The pixels are the payload, in raster order across "
            "frames. Re-encoding this image destroys it: any optimiser, "
            "screenshot or preview re-compresses the pixels and the bytes "
            "do not survive. Extract with tools/machinesoul.py.")
    out.append(_chunk(b"tEXt", b"Software\x00" + b"MACHINESOUL1"))
    out.append(_chunk(b"tEXt", b"Comment\x00" + text.encode("utf-8")))
    out.append(_chunk(b"acTL", struct.pack(">II", frames, 0)))

    span = stride * height
    sequence = 0
    for index in range(frames):
        raw = b"".join(_rows(body[index * span:(index + 1) * span], width))
        out.append(_chunk(b"fcTL", struct.pack(
            ">IIIIIHHBB", sequence, width, height, 0, 0,
            max(1, int(delay_ms)), 1000, 0, 0)))
        sequence += 1
        if index == 0:
            out.append(_chunk(b"IDAT", zlib.compress(raw, 9)))
        else:
            out.append(_chunk(b"fdAT",
                              struct.pack(">I", sequence) + zlib.compress(raw, 9)))
            sequence += 1

    out.append(_chunk(b"IEND", b""))
    blob = b"".join(out)
    with open(out_path, "wb") as handle:
        handle.write(blob)
    return frames, width, height, len(blob)


class CapsuleError(Exception):
    """Refuse rather than return bytes that were not the payload."""


def _unfilter(raw, width, height):
    """Undo PNG scanline filters. Present so a re-encoded capsule that
    happens to survive still reads, not because this writer emits them."""
    stride = width * CHANNELS
    out = bytearray()
    previous = bytearray(stride)
    position = 0
    for _ in range(height):
        if position >= len(raw):
            break
        kind = raw[position]
        position += 1
        line = bytearray(raw[position:position + stride])
        position += stride
        if kind == 1:
            for i in range(CHANNELS, len(line)):
                line[i] = (line[i] + line[i - CHANNELS]) & 0xFF
        elif kind == 2:
            for i in range(len(line)):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif kind == 3:
            for i in range(len(line)):
                left = line[i - CHANNELS] if i >= CHANNELS else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(len(line)):
                a = line[i - CHANNELS] if i >= CHANNELS else 0
                b = previous[i]
                c = previous[i - CHANNELS] if i >= CHANNELS else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif kind != 0:
            raise CapsuleError(f"unknown PNG filter {kind}")
        out += line
        previous = line
    return bytes(out)


def read_capsule(png_path):
    """Every pixel byte, in frame order. Raises rather than guessing."""
    with open(png_path, "rb") as handle:
        data = handle.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise CapsuleError("not a PNG")

    width = height = None
    streams = []
    position = 8
    while position + 8 <= len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        body = data[position + 8:position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", body[:10])
            if depth != 8 or colour != 6:
                raise CapsuleError(
                    f"capsule must be 8-bit RGBA, got depth {depth} colour "
                    f"type {colour}")
        elif kind == b"IDAT":
            streams.append(body)
        elif kind == b"fdAT":
            streams.append(body[4:])
        elif kind == b"IEND":
            break

    if width is None or not streams:
        raise CapsuleError("no image data")

    blob = bytearray()
    for stream in streams:
        blob += _unfilter(zlib.decompress(stream), width, height)
    return bytes(blob)


def extract(png_path):
    """The payload, or an exception. Never a partial file presented as whole."""
    blob = read_capsule(png_path)
    if len(blob) < HEADER:
        raise CapsuleError("too small to hold a header")
    if blob[:len(MAGIC)] != MAGIC:
        raise CapsuleError(
            f"not a MACHINESOUL1 capsule (found {blob[:9]!r}). A re-encoded "
            "image will fail here: the pixels were re-compressed and the "
            "bytes underneath them changed.")

    at = len(MAGIC)
    version = blob[at]
    at += 1
    length = struct.unpack(">Q", blob[at:at + 8])[0]
    at += 8
    frames = struct.unpack(">I", blob[at:at + 4])[0]
    at += 4
    digest = blob[at:at + 32]
    at += 32

    if version != VERSION:
        raise CapsuleError(f"capsule version {version}, this reads {VERSION}")
    if at + length > len(blob):
        raise CapsuleError(
            f"capsule declares {length} bytes but carries {len(blob) - at}; "
            "it is truncated and nothing is written")

    payload = blob[at:at + length]
    actual = hashlib.sha256(payload).digest()
    if actual != digest:
        raise CapsuleError(
            "sha256 mismatch: the capsule declares "
            f"{digest.hex()[:16]} and carries {actual.hex()[:16]}. Nothing "
            "is written -- a capsule that fails its own checksum is not a "
            "slightly damaged archive, it is not the archive.")
    return payload, {"version": version, "frames": frames,
                     "length": length, "sha256": digest.hex()}


def cmd_build(args):
    source = args.source
    if os.path.isdir(source):
        payload = tar_directory(source)
        kind = f"tar of {source}"
    else:
        with open(source, "rb") as handle:
            payload = handle.read()
        kind = source

    frames, width, height, written = build(
        payload, args.out, frames=args.frames, delay_ms=args.delay)
    print(f"capsule: {args.out}")
    print(f"  payload   {len(payload):,} bytes  ({kind})")
    print(f"  sha256    {hashlib.sha256(payload).hexdigest()}")
    print(f"  frames    {frames} x {width}x{height} RGBA")
    print(f"  file      {written:,} bytes  ({written / max(1, len(payload)):.2f}x)")
    return 0


def cmd_extract(args):
    try:
        payload, meta = extract(args.capsule)
    except CapsuleError as error:
        print(f"refused: {error}")
        return 1

    out = args.out
    if args.untar or (out and out.endswith(os.sep)) or os.path.isdir(out or ""):
        target = out or "."
        os.makedirs(target, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            _safe_extract(archive, target)
        print(f"extracted {meta['length']:,} bytes into {target}")
    else:
        with open(out, "wb") as handle:
            handle.write(payload)
        print(f"wrote {meta['length']:,} bytes to {out}")
    print(f"  sha256 verified  {meta['sha256']}")
    return 0


def _safe_extract(archive, target):
    """Refuse paths that escape the destination.

    An archive carried inside an image is still an archive, and an entry
    named ../../ is the oldest trick there is. The capsule verifies who
    built it, not what they meant.
    """
    root = os.path.realpath(target)
    for member in archive.getmembers():
        destination = os.path.realpath(os.path.join(target, member.name))
        if destination != root and not destination.startswith(root + os.sep):
            raise CapsuleError(f"archive entry escapes the target: {member.name}")
        if member.issym() or member.islnk():
            raise CapsuleError(f"archive contains a link: {member.name}")
    archive.extractall(target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="pack a file or directory into a capsule")
    b.add_argument("source")
    b.add_argument("--out", required=True)
    b.add_argument("--frames", type=int, default=8)
    b.add_argument("--delay", type=int, default=120)
    b.set_defaults(func=cmd_build)

    e = sub.add_parser("extract", help="verify a capsule and write its payload")
    e.add_argument("capsule")
    e.add_argument("--out", required=True)
    e.add_argument("--untar", action="store_true")
    e.set_defaults(func=cmd_extract)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

