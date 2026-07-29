"""machinesoul: Sable's data-preservation logic language.

machinesoul maps an ordered field of four-coordinate integer vectors directly
to RGBA pixels across PNG or APNG frames. The inverse reads those pixels in
the same order and reconstructs the preserved source exactly. There is no
cosine threshold and no "close enough" result: the source digest agrees or
the decompiler refuses and keeps no partial output.

This definition is deliberately separate from machinespirit:

    machinesoul     Sable's data-preservation logic language. Vector to
                    pixel, reversible 1:1, integrity-gated.
    machinespirit   Sable's memory language. Anchors, per-token traces,
                    recall and semantic reconstruction. Meaning survives
                    imperfectly, and that measured loss is the research.

A machinesoul release artifact is a PNG/APNG file, not a ZIP allocation with
an image suffix. After the recipient decompiles all capsule vectors, the
verified reassembler restores each preserved file directly into the install
tree. No ZIP or tar layer sits between the reviewed source boundaries and the
published machinesoul fields.

The preservation header occupies the first pixel vectors in raster order:

    magic       MACHINESOUL1
    version     current preservation-language version
    length      exact preserved-source extent
    frames      declared APNG frame count
    digest      sha256 of the reconstructed source
    source      ordered vector field
    filler      zero vectors to the final frame boundary

Re-encoding, resizing, cropping, optimising, or screenshotting a capsule can
change its vectors and is refused. Download the PNG/APNG asset itself and use
the published decompiler.

    python tools/machinesoul.py build docs/VECTOR_TRANSLATION_RESEARCH.md \
        --out SABLERESEARCHA-RESEARCH.png
    python tools/machinesoul.py extract SABLERESEARCHA-RESEARCH.png \
        --out VECTOR_TRANSLATION_RESEARCH.recovered.md
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


def tar_paths(paths, root):
    """Deterministic tar of an explicit file list, relative to root.

    tar_directory() takes whatever happens to be under a folder. This takes
    exactly what the caller decided to include, which is what a reviewed
    subsystem map needs -- the map is the thing that was checked, so the
    archive must follow it rather than the filesystem.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for relative in sorted(paths):
            full = os.path.join(root, relative.replace("/", os.sep))
            info = archive.gettarinfo(full, relative)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with open(full, "rb") as handle:
                archive.addfile(info, handle)
    return buffer.getvalue()


def build(payload, out_path, frames=8, width=WIDTH, delay_ms=120, note="",
          description=None):
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
    if description:
        out.append(_description_chunk(description))
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


# --- streaming ---------------------------------------------------------
#
# build() holds the whole payload, compresses it in one call, and assembles
# the file in a list. That is fine for documents and impossible for a
# release: a 13 GB archive needs roughly two and a half times that at peak,
# against 5.7 GB free on the machine this was written for.
#
# The fix is not a faster processor or a GPU. Nothing here is an image
# operation -- no pixels are filtered, rendered or sampled -- so there is no
# parallel work to offload, and VRAM is smaller than the peak anyway.
# DEFLATE is a sequential sliding window, and the bottleneck is capacity.
# Processing in fixed blocks makes peak memory a constant.
#
# One PNG constraint shapes this: a chunk declares its length before its
# data, so a frame's compressed bytes must exist before its header can be
# written. Each frame is therefore compressed to a spill file and copied
# through, which keeps memory at the block size rather than the frame size.

BLOCK = 8 * 1024 * 1024

# Rows per frame. 4096 rows at 256 px RGBA is a 4 MiB frame, so a 13 GB
# payload becomes a few thousand frames rather than one impossible one.
FRAME_ROWS = 4096


def _payload_stream(handle, header, total_capacity, size):
    """Header, then the file, then zero padding, in BLOCK-sized pieces."""
    yield header
    sent = len(header)
    remaining = size
    while remaining > 0:
        block = handle.read(min(BLOCK, remaining))
        if not block:
            raise CapsuleError(
                f"source ended after {size - remaining} of {size} bytes")
        remaining -= len(block)
        sent += len(block)
        yield block
    while sent < total_capacity:
        pad = min(BLOCK, total_capacity - sent)
        sent += pad
        yield b"\x00" * pad


def _sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(BLOCK), b""):
            digest.update(block)
    return digest.digest()


# A capsule can carry a plain-language description of its own payload, so a
# recipient can see what a 1.8 GB image is about without decoding it. The
# text is supplied by the caller and never computed here: this module maps
# bytes to pixels and holds no opinion about meaning, which is the line that
# keeps it separate from machinespirit.
#
# Two properties travel with it and both are stated in the chunk itself.
#
#   It is OUTSIDE the digest. tEXt sits beside the pixel data, so an edited
#   description does not fail the SHA gate. The payload is guaranteed; the
#   description is a hint. Anything else would be an unverified claim
#   riding a verified one, which is the silent failure this project ranks
#   worst.
#
#   It LEAKS. A description of private contents, in cleartext, in a file
#   that looks like an image and gets forwarded like one, is a disclosure
#   with nothing about the file to warn anybody. So it is opt-in, never
#   automatic, and no code path here supplies a default.
DESCRIPTION_KEY = b"Description"

DESCRIPTION_PREFACE = (
    "Unverified description of this capsule's payload. It is NOT covered "
    "by the MACHINESOUL1 sha256 gate -- the payload is guaranteed, this "
    "text is a hint and can be edited without failing extraction. "
)


def _description_chunk(description):
    body = (DESCRIPTION_KEY + b"\x00"
            + (DESCRIPTION_PREFACE + description).encode("utf-8"))
    return _chunk(b"tEXt", body)


def read_description(png_path):
    """The capsule's description, without decoding a byte of its payload.

    The whole point of putting it in metadata: answering "what is this"
    should not cost a full extraction of something multi-gigabyte.
    """
    with open(png_path, "rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise CapsuleError("not a PNG")
        while True:
            head = handle.read(8)
            if len(head) < 8:
                return None
            length = struct.unpack(">I", head[:4])[0]
            kind = head[4:8]
            if kind in (b"IDAT", b"fdAT", b"IEND"):
                return None            # past the metadata, stop reading
            body = handle.read(length)
            handle.read(4)
            if kind == b"tEXt" and body.startswith(DESCRIPTION_KEY + b"\x00"):
                text = body[len(DESCRIPTION_KEY) + 1:].decode("utf-8", "replace")
                if text.startswith(DESCRIPTION_PREFACE):
                    return text[len(DESCRIPTION_PREFACE):]
                return text


def build_stream(source_path, out_path, width=WIDTH, frame_rows=FRAME_ROWS,
                 delay_ms=120, note="", progress=None, description=None):
    """Build a capsule of any size with bounded memory.

    Same container as build(); a capsule from either is read by the same
    extractor. Returns (frames, width, height, bytes written).

    `description` is optional and never defaulted -- see DESCRIPTION_KEY.
    """
    size = os.path.getsize(source_path)
    digest = _sha256_of_file(source_path)

    stride = width * CHANNELS
    frame_bytes = stride * frame_rows
    total = HEADER + size
    frames = max(1, -(-total // frame_bytes))
    capacity = frame_bytes * frames

    header = (MAGIC + bytes([VERSION]) + struct.pack(">Q", size)
              + struct.pack(">I", frames) + digest)

    text = (note or
            "MACHINESOUL1. The pixels are the payload, in raster order "
            "across frames. Re-encoding this image destroys it. Extract "
            "with machinesoul.py extract.")

    spill = out_path + ".frame.tmp"
    try:
        _build_stream_frames(source_path, out_path, spill, header, text,
                             frames, width, frame_rows, capacity, size,
                             delay_ms, progress, description)
    except BaseException:
        # A 13 GB build that dies partway leaves a partial capsule and a
        # frame spill behind, on the machine whose free space is the whole
        # reason this streams rather than buffering.
        for path in (out_path, spill):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        raise
    finally:
        if os.path.exists(spill):
            try:
                os.remove(spill)
            except OSError:
                pass

    return frames, width, frame_rows, os.path.getsize(out_path)


def _build_stream_frames(source_path, out_path, spill, header, text, frames,
                         width, frame_rows, capacity, size, delay_ms,
                         progress, description=None):
    """Write the capsule frame by frame. Cleanup belongs to the caller."""
    stride = width * CHANNELS
    frame_bytes = stride * frame_rows

    with open(source_path, "rb") as source, open(out_path, "wb") as out:
        out.write(b"\x89PNG\r\n\x1a\n")
        out.write(_chunk(b"IHDR", struct.pack(">IIBBBBB", width, frame_rows,
                                              8, 6, 0, 0, 0)))
        out.write(_chunk(b"tEXt", b"Software\x00MACHINESOUL1"))
        out.write(_chunk(b"tEXt", b"Comment\x00" + text.encode("utf-8")))
        if description:
            out.write(_description_chunk(description))
        out.write(_chunk(b"acTL", struct.pack(">II", frames, 0)))

        stream = _payload_stream(source, header, capacity, size)
        carry = bytearray()
        sequence = 0

        for index in range(frames):
            # Gather exactly one frame, one block at a time.
            compressor = zlib.compressobj(6)
            written = 0
            with open(spill, "wb") as frame_out:
                while written < frame_bytes:
                    while len(carry) < stride and written + len(carry) < frame_bytes:
                        try:
                            carry += next(stream)
                        except StopIteration:
                            break
                    if not carry:
                        break
                    take = min(stride, len(carry), frame_bytes - written)
                    row = bytes(carry[:take])
                    del carry[:take]
                    written += take
                    frame_out.write(compressor.compress(b"\x00" + row))
                frame_out.write(compressor.flush())

            # fcTL always precedes the frame it describes.
            out.write(_chunk(b"fcTL", struct.pack(
                ">IIIIIHHBB", sequence, width, frame_rows, 0, 0,
                max(1, int(delay_ms)), 1000, 0, 0)))
            sequence += 1

            length = os.path.getsize(spill)
            if index == 0:
                out.write(struct.pack(">I", length) + b"IDAT")
                crc = zlib.crc32(b"IDAT")
            else:
                # fdAT carries its own sequence number inside the payload,
                # so the declared length covers those four bytes too.
                out.write(struct.pack(">I", length + 4) + b"fdAT")
                crc = zlib.crc32(b"fdAT")
                marker = struct.pack(">I", sequence)
                out.write(marker)
                crc = zlib.crc32(marker, crc)
                sequence += 1

            with open(spill, "rb") as frame_in:
                for block in iter(lambda: frame_in.read(BLOCK), b""):
                    out.write(block)
                    crc = zlib.crc32(block, crc)
            out.write(struct.pack(">I", crc & 0xFFFFFFFF))
            if progress:
                progress(index + 1, frames)

        out.write(_chunk(b"IEND", b""))


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
    for index, stream in enumerate(streams):
        try:
            raw = zlib.decompress(stream)
        except zlib.error as error:
            # A damaged download fails here, inside DEFLATE, before any
            # checksum gets a chance to speak. Raising zlib's own exception
            # would hand a recipient a stack trace where the honest answer
            # is one sentence.
            raise CapsuleError(
                f"frame {index} could not be decompressed ({error}). The "
                "capsule is damaged or was re-encoded; nothing is written.")
        blob += _unfilter(raw, width, height)
    return bytes(blob)


def extract(png_path):
    """The payload, or an exception. Never a partial file presented as whole."""
    blob = read_capsule(png_path)
    if len(blob) < HEADER:
        raise CapsuleError("too small to hold a header")
    if blob[:len(MAGIC)] != MAGIC:
        raise CapsuleError(
            f"not a MACHINESOUL1 capsule (found {blob[:len(MAGIC)]!r}). A re-encoded "
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


def _chunks_of(handle):
    """Walk PNG chunks without holding the file."""
    if handle.read(8) != b"\x89PNG\r\n\x1a\n":
        raise CapsuleError("not a PNG")
    while True:
        head = handle.read(8)
        if len(head) < 8:
            return
        length = struct.unpack(">I", head[:4])[0]
        kind = head[4:8]
        yield kind, length, handle
        handle.read(4)                     # trailing CRC
        if kind == b"IEND":
            return


def extract_stream(png_path, out_path, progress=None):
    """Extract a capsule of any size without holding it.

    A decompiler that needs as much memory as the archive is not a
    decompiler anyone can run, which would make a capsule-only release a
    capsule nobody opens.

    Only filter 0 is handled here, which is what both builders emit. A
    capsule that has been through another encoder is refused rather than
    guessed at, and would not survive re-encoding anyway.
    """
    stride = None
    header = bytearray()
    declared = None
    digest_declared = None
    written = 0
    running = hashlib.sha256()
    carry = bytearray()
    frames_seen = 0

    # Write beside the target and rename only once the digest agrees.
    # Opening out_path directly truncated whatever was already there before
    # a single byte had been checked, so a refused capsule destroyed an
    # existing file while the refusal said nothing was kept. It was true of
    # the payload and false of the file.
    temp_path = out_path + ".partial"
    out = open(temp_path, "wb")
    try:
        with open(png_path, "rb") as handle:
            for kind, length, source in _chunks_of(handle):
                if kind == b"IHDR":
                    body = source.read(length)
                    width, height, depth, colour = struct.unpack(">IIBB",
                                                                 body[:10])
                    if depth != 8 or colour != 6:
                        raise CapsuleError(
                            f"capsule must be 8-bit RGBA, got depth {depth} "
                            f"colour type {colour}")
                    stride = width * CHANNELS
                    continue
                if kind not in (b"IDAT", b"fdAT"):
                    source.read(length)
                    continue

                remaining = length
                if kind == b"fdAT":
                    source.read(4)
                    remaining -= 4
                frames_seen += 1
                decompressor = zlib.decompressobj()

                while remaining > 0:
                    block = source.read(min(BLOCK, remaining))
                    if not block:
                        raise CapsuleError("capsule ends inside a frame")
                    remaining -= len(block)
                    try:
                        carry += decompressor.decompress(block)
                    except zlib.error as error:
                        raise CapsuleError(
                            f"frame {frames_seen - 1} could not be "
                            f"decompressed ({error}). The capsule is damaged "
                            "or was re-encoded; nothing is kept.")

                    while len(carry) >= stride + 1:
                        if carry[0] != 0:
                            raise CapsuleError(
                                f"unsupported PNG filter {carry[0]}; this "
                                "capsule was re-encoded")
                        row = bytes(carry[1:stride + 1])
                        del carry[:stride + 1]

                        if len(header) < HEADER:
                            need = HEADER - len(header)
                            header += row[:need]
                            row = row[need:]
                            if len(header) == HEADER:
                                if bytes(header[:len(MAGIC)]) != MAGIC:
                                    raise CapsuleError(
                                        "not a MACHINESOUL1 capsule. A "
                                        "re-encoded image fails here.")
                                at = len(MAGIC)
                                version = header[at]
                                if version != VERSION:
                                    raise CapsuleError(
                                        f"capsule version {version}, this "
                                        f"reads {VERSION}")
                                declared = struct.unpack(
                                    ">Q", bytes(header[at + 1:at + 9]))[0]
                                digest_declared = bytes(
                                    header[at + 13:at + 45])
                            if not row:
                                continue

                        if declared is None:
                            continue
                        take = min(len(row), declared - written)
                        if take > 0:
                            out.write(row[:take])
                            running.update(row[:take])
                            written += take
                if progress:
                    progress(written, declared or 0)

        if declared is None:
            raise CapsuleError("no capsule header found")
        if written < declared:
            raise CapsuleError(
                f"capsule declares {declared} bytes but carries {written}; "
                "it is truncated and nothing is kept")
        if running.digest() != digest_declared:
            raise CapsuleError(
                "sha256 mismatch: the capsule declares "
                f"{digest_declared.hex()[:16]} and carries "
                f"{running.hexdigest()[:16]}. Nothing is kept -- a capsule "
                "that fails its own checksum is not the archive.")
    except BaseException:
        out.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    out.close()
    os.replace(temp_path, out_path)
    return {"length": declared, "sha256": running.hexdigest(),
            "frames": frames_seen}


def cmd_build(args):
    """A directory is tarred in memory; a file streams.

    The split is by how the payload arrives rather than by size. A release
    archive is already a file, so the path that matters for 13 GB never
    holds it.
    """
    source = args.source
    if os.path.isdir(source):
        payload = tar_directory(source)
        frames, width, height, written = build(
            payload, args.out, frames=args.frames, delay_ms=args.delay,
            description=args.describe)
        size, digest = len(payload), hashlib.sha256(payload).hexdigest()
        kind = f"tar of {source}"
    else:
        size = os.path.getsize(source)

        def tick(done, total):
            if total and (done % 200 == 0 or done == total):
                print(f"    frame {done}/{total}", flush=True)

        frames, width, height, written = build_stream(
            source, args.out, frame_rows=args.frame_rows,
            delay_ms=args.delay, description=args.describe,
            progress=tick if size > 64 * 1024 ** 2 else None)
        digest = _sha256_of_file(source).hex()
        kind = source

    print(f"capsule: {args.out}")
    print(f"  payload   {size:,} bytes  ({kind})")
    print(f"  sha256    {digest}")
    print(f"  frames    {frames} x {width}x{height} RGBA")
    print(f"  file      {written:,} bytes  ({written / max(1, size):.2f}x)")
    return 0


def cmd_describe(args):
    try:
        description = read_description(args.capsule)
    except CapsuleError as error:
        print(f"refused: {error}")
        return 1

    if description is None:
        print("no description; this capsule carries only its payload")
        return 0

    print(description)
    print()
    print("  Not covered by the payload's sha256 gate. It is a hint about "
          "the contents, not a guarantee of them.")
    return 0


def cmd_extract(args):
    # Straight to a file, without holding it. A decompiler that needs as
    # much memory as the archive is one nobody can run.
    if not args.untar:
        try:
            meta = extract_stream(args.capsule, args.out)
        except CapsuleError as error:
            print(f"refused: {error}")
            return 1
        print(f"wrote {meta['length']:,} bytes to {args.out}")
        print(f"  sha256 verified  {meta['sha256']}")
        return 0

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
    b.add_argument("--frames", type=int, default=8,
                   help="directories only; a file streams and sizes itself")
    b.add_argument("--frame-rows", type=int, default=FRAME_ROWS,
                   help="rows per frame when streaming a file")
    b.add_argument("--delay", type=int, default=120)
    b.add_argument("--describe", default=None,
                   help="plain-language description of the payload, stored "
                        "in PNG metadata. Readable WITHOUT extracting, and "
                        "therefore readable by anyone who receives the file. "
                        "Off unless given; never describe private contents.")
    b.set_defaults(func=cmd_build)

    d = sub.add_parser("describe",
                       help="print a capsule's description without decoding it")
    d.add_argument("capsule")
    d.set_defaults(func=cmd_describe)

    e = sub.add_parser("extract", help="verify a capsule and write its payload")
    e.add_argument("capsule")
    e.add_argument("--out", required=True)
    e.add_argument("--untar", action="store_true")
    e.set_defaults(func=cmd_extract)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
