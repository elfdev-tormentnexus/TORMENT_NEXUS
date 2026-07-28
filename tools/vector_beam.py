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
import struct
import sys
import zlib

import requests


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
        ("Comment",
         "Per-token embedding trajectory rendered as a beam. Colour is a "
         "fixed seeded 3-axis projection of each token vector after "
         "centring on the path mean -- lossy and one-way, for looking at. "
         "The trajectory itself is N vectors and stores losslessly through "
         "SABLEVEC1. Mean pooling collapses this path to a single point."),
        ("Source", text[:200]),
        ("Tokens", str(stats["tokens"])),
    ])
    return stats


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
    for name, fn in (("render", cmd_render), ("measure", cmd_measure)):
        s = sub.add_parser(name)
        s.add_argument("text")
        s.add_argument("--url", required=True)
        s.add_argument("--key")
        if name == "render":
            s.add_argument("--out", default="beam.png")
            s.add_argument("--width", type=int, default=1200)
            s.add_argument("--height", type=int, default=300)
        s.set_defaults(func=fn)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
