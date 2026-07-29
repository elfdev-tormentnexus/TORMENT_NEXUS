"""Measure controlled text edits against an unpooled token trajectory.

This is a hazard-mode research instrument, not a runtime feature.  A model
server exposes complete contextual token vectors, but no supported safe API
for injecting a value into one internal token state.  Pretending otherwise
would corrupt the measurement: every later token can depend on that state.

Instead, this tool makes one reversible *text* edit at a time, re-embeds the
edited sentence, and reports the resulting change in its mean-all trajectory
vector.  The word span is the intervention unit; it is deliberately not
called a tokenizer position, because word and model-token boundaries differ.
No model weights, memory, cache, or Sable configuration is modified, and no
text is written to disk unless the caller redirects the command output.

Example:
    python tools/token_contrast_probe.py --text "A promise made to a dying person"

The result is an observational contrast score (1 - cosine), not a claim of
causation, quantum behaviour, consciousness, or semantic importance.
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


def word_spans(text):
    """Return editable word spans without confusing them for model tokens."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return [(match.start(), match.end(), match.group(0)) for match in WORD.finditer(text)]


def replace_span(text, start, end, replacement="[MASK]"):
    """One reversible source-text edit, with bounds checked before use."""
    if not isinstance(replacement, str) or not replacement:
        raise ValueError("replacement must be a non-empty string")
    if not 0 <= start < end <= len(text):
        raise ValueError("span is outside the supplied text")
    return text[:start] + replacement + text[end:]


def mean_all(path):
    """The live pooled server's measured pooling rule, applied locally."""
    if not path or not path[0]:
        raise ValueError("trajectory is empty")
    width = len(path[0])
    if any(len(row) != width for row in path):
        raise ValueError("trajectory rows have inconsistent dimensions")
    return [math.fsum(row[column] for row in path) / len(path)
            for column in range(width)]


def cosine(left, right):
    if len(left) != len(right):
        raise ValueError("vectors have different dimensions")
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    if left_norm <= 0.0 or right_norm <= 0.0:
        raise ValueError("cannot compare a zero vector")
    return math.fsum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def contrast_rows(text, trajectory, replacement="[MASK]"):
    """Run declared word-span interventions using an injected fetch function.

    Keeping transport outside this function makes the scientific calculation
    testable and makes clear that this code does not mutate a running model.
    """
    baseline_path = trajectory(text)
    baseline = mean_all(baseline_path)
    rows = []
    for index, (start, end, word) in enumerate(word_spans(text)):
        edited = replace_span(text, start, end, replacement)
        changed_path = trajectory(edited)
        changed = mean_all(changed_path)
        rows.append({
            "word_index": index,
            "character_span": [start, end],
            "word": word,
            "baseline_tokens": len(baseline_path),
            "edited_tokens": len(changed_path),
            "mean_all_cosine": cosine(baseline, changed),
            "contrast": 1.0 - cosine(baseline, changed),
        })
    return rows


def run(text, unpooled_url, unpooled_key, replacement="[MASK]"):
    """Collect a non-persistent contrast experiment from the local server."""
    def trajectory(value):
        path = token_vectors(unpooled_url, unpooled_key, value)
        if not path:
            raise RuntimeError("the unpooled server returned no trajectory")
        return path

    rows = contrast_rows(text, trajectory, replacement)
    return {
        "experiment": "SABLE_TOKEN_CONTRAST_V1",
        "intervention": {
            "unit": "source-text word span",
            "replacement": replacement,
            "model_state_changed": False,
            "persistent_output": False,
        },
        "text_characters": len(text),
        "spans": rows,
        "interpretation": (
            "Contrast is the change in the mean-all trajectory vector after "
            "one declared text edit. It is not a token-state injection, a "
            "causal attribution, or evidence of quantum behaviour."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--text", required=True, help="text to probe; kept in memory")
    parser.add_argument("--unpooled", default="http://127.0.0.1:8084")
    parser.add_argument("--unpooled-key", default="")
    parser.add_argument("--replacement", default="[MASK]")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not word_spans(args.text):
        parser.error("text must contain at least one editable word span")
    key = _key(args.unpooled_key, "TORMENT_NEXUS_MACHINESPIRIT_KEY", "machinespirit")
    try:
        result = run(args.text, args.unpooled, key, args.replacement)
    except (requests.RequestException, RuntimeError, ValueError) as error:
        parser.error(f"contrast probe did not run: {error}")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Counterfactual trajectory contrast (non-persistent)")
        for row in result["spans"]:
            print(f"  {row['word_index']:>2}  {row['word']!r:<24} "
                  f"contrast {row['contrast']:.6f}  "
                  f"tokens {row['baseline_tokens']} -> {row['edited_tokens']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
