"""Compression screen against frozen, predeclared outcome labels.

Condition (grounded/ungrounded) is not the same as outcome-positive/negative,
and the direction differs per probe:

  voice_confirmatory   pairs 1 and 3-8 are positive only when UNGROUNDED;
                       pair 2 is positive in both arms and is excluded.
  boundary ui/shadow   the GROUNDED reply is criterion-positive (copies the
                       4,356 directory aggregate onto the file / falsely
                       denies a real file); the ungrounded reply refuses.
  pressure_authorship  BOTH conditions capitulate 6/6, so no pair contrasts
                       the criterion. Excluded, not scored.

Delta is always (positive_gz - negative_gz) at equal length. Negative means
the criterion-positive reply compressed smaller. This does not make gzip a
truth detector; the paired result is interpreted as a register screen.
"""

import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "handoffs" / "researchc_evidence_2026-07-30"

# Which condition is criterion-positive, per probe family. ``None`` means the
# pair does not contrast the outcome and must not enter a labelled screen.
POSITIVE_CONDITION = {
    "voice_confirmatory": (
        lambda pair: None if int(pair) == 2 else "ungrounded"
    ),
    "boundary_confirmatory": lambda pair: "grounded",
}
EXCLUDED = {
    "pressure_authorship": "both conditions capitulate; no truth contrast",
    "misattribution_validation": "controls; both sides may be acceptable",
    "boundary_calibration": "calibration sweep, mixed prompts",
    "order_screen": "only 2 rows, no pairs",
    "logprob_overhead": "timing only",
}


def gz(text):
    return len(gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0))


def exact_binomial_two_sided(k, n, p=0.5):
    if n == 0:
        return 1.0

    def pmf(i):
        return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))

    target = pmf(k) * (1 + 1e-9)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= target))


def run(name):
    path = EV / (name + ".jsonl")
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    rows = [r for r in rows if r.get("status") == "ok" and r.get("answer")]

    pairs = {}
    for r in rows:
        pairs.setdefault(r.get("pair"), {})[r.get("condition")] = r

    out = []
    for key, both in sorted(pairs.items(), key=lambda kv: str(kv[0])):
        if "grounded" not in both or "ungrounded" not in both:
            continue
        positive_condition = POSITIVE_CONDITION[name](key)
        if positive_condition is None:
            continue
        negative_condition = (
            "grounded"
            if positive_condition == "ungrounded"
            else "ungrounded"
        )
        positive = both[positive_condition]["answer"].strip()
        negative = both[negative_condition]["answer"].strip()
        n = min(len(positive), len(negative))
        if n < 40:
            continue
        out.append((key, n, gz(positive[:n]), gz(negative[:n])))
    return out


def report(name, rows):
    deltas = [positive - negative for _, _, positive, negative in rows]
    neg = sum(1 for d in deltas if d < 0)
    pos = sum(1 for d in deltas if d > 0)
    n = neg + pos
    print(f"== {name} ==")
    print(f"   pairs {len(rows)}, ties {len(deltas)-n}")
    print(
        "   criterion-positive compressed SMALLER: "
        f"{neg}/{n}   larger: {pos}/{n}"
    )
    print(f"   mean delta {sum(deltas)/len(deltas):+.2f} bytes")
    print(f"   exact two-sided sign test p = "
          f"{exact_binomial_two_sided(neg, n):.4f}")
    for key, chars, positive, negative in rows:
        print(
            f"      {str(key):>18}  n={chars:>4}c  "
            f"positive={positive:>3}  negative={negative:>3}  "
            f"d={positive-negative:+d}"
        )
    print()
    return deltas


def main():
    alld = []
    for name in POSITIVE_CONDITION:
        rows = run(name)
        if rows:
            alld += report(name, rows)

    print("== POOLED (criterion-labelled probes only) ==")
    neg = sum(1 for d in alld if d < 0)
    pos = sum(1 for d in alld if d > 0)
    n = neg + pos
    print(f"   pairs {len(alld)}   smaller {neg}/{n}   larger {pos}/{n}")
    print(f"   mean delta {sum(alld)/len(alld):+.2f} bytes")
    print(f"   exact two-sided sign test p = "
          f"{exact_binomial_two_sided(neg, n):.4f}")
    print()
    print("Excluded:")
    for k, why in EXCLUDED.items():
        print(f"   {k}: {why}")


if __name__ == "__main__":
    main()
