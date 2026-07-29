"""Map how removing the other half of a text changes token trajectories.

This is a classical context-dependence experiment.  It runs the complete text,
its prefix, and its suffix through the same unpooled embedding server, then
compares each retained content-token vector with its full-context counterpart.
The tool refuses a cut whose token accounting changes, rather than pretending
that two unlike positions are corresponding tokens.

It does not split a model token, change model state, or make a claim about
physical entanglement.  It measures contextual coupling in a transformer.
"""

import argparse
import json
import math
import os
import re
import sys

import requests


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pooling_probe import _key, token_vectors  # noqa: E402


WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def split_at_word_midpoint(text):
    """Return a non-empty prefix/suffix split at a source-word boundary."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    spans = list(WORD.finditer(text))
    if len(spans) < 2:
        raise ValueError("need at least two words to make a bisection")
    cut_after = spans[(len(spans) // 2) - 1].end()
    suffix_start = cut_after
    while suffix_start < len(text) and text[suffix_start].isspace():
        suffix_start += 1
    prefix = text[:cut_after].rstrip()
    suffix = text[suffix_start:].lstrip()
    if not prefix or not suffix:
        raise ValueError("word midpoint did not create two non-empty texts")
    return prefix, suffix, suffix_start


def cosine(left, right):
    if len(left) != len(right):
        raise ValueError("vectors have different dimensions")
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    if left_norm <= 0.0 or right_norm <= 0.0:
        raise ValueError("cannot compare a zero vector")
    return math.fsum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _content(path):
    """Drop the known leading/trailing specials returned by this BERT server."""
    if not path or len(path) < 3:
        raise ValueError("need a path with CLS, content, and SEP rows")
    width = len(path[0])
    if not width or any(len(row) != width for row in path):
        raise ValueError("trajectory rows have inconsistent dimensions")
    return path[1:-1]


def _side_rows(full_rows, half_rows, side):
    """Score corresponding retained content rows against their full context."""
    if len(full_rows) != len(half_rows):
        raise ValueError("the cut changed content-token accounting")
    rows = []
    for index, (full, half) in enumerate(zip(full_rows, half_rows)):
        distance = (len(full_rows) - index) if side == "prefix" else (index + 1)
        similarity = cosine(full, half)
        rows.append({
            "content_index": index,
            "distance_from_cut_tokens": distance,
            "cosine": similarity,
            "drift": 1.0 - similarity,
        })
    return rows


def _summary(rows):
    drifts = [row["drift"] for row in rows]
    return {
        "content_tokens": len(rows),
        "mean_drift": math.fsum(drifts) / len(drifts),
        "maximum_drift": max(drifts),
        "nearest_cut_drift": rows[-1]["drift"] if rows[0]["distance_from_cut_tokens"] > 1 else rows[0]["drift"],
        "farthest_cut_drift": rows[0]["drift"] if rows[0]["distance_from_cut_tokens"] > 1 else rows[-1]["drift"],
    }


def analyse(text, trajectory):
    """Run a three-branch context-bisection experiment via a fetch function."""
    prefix, suffix, offset = split_at_word_midpoint(text)
    full_path = trajectory(text)
    prefix_path = trajectory(prefix)
    suffix_path = trajectory(suffix)
    full = _content(full_path)
    left = _content(prefix_path)
    right = _content(suffix_path)
    if len(full) != len(left) + len(right):
        raise ValueError(
            "the full path does not equal prefix plus suffix content-token counts")
    prefix_rows = _side_rows(full[:len(left)], left, "prefix")
    suffix_rows = _side_rows(full[len(left):], right, "suffix")
    return {
        "experiment": "SABLE_CONTEXT_BISECTION_V1",
        "model_state_changed": False,
        "cut_character_offset": offset,
        "full_tokens": len(full_path),
        "prefix": _summary(prefix_rows),
        "suffix": _summary(suffix_rows),
        "mean_drift": math.fsum(
            row["drift"] for row in prefix_rows + suffix_rows
        ) / len(full),
        "rows": {"prefix": prefix_rows, "suffix": suffix_rows},
        "interpretation": (
            "Drift measures a retained token's vector change when the other "
            "half of its source context is absent. It is contextual coupling, "
            "not token splitting or physical entanglement."
        ),
    }


def run(text, unpooled_url, unpooled_key):
    def trajectory(value):
        path = token_vectors(unpooled_url, unpooled_key, value)
        if not path:
            raise RuntimeError("the unpooled server returned no trajectory")
        return path
    return analyse(text, trajectory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--text", action="append", required=True,
                        help="text to measure; repeatable and kept in memory")
    parser.add_argument("--unpooled", default="http://127.0.0.1:8084")
    parser.add_argument("--unpooled-key", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    key = _key(args.unpooled_key, "TORMENT_NEXUS_MACHINESPIRIT_KEY", "machinespirit")
    try:
        results = [run(text, args.unpooled, key) for text in args.text]
    except (requests.RequestException, RuntimeError, ValueError) as error:
        parser.error(f"bisection probe did not run: {error}")
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for index, row in enumerate(results, start=1):
            print(f"probe {index}: {row['full_tokens']} full tokens; "
                  f"mean drift {row['mean_drift']:.6f}")
            for side in ("prefix", "suffix"):
                summary = row[side]
                print(f"  {side:<6} {summary['content_tokens']} tokens; "
                      f"mean {summary['mean_drift']:.6f}; "
                      f"near-cut {summary['nearest_cut_drift']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
