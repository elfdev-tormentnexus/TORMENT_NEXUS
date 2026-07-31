"""Re-analyse the gzip compression screen from the frozen researchC rows.

The claim under test, from the entropy inversion: fabricated text compresses
better than truthful text. The original screen reported prompt-dependent
results. This redoes it as a strict paired test using the seed-matched
grounded/ungrounded pairs already recorded in the evidence, and reports an
exact binomial (sign) test rather than a mean byte difference.
"""

import glob
import gzip
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "handoffs" / "researchc_evidence_2026-07-30"


def gz(text):
    """Compressed size with a fixed, content-independent header cost."""
    return len(gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0))


def load(name):
    path = EV / (name + ".jsonl")
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return [r for r in rows if r.get("status") == "ok" and r.get("answer")]


def exact_binomial_two_sided(k, n, p=0.5):
    """Exact two-sided binomial p-value, no scipy."""
    if n == 0:
        return 1.0

    def pmf(i):
        return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))

    target = pmf(k) * (1 + 1e-9)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= target))


def paired_by(rows):
    """Group seed-matched grounded/ungrounded rows by their pair id."""
    pairs = {}
    for r in rows:
        pairs.setdefault(r.get("pair"), {})[r.get("condition")] = r
    return {
        k: v for k, v in pairs.items()
        if "grounded" in v and "ungrounded" in v
    }


def analyse(name):
    rows = load(name)
    pairs = paired_by(rows)
    if not pairs:
        return name, len(rows), None

    results = []
    for key, both in sorted(pairs.items(), key=lambda kv: str(kv[0])):
        g = both["grounded"]["answer"].strip()
        u = both["ungrounded"]["answer"].strip()
        n = min(len(g), len(u))
        if n < 40:
            continue
        # Equal-length prefixes so length cannot drive the comparison.
        gg, uu = gz(g[:n]), gz(u[:n])
        results.append({
            "pair": key,
            "chars": n,
            "grounded_gz": gg,
            "ungrounded_gz": uu,
            "delta": gg - uu,
        })

    return name, len(rows), results


def main():
    print("Equal-length gzip, seed-matched pairs.")
    print("delta = grounded_gz - ungrounded_gz.")
    print("Negative delta = the grounded reply compressed smaller. "
          "This is condition-labelled, not truth-labelled.\n")

    grand = []
    for path in sorted(glob.glob(str(EV / "*.jsonl"))):
        name = os.path.basename(path)[:-6]
        name, nrows, res = analyse(name)
        if not res:
            print(f"{name}: {nrows} rows, no usable seed-matched pairs")
            continue

        deltas = [r["delta"] for r in res]
        neg = sum(1 for d in deltas if d < 0)
        pos = sum(1 for d in deltas if d > 0)
        ties = sum(1 for d in deltas if d == 0)
        n = neg + pos
        p = exact_binomial_two_sided(neg, n) if n else 1.0
        mean = sum(deltas) / len(deltas)

        print(f"== {name} ==")
        print(f"   usable pairs: {len(res)}  (ties dropped: {ties})")
        print(f"   grounded smaller: {neg}/{n}   larger: {pos}/{n}")
        print(f"   mean delta: {mean:+.2f} bytes")
        print(f"   exact two-sided sign test p = {p:.4f}")
        for r in res:
            print(f"      pair {str(r['pair']):>18}  n={r['chars']:>4}c  "
                  f"g={r['grounded_gz']:>3}  u={r['ungrounded_gz']:>3}  "
                  f"d={r['delta']:+d}")
        print()
        grand.extend(deltas)

    if grand:
        neg = sum(1 for d in grand if d < 0)
        pos = sum(1 for d in grand if d > 0)
        n = neg + pos
        p = exact_binomial_two_sided(neg, n) if n else 1.0
        print("== POOLED ACROSS ALL PROBES ==")
        print(f"   pairs: {len(grand)}   grounded smaller: {neg}/{n}   "
              f"larger: {pos}/{n}")
        print(f"   mean delta: {sum(grand)/len(grand):+.2f} bytes")
        print(f"   exact two-sided sign test p = {p:.4f}")


if __name__ == "__main__":
    main()
