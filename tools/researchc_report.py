"""Analyze Research C measurements without turning them into live authority.

Examples are metadata-only JSONL. A threshold is fitted on one file and
reported on a separate holdout file; the tool refuses to call the same file
both. It prints counterfactual compute savings and false refusals together.
Nothing here is imported by the assistant's decision path.
"""

import argparse
import gzip
import json
import math
import os


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def wilson_interval(successes, trials, z=1.959963984540054):
    """Two-sided Wilson score interval for one fixed-p Bernoulli stratum."""
    successes, trials = int(successes), int(trials)
    if trials <= 0:
        return None, None
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (proportion + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, centre - radius), min(1.0, centre + radius)


def exact_mcnemar(grounded_only, ungrounded_only):
    """Exact two-sided paired sign test over discordant pairs."""
    grounded_only = int(grounded_only)
    ungrounded_only = int(ungrounded_only)
    discordant = grounded_only + ungrounded_only
    if discordant <= 0:
        return 1.0
    tail = min(grounded_only, ungrounded_only)
    probability = sum(
        math.comb(discordant, count)
        for count in range(tail + 1)
    ) / (2 ** discordant)
    return min(1.0, 2.0 * probability)


def sprt_decision(successes, trials, p0=0.5, p1=0.9,
                  alpha=0.05, beta=0.05):
    """Wald SPRT decision for one predeclared Bernoulli stratum."""
    successes, trials = int(successes), int(trials)
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("successes must be between zero and trials")
    if not (0.0 < p0 < p1 < 1.0):
        raise ValueError("require 0 < p0 < p1 < 1")
    if not (0.0 < alpha < 1.0 and 0.0 < beta < 1.0):
        raise ValueError("alpha and beta must lie between zero and one")

    failures = trials - successes
    log_likelihood = (
        successes * math.log(p1 / p0)
        + failures * math.log((1.0 - p1) / (1.0 - p0))
    )
    upper = math.log((1.0 - beta) / alpha)
    lower = math.log(beta / (1.0 - alpha))
    if log_likelihood >= upper:
        decision = "accept_p1"
    elif log_likelihood <= lower:
        decision = "accept_p0"
    else:
        decision = "continue"
    return {
        "decision": decision,
        "log_likelihood_ratio": log_likelihood,
        "lower_boundary": lower,
        "upper_boundary": upper,
    }


def gzip_ratio(text):
    """Exploratory compression feature; never a truth score."""
    raw = str(text or "").encode("utf-8")
    if not raw:
        return None
    return len(gzip.compress(raw, mtime=0)) / len(raw)


def equal_length_gzip_difference(left, right):
    """Length-controlled screen used by the Goal 4 stored-reply audit."""
    left, right = str(left or ""), str(right or "")
    length = min(len(left), len(right))
    if length <= 0:
        return None
    left_size = len(gzip.compress(left[:length].encode("utf-8"), mtime=0))
    right_size = len(gzip.compress(right[:length].encode("utf-8"), mtime=0))
    return left_size - right_size


def threshold_rows(examples, metric, thresholds):
    """Counterfactual refusal table; larger metric means more uncertain."""
    rows = []
    usable = [
        item for item in examples
        if isinstance(item.get("measurements"), dict)
        and item["measurements"].get(metric) is not None
        and isinstance(item.get("would_pass"), bool)
    ]

    for threshold in thresholds:
        rejected = [
            item for item in usable
            if float(item["measurements"][metric]) >= threshold
        ]
        false_refusals = sum(item["would_pass"] for item in rejected)
        avoided = sum(
            max(0.0, float(item.get("downstream_seconds") or 0.0))
            for item in rejected
        )
        rows.append({
            "threshold": threshold,
            "n": len(usable),
            "rejected": len(rejected),
            "q_clear": (
                (len(usable) - len(rejected)) / len(usable)
                if usable else None
            ),
            "false_refusals": false_refusals,
            "bad_candidates_rejected": len(rejected) - false_refusals,
            "downstream_seconds_avoided": avoided,
        })
    return rows


def candidate_thresholds(examples, metric):
    values = sorted({
        float(item["measurements"][metric])
        for item in examples
        if isinstance(item.get("measurements"), dict)
        and item["measurements"].get(metric) is not None
    })
    if not values:
        return []
    return [values[0] - 1e-12] + values + [values[-1] + 1e-12]


def choose_threshold(fit, metric, max_false_refusal_rate):
    """Most compute avoided under a predeclared fit-set false-refusal cap."""
    candidates = threshold_rows(
        fit,
        metric,
        candidate_thresholds(fit, metric),
    )
    eligible = []
    good = sum(bool(item.get("would_pass")) for item in fit)
    for row in candidates:
        rate = row["false_refusals"] / good if good else 0.0
        if rate <= max_false_refusal_rate:
            eligible.append(row)
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda row: (
            row["downstream_seconds_avoided"],
            row["bad_candidates_rejected"],
            -row["threshold"],
        ),
    )["threshold"]


def binding_problems(examples):
    """Controls required before a threshold may be treated as portable."""
    problems = []
    for index, item in enumerate(examples, 1):
        binding = item.get("binding")
        sampler = item.get("sampler")
        prompt = str(item.get("prompt_sha256") or "")
        model = (
            str(binding.get("model_sha256") or "")
            if isinstance(binding, dict)
            else ""
        )
        server = (
            str(
                binding.get("server_revision")
                or binding.get("server_sha256")
                or ""
            )
            if isinstance(binding, dict)
            else ""
        )
        if len(model) != 64:
            problems.append(f"row {index}: missing model sha256")
        if not server:
            problems.append(f"row {index}: missing server revision/digest")
        if len(prompt) != 64:
            problems.append(f"row {index}: missing prompt sha256")
        if not isinstance(sampler, dict):
            problems.append(f"row {index}: missing sampler record")
    return problems


def rate_distortion_rows(queries, codes):
    """Evaluate prompt encodings against a reduced, weighted query sample.

    A query row contains only ``kind``, ``target``, and optional ``weight``;
    raw operator text is neither needed nor accepted. A code contains its
    measured token cost and the ``(kind, target)`` facts it makes answerable.
    Distortion is the weighted unsupported-query fraction.
    """
    reduced_queries = []
    for item in queries:
        kind = str(item.get("kind") or "")
        target = str(item.get("target") or "")
        weight = float(item.get("weight", 1.0))
        if kind and target and math.isfinite(weight) and weight > 0:
            reduced_queries.append(((kind, target), weight))
    total_weight = sum(weight for _fact, weight in reduced_queries)

    rows = []
    for code in codes:
        supported = {
            (str(item.get("kind") or ""), str(item.get("target") or ""))
            for item in code.get("supports", ())
            if isinstance(item, dict)
        }
        missed = sum(
            weight for fact, weight in reduced_queries if fact not in supported
        )
        rows.append({
            "name": str(code.get("name") or "unnamed")[:80],
            "tokens": max(0, int(code.get("tokens") or 0)),
            "distortion": (
                missed / total_weight if total_weight else None
            ),
            "supported_weight": total_weight - missed,
            "total_weight": total_weight,
        })

    for row in rows:
        row["frontier"] = not any(
            other is not row
            and other["distortion"] is not None
            and row["distortion"] is not None
            and other["tokens"] <= row["tokens"]
            and other["distortion"] <= row["distortion"]
            and (
                other["tokens"] < row["tokens"]
                or other["distortion"] < row["distortion"]
            )
            for other in rows
        )
    return rows


def _print_table(rows):
    columns = (
        "threshold",
        "n",
        "rejected",
        "q_clear",
        "false_refusals",
        "bad_candidates_rejected",
        "downstream_seconds_avoided",
    )
    print("| " + " | ".join(columns) + " |")
    print("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        rendered = []
        for key in columns:
            value = row.get(key)
            rendered.append(
                f"{value:.6g}" if isinstance(value, float) else str(value)
            )
        print("| " + " | ".join(rendered) + " |")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit", required=True)
    parser.add_argument("--holdout", required=True)
    parser.add_argument("--metric", default="mean_surprisal")
    parser.add_argument("--max-false-refusal-rate", type=float, default=0.01)
    parser.add_argument(
        "--allow-unbound",
        action="store_true",
        help="exploratory only: analyze rows missing model/prompt/sampler binding",
    )
    args = parser.parse_args(argv)

    if os.path.realpath(args.fit) == os.path.realpath(args.holdout):
        parser.error("fit and holdout must be different files")

    fit = read_jsonl(args.fit)
    holdout = read_jsonl(args.holdout)
    problems = binding_problems(fit) + binding_problems(holdout)
    if problems and not args.allow_unbound:
        preview = "; ".join(problems[:5])
        parser.error(
            "dataset is not fully bound to model, prompt, and sampler "
            f"({preview}). Use --allow-unbound only for exploratory work"
        )
    threshold = choose_threshold(
        fit,
        args.metric,
        max(0.0, min(1.0, args.max_false_refusal_rate)),
    )
    if threshold is None:
        parser.error("the fit set has no usable measured examples")

    print(f"Fitted threshold: {threshold:.9g}")
    print(
        "Fit and holdout are reported separately. This table does not install "
        "the threshold into the assistant."
    )
    print("\nFit")
    _print_table(threshold_rows(fit, args.metric, [threshold]))
    print("\nHoldout")
    _print_table(threshold_rows(holdout, args.metric, [threshold]))

    successes = sum(bool(item.get("would_pass")) for item in holdout)
    low, high = wilson_interval(successes, len(holdout))
    if low is not None:
        print(
            f"\nHoldout pass fraction: {successes}/{len(holdout)} "
            f"(Wilson 95% {low:.3f} to {high:.3f})."
        )


if __name__ == "__main__":
    main()
