"""Does a codebook-of-vectors pay for itself at this project's scale?

Product quantisation splits each vector into M sub-vectors, learns K
centroids per subspace, and stores each vector as M small indices. The
codebook is the decompiler and the codebook is itself vectors, which is the
recursion worth testing.

The cost has a fixed part and a per-vector part, and that is the whole
question:

    codebook  = K * D * 4 bytes        (independent of M)
    per vector= M bytes                (at K <= 256, one byte an index)

So it is a fixed toll paid up front against a much cheaper per-vector rate.
Below some corpus size the toll is never recovered.
"""
import json
import os
import sys

import numpy as np

ROOT = r"C:\Users\evely\Documents\AI_Project"

cache = json.load(open(os.path.join(ROOT, "assistant", "cache",
                                    "embeddings.json")))
vectors = np.array(list(cache["vectors"].values()), dtype=np.float32)
story = np.array(json.load(open(
    r"C:\Users\evely\AppData\Local\Temp\claude"
    r"\C--Users-evely-Documents-AI-Project"
    r"\ad0616ed-0b9b-44d3-b463-4567fcc9fc8c\scratchpad\story_vectors.json"
)), dtype=np.float32)

data = np.vstack([vectors, story])
N, D = data.shape
print(f"corpus: {N} vectors x {D} dims  "
      f"({vectors.shape[0]} from cache + {story.shape[0]} from the story)")
print()


def kmeans(x, k, iters=25, seed=0):
    rng = np.random.default_rng(seed)
    centres = x[rng.choice(len(x), size=min(k, len(x)), replace=False)].copy()
    if len(centres) < k:                       # fewer points than centroids
        pad = rng.normal(x.mean(0), x.std(0) + 1e-6, size=(k - len(centres),
                                                           x.shape[1]))
        centres = np.vstack([centres, pad.astype(np.float32)])
    for _ in range(iters):
        d = ((x[:, None, :] - centres[None, :, :]) ** 2).sum(-1)
        assign = d.argmin(1)
        for j in range(k):
            hit = x[assign == j]
            if len(hit):
                centres[j] = hit.mean(0)
    return centres


def cosine_rows(a, b):
    na = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    nb = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return (na * nb).sum(1)


print(f"{'scheme':<26}{'bytes':>10}{'vs float32':>12}{'mean cos':>11}")
print("-" * 59)

raw = N * D * 4
print(f"{'float32 raw':<26}{raw:>10,}{'1.00x':>12}{'1.000000':>11}")

u8 = N * D
lo, hi = data.min(), data.max()
q = np.round((data - lo) / ((hi - lo) / 255)).clip(0, 255)
deq = lo + q * ((hi - lo) / 255)
print(f"{'uint8 quantised':<26}{u8:>10,}{raw / u8:>11.2f}x"
      f"{cosine_rows(data, deq).mean():>11.6f}")

for M, K in ((8, 256), (8, 64), (8, 16), (16, 256)):
    sub = D // M
    codebook_bytes = K * D * 4
    bits = 8 if K <= 256 else 16
    codes_bytes = N * M * (bits // 8)
    total = codebook_bytes + codes_bytes

    rebuilt = np.zeros_like(data)
    for m in range(M):
        piece = data[:, m * sub:(m + 1) * sub]
        centres = kmeans(piece, K, seed=m)
        d = ((piece[:, None, :] - centres[None, :, :]) ** 2).sum(-1)
        rebuilt[:, m * sub:(m + 1) * sub] = centres[d.argmin(1)]

    cos = cosine_rows(data, rebuilt).mean()
    label = f"PQ M={M} K={K}"
    print(f"{label:<26}{total:>10,}{raw / total:>11.2f}x{cos:>11.6f}")

print()
print("crossover, where the codebook toll is finally repaid:")
for K in (16, 64, 256):
    cb = K * D * 4
    n_vs_f32 = cb / (D * 4 - 8)
    n_vs_u8 = cb / (D - 8) if D > 8 else float("inf")
    print(f"  K={K:<4} codebook {cb:>9,} bytes   "
          f"beats float32 above {n_vs_f32:>8,.0f} vectors   "
          f"beats uint8 above {n_vs_u8:>8,.0f}")
print()
print(f"this corpus is {N} vectors.")
