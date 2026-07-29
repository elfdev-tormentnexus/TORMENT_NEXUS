"""machinespirit as a codec: compile to anchor coordinates, and back.

The operator asked how well this compiles and decompiles, and where that
might be useful. The answer has a hard ceiling that is worth stating before
any number, because it is a property of the arithmetic and not of the
implementation.

Encoding replaces a 384-dimensional vector with its cosine to each of N
anchors. The anchors span at most N dimensions, so the coordinates retain
the vector's projection onto that span and discard everything orthogonal to
it. With N < 384 that discard is guaranteed and no decoder recovers it.
Below N = 384 this is lossy by construction; the only question is how much,
and that is measured here rather than argued.

Separately and more absolutely: none of this recovers TEXT. The embedding
was already a lossy function of the words before any anchor was involved,
and nothing here inverts it. Recovering wording from an embedding needs a
trained inverse model and is approximate even then. So "decompile" means
recovering the VECTOR, and then asking whether that vector still finds the
document it came from.

Two decoders, because the cheap one is what people reach for first:

    transpose     v' = sum(c_i * a_i). One pass, no solve. Treats the
                  anchor set as if it were orthonormal, which it is not,
                  so popular directions are counted many times.
    least squares v' = A (A^T A + kI)^-1 c. Solves for the combination
                  that actually produces these coordinates. Ridge term
                  because the anchor Gram matrix is near-singular -- the
                  anchors are correlated, which is the same anisotropy
                  that makes profile() subtract the mean.

Reported per item: cosine between original and reconstruction, and whether
the reconstruction still retrieves the original out of a corpus. The second
is the one that decides whether this is useful for anything.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "assistant"))

RIDGE = 1e-3


def cosine(left, right):
    a = sum(x * x for x in left) ** 0.5 or 1.0
    b = sum(x * x for x in right) ** 0.5 or 1.0
    return sum(x * y for x, y in zip(left, right)) / (a * b)


def unit(vector):
    length = sum(x * x for x in vector) ** 0.5
    return [x / length for x in vector] if length > 0 else list(vector)


def encode(vector, anchors):
    """The compile step: one cosine per anchor. This is the whole format."""
    return [cosine(vector, anchor) for anchor in anchors]


def decode_transpose(coords, anchors):
    """The obvious decoder, kept because it is the one people try."""
    width = len(anchors[0])
    out = [0.0] * width
    for weight, anchor in zip(coords, anchors):
        for i in range(width):
            out[i] += weight * anchor[i]
    return out


def _solve(matrix, rhs):
    """Gaussian elimination with partial pivoting. Small N, pure stdlib."""
    n = len(matrix)
    grid = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda r: abs(grid[r][column]))
        if abs(grid[pivot][column]) < 1e-12:
            continue
        grid[column], grid[pivot] = grid[pivot], grid[column]
        scale = grid[column][column]
        for r in range(column + 1, n):
            factor = grid[r][column] / scale
            if factor == 0.0:
                continue
            for c in range(column, n + 1):
                grid[r][c] -= factor * grid[column][c]
    out = [0.0] * n
    for row in range(n - 1, -1, -1):
        if abs(grid[row][row]) < 1e-12:
            continue
        total = grid[row][n] - sum(grid[row][c] * out[c]
                                   for c in range(row + 1, n))
        out[row] = total / grid[row][row]
    return out


def decode_least_squares(coords, anchors, ridge=RIDGE, gram=None):
    """Solve for the combination that would produce these coordinates."""
    n = len(anchors)
    if gram is None:
        gram = gram_matrix(anchors, ridge)
    weights = _solve(gram, list(coords))
    width = len(anchors[0])
    out = [0.0] * width
    for weight, anchor in zip(weights, anchors):
        if weight == 0.0:
            continue
        for i in range(width):
            out[i] += weight * anchor[i]
    return out


def gram_matrix(anchors, ridge=RIDGE):
    """A^T A with a ridge, computed once and reused across items."""
    n = len(anchors)
    grid = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            value = sum(x * y for x, y in zip(anchors[i], anchors[j]))
            grid[i][j] = grid[j][i] = value
        grid[i][i] += ridge
    return grid


def retrieval_rank(vector, corpus, index):
    """Where the true item lands when the reconstruction does the search."""
    target = cosine(vector, corpus[index])
    return 1 + sum(1 for i, other in enumerate(corpus)
                   if i != index and cosine(vector, other) > target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--anchors", default="2",
                        help="dictionary version to encode against")
    parser.add_argument("--limit", type=int, default=24,
                        help="how many corpus chunks to round-trip")
    parser.add_argument("--corpus",
                        default=os.path.join(ROOT, "docs",
                                             "THE_STORY_OF_SABLE.md"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    os.environ["TORMENT_NEXUS_ANCHOR_VERSION"] = args.anchors
    from core import embedding_server, machinespirit

    machinespirit.ANCHOR_VERSION = args.anchors
    machinespirit.reset_cache()

    anchors = machinespirit.anchor_vectors(True, True)
    if not anchors:
        print("the pooled embedding server is not answering; nothing measured")
        return 1
    texts = machinespirit.anchor_texts(True, True)
    anchors = [unit(a) for a in anchors[:len(texts)]]

    raw = open(args.corpus, encoding="utf-8").read()
    chunks = [p.strip().replace("\n", " ") for p in raw.split("\n\n")]
    chunks = [c[:800] for c in chunks if len(c) > 120][:args.limit]
    corpus = embedding_server.embed(chunks, timeout=120)
    if not corpus:
        print("could not embed the corpus")
        return 1
    corpus = [unit(v) for v in corpus]

    print(f"{len(anchors)} anchors (v{args.anchors}), {len(corpus[0])} "
          f"dimensions, {len(corpus)} chunks")
    print(f"anchor span covers at most {len(anchors)} of "
          f"{len(corpus[0])} dimensions "
          f"({min(1.0, len(anchors) / len(corpus[0])):.0%})\n")

    gram = gram_matrix(anchors)
    rows = []
    for index, vector in enumerate(corpus):
        coords = encode(vector, anchors)
        rebuilt = {
            "transpose": decode_transpose(coords, anchors),
            "least squares": decode_least_squares(coords, anchors, gram=gram),
        }
        row = {"chunk": index}
        for name, candidate in rebuilt.items():
            row[name] = {
                "cosine": cosine(vector, candidate),
                "rank": retrieval_rank(candidate, corpus, index),
            }
        rows.append(row)

    if args.json:
        print(json.dumps(rows, indent=1))
        return 0

    print(f"{'decoder':<16} {'mean cosine':>12} {'worst':>8} "
          f"{'recovered@1':>13} {'median rank':>12}")
    print("-" * 66)
    for name in ("transpose", "least squares"):
        cosines = [r[name]["cosine"] for r in rows]
        ranks = [r[name]["rank"] for r in rows]
        hit = sum(1 for r in ranks if r == 1) / len(ranks)
        median = sorted(ranks)[len(ranks) // 2]
        print(f"{name:<16} {sum(cosines) / len(cosines):>12.4f} "
              f"{min(cosines):>8.4f} {hit:>12.0%} {median:>12}")

    print("\nrecovered@1 is the reconstruction finding its own chunk again.")
    print("Neither decoder recovers the text; both recover a vector.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
