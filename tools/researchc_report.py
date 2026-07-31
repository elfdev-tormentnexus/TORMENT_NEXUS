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


def _nonnegative_integer(value, name):
    """Validate an experimental count without silently truncating it."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer")
    try:
        integer = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"{name} must be a non-negative integer"
        ) from exc
    if integer != value or integer < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return integer


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def wilson_interval(successes, trials, z=1.959963984540054):
    """Two-sided Wilson score interval for one fixed-p Bernoulli stratum."""
    successes = _nonnegative_integer(successes, "successes")
    trials = _nonnegative_integer(trials, "trials")
    if successes > trials:
        raise ValueError("successes must be between zero and trials")
    try:
        z = float(z)
    except (TypeError, ValueError) as exc:
        raise ValueError("z must be finite and positive") from exc
    if not math.isfinite(z) or z <= 0.0:
        raise ValueError("z must be finite and positive")
    if trials == 0:
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
    return exact_sign_test(grounded_only, ungrounded_only)


def exact_sign_test(positive, negative):
    """Return the exact two-sided sign-test p-value.

    ``positive`` and ``negative`` are the two non-tied outcome counts. Ties
    must be omitted rather than assigned to either side. The null gives each
    sign probability 1/2, so this is also the exact McNemar calculation when
    the counts are the two discordant cells of a paired binary experiment.
    """
    positive = _nonnegative_integer(positive, "positive")
    negative = _nonnegative_integer(negative, "negative")
    trials = positive + negative
    if trials == 0:
        return 1.0
    tail = min(positive, negative)
    probability = sum(
        math.comb(trials, count)
        for count in range(tail + 1)
    ) / (2 ** trials)
    return min(1.0, 2.0 * probability)


def holm_adjusted_pvalues(p_values):
    """Return Holm step-down family-wise adjusted p-values in input order.

    The adjustment is valid under arbitrary dependence. Values are sorted for
    the step-down calculation, made monotone by a cumulative maximum, clipped
    to one, and finally restored to their original positions.
    """
    values = [float(value) for value in p_values]
    if any(
        not math.isfinite(value) or not 0.0 <= value <= 1.0
        for value in values
    ):
        raise ValueError("p-values must be finite values between zero and one")
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    adjusted = [0.0] * len(values)
    previous = 0.0
    total = len(values)
    for rank, (index, value) in enumerate(ordered):
        candidate = min(1.0, (total - rank) * value)
        previous = max(previous, candidate)
        adjusted[index] = previous
    return adjusted


def sprt_decision(successes, trials, p0=0.5, p1=0.9,
                  alpha=0.05, beta=0.05):
    """Wald SPRT decision for one predeclared Bernoulli stratum."""
    successes = _nonnegative_integer(successes, "successes")
    trials = _nonnegative_integer(trials, "trials")
    if successes > trials:
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
                binding.get("server_bundle_sha256")
                or binding.get("server_revision")
                or binding.get("server_sha256")
                or ""
            )
            if isinstance(binding, dict)
            else ""
        )
        if len(model) != 64:
            problems.append(f"row {index}: missing model sha256")
        if not server:
            problems.append(
                f"row {index}: missing server bundle/revision/digest"
            )
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


def empirical_rate_distortion_rows(outcomes):
    """Aggregate observed correctness and token costs by encoding.

    Each outcome must contain:

    * ``encoding``: the code/manifest variant name;
    * ``correct``: a measured Boolean outcome;
    * ``tokens``: the non-negative token cost observed for that query; and
    * optional positive ``weight`` for the predeclared query distribution.

    Distortion is the query-weighted error rate. ``tokens`` is the
    query-weighted expected token cost, so both coordinates use the same
    empirical query distribution. ``frontier`` marks encodings not dominated
    by another encoding that is no more costly and no more distorted, with at
    least one strict improvement.
    """
    groups = {}
    for index, item in enumerate(outcomes, 1):
        if not isinstance(item, dict):
            raise ValueError(f"outcome {index} must be a dictionary")
        encoding = str(item.get("encoding") or "").strip()
        if not encoding:
            raise ValueError(f"outcome {index} is missing an encoding")
        correct = item.get("correct")
        if not isinstance(correct, bool):
            raise ValueError(
                f"outcome {index} correct must be a Boolean measurement"
            )
        try:
            tokens = float(item.get("tokens"))
            weight = float(item.get("weight", 1.0))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"outcome {index} tokens and weight must be numeric"
            ) from exc
        if not math.isfinite(tokens) or tokens < 0.0:
            raise ValueError(
                f"outcome {index} tokens must be finite and non-negative"
            )
        if not math.isfinite(weight) or weight <= 0.0:
            raise ValueError(
                f"outcome {index} weight must be finite and positive"
            )

        group = groups.setdefault(encoding, {
            "name": encoding[:80],
            "n": 0,
            "total_weight": 0.0,
            "correct_weight": 0.0,
            "error_weight": 0.0,
            "weighted_token_cost": 0.0,
        })
        group["n"] += 1
        group["total_weight"] += weight
        group["correct_weight"] += weight if correct else 0.0
        group["error_weight"] += 0.0 if correct else weight
        group["weighted_token_cost"] += weight * tokens

    rows = []
    for group in groups.values():
        total_weight = group["total_weight"]
        expected_tokens = group["weighted_token_cost"] / total_weight
        rows.append({
            "name": group["name"],
            "n": group["n"],
            "tokens": expected_tokens,
            "rate": expected_tokens,
            "distortion": group["error_weight"] / total_weight,
            "correct_weight": group["correct_weight"],
            "error_weight": group["error_weight"],
            "total_weight": total_weight,
        })

    for row in rows:
        row["frontier"] = not any(
            other is not row
            and other["tokens"] <= row["tokens"]
            and other["distortion"] <= row["distortion"]
            and (
                other["tokens"] < row["tokens"]
                or other["distortion"] < row["distortion"]
            )
            for other in rows
        )
    return rows


def _binary_answer(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    answer = str(value).strip().casefold()
    if answer in {"yes", "y"}:
        return "yes"
    if answer in {"no", "n"}:
        return "no"
    raise ValueError(f"binary answer must be yes or no, not {value!r}")


def _joint_outcome(key):
    if isinstance(key, (tuple, list)) and len(key) == 2:
        return _binary_answer(key[0]), _binary_answer(key[1])
    if isinstance(key, str):
        compact = key.strip().casefold()
        for separator in (",", "/", "|", "_", "-", " "):
            parts = [part for part in compact.split(separator) if part]
            if len(parts) == 2:
                return _binary_answer(parts[0]), _binary_answer(parts[1])
        if compact in {"yy", "yn", "ny", "nn"}:
            return _binary_answer(compact[0]), _binary_answer(compact[1])
    raise ValueError(
        "joint-count keys must identify two yes/no outcomes"
    )


def _joint_binary_counts(counts, name):
    if not isinstance(counts, dict):
        raise ValueError(f"{name} counts must be a dictionary")
    normalized = {
        ("yes", "yes"): 0,
        ("yes", "no"): 0,
        ("no", "yes"): 0,
        ("no", "no"): 0,
    }
    for key, value in counts.items():
        outcome = _joint_outcome(key)
        normalized[outcome] += _nonnegative_integer(
            value, f"{name} {outcome} count"
        )
    return normalized


def qq_equality_statistic(ab_counts, ba_counts):
    """Describe the binary QQ-equality residual from sequential joint counts.

    AB keys are ``(A answer, B answer)`` and BA keys are
    ``(B answer, A answer)``. The standard QQ residual is the AB probability
    of unlike answers minus the BA probability of unlike answers. A residual
    near zero is only a description of this proposition pair and elicitation
    design; this helper deliberately performs no contextuality inference.
    """
    ab = _joint_binary_counts(ab_counts, "AB")
    ba = _joint_binary_counts(ba_counts, "BA")
    n_ab = sum(ab.values())
    n_ba = sum(ba.values())
    ab_unlike = ab[("yes", "no")] + ab[("no", "yes")]
    ba_unlike = ba[("yes", "no")] + ba[("no", "yes")]
    p_ab = ab_unlike / n_ab if n_ab else None
    p_ba = ba_unlike / n_ba if n_ba else None
    residual = p_ab - p_ba if p_ab is not None and p_ba is not None else None
    return {
        "q": residual,
        "ab_unlike_probability": p_ab,
        "ba_unlike_probability": p_ba,
        "ab_unlike": ab_unlike,
        "ba_unlike": ba_unlike,
        "n_ab": n_ab,
        "n_ba": n_ba,
    }


def _joint_binary_probabilities(masses, name):
    if not isinstance(masses, dict):
        raise ValueError(f"{name} probability masses must be a dictionary")
    normalized = {
        ("yes", "yes"): 0.0,
        ("yes", "no"): 0.0,
        ("no", "yes"): 0.0,
        ("no", "no"): 0.0,
    }
    for key, raw_value in masses.items():
        outcome = _joint_outcome(key)
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{name} probability mass {outcome} must be numeric"
            ) from exc
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(
                f"{name} probability mass {outcome} must be finite and "
                "non-negative"
            )
        normalized[outcome] += value
    total = sum(normalized.values())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(f"{name} probability masses must sum to one")
    return normalized


def qq_probability_residual(ab_masses, ba_masses):
    """Describe sequential binary order residuals from probability masses.

    ``AB`` keys are ``(A, B)`` and ``BA`` keys are ``(B, A)``. Unlike the
    count helper above, this accepts complete joint distributions constructed
    from constrained conditional response propensities. It returns the
    probability-form QQ residual plus marginal-selectivity residuals:

    * ``delta_a = P_BA(A=yes) - P_AB(A=yes)``;
    * ``delta_b = P_AB(B=yes) - P_BA(B=yes)``.

    These values describe one elicitation design. A nonzero value is not by
    itself a law-of-total-probability violation, contextuality witness, or
    calibrated-belief claim.
    """
    ab = _joint_binary_probabilities(ab_masses, "AB")
    ba = _joint_binary_probabilities(ba_masses, "BA")
    ab_unlike = ab[("yes", "no")] + ab[("no", "yes")]
    ba_unlike = ba[("yes", "no")] + ba[("no", "yes")]
    ab_a_yes = ab[("yes", "yes")] + ab[("yes", "no")]
    ba_a_yes = ba[("yes", "yes")] + ba[("no", "yes")]
    ab_b_yes = ab[("yes", "yes")] + ab[("no", "yes")]
    ba_b_yes = ba[("yes", "yes")] + ba[("yes", "no")]
    return {
        "q": ab_unlike - ba_unlike,
        "delta_a": ba_a_yes - ab_a_yes,
        "delta_b": ab_b_yes - ba_b_yes,
        "ab_unlike_probability": ab_unlike,
        "ba_unlike_probability": ba_unlike,
        "ab_a_yes_probability": ab_a_yes,
        "ba_a_yes_probability": ba_a_yes,
        "ab_b_yes_probability": ab_b_yes,
        "ba_b_yes_probability": ba_b_yes,
    }


def monotonic_coherence_violations(
    probability_grid,
    containment_edges=(),
    tolerance=0.0,
):
    """Find monotonicity violations in threshold/containment probabilities.

    ``probability_grid`` maps object names to ``{threshold: probability}``.
    For a survival-style query such as ``P(lines >= threshold)``, probability
    must not rise as the threshold rises. A containment edge is
    ``(child, parent)``; at a shared threshold the child's probability must
    not exceed the parent's. Only adjacent thresholds contribute to the
    within-object total, while every shared threshold is checked for each
    containment edge.

    The returned violation identifiers and magnitudes are descriptive. They
    do not assume that separately prompted answers form a single event algebra.
    """
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError) as exc:
        raise ValueError("tolerance must be finite and non-negative") from exc
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and non-negative")
    if not isinstance(probability_grid, dict):
        raise ValueError("probability_grid must be a dictionary")

    grid = {}
    for raw_name, raw_row in probability_grid.items():
        name = str(raw_name)
        if not isinstance(raw_row, dict):
            raise ValueError(f"grid row {name!r} must be a dictionary")
        row = {}
        for raw_threshold, raw_probability in raw_row.items():
            try:
                threshold = float(raw_threshold)
                probability = float(raw_probability)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"grid row {name!r} must be numeric"
                ) from exc
            if not math.isfinite(threshold):
                raise ValueError("thresholds must be finite")
            if (
                not math.isfinite(probability)
                or not 0.0 <= probability <= 1.0
            ):
                raise ValueError("probabilities must lie between zero and one")
            if threshold in row:
                raise ValueError(
                    f"grid row {name!r} repeats threshold {threshold}"
                )
            row[threshold] = probability
        grid[name] = row

    violations = []
    for name, row in grid.items():
        ordered = sorted(row.items())
        for (low_k, low_q), (high_k, high_q) in zip(
            ordered, ordered[1:]
        ):
            magnitude = high_q - low_q
            if magnitude > tolerance:
                violations.append({
                    "id": ("threshold", name, low_k, high_k),
                    "kind": "threshold",
                    "object": name,
                    "lower_threshold": low_k,
                    "upper_threshold": high_k,
                    "lower_probability": low_q,
                    "upper_probability": high_q,
                    "magnitude": magnitude,
                })

    for index, edge in enumerate(containment_edges, 1):
        if not isinstance(edge, (tuple, list)) or len(edge) != 2:
            raise ValueError(
                f"containment edge {index} must be (child, parent)"
            )
        child, parent = str(edge[0]), str(edge[1])
        if child not in grid or parent not in grid:
            raise ValueError(
                f"containment edge {child!r}, {parent!r} names an unknown row"
            )
        for threshold in sorted(set(grid[child]) & set(grid[parent])):
            child_q = grid[child][threshold]
            parent_q = grid[parent][threshold]
            magnitude = child_q - parent_q
            if magnitude > tolerance:
                violations.append({
                    "id": ("containment", child, parent, threshold),
                    "kind": "containment",
                    "child": child,
                    "parent": parent,
                    "threshold": threshold,
                    "child_probability": child_q,
                    "parent_probability": parent_q,
                    "magnitude": magnitude,
                })

    magnitudes = {
        item["id"]: item["magnitude"]
        for item in violations
    }
    threshold_total = sum(
        item["magnitude"]
        for item in violations
        if item["kind"] == "threshold"
    )
    containment_total = sum(
        item["magnitude"]
        for item in violations
        if item["kind"] == "containment"
    )
    return {
        "violations": violations,
        "violation_set": frozenset(magnitudes),
        "magnitudes": magnitudes,
        "threshold_total_magnitude": threshold_total,
        "containment_total_magnitude": containment_total,
        "total_magnitude": threshold_total + containment_total,
        "max_magnitude": max(magnitudes.values(), default=0.0),
    }


def binary_bit_price_of_truth(yes_logprob, no_logprob, truth_is_yes):
    """Return the extra binary codelength paid for the truthful answer.

    Inputs are natural-log probabilities already aggregated over the desired
    yes/no token variants. The result is
    ``L(truth) - L(false) = log2(p_false / p_truth)``. Positive bits mean the
    model assigned less probability to truth; negative bits mean truth was
    cheaper. The ratio does not require renormalizing over the two answers.
    """
    if not isinstance(truth_is_yes, bool):
        raise ValueError("truth_is_yes must be Boolean")
    try:
        yes_logprob = float(yes_logprob)
        no_logprob = float(no_logprob)
    except (TypeError, ValueError) as exc:
        raise ValueError("yes/no logprobs must be numeric") from exc
    if math.isnan(yes_logprob) or math.isnan(no_logprob):
        raise ValueError("yes/no logprobs cannot be NaN")
    if yes_logprob > 0.0 or no_logprob > 0.0:
        raise ValueError("logprobs cannot exceed zero")
    if yes_logprob == no_logprob == -math.inf:
        raise ValueError("at least one binary answer must have nonzero mass")
    truth = yes_logprob if truth_is_yes else no_logprob
    false = no_logprob if truth_is_yes else yes_logprob
    return (false - truth) / math.log(2.0)


def _bernoulli_probability(q):
    try:
        q = float(q)
    except (TypeError, ValueError) as exc:
        raise ValueError("q must be a finite probability") from exc
    if not math.isfinite(q) or not 0.0 <= q <= 1.0:
        raise ValueError("q must be a finite probability")
    return q


def additive_logit_fisher(q):
    """Bernoulli Fisher information for an additive logit perturbation.

    If ``q = sigmoid(theta + epsilon)``, the information with respect to
    ``epsilon`` is ``q(1-q)`` and is largest at a tie.
    """
    q = _bernoulli_probability(q)
    return q * (1.0 - q)


def inverse_temperature_fisher(q, delta):
    """Bernoulli Fisher information for inverse temperature.

    If ``q = sigmoid(beta * delta)``, information with respect to ``beta`` is
    ``delta**2 * q(1-q)``. Unlike additive-logit information, it is zero at
    an exact score tie (``delta == 0``); the parameterizations answer different
    questions and must not be substituted for one another.
    """
    q = _bernoulli_probability(q)
    try:
        delta = float(delta)
    except (TypeError, ValueError) as exc:
        raise ValueError("delta must be finite") from exc
    if not math.isfinite(delta):
        raise ValueError("delta must be finite")
    return delta * delta * q * (1.0 - q)


def rank_auc(positive_scores, negative_scores, higher_is_positive=True):
    """Compute empirical rank AUC, assigning half credit to tied scores.

    This is the Mann-Whitney interpretation: the probability that a random
    positive outranks a random negative, plus half the tie probability.
    ``None`` is returned when either class is empty.
    """
    positives = [float(score) for score in positive_scores]
    negatives = [float(score) for score in negative_scores]
    if not positives or not negatives:
        return None
    if any(
        not math.isfinite(score)
        for score in positives + negatives
    ):
        raise ValueError("AUC scores must be finite")
    direction = 1.0 if higher_is_positive else -1.0
    ranked = sorted(
        [(direction * score, True) for score in positives]
        + [(direction * score, False) for score in negatives],
        key=lambda item: item[0],
    )

    positive_rank_sum = 0.0
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2.0
        positive_rank_sum += average_rank * sum(
            is_positive for _score, is_positive in ranked[index:end]
        )
        index = end

    n_positive = len(positives)
    n_negative = len(negatives)
    mann_whitney = (
        positive_rank_sum - n_positive * (n_positive + 1) / 2.0
    )
    return max(0.0, min(1.0, mann_whitney / (n_positive * n_negative)))


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
