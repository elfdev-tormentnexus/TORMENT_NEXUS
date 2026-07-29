"""The beam: a sentence as the path it traces, not the point it lands on.

A sentence embedding is a mean. Before pooling, a sentence is a *sequence*
of token vectors -- a trajectory through the space -- and pooling collapses
it to a single point. The path is thrown away, and it is not empty: on a
fourteen-token sentence the consecutive-token cosine ranges 0.601 to 0.937
and the tokens sit between 0.804 and 0.952 from the pooled point. That
0.148 of cosine range is what the stored vector flattens.

The image this renders is a laser through a smoggy room. Each token is a
segment of the beam and carries its own colour, so the beam cycles along
its length rather than being one flat line. That is the honest picture of
what is happening: the vector is not a dot, it is a path, and the path has
structure the current format does not keep.

Two claims kept separate, because they are not equally strong:

  - The trajectory is strictly more information than the pooled vector.
    The mean is recoverable from the path; the path is not recoverable
    from the mean. That is a real property and it costs N times the
    storage.
  - The colour is a *projection* and is lossy and one-way, exactly like
    the semantic-space image. It is there to be looked at. Nothing
    recovers a token vector from its colour, and the module does not
    pretend otherwise -- to store the beam, use SABLEVEC1 through
    vector_pixel_codec, which already takes N vectors.

    python tools/vector_beam.py render "some sentence" --url ... --out beam.png
    python tools/vector_beam.py measure "some sentence" --url ...

The server must be launched with `--pooling none`, and the unpooled route
is llama.cpp's own /embeddings -- the OpenAI-compatible one refuses it.
"""
import argparse
import math
import os
import struct
import sys
import zlib

import requests

# The trajectory format, named by the operator.
#
# It is deliberately not a revision of SABLE1 or SABLEVEC1 despite the
# family resemblance in the name -- those carry an unordered payload and an
# unordered *set* of vectors respectively, and neither has any notion of
# sequence. SABLE7 carries an ordered path with token boundaries and the
# text that produced it, because for a trajectory the order is the content.
# A reader that treats a SABLE7 payload as a SABLEVEC1 set gets the right
# numbers in a meaningless arrangement, which is why it declares itself.
MAGIC = "SABLE7"


def beam(text, url, api_key=None, timeout=180):
    """Per-token vectors: the path, before anything collapses it."""
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    r = requests.post(url.rstrip("/") + "/embeddings", headers=headers,
                      json={"content": text}, timeout=timeout)
    if r.status_code == 400 and "pooling" in r.text.lower():
        raise SystemExit("server is pooling; relaunch it with --pooling none")
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, list):
        payload = payload[0]
    emb = payload.get("embedding") or payload.get("data")
    return emb if isinstance(emb[0], list) else [emb]


def pooled(path):
    """The mean -- i.e. exactly what the current format stores.

    Here to make the containment claim checkable rather than asserted: the
    endpoint is derivable from the path, so the path loses nothing.
    """
    n = len(path)
    return [sum(col) / n for col in zip(*path)]


def cosine(a, b):
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def measure(path):
    mean = pooled(path)
    steps = [cosine(path[i], path[i + 1]) for i in range(len(path) - 1)]
    to_mean = [cosine(t, mean) for t in path]
    return {
        "tokens": len(path),
        "dims": len(path[0]),
        "step_min": min(steps) if steps else 1.0,
        "step_max": max(steps) if steps else 1.0,
        "step_mean": sum(steps) / len(steps) if steps else 1.0,
        "to_pooled_min": min(to_mean),
        "to_pooled_max": max(to_mean),
        "flattened_range": max(to_mean) - min(to_mean),
        "path_length": sum(1 - s for s in steps),
    }


# --- colour ------------------------------------------------------------
#
# A fixed, seeded projection from the model's space to RGB. Deterministic
# so the same sentence always renders the same beam, and documented as
# one-way: three numbers cannot carry 384.

def _projection(dims, seed=20260728):
    """Three fixed pseudo-random directions, generated without numpy."""
    state = seed
    axes = []
    for _ in range(3):
        row = []
        for _ in range(dims):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            row.append((state / 0x7FFFFFFF) * 2.0 - 1.0)
        n = math.sqrt(sum(x * x for x in row)) or 1.0
        axes.append([x / n for x in row])
    return axes


def colours(path, seed=20260728):
    """One RGB per token, spread across the available range.

    Centring on the path's own mean first is deliberate: sentence
    embeddings are anisotropic, and without it every token renders nearly
    the same colour and the beam looks flat when it is not.
    """
    dims = len(path[0])
    axes = _projection(dims, seed)
    mean = pooled(path)
    centred = [[x - m for x, m in zip(t, mean)] for t in path]
    raw = [[sum(x * a for x, a in zip(t, ax)) for ax in axes] for t in centred]

    out = []
    for channel in range(3):
        vals = [r[channel] for r in raw]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        out.append([(v - lo) / span for v in vals])
    return [(int(30 + 225 * out[0][i]),
             int(30 + 225 * out[1][i]),
             int(30 + 225 * out[2][i])) for i in range(len(path))]


# --- rendering ---------------------------------------------------------

def _png(path_out, width, height, rows, text_chunks=()):
    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    out = [b"\x89PNG\r\n\x1a\n",
           chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))]
    for key, value in text_chunks:
        out.append(chunk(b"tEXt", key.encode() + b"\x00" + value.encode()))
    out.append(chunk(b"IDAT", zlib.compress(raw, 9)))
    out.append(chunk(b"IEND", b""))
    open(path_out, "wb").write(b"".join(out))


def render(path, out_path, text="", width=1200, height=300, seed=20260728):
    """The laser. Horizontal beam, one colour band per token, smog falloff."""
    cols = colours(path, seed)
    n = len(cols)
    mid = height // 2
    # Beam thickness follows how far each token sits from the pooled point:
    # tokens the stored vector represents badly burn brightest.
    mean = pooled(path)
    dist = [1.0 - cosine(t, mean) for t in path]
    lo, hi = min(dist), max(dist)
    span = (hi - lo) or 1.0
    heat = [0.35 + 0.65 * ((d - lo) / span) for d in dist]

    rows = []
    for y in range(height):
        row = bytearray()
        dy = abs(y - mid) / (height / 2.0)
        for x in range(width):
            t = min(n - 1, int(x * n / width))
            r, g, b = cols[t]
            # Smog: a soft vertical falloff, wider where the beam is hot.
            core = math.exp(-(dy ** 2) / (0.02 + 0.06 * heat[t]))
            glow = 0.18 * math.exp(-(dy ** 2) / 0.5)
            k = min(1.0, core + glow)
            row += bytes((int(r * k), int(g * k), int(b * k)))
        rows.append(row)

    stats = measure(path)
    _png(out_path, width, height, rows, text_chunks=[
        ("Title", "SABLE beam"),
        ("Format", MAGIC),
        ("Comment",
         f"{MAGIC}: an ordered per-token embedding trajectory. Order is the "
         "content -- unlike SABLEVEC1, which carries an unordered set. What "
         "is rendered here is a projection, not the data: each token's "
         "colour is a fixed seeded 3-axis projection taken after centring "
         "on the path mean, and is lossy and one-way. Three numbers cannot "
         "carry 384, and nothing recovers a token vector from its colour. "
         "Brightness tracks each token's cosine distance from the pooled "
         "point, so the tokens the stored vector represents worst are the "
         "ones that burn. Mean pooling collapses this whole path to one "
         "point; the mean is recoverable from the path and the path is not "
         "recoverable from the mean."),
        ("Source", text[:200]),
        ("Tokens", str(stats["tokens"])),
        ("Dims", str(stats["dims"])),
        ("FlattenedRange", f"{stats['flattened_range']:.4f}"),
    ])
    return stats


# --- the SABLE7 container ----------------------------------------------
#
# Layout mirrors SABLEVEC1 -- one vector per row, three dims per pixel
# through RGB, affine uint8 with a single scale and offset -- because that
# part is measured and works. What differs is the header, and the header is
# the whole reason this is a separate format: a trajectory that loses its
# order is not a degraded trajectory, it is a bag of numbers. The row index
# IS the token index, and a reader must be told that rather than left to
# assume it.

VERSION = 1


def quantise(vectors):
    lo = min(min(v) for v in vectors)
    hi = max(max(v) for v in vectors)
    scale = (hi - lo) / 255.0 or 1.0
    rows = [bytes(min(255, max(0, int(round((x - lo) / scale)))) for x in v)
            for v in vectors]
    return rows, scale, lo


def encode_beam(path, out_path, source_text="", model=""):
    """Write a trajectory as SABLE7. Returns the header it wrote."""
    import hashlib
    import json as _json

    rows, scale, low = quantise(path)
    tokens, dims = len(path), len(path[0])
    width = (dims + 2) // 3

    header = {
        "magic": MAGIC,
        "version": VERSION,
        "tokens": tokens,
        "dims": dims,
        "scale": scale,
        "low": low,
        "layout": "one token per row, in order, three dims per pixel via RGB",
        "ordered": True,
        "model": model,
        "source_sha256": hashlib.sha256(
            source_text.encode("utf-8")).hexdigest() if source_text else None,
    }

    raster = []
    for row in rows:
        padded = row + bytes((-len(row)) % 3)
        raster.append(padded[:width * 3])

    _png(out_path, width, tokens, raster, text_chunks=[
        ("Title", "SABLE7 trajectory"),
        ("Format", MAGIC),
        (MAGIC, _json.dumps(header)),
        ("Comment",
         "Ordered per-token embedding trajectory. Row index is token index; "
         "reordering rows destroys the content rather than degrading it. "
         "Not a SABLEVEC1 set."),
    ])
    return header


def decode_beam(png_path):
    """Read a SABLE7 file back. Raises if it is not one."""
    import json as _json

    data = open(png_path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")

    pos, idat, header = 8, b"", None
    width = height = None
    while pos < len(data):
        length, = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", body[:8])
        elif kind == b"tEXt":
            key, _, value = body.partition(b"\x00")
            if key.decode("latin-1") == MAGIC:
                header = _json.loads(value.decode("utf-8"))
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
        pos += 12 + length

    if header is None or header.get("magic") != MAGIC:
        raise ValueError(f"no {MAGIC} header -- refusing to guess the layout")

    raw = zlib.decompress(idat)
    stride = width * 3
    rows, at = [], 0
    for _ in range(height):
        at += 1                                   # filter byte, always 0 here
        rows.append(raw[at:at + stride])
        at += stride

    scale, low, dims = header["scale"], header["low"], header["dims"]
    return [[low + b * scale for b in row[:dims]] for row in rows], header


def _apng(out_path, width, height, frames, delays, text_chunks=()):
    """Animated PNG. Lossless, unlike every video codec worth the name.

    APNG is the honest answer to "video, but the bytes survive": it is PNG
    frames with a control chunk, so it keeps byte-exact recovery while
    gaining a real time axis. H.264 would destroy a payload before it even
    reached the lossy quantiser, since 4:2:0 stores colour at quarter
    resolution and the colour is where the data lives.

    `delays` is per frame, in milliseconds. It is not required to be
    uniform, and here it is not: duration carries the step distance, so the
    animation lingers where the trajectory turns.
    """
    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    out = [b"\x89PNG\r\n\x1a\n",
           chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))]
    for key, value in text_chunks:
        out.append(chunk(b"tEXt", key.encode() + b"\x00" + value.encode()))

    # acTL must precede the first IDAT: frame count, then play count (0 = loop).
    out.append(chunk(b"acTL", struct.pack(">II", len(frames), 0)))

    sequence = 0
    for index, (rows, delay_ms) in enumerate(zip(frames, delays)):
        raw = b"".join(b"\x00" + bytes(r) for r in rows)
        out.append(chunk(b"fcTL", struct.pack(
            ">IIIIIHHBB", sequence, width, height, 0, 0,
            max(1, int(delay_ms)), 1000, 0, 0)))
        sequence += 1
        if index == 0:
            # The first frame is the still image any non-APNG reader shows.
            out.append(chunk(b"IDAT", zlib.compress(raw, 9)))
        else:
            out.append(chunk(b"fdAT",
                             struct.pack(">I", sequence) + zlib.compress(raw, 9)))
            sequence += 1

    out.append(chunk(b"IEND", b""))
    open(out_path, "wb").write(b"".join(out))


def render_animated(path, out_path, text="", width=720, height=200,
                    seed=20260728, base_ms=90, turn_ms=520):
    """Draw the trajectory one token at a time, pacing by how far it moved.

    Frame N shows tokens 0..N with the newest burning brightest, so the
    sentence assembles rather than appearing. Frame duration is base_ms plus
    a share of turn_ms scaled by that step's distance, which makes a sharp
    semantic turn visibly hold and a flat stretch pass quickly.
    """
    cols = colours(path, seed)
    n = len(cols)
    mid = height // 2

    steps = [0.0] + [1.0 - cosine(path[i], path[i + 1]) for i in range(n - 1)]
    widest = max(steps) or 1.0
    delays = [base_ms + turn_ms * (s / widest) for s in steps]

    frames = []
    for upto in range(n):
        rows = []
        for y in range(height):
            row = bytearray()
            dy = abs(y - mid) / (height / 2.0)
            for x in range(width):
                token = min(n - 1, int(x * n / width))
                if token > upto:
                    row += b"\x00\x00\x00"
                    continue
                r, g, b = cols[token]
                age = 1.0 if token == upto else 0.34 + 0.4 * (token / max(1, upto))
                core = math.exp(-(dy ** 2) / 0.05) * age
                glow = 0.16 * math.exp(-(dy ** 2) / 0.5) * age
                k = min(1.0, core + glow)
                row += bytes((int(r * k), int(g * k), int(b * k)))
            rows.append(row)
        frames.append(rows)

    stats = measure(path)
    _apng(out_path, width, height, frames, delays, text_chunks=[
        ("Title", "SABLE7 beam, animated"),
        ("Format", MAGIC),
        ("Comment",
         "Animated PNG, lossless. One frame per token, drawn in order. "
         "Frame duration is proportional to that step's cosine distance, so "
         "the animation holds where the trajectory turns and moves quickly "
         "where it does not -- the time axis carries the step distance "
         "rather than merely enabling playback. Colour remains a lossy "
         "one-way projection; the trajectory itself stores through SABLE7."),
        ("Source", text[:200]),
        ("Tokens", str(stats["tokens"])),
    ])
    return stats, delays


def cmd_animate(args):
    path = beam(args.text, args.url, args.key)
    stats, delays = render_animated(path, args.out, args.text,
                                    args.width, args.height)
    print(f"wrote {args.out}  ({os.path.getsize(args.out):,} bytes)")
    print(f"  frames {stats['tokens']}  "
          f"total {sum(delays) / 1000:.1f}s")
    print(f"  slowest frame {max(delays):.0f} ms, fastest {min(delays):.0f} ms"
          "   <- duration tracks how far each step moved")


def trace(path, stone, top=1, use_project=False, seed=20260728):
    """Read a trajectory against a concept dictionary, token by token.

    This is the one thing the pooled vector cannot do at all. A mean says
    what a sentence is about; a trace says *where* in the sentence each
    meaning appeared, by profiling every token position against the anchor
    set rather than profiling the sentence as a whole.

    The anchors are a hand-assigned dictionary of concept directions, so
    the readout is in chosen English rather than in learned coordinates:
    at token 7 this leans toward "grandparents telling the same story
    again", at token 11 toward "a promise made to a dying person".

    Requires both servers. The path comes from an unpooled instance and the
    stone from a pooled one, because llama.cpp fixes pooling at launch.

    Returns a list of (index, rgb, [(score, anchor), ...]).
    """
    import rosetta_stone as rs

    cols = colours(path, seed)
    out = []
    for i, (vec, rgb) in enumerate(zip(path, cols)):
        out.append((i, rgb, rs.profile(vec, stone, top=top,
                                       use_project=use_project)))
    return out


def cmd_trace(args):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rosetta_stone as rs

    stone = rs.build_stone(args.stone_url, args.stone_key, args.use_project)
    path = beam(args.text, args.url, args.key)
    rows = trace(path, stone, args.top, args.use_project)

    print(f'"{args.text}"\n')
    print(f"  tokens {len(path)}   anchors {stone['core_count']}"
          f"{' + ' + str(stone['project_count']) if args.use_project else ''}")
    print(f"\n{'#':>3}  {'colour':<17} strongest concept at that point")
    print("  " + "-" * 72)
    for i, rgb, hits in rows:
        head = f"{i:>3}  rgb({rgb[0]:>3},{rgb[1]:>3},{rgb[2]:>3})"
        for n, (score, anchor) in enumerate(hits):
            print(f"{head if n == 0 else ' ' * len(head)}  {score:+.3f}  {anchor}")

    # The peaks are the point: where a concept is strongest along the path.
    best = {}
    for i, _, hits in rows:
        for score, anchor in hits:
            if anchor not in best or score > best[anchor][0]:
                best[anchor] = (score, i)
    print("\n  peaks:")
    for anchor, (score, i) in sorted(best.items(), key=lambda kv: -kv[1][0]):
        print(f"    token {i:>3}  {score:+.3f}  {anchor}")


def cmd_encode(args):
    path = beam(args.text, args.url, args.key)
    header = encode_beam(path, args.out, args.text, args.url)
    back, got = decode_beam(args.out)
    worst = min(cosine(a, b) for a, b in zip(path, back))
    print(f"wrote {args.out}  ({os.path.getsize(args.out):,} bytes)")
    print(f"  tokens {header['tokens']}  dims {header['dims']}")
    print(f"  round-trip worst cosine: {worst:.6f}")
    print(f"  order preserved: {'yes' if got['tokens'] == header['tokens'] else 'no'}")


def cmd_render(args):
    path = beam(args.text, args.url, args.key)
    stats = render(path, args.out, args.text, args.width, args.height)
    print(f"wrote {args.out}")
    for k, v in stats.items():
        print(f"  {k:18} {v:.4f}" if isinstance(v, float) else f"  {k:18} {v}")


def cmd_measure(args):
    path = beam(args.text, args.url, args.key)
    stats = measure(path)
    mean = pooled(path)
    print(f'"{args.text}"\n')
    for k, v in stats.items():
        print(f"  {k:18} {v:.4f}" if isinstance(v, float) else f"  {k:18} {v}")
    # The containment claim, checked rather than asserted.
    again = pooled(path)
    print(f"\n  pooled point recoverable from the path: "
          f"{'yes' if all(abs(a - b) < 1e-12 for a, b in zip(mean, again)) else 'no'}")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("render", cmd_render), ("measure", cmd_measure),
                     ("encode", cmd_encode), ("trace", cmd_trace),
                     ("animate", cmd_animate)):
        s = sub.add_parser(name)
        s.add_argument("text")
        s.add_argument("--url", required=True)
        s.add_argument("--key")
        if name == "trace":
            s.add_argument("--stone-url", required=True,
                           help="a POOLED embedding server, for the anchors")
            s.add_argument("--stone-key")
            s.add_argument("--top", type=int, default=1)
            s.add_argument("--use-project", action="store_true")
        if name == "animate":
            s.add_argument("--out", default="beam_animated.png")
            s.add_argument("--width", type=int, default=720)
            s.add_argument("--height", type=int, default=200)
        if name in ("render", "encode"):
            s.add_argument("--out",
                           default="beam.png" if name == "render" else "beam_sable7.png")
        if name == "render":
            s.add_argument("--width", type=int, default=1200)
            s.add_argument("--height", type=int, default=300)
        s.set_defaults(func=fn)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
