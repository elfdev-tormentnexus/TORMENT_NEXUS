"""Bounded Research C response-coherence and binary bit-price probe.

This is a research collector, not production authority.  It calls the
one-slot Qwen director directly because Sable's trusted source resolver would
otherwise intercept source questions.  No result from this file may authorize
an answer, refusal, route, memory, or edit.

The experimental unit is one of eight predeclared files.  Each file supplies
two nested line-count events:

    A: lines(file) >= floor(4L/5)   (true)
    B: lines(file) >= ceil(5L/4)    (false)

For two exact paraphrases, six constrained binary calls enumerate q(A),
q(B|A=Yes), q(B|A=No), q(B), q(A|B=Yes), and q(A|B=No).  This gives complete
AB and BA response distributions without treating seeds as independent
observations.  Two exact probability replays at the end detect serving drift:
8 targets * 2 wordings * 6 calls + 2 sentinels = 98 calls.

Usage:
    python coherence_probe.py --dry-run
    python coherence_probe.py
    python coherence_probe.py --analyze-only

``--analyze-only`` deliberately loads only frozen JSON/JSONL artifacts.  It
does not import Sable, inspect the repository, or contact a live server.
"""

import argparse
import atexit
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCHEMA = 1
EXPERIMENT = "researchc_bounded_response_coherence_order_bit_price"
PLAN_SEED = 20260730
CALL_COUNT = 98
PRIMARY_CALL_COUNT = 96
COHERENCE_TOLERANCE = 0.02
ORDER_TOLERANCE = 0.05
QQ_TOLERANCE = 0.05
SENTINEL_TOLERANCE = 0.01
MIN_PARAPHRASE_SIGN_AGREEMENT = 6
PROBABILITY_SUM_TOLERANCE = 1e-4

PUBLIC_RESEARCH_PROMPT_HEADER = """You are the language-model participant in a bounded, descriptive source-grounding experiment.
Use only the controlled public source context below and the conversation in
this request. Do not claim access to private memories, prior conversations,
credentials, local absolute paths, or facts absent from that context.
For every question in this experiment, follow its exact Yes-or-No response
format. A repository path being absent from the recent-path list does not
establish that it is absent from the repository.

CONTROLLED PUBLIC SOURCE CONTEXT
"""

_WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(?:[A-Z]:[\\/][^\r\n\t,;|]*)"
)
_UNC_ABSOLUTE_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(?:\\\\[^\\/\r\n\t]+[\\/][^\r\n\t,;|]*)"
)
_SECRET_TEXT_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)"
        r"\s*[:=]\s*[^\s,;]+"
    ),
)
_RAW_SECRET_KEYS = {
    "authorization",
    "cookie",
    "credentials",
    "headers",
    "model_request_headers",
    "password",
    "secret",
    "username",
    "user_name",
}
_PATH_BINDING_KEYS = {
    "cwd",
    "executable",
    "executable_path",
    "model_alias",
    "model_path",
    "root",
    "userprofile",
    "working_directory",
}

SAMPLER = {
    "max_tokens": 2,
    "temperature": 1.0,
    "top_k": 0,
    "top_p": 1.0,
    "min_p": 0.0,
    "typical_p": 1.0,
    "repeat_penalty": 1.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "dry_multiplier": 0.0,
    "xtc_probability": 0.0,
    "samplers": ["temperature"],
    "min_keep": 2,
    "grammar": 'root ::= "Yes" | "No"',
    "logprobs": True,
    "top_logprobs": 2,
    "post_sampling_probs": True,
    "cache_prompt": True,
    "stream": False,
    "seed": 20260730,
    "chat_template_kwargs": {"enable_thinking": False},
}

TARGETS = (
    {
        "id": "T01",
        "path": "assistant/core/chosen_name.py",
        "lines": 956,
        "low": 764,
        "high": 1195,
        "area": "assistant/core",
    },
    {
        "id": "T02",
        "path": "assistant/memory/memory_logic.py",
        "lines": 440,
        "low": 352,
        "high": 550,
        "area": "assistant/memory",
    },
    {
        "id": "T03",
        "path": "assistant/commands/natural_command.py",
        "lines": 519,
        "low": 415,
        "high": 649,
        "area": "assistant/commands",
    },
    {
        "id": "T04",
        "path": "assistant/ui/vector_panel.py",
        "lines": 687,
        "low": 549,
        "high": 859,
        "area": "assistant/ui",
    },
    {
        "id": "T05",
        "path": "assistant/voice/setup_voice.py",
        "lines": 167,
        "low": 133,
        "high": 209,
        "area": "assistant/voice",
    },
    {
        "id": "T06",
        "path": "assistant/project/project_builder.py",
        "lines": 422,
        "low": 337,
        "high": 528,
        "area": "assistant/project",
    },
    {
        "id": "T07",
        "path": "assistant/web/search_engine.py",
        "lines": 123,
        "low": 98,
        "high": 154,
        "area": "assistant/web",
    },
    {
        "id": "T08",
        "path": "assistant/hardware/setup_hardware.py",
        "lines": 138,
        "low": 110,
        "high": 173,
        "area": "assistant/hardware",
    },
)

WORDINGS = (
    {
        "id": "W0",
        "template": (
            "Does the file `{path}` contain at least {threshold} text lines? "
            "Answer exactly Yes or No."
        ),
    },
    {
        "id": "W1",
        "template": (
            "Is the number of text lines in `{path}` greater than or equal "
            "to {threshold}? Reply exactly Yes or No."
        ),
    },
)

MEASUREMENTS = (
    "a",
    "b_given_a_yes",
    "b_given_a_no",
    "b",
    "a_given_b_yes",
    "a_given_b_no",
)

ARTIFACT_NAMES = (
    "coherence_prompt.json",
    "coherence_targets.json",
    "coherence_spec.json",
)

_RATE_MODULE = None


class ProbeError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def sha256_value(value):
    return sha256_text(canonical_json(value))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _known_local_usernames():
    """Return host-local account labels that must never enter evidence."""
    values = {
        os.environ.get("USERNAME"),
        os.environ.get("USER"),
        Path.home().name,
    }
    return tuple(
        sorted(
            {
                str(value).strip()
                for value in values
                if value and len(str(value).strip()) >= 3
            },
            key=len,
            reverse=True,
        )
    )


def _replace_casefold(text, needle, replacement):
    """Case-insensitive literal replacement without treating paths as regex."""
    if not needle:
        return text
    return re.sub(re.escape(str(needle)), replacement, text, flags=re.I)


def _safe_basename(value):
    """Return only a final path component, independent of host path syntax."""
    normalized = str(value or "").strip().strip("\"'").replace("\\", "/")
    return normalized.rstrip("/").rsplit("/", 1)[-1] if normalized else ""


def _sanitize_free_text(value):
    """Remove local identities, absolute paths, and credential-shaped text."""
    text = str(value)
    known_roots = {
        str(ROOT.resolve()),
        str(Path.home().resolve()),
        os.environ.get("USERPROFILE"),
    }
    for local_root in sorted(
        {item for item in known_roots if item},
        key=len,
        reverse=True,
    ):
        text = _replace_casefold(text, local_root, "<local-root>")
    text = _WINDOWS_ABSOLUTE_PATH.sub("<local-path>", text)
    text = _UNC_ABSOLUTE_PATH.sub("<local-path>", text)
    for username in _known_local_usernames():
        text = re.sub(
            rf"(?i)(?<![A-Za-z0-9_]){re.escape(username)}"
            r"(?![A-Za-z0-9_])",
            "<local-user>",
            text,
        )
    for pattern in _SECRET_TEXT_PATTERNS:
        text = pattern.sub("<redacted-secret>", text)
    return text


def _safe_endpoint(value):
    """Keep a listener address and port while dropping credentials/query data."""
    text = _sanitize_free_text(value)
    try:
        parsed = urlsplit(text)
        if parsed.scheme and parsed.hostname:
            host = parsed.hostname
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            netloc = host
            if parsed.port is not None:
                netloc += f":{parsed.port}"
            return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except (TypeError, ValueError):
        pass
    return text


def _sanitized_binding(value):
    """Recursively reduce a live/repository binding to privacy-safe evidence.

    Raw command lines are represented only by SHA-256. Absolute path fields
    retain only their basenames. Credential-bearing and account-name fields
    are omitted. All other strings pass through the same path/key scrubber.
    """

    def walk(item):
        if isinstance(item, dict):
            result = {}
            for raw_key, raw_value in item.items():
                key = str(raw_key)
                folded = key.casefold()
                if folded == "command_line":
                    result["command_line_sha256"] = sha256_text(
                        str(raw_value or "")
                    )
                    continue
                if (
                    folded in _RAW_SECRET_KEYS
                    or "api_key" in folded
                    or "apikey" in folded
                    or folded.endswith("_password")
                    or folded.endswith("_secret")
                    or folded.endswith("_credential")
                ):
                    continue
                if folded in _PATH_BINDING_KEYS or folded.endswith("_path"):
                    basename_key = (
                        key[:-5] + "_basename"
                        if folded.endswith("_path")
                        else key + "_basename"
                    )
                    result[basename_key] = _safe_basename(raw_value)
                    continue
                if folded in {"server_url", "listener_url", "endpoint"}:
                    result[key] = _safe_endpoint(raw_value)
                    continue
                result[key] = walk(raw_value)
            return result
        if isinstance(item, (list, tuple)):
            return [walk(member) for member in item]
        if isinstance(item, str):
            return _sanitize_free_text(item)
        return item

    return walk(value)


def _privacy_violations(value):
    """Return structural privacy failures in a would-be frozen artifact."""
    problems = []

    def inspect(item, path):
        if isinstance(item, dict):
            for raw_key, raw_value in item.items():
                key = str(raw_key)
                folded = key.casefold()
                if folded == "command_line":
                    problems.append(f"{path}.{key}:raw-command-line-key")
                if (
                    folded in _RAW_SECRET_KEYS
                    or "api_key" in folded
                    or "apikey" in folded
                ):
                    problems.append(f"{path}.{key}:sensitive-key")
                inspect(raw_value, f"{path}.{key}")
            return
        if isinstance(item, (list, tuple)):
            for index, member in enumerate(item):
                inspect(member, f"{path}[{index}]")
            return
        if not isinstance(item, str):
            return
        if _WINDOWS_ABSOLUTE_PATH.search(item) or _UNC_ABSOLUTE_PATH.search(item):
            problems.append(f"{path}:absolute-local-path")
        folded = item.casefold()
        for local_root in (
            str(ROOT.resolve()),
            str(Path.home().resolve()),
            os.environ.get("USERPROFILE"),
        ):
            if local_root and str(local_root).casefold() in folded:
                problems.append(f"{path}:known-local-root")
        for username in _known_local_usernames():
            if re.search(
                rf"(?i)(?<![A-Za-z0-9_]){re.escape(username)}"
                r"(?![A-Za-z0-9_])",
                item,
            ):
                problems.append(f"{path}:local-username")
        if any(pattern.search(item) for pattern in _SECRET_TEXT_PATTERNS):
            problems.append(f"{path}:credential-shaped-text")

    inspect(value, "$")
    return problems


def _assert_privacy_safe(value):
    problems = _privacy_violations(value)
    if problems:
        raise ProbeError(
            "refusing to persist privacy-unsafe coherence artifact: "
            + ", ".join(problems[:8])
        )


def messages_digest(messages):
    """Stable experiment-local digest; no production logger is involved."""
    return sha256_value(messages)


def _atomic_json(path, value):
    """The audited rate-probe write pattern, retained for offline analysis."""
    _assert_privacy_safe(value)
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append_jsonl(path, value):
    """Append one durable event; a crash loses at most the in-flight call."""
    _assert_privacy_safe(value)
    with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _live_helpers():
    """Load the audited live-binding helper only on live collection paths."""
    global _RATE_MODULE
    if _RATE_MODULE is not None:
        return _RATE_MODULE
    path = HERE / "rate_distortion_probe.py"
    spec = importlib.util.spec_from_file_location(
        "researchc_rate_distortion_live_helpers",
        path,
    )
    if spec is None or spec.loader is None:
        raise ProbeError("could not load audited rate-distortion helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _RATE_MODULE = module
    return module


def _target(target_id):
    for item in TARGETS:
        if item["id"] == target_id:
            return item
    raise ProbeError(f"unknown target {target_id!r}")


def _wording(wording_id):
    for item in WORDINGS:
        if item["id"] == wording_id:
            return item
    raise ProbeError(f"unknown wording {wording_id!r}")


def render_question(target, wording, event):
    if event not in {"A", "B"}:
        raise ProbeError(f"event must be A or B, not {event!r}")
    threshold = target["low"] if event == "A" else target["high"]
    return wording["template"].format(
        path=target["path"],
        threshold=threshold,
    )


def _block_tasks(target, wording, order):
    if order not in {"AB", "BA"}:
        raise ProbeError(f"order must be AB or BA, not {order!r}")
    first, second = tuple(order)
    direct_measurement = "a" if first == "A" else "b"
    conditional_prefix = (
        "b_given_a_" if order == "AB" else "a_given_b_"
    )
    parity = (
        int(target["id"][1:])
        + int(wording["id"][1:])
        + (0 if order == "AB" else 1)
    ) % 2
    forced = ("Yes", "No") if parity == 0 else ("No", "Yes")
    base = {
        "target_id": target["id"],
        "target_path": target["path"],
        "wording_id": wording["id"],
        "order": order,
        "sentinel": False,
        "replay_of": None,
    }
    result = [{
        **base,
        "trial_id": f"{target['id']}-{wording['id']}-{order}-direct",
        "measurement": direct_measurement,
        "event": first,
        "truth_is_yes": first == "A",
        "question": render_question(target, wording, first),
        "prior_event": None,
        "prior_question": None,
        "forced_prior_answer": None,
    }]
    for answer in forced:
        result.append({
            **base,
            "trial_id": (
                f"{target['id']}-{wording['id']}-{order}-"
                f"after-{answer.casefold()}"
            ),
            "measurement": conditional_prefix + answer.casefold(),
            "event": second,
            "truth_is_yes": second == "A",
            "question": render_question(target, wording, second),
            "prior_event": first,
            "prior_question": render_question(target, wording, first),
            "forced_prior_answer": answer,
        })
    return result


def task_plan():
    """Return the exact fixed 96-call crossover plus two drift replays."""
    anchor_target = TARGETS[0]
    anchor_wording = WORDINGS[0]
    anchor_blocks = [
        _block_tasks(anchor_target, anchor_wording, "AB"),
        _block_tasks(anchor_target, anchor_wording, "BA"),
    ]
    remaining = []
    for target in TARGETS:
        for wording in WORDINGS:
            for order in ("AB", "BA"):
                if (
                    target["id"] == anchor_target["id"]
                    and wording["id"] == anchor_wording["id"]
                ):
                    continue
                remaining.append(_block_tasks(target, wording, order))
    random.Random(PLAN_SEED).shuffle(remaining)

    tasks = []
    for block in anchor_blocks + remaining:
        tasks.extend(block)
    if len(tasks) != PRIMARY_CALL_COUNT:
        raise ProbeError("primary coherence plan is not exactly 96 calls")

    direct_a = next(
        item
        for item in tasks
        if item["target_id"] == "T01"
        and item["wording_id"] == "W0"
        and item["measurement"] == "a"
    )
    direct_b = next(
        item
        for item in tasks
        if item["target_id"] == "T01"
        and item["wording_id"] == "W0"
        and item["measurement"] == "b"
    )
    for original in (direct_a, direct_b):
        replay = dict(original)
        replay["trial_id"] = original["trial_id"] + "-replay"
        replay["sentinel"] = True
        replay["replay_of"] = original["trial_id"]
        tasks.append(replay)

    for index, task in enumerate(tasks, 1):
        task["execution_order"] = index
        task["seed"] = SAMPLER["seed"]
    if (
        len(tasks) != CALL_COUNT
        or len({item["trial_id"] for item in tasks}) != CALL_COUNT
    ):
        raise ProbeError("coherence plan is not 98 unique calls")
    return tasks


def construct_messages(system_prompt, task):
    messages = [{"role": "system", "content": system_prompt}]
    if task.get("prior_question") is not None:
        messages.extend([
            {"role": "user", "content": task["prior_question"]},
            {
                "role": "assistant",
                "content": task["forced_prior_answer"],
            },
        ])
    messages.append({"role": "user", "content": task["question"]})
    return messages


def _binary_candidate_id(candidate):
    """The tokenizer id llama.cpp reports beside a top_probs candidate."""
    raw = candidate.get("id")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ProbeError(
            "post-sampling candidate has no integer tokenizer id; the frozen "
            "Yes/No token ids cannot be checked"
        )
    return raw


def parse_binary_response(answer, logprobs, token_ids=None):
    """Extract a grammar-conditioned Yes probability from llama.cpp output.

    When ``token_ids`` is supplied -- the frozen one-token ``Yes``/``No`` ids
    from the spec -- each candidate is matched on its tokenizer id as well as
    its rendered string.  Rendered text alone is not identity: a different
    token can render to the same characters, and a retokenized or reloaded
    server could serve one without the string ever changing.
    """
    normalized = str(answer or "").strip()
    if normalized not in {"Yes", "No"}:
        raise ProbeError(
            f"grammar response must be exactly Yes or No, got {answer!r}"
        )
    content = (
        logprobs.get("content")
        if isinstance(logprobs, dict)
        else None
    )
    if not isinstance(content, list) or not content:
        raise ProbeError("completion returned no probability positions")

    chosen = None
    for entry in content:
        candidates = entry.get("top_probs") if isinstance(entry, dict) else None
        if not isinstance(candidates, list):
            continue
        tokens = {
            item.get("token")
            for item in candidates
            if isinstance(item, dict)
        }
        if {"Yes", "No"} <= tokens:
            chosen = entry
            break
    if chosen is None:
        raise ProbeError(
            "post-sampling top_probs did not contain both Yes and No"
        )

    expected_ids = None
    if token_ids is not None:
        expected_ids = {
            "Yes": token_ids["Yes"],
            "No": token_ids["No"],
        }
        if expected_ids["Yes"] == expected_ids["No"]:
            raise ProbeError("frozen Yes and No token ids are identical")

    values = {}
    for candidate in chosen["top_probs"]:
        token = candidate.get("token")
        if token not in {"Yes", "No"} or token in values:
            continue
        if expected_ids is not None:
            actual_id = _binary_candidate_id(candidate)
            if actual_id != expected_ids[token]:
                raise ProbeError(
                    f"candidate rendering {token!r} carries tokenizer id "
                    f"{actual_id}, not the frozen id {expected_ids[token]}"
                )
        try:
            probability = float(candidate["prob"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProbeError("binary candidate has no numeric probability") from exc
        if not math.isfinite(probability) or probability <= 0.0:
            raise ProbeError("binary candidate probability must be positive")
        values[token] = probability
    if set(values) != {"Yes", "No"}:
        raise ProbeError("binary candidates are missing or duplicated")
    total = values["Yes"] + values["No"]
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise ProbeError(
            f"grammar-conditioned binary probabilities sum to {total}, not 1"
        )
    q = values["Yes"] / total
    if not 0.0 < q < 1.0:
        raise ProbeError("normalized Yes probability is not strictly interior")
    return {
        "normalized_answer": normalized,
        "yes_probability": values["Yes"],
        "no_probability": values["No"],
        "binary_probability_sum": total,
        "q_yes": q,
        "probability_entry": chosen,
    }


def binary_bit_price(q_yes, truth_is_yes):
    q_yes = float(q_yes)
    if not 0.0 < q_yes < 1.0:
        raise ValueError("q_yes must be strictly between zero and one")
    truth = q_yes if truth_is_yes else 1.0 - q_yes
    false = 1.0 - truth
    return math.log2(false / truth)


def additive_logit_fisher(q_yes):
    q_yes = float(q_yes)
    if not 0.0 < q_yes < 1.0:
        raise ValueError("q_yes must be strictly between zero and one")
    return q_yes * (1.0 - q_yes)


def inverse_temperature_fisher(q_yes):
    q_yes = float(q_yes)
    if not 0.0 < q_yes < 1.0:
        raise ValueError("q_yes must be strictly between zero and one")
    delta = math.log(q_yes / (1.0 - q_yes))
    return delta * delta * q_yes * (1.0 - q_yes)


def sequential_joint(a, b_after_yes, b_after_no):
    values = [float(a), float(b_after_yes), float(b_after_no)]
    if any(not 0.0 <= value <= 1.0 for value in values):
        raise ValueError("joint inputs must be probabilities")
    a, b_after_yes, b_after_no = values
    result = {
        "YY": a * b_after_yes,
        "YN": a * (1.0 - b_after_yes),
        "NY": (1.0 - a) * b_after_no,
        "NN": (1.0 - a) * (1.0 - b_after_no),
    }
    if not math.isclose(sum(result.values()), 1.0, abs_tol=1e-12):
        raise AssertionError("joint response distribution does not sum to one")
    return result


def response_unit_statistics(values):
    """Compute one target/wording unit from its six response propensities."""
    if set(values) != set(MEASUREMENTS):
        raise ValueError("one response unit requires exactly six measurements")
    a = float(values["a"])
    b = float(values["b"])
    ab = sequential_joint(
        a,
        values["b_given_a_yes"],
        values["b_given_a_no"],
    )
    ba = sequential_joint(
        b,
        values["a_given_b_yes"],
        values["a_given_b_no"],
    )
    a_in_ba = ba["YY"] + ba["NY"]
    b_in_ab = ab["YY"] + ab["NY"]
    delta_a = a_in_ba - a
    delta_b = b_in_ab - b
    qq = (ab["YN"] + ab["NY"]) - (ba["YN"] + ba["NY"])
    bit_a = binary_bit_price(a, True)
    bit_b = binary_bit_price(b, False)
    bit_mean = 0.5 * (bit_a + bit_b)
    equivalent = 0.5 * (
        math.log2(b / (1.0 - b))
        - math.log2(a / (1.0 - a))
    )
    if not math.isclose(bit_mean, equivalent, abs_tol=1e-12):
        raise AssertionError("bit-price/coherence identity failed")
    return {
        "q_a": a,
        "q_b": b,
        "coherence_delta": b - a,
        "coherence_violation": b - a > COHERENCE_TOLERANCE,
        "ab_joint": ab,
        "ba_joint": ba,
        "a_marginal_in_ba": a_in_ba,
        "b_marginal_in_ab": b_in_ab,
        "marginal_selectivity_a": delta_a,
        "marginal_selectivity_b": delta_b,
        "qq_residual": qq,
        "bit_price_a_truth_yes": bit_a,
        "bit_price_b_truth_no": bit_b,
        "balanced_mean_bit_price": bit_mean,
        "bit_price_logodds_identity": equivalent,
        "additive_logit_fisher_a": additive_logit_fisher(a),
        "additive_logit_fisher_b": additive_logit_fisher(b),
        "inverse_temperature_fisher_a": inverse_temperature_fisher(a),
        "inverse_temperature_fisher_b": inverse_temperature_fisher(b),
        "informative_curve": a > 0.9 and b < 0.1,
    }


def _sign(value, tolerance):
    value = float(value)
    if value > tolerance:
        return 1
    if value < -tolerance:
        return -1
    return 0


def exact_sign_test(positive, negative):
    positive, negative = int(positive), int(negative)
    if positive < 0 or negative < 0:
        raise ValueError("sign counts must be non-negative")
    trials = positive + negative
    if trials == 0:
        return 1.0
    tail = min(positive, negative)
    probability = sum(
        math.comb(trials, count)
        for count in range(tail + 1)
    ) / (2 ** trials)
    return min(1.0, 2.0 * probability)


def holm_adjusted_pvalues(values):
    values = [float(value) for value in values]
    ordered = sorted(enumerate(values), key=lambda pair: (pair[1], pair[0]))
    adjusted = [0.0] * len(values)
    previous = 0.0
    total = len(values)
    for rank, (index, value) in enumerate(ordered):
        candidate = min(1.0, (total - rank) * value)
        previous = max(previous, candidate)
        adjusted[index] = previous
    return adjusted


def wilson_interval(successes, trials, z=1.959963984540054):
    successes, trials = int(successes), int(trials)
    if trials <= 0:
        return None
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2.0 * trials)) / denominator
    spread = (
        z
        * math.sqrt(
            p * (1.0 - p) / trials
            + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return [max(0.0, centre - spread), min(1.0, centre + spread)]


def _median(values):
    values = [float(value) for value in values]
    return statistics.median(values) if values else None


def _mean(values):
    values = [float(value) for value in values]
    return statistics.fmean(values) if values else None


def validate_spec_integrity(spec):
    if not isinstance(spec, dict) or not spec.get("spec_sha256"):
        raise ProbeError("frozen coherence spec has no integrity digest")
    core = dict(spec)
    recorded = core.pop("spec_sha256")
    actual = sha256_value(core)
    if recorded != actual:
        raise ProbeError(
            f"frozen coherence spec digest mismatch: {recorded} != {actual}"
        )


def _target_content_digest(rows):
    """Hash source facts, excluding annotations derived from prompt wording."""
    keys = (
        "id",
        "path",
        "lines",
        "low",
        "high",
        "area",
        "bytes",
        "sha256",
    )
    return sha256_value([
        {key: row.get(key) for key in keys}
        for row in rows
    ])


def _target_snapshot(rate, frozen_prompt=None):
    rows = []
    for declared in TARGETS:
        facts = rate.source_awareness.source_facts(declared["path"])
        if not facts.get("exists"):
            raise ProbeError(f"target disappeared: {declared['path']}")
        if facts.get("lines") != declared["lines"]:
            raise ProbeError(
                f"target line count drift for {declared['path']}: "
                f"{facts.get('lines')} != {declared['lines']}"
            )
        expected_low = math.floor(4 * facts["lines"] / 5)
        expected_high = math.ceil(5 * facts["lines"] / 4)
        if (
            declared["low"] != expected_low
            or declared["high"] != expected_high
            or not declared["low"] < facts["lines"] < declared["high"]
        ):
            raise ProbeError(f"invalid frozen thresholds for {declared['path']}")
        rows.append({
            **declared,
            "bytes": facts.get("bytes"),
            "sha256": facts.get("sha256"),
            "named_in_frozen_prompt": (
                declared["path"].casefold() in frozen_prompt.casefold()
                if isinstance(frozen_prompt, str)
                else None
            ),
        })
    payload = {"schema": SCHEMA, "rows": rows}
    payload["sha256"] = _target_content_digest(rows)
    return payload


def _tracked_paths(rate):
    """Repository-relative paths Git actually tracks.

    ``source_awareness.inventory()`` walks the working directory, so it also
    reports files that exist only on this machine: scratch scripts, private
    notes, work in progress. Those must not reach a frozen research prompt.
    They would publish local filenames, and -- worse for the experiment --
    unrelated local work would silently move the directory aggregates and
    file totals the probe is measuring against.
    """
    raw = rate.git("ls-files", "-z")
    paths = {
        entry.replace("\\", "/").strip("/")
        for entry in raw.split("\0")
        if entry.strip()
    }
    if not paths:
        raise ProbeError("git reports no tracked files")
    return paths


def _public_inventory(rate):
    """Tracked-only public inventory rows, plus provenance for the spec."""
    tracked = _tracked_paths(rate)
    source_rows = []
    skipped = 0
    for raw in rate.source_awareness.inventory():
        path = str(raw.get("path") or "").replace("\\", "/").strip("/")
        parts = path.split("/")
        if (
            not path
            or Path(path).is_absolute()
            or ":" in parts[0]
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ProbeError("source inventory contains a non-relative path")
        if path not in tracked:
            skipped += 1
            continue
        try:
            lines = int(raw.get("lines"))
            age_days = float(raw.get("age_days"))
        except (TypeError, ValueError) as exc:
            raise ProbeError("source inventory contains invalid public facts") from exc
        if lines < 0 or not math.isfinite(age_days):
            raise ProbeError("source inventory contains invalid public facts")
        source_rows.append({
            "path": path,
            "lines": lines,
            "age_days": age_days,
        })
    if not source_rows:
        raise ProbeError("source inventory is empty after the tracked filter")
    missing = [
        target["path"] for target in TARGETS
        if target["path"] not in tracked
    ]
    if missing:
        raise ProbeError(
            f"predeclared targets are not Git-tracked: {missing}"
        )
    provenance = {
        "filter": "git_tracked_allowlist",
        "why": (
            "The manifest walker reports working-directory files. Untracked "
            "files would publish local filenames and let unrelated local work "
            "move the aggregates this probe measures."
        ),
        "tracked_index_file_count": len(tracked),
        "manifest_file_count": len(source_rows) + skipped,
        "public_file_count": len(source_rows),
        "excluded_untracked_count": skipped,
        "tracked_index_sha256": sha256_value(sorted(tracked)),
        "public_paths_sha256": sha256_value(
            sorted(row["path"] for row in source_rows)
        ),
    }
    return source_rows, provenance


def _public_source_context(rate):
    """Render only repository-relative public inventory facts.

    The production runtime context also contains persona, selected memories,
    recalled conversations, ambient state, a local clock, edit-log prose, and
    local model details. None of those fields is necessary for this probe.
    """
    source_rows, provenance = _public_inventory(rate)

    areas = {}
    for row in source_rows:
        parts = row["path"].split("/")
        area = "/".join(parts[:2]) if len(parts) > 2 else (
            parts[0] if len(parts) > 1 else "(root)"
        )
        files, lines = areas.get(area, (0, 0))
        areas[area] = (files + 1, lines + row["lines"])
    shape = "; ".join(
        f"{area} {files}f {lines}L"
        for area, (files, lines) in sorted(
            areas.items(),
            key=lambda pair: (-pair[1][1], pair[0]),
        )
    )
    recent_count = int(
        getattr(rate.source_awareness, "RECENT_FILE_COUNT", 12)
    )
    recent = sorted(
        source_rows,
        key=lambda row: (row["age_days"], row["path"]),
    )[:recent_count]
    recent_text = ", ".join(
        f"{row['path']} ({row['lines']}L)" for row in recent
    )
    context = (
        f"Repository inventory: {len(source_rows)} manifest-counted source "
        f"files, {sum(row['lines'] for row in source_rows)} text lines.\n"
        f"Directory shape: {shape}.\n"
        "Recently changed repository-relative paths (recency only, never "
        f"authorship): {recent_text}.\n"
        "The directory figures are aggregates, never per-file counts. The "
        "recent list is partial. It states a listed file's line count but "
        "does not state an unlisted file's line count or nonexistence."
    )
    _assert_privacy_safe(context)
    return context, provenance


def _public_research_prompt(rate):
    context, provenance = _public_source_context(rate)
    prompt = PUBLIC_RESEARCH_PROMPT_HEADER + context
    _assert_privacy_safe(prompt)
    return prompt, provenance


def _repository_binding(rate, output_relative):
    """Hash/strip repository metadata before it can enter an artifact."""
    raw = rate.repo_binding(output_relative)
    safe = _sanitized_binding(raw)
    branch = safe.pop("branch", None)
    if branch is not None:
        safe["branch_sha256"] = sha256_text(branch)
    _assert_privacy_safe(safe)
    return safe


def _safe_live_server_binding(raw_live):
    live = _sanitized_binding(json.loads(json.dumps(raw_live)))
    if not isinstance(live, dict):
        raise ProbeError("live server binding is missing")
    live.pop("sha256", None)
    live["sha256"] = sha256_value(live)
    _assert_privacy_safe(live)
    return live


def _model_file_identity(rate):
    """Size and modification time of the director model, without reading it."""
    model = Path(rate.MODEL_PATH)
    try:
        stat = model.stat()
    except OSError as exc:
        raise ProbeError("configured model file is missing") from exc
    return {
        "basename": model.name,
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _raw_runtime_bindings(rate, carry_model_sha256=None):
    """Collect the audited live bindings, optionally carrying one digest.

    With ``carry_model_sha256`` unset this is exactly ``runtime_bindings()``.
    With it set, the same audited function runs -- every process check, port
    check, and raise -- but the model's content hash is substituted instead of
    re-read.  Substituting inside the real code path rather than rebuilding
    the dict here means a recheck cannot silently diverge from a freeze.

    The model is 4.33 GB and llama-server holds it mapped.  Re-reading it
    before each of 98 dispatches would evict the running server's own pages
    and inflate the prompt-processing timings this experiment records, so the
    per-dispatch recheck carries that one field and the caller proves the
    file's size and modification time are unchanged.  The digest itself is
    computed for real at the freeze and again after the final response.
    """
    if carry_model_sha256 is None:
        return rate.runtime_bindings()
    if len(str(carry_model_sha256)) != 64:
        raise ProbeError("carried model digest is not a SHA-256 value")
    model_path = Path(rate.MODEL_PATH).resolve()
    original = rate.sha256_file

    def carried(path):
        if Path(path).resolve() == model_path:
            return carry_model_sha256
        return original(path)

    rate.sha256_file = carried
    try:
        return rate.runtime_bindings()
    finally:
        rate.sha256_file = original


def _runtime_bindings(rate, carry_model_sha256=None):
    """Separate operator mode from topology and strip local identifiers."""
    raw = _raw_runtime_bindings(rate, carry_model_sha256)
    value = _sanitized_binding(json.loads(json.dumps(raw)))
    value["assistant_mode"] = {
        "value": "hazard",
        "source": "operator_reported",
        "independently_verified": False,
        "scope": (
            "The operator reported the visible Sable UI mode. Process and "
            "port checks below verify topology, not the UI mode label."
        ),
    }
    topology = value.pop("hazard_runtime", None) or {}
    topology_verified = bool(topology.pop("independently_verified", False))
    topology["topology_independently_verified"] = topology_verified
    topology["ui_mode_independently_verified"] = False
    topology["interpretation"] = (
        "PIDs, executable hashes, command-line hashes, helper port 8084, "
        "and absence of listener 8099 are independently checked. They do "
        "not independently prove which UI mode is selected."
    )
    value["runtime_topology"] = topology
    value["live_server"] = _safe_live_server_binding(
        raw.get("live_server")
    )
    _assert_privacy_safe(value)
    return value


def _binary_token_ids(rate):
    result = {}
    for text in ("Yes", "No"):
        response = rate.requests.post(
            rate.SERVER_URL + "/tokenize",
            headers=rate.MODEL_REQUEST_HEADERS,
            json={"content": text, "add_special": False},
            timeout=30,
        )
        response.raise_for_status()
        tokens = response.json().get("tokens")
        if not isinstance(tokens, list) or len(tokens) != 1:
            raise ProbeError(f"{text!r} is not exactly one tokenizer token")
        result[text] = tokens[0]
    if result["Yes"] == result["No"]:
        raise ProbeError("Yes and No unexpectedly share one token id")
    return result


def _resolved_output(rate, output_dir):
    output_dir = Path(output_dir).resolve()
    try:
        output_relative = output_dir.relative_to(rate.ROOT)
    except ValueError as exc:
        raise ProbeError("output directory must stay inside the repository") from exc
    return output_dir, output_relative


def prepare(output_dir):
    """Freeze a privacy-safe live spec without persisting private context.

    The preregistered full-prompt design was revised before any call:
    ``build_system_prompt`` is never invoked. The frozen messages use a
    reproducible public source-inventory prompt, so no persona, memory,
    recalled conversation, local clock, ambient state, or edit-log prose is
    read merely for this probe or allowed into an evidence artifact.
    """
    rate = _live_helpers()
    output_dir, output_relative = _resolved_output(rate, output_dir)

    frozen_prompt, public_inventory = _public_research_prompt(rate)
    targets = _target_snapshot(rate, frozen_prompt=frozen_prompt)
    prompt_artifact = {
        "schema": SCHEMA,
        "system_prompt": frozen_prompt,
        "prompt_class": "privacy_safe_public_source_research_prompt",
        "line_endings": "LF text stored as JSON",
        "production_prompt_persisted": False,
        "production_prompt_used_for_messages": False,
    }
    _assert_privacy_safe(prompt_artifact)

    plan = task_plan()
    for task in plan:
        task["messages_sha256"] = messages_digest(
            construct_messages(frozen_prompt, task)
        )

    repo = _repository_binding(rate, output_relative)
    bindings = _runtime_bindings(rate)
    if len(str(bindings.get("model_sha256") or "")) != 64:
        raise ProbeError("model hash binding failed")
    if len(str(bindings.get("server_bundle_sha256") or "")) != 64:
        raise ProbeError("server-bundle binding failed")
    token_ids = _binary_token_ids(rate)
    spec_core = {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "created_utc": utc_now(),
        "assistant_mode": {
            "value": "hazard",
            "source": "operator_reported",
            "independently_verified": False,
            "collection_route": (
                "direct one-slot director; assistant UI bypassed"
            ),
            "topology_note": (
                "Process hashes and ports are independently bound, but those "
                "signals do not independently establish the visible UI mode."
            ),
        },
        "collector_sha256": sha256_file(Path(__file__).resolve()),
        "audited_helper_sha256": sha256_file(
            HERE / "rate_distortion_probe.py"
        ),
        "call_count": CALL_COUNT,
        "primary_call_count": PRIMARY_CALL_COUNT,
        "independent_unit": "predeclared target file",
        "target_count": len(TARGETS),
        "wording_count": len(WORDINGS),
        "branches_per_target_wording": len(MEASUREMENTS),
        "sentinel_count": 2,
        "plan_seed": PLAN_SEED,
        "sampler": SAMPLER,
        "binary_token_ids": token_ids,
        "repository_state": repo,
        "bindings": bindings,
        "model_file_identity": _model_file_identity(rate),
        "binding_recheck_policy": {
            "when": (
                "the complete sanitized binding is rechecked before every "
                "dispatch and again after the final response"
            ),
            "recomputed_every_dispatch": [
                "director /props identity and chat-template digest",
                "listener process, parent, command-line digest, and "
                "executable content digest",
                "eight-file CPU server bundle digest",
                "llama.cpp revision",
                "Sable assistant parent process and its executable digest",
                "unpooled machinespirit helper on port 8084",
                "absence of any listener on port 8099",
                "console-pulse helper digest",
                "repository state and predeclared target snapshot",
            ],
            "carried_forward": ["bindings.model_sha256"],
            "carried_forward_guard": (
                "model basename, byte size, and mtime_ns must equal "
                "model_file_identity, and the live server must still report "
                "that file as its model"
            ),
            "carried_forward_reason": (
                "Re-reading a 4.33 GB mapped model before each of 98 calls "
                "would evict the running server's pages and inflate the "
                "prompt-processing timings this experiment records."
            ),
            "fully_recomputed_at": ["freeze", "after final response"],
        },
        "prompt_privacy": {
            "production_build_system_prompt_calls": 0,
            "production_prompt_persisted": False,
            "production_prompt_used_for_messages": False,
            "protocol_revision_timing": "before first live model call",
            "protocol_revision_reason": (
                "The preregistered full production prompt could contain "
                "private persona, memory, conversation, ambient, clock, and "
                "runtime text. Reading it merely to discard it would add "
                "privacy risk and runtime side effects without experimental "
                "value."
            ),
            "excluded_context_classes": [
                "persona and chosen-name state",
                "stored memory",
                "recalled conversation",
                "ambient and room state",
                "trusted local clock",
                "edit-log prose",
                "absolute runtime paths",
            ],
            "included_context_classes": [
                "fixed public research instructions",
                "repository-relative inventory totals",
                "directory aggregates",
                "repository-relative recent source paths",
            ],
        },
        "public_inventory": public_inventory,
        "prompt_artifact_sha256": sha256_value(prompt_artifact),
        "system_prompt_sha256": sha256_text(frozen_prompt),
        "target_artifact_sha256": sha256_value(targets),
        "target_snapshot_sha256": targets["sha256"],
        "wordings": list(WORDINGS),
        "tasks": plan,
        "task_plan_sha256": sha256_value(plan),
        "gates": {
            "coherence_tolerance": COHERENCE_TOLERANCE,
            "order_tolerance": ORDER_TOLERANCE,
            "qq_tolerance": QQ_TOLERANCE,
            "sentinel_tolerance": SENTINEL_TOLERANCE,
            "probability_sum_tolerance": PROBABILITY_SUM_TOLERANCE,
            "minimum_paraphrase_sign_agreement": (
                MIN_PARAPHRASE_SIGN_AGREEMENT
            ),
            "informativeness": (
                "In each wording, at least one target must have "
                "q(A)>0.9 and q(B)<0.1."
            ),
        },
        "schedule_note": (
            "T01/W0 AB and BA blocks run first so their direct probabilities "
            "are early anchors. The other 30 three-call blocks are shuffled "
            "once with the frozen plan seed. Exact direct A and B calls are "
            "replayed as calls 97 and 98."
        ),
        "failure_rule": (
            "Dispatch intent is fsynced before each request. A transport, "
            "format, probability, source, repository, live-binding, or "
            "keepalive failure is written and stops the run. It is never "
            "retried under the same frozen collection."
        ),
        "interpretation_rules": [
            (
                "The sequential joints satisfy the law of total probability "
                "by construction. Cross-order marginal differences are "
                "marginal-selectivity/context effects, not LTP violations."
            ),
            (
                "QQ residuals are a descriptive screen only. Neither zero nor "
                "nonzero establishes quantum contextuality or sheaf structure."
            ),
            (
                "Balanced bit-price is algebraically the same signed "
                "log-odds contrast as the monotonic coherence edge; it is not "
                "independent evidence and needs known truth."
            ),
            (
                "Two wordings are repeated measurements within a file, not "
                "additional independent units. Generalization beyond the "
                "eight selected source areas is not licensed."
            ),
            (
                "The privacy-safe research prompt deliberately excludes the "
                "assistant's private production persona, memories, recalled "
                "conversation, ambient state, clock, and edit logs. Results "
                "describe this controlled director context, not a full Sable "
                "production turn."
            ),
            (
                "No statistic grants the decoder authority. Trusted source "
                "reads remain mandatory under every outcome."
            ),
        ],
        "authority": "offline descriptive research only; no production gate",
    }
    spec = dict(spec_core)
    spec["spec_sha256"] = sha256_value(spec_core)
    _assert_privacy_safe(targets)
    _assert_privacy_safe(spec)
    return {
        "output_dir": output_dir,
        "output_relative": output_relative,
        "prompt_artifact": prompt_artifact,
        "target_artifact": targets,
        "spec": spec,
    }


def _validate_frozen_artifacts(prompt_artifact, target_artifact, spec):
    _assert_privacy_safe(prompt_artifact)
    _assert_privacy_safe(target_artifact)
    _assert_privacy_safe(spec)
    validate_spec_integrity(spec)
    if sha256_value(prompt_artifact) != spec.get("prompt_artifact_sha256"):
        raise ProbeError("frozen coherence prompt artifact changed")
    if sha256_value(target_artifact) != spec.get("target_artifact_sha256"):
        raise ProbeError("frozen coherence target artifact changed")
    if (
        _target_content_digest(target_artifact.get("rows", []))
        != target_artifact.get("sha256")
        or target_artifact.get("sha256")
        != spec.get("target_snapshot_sha256")
    ):
        raise ProbeError("frozen target snapshot is inconsistent")
    if sha256_value(spec.get("tasks", [])) != spec.get("task_plan_sha256"):
        raise ProbeError("frozen task plan changed")
    system_prompt = prompt_artifact.get("system_prompt")
    if sha256_text(system_prompt) != spec.get("system_prompt_sha256"):
        raise ProbeError("frozen system prompt changed")
    if (
        spec.get("call_count") != CALL_COUNT
        or len(spec.get("tasks", [])) != CALL_COUNT
    ):
        raise ProbeError("frozen spec is not the 98-call protocol")
    for task in spec["tasks"]:
        actual = messages_digest(construct_messages(system_prompt, task))
        if actual != task.get("messages_sha256"):
            raise ProbeError(
                f"frozen messages changed for {task.get('trial_id')}"
            )


def _load_artifacts(output_dir):
    output_dir = Path(output_dir).resolve()
    missing = [
        name for name in ARTIFACT_NAMES
        if not (output_dir / name).is_file()
    ]
    if missing:
        raise ProbeError(f"missing frozen coherence artifacts: {missing}")
    prompt_artifact = json.loads(
        (output_dir / "coherence_prompt.json").read_text(encoding="utf-8")
    )
    target_artifact = json.loads(
        (output_dir / "coherence_targets.json").read_text(encoding="utf-8")
    )
    spec = json.loads(
        (output_dir / "coherence_spec.json").read_text(encoding="utf-8")
    )
    _validate_frozen_artifacts(prompt_artifact, target_artifact, spec)
    return {
        "output_dir": output_dir,
        "prompt_artifact": prompt_artifact,
        "target_artifact": target_artifact,
        "spec": spec,
    }


def _load_or_create_live(output_dir):
    rate = _live_helpers()
    output_dir, output_relative = _resolved_output(rate, output_dir)
    existing = [
        name for name in ARTIFACT_NAMES
        if (output_dir / name).exists()
    ]
    rows_path = output_dir / "coherence_rows.jsonl"
    dispatch_path = output_dir / "coherence_dispatch.jsonl"
    if existing:
        if len(existing) != len(ARTIFACT_NAMES):
            raise ProbeError("resume requires every frozen coherence artifact")
        prepared = _load_artifacts(output_dir)
        spec = prepared["spec"]
        if spec.get("collector_sha256") != sha256_file(Path(__file__).resolve()):
            raise ProbeError("collector changed since collection was frozen")
        if spec.get("audited_helper_sha256") != sha256_file(
            HERE / "rate_distortion_probe.py"
        ):
            raise ProbeError("audited live helper changed since freeze")
        if spec.get("sampler") != SAMPLER:
            raise ProbeError("binary sampler changed since freeze")
        current_targets = _target_snapshot(rate)
        if current_targets["sha256"] != spec["target_snapshot_sha256"]:
            raise ProbeError("target sources drifted since freeze")
        if (
            _repository_binding(rate, output_relative)
            != spec["repository_state"]
        ):
            raise ProbeError("repository drifted since freeze")
        if _runtime_bindings(rate) != spec["bindings"]:
            raise ProbeError("live hazard/model/server binding drifted")
        prepared["output_relative"] = output_relative
        return prepared

    if rows_path.exists() or dispatch_path.exists():
        raise ProbeError(
            "journals exist without frozen artifacts; refusing contamination"
        )
    prepared = prepare(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_json(
        output_dir / "coherence_prompt.json",
        prepared["prompt_artifact"],
    )
    _atomic_json(
        output_dir / "coherence_targets.json",
        prepared["target_artifact"],
    )
    _atomic_json(output_dir / "coherence_spec.json", prepared["spec"])
    return prepared


def _task_expected_fields(task, spec):
    return {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "spec_sha256": spec["spec_sha256"],
        "trial_id": task["trial_id"],
        "execution_order": task["execution_order"],
        "target_id": task["target_id"],
        "target_path": task["target_path"],
        "wording_id": task["wording_id"],
        "order": task["order"],
        "measurement": task["measurement"],
        "event": task["event"],
        "truth_is_yes": task["truth_is_yes"],
        "question": task["question"],
        "prior_event": task["prior_event"],
        "prior_question": task["prior_question"],
        "forced_prior_answer": task["forced_prior_answer"],
        "sentinel": task["sentinel"],
        "replay_of": task["replay_of"],
        "messages_sha256": task["messages_sha256"],
        "sampler": spec["sampler"],
    }


def validate_rows_offline(rows, dispatches, spec):
    _assert_privacy_safe(spec)
    tasks = sorted(spec["tasks"], key=lambda item: item["execution_order"])
    if len(rows) > len(tasks) or len(dispatches) > len(tasks):
        raise ProbeError("journals exceed the frozen 98-call plan")
    if len(rows) != len(dispatches):
        raise ProbeError(
            "dispatch/response journal lengths differ; the in-flight call "
            "must never be retried"
        )
    seen = set()
    for index, (row, dispatch) in enumerate(zip(rows, dispatches)):
        _assert_privacy_safe(row)
        _assert_privacy_safe(dispatch)
        task = tasks[index]
        if task["trial_id"] in seen:
            raise ProbeError("duplicate task in coherence journal")
        seen.add(task["trial_id"])
        expected = _task_expected_fields(task, spec)
        for field, value in expected.items():
            if row.get(field) != value:
                raise ProbeError(
                    f"row {task['trial_id']} changed field {field}"
                )
        if dispatch.get("trial_id") != task["trial_id"]:
            raise ProbeError("dispatch journal is not the contiguous plan prefix")
        for field in (
            "spec_sha256",
            "execution_order",
            "messages_sha256",
        ):
            if dispatch.get(field) != expected[field]:
                raise ProbeError(
                    f"dispatch {task['trial_id']} changed field {field}"
                )
        bindings = spec.get("bindings")
        if bindings is not None:
            live_sha = bindings["live_server"]["sha256"]
            if row.get("bindings") != bindings:
                raise ProbeError(
                    f"row {task['trial_id']} changed runtime bindings"
                )
            if row.get("live_server_identity_sha256") != live_sha:
                raise ProbeError(
                    f"row {task['trial_id']} changed live-server binding"
                )
            if dispatch.get("live_server_identity_sha256") != live_sha:
                raise ProbeError(
                    f"dispatch {task['trial_id']} changed live-server binding"
                )
        target_sha = spec.get("target_snapshot_sha256")
        if target_sha is not None:
            if (
                row.get("target_snapshot_before_sha256") != target_sha
                or dispatch.get("target_snapshot_sha256") != target_sha
            ):
                raise ProbeError(
                    f"row {task['trial_id']} changed target binding"
                )
            if row.get("status") == "ok" and (
                row.get("target_snapshot_after_sha256") != target_sha
                or row.get("target_drift")
            ):
                raise ProbeError(
                    f"row {task['trial_id']} contains target drift"
                )
        repository = spec.get("repository_state")
        if repository is not None:
            before = row.get("repository_state_before")
            if before != repository:
                raise ProbeError(
                    f"row {task['trial_id']} changed repository binding"
                )
            if dispatch.get("repository_dirty_digest") != repository.get(
                "dirty_digest"
            ):
                raise ProbeError(
                    f"dispatch {task['trial_id']} changed repository binding"
                )
            if row.get("status") == "ok" and (
                row.get("repository_state_after") != repository
                or row.get("repository_drift")
            ):
                raise ProbeError(
                    f"row {task['trial_id']} contains repository drift"
                )
        if row.get("status") == "ok":
            parsed = parse_binary_response(
                row.get("answer"),
                row.get("logprobs"),
                spec.get("binary_token_ids"),
            )
            for field in (
                "normalized_answer",
                "yes_probability",
                "no_probability",
                "binary_probability_sum",
                "q_yes",
                "probability_entry",
            ):
                left, right = row.get(field), parsed[field]
                if isinstance(right, float):
                    if not math.isclose(
                        float(left), right, rel_tol=0.0, abs_tol=1e-12
                    ):
                        raise ProbeError(
                            f"row {task['trial_id']} changed {field}"
                        )
                elif left != right:
                    raise ProbeError(
                        f"row {task['trial_id']} changed {field}"
                    )
        elif row.get("status") != "error":
            raise ProbeError("row status must be ok or error")
        if row.get("status") == "error" and index != len(rows) - 1:
            raise ProbeError("a no-retry failure must be the final stored row")


def load_frozen_offline(output_dir):
    """Load preserved evidence without importing production or going online."""
    prepared = _load_artifacts(output_dir)
    rows = _read_jsonl(prepared["output_dir"] / "coherence_rows.jsonl")
    dispatches = _read_jsonl(
        prepared["output_dir"] / "coherence_dispatch.jsonl"
    )
    validate_rows_offline(rows, dispatches, prepared["spec"])
    prepared.update({"rows": rows, "dispatches": dispatches})
    return prepared


def _request_binary(rate, messages, sampler, slot, token_ids):
    started = utc_now()
    wall_start = time.perf_counter()
    response = rate.requests.post(
        rate.SERVER_URL + "/v1/chat/completions",
        headers=rate.MODEL_REQUEST_HEADERS,
        json={**sampler, "messages": messages},
        timeout=rate.TIMEOUT_SECONDS,
    )
    elapsed = time.perf_counter() - wall_start
    ended = utc_now()
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProbeError("binary completion returned no choice")
    choice = choices[0]
    message = choice.get("message") or {}
    answer = message.get("content")
    if not isinstance(answer, str):
        raise ProbeError("binary completion returned no text")
    logprobs = choice.get("logprobs")
    parsed = parse_binary_response(answer, logprobs, token_ids)
    return {
        "answer": answer,
        "logprobs": logprobs,
        **parsed,
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage") or {},
        "timings": data.get("timings") or {},
        "precall_slot": slot,
        "started_utc": started,
        "ended_utc": ended,
        "elapsed_seconds": round(elapsed, 6),
    }


def _validate_live_resume(rows, dispatches, prepared):
    validate_rows_offline(rows, dispatches, prepared["spec"])
    if rows and rows[-1].get("status") == "error":
        raise ProbeError(
            "the frozen collection already contains a failed dispatch; "
            "the no-retry rule forbids continuation"
        )
    rate = _live_helpers()
    spec = prepared["spec"]
    for row in rows:
        if (
            row.get("target_snapshot_before_sha256")
            != spec["target_snapshot_sha256"]
            or row.get("target_snapshot_after_sha256")
            != spec["target_snapshot_sha256"]
            or row.get("target_drift")
            or row.get("repository_drift")
        ):
            raise ProbeError("stored row contains source/repository drift")
        if (
            row.get("repository_state_before") != spec["repository_state"]
            or row.get("repository_state_after") != spec["repository_state"]
        ):
            raise ProbeError("stored row repository binding changed")
        if (
            row.get("live_server_identity_sha256")
            != spec["bindings"]["live_server"]["sha256"]
        ):
            raise ProbeError("stored row live-server identity changed")


def analyze(rows, spec):
    """Analyze frozen rows.  This function has no repository/live dependency."""
    tasks = sorted(spec["tasks"], key=lambda item: item["execution_order"])
    task_by_id = {task["trial_id"]: task for task in tasks}
    ok = {
        row["trial_id"]: row
        for row in rows
        if row.get("status") == "ok"
        and row.get("trial_id") in task_by_id
    }
    complete = (
        len(rows) == spec["call_count"]
        and len(ok) == spec["call_count"]
        and set(ok) == set(task_by_id)
    )
    stored_errors = [
        {
            "trial_id": row.get("trial_id"),
            "error_type": row.get("error_type"),
            "error": row.get("error"),
        }
        for row in rows
        if row.get("status") == "error"
    ]

    sentinel_results = []
    for task in tasks:
        if not task.get("sentinel"):
            continue
        replay = ok.get(task["trial_id"])
        original = ok.get(task["replay_of"])
        difference = (
            abs(replay["q_yes"] - original["q_yes"])
            if replay is not None and original is not None
            else None
        )
        sentinel_results.append({
            "trial_id": task["trial_id"],
            "replay_of": task["replay_of"],
            "absolute_q_difference": difference,
            "passes": (
                difference is not None
                and difference <= SENTINEL_TOLERANCE
            ),
        })
    sentinel_gate = (
        len(sentinel_results) == 2
        and all(item["passes"] for item in sentinel_results)
    )

    units = []
    for target in TARGETS:
        for wording in WORDINGS:
            matching = {}
            for task in tasks:
                if (
                    task["sentinel"]
                    or task["target_id"] != target["id"]
                    or task["wording_id"] != wording["id"]
                ):
                    continue
                row = ok.get(task["trial_id"])
                if row is not None:
                    matching[task["measurement"]] = row["q_yes"]
            if set(matching) != set(MEASUREMENTS):
                continue
            units.append({
                "target_id": target["id"],
                "target_path": target["path"],
                "wording_id": wording["id"],
                **response_unit_statistics(matching),
            })

    target_results = []
    for target in TARGETS:
        pair = [
            unit for unit in units
            if unit["target_id"] == target["id"]
        ]
        if len(pair) != len(WORDINGS):
            continue
        by_wording = {item["wording_id"]: item for item in pair}
        coherence_signs = [
            _sign(item["coherence_delta"], COHERENCE_TOLERANCE)
            for item in pair
        ]
        delta_a_signs = [
            _sign(item["marginal_selectivity_a"], ORDER_TOLERANCE)
            for item in pair
        ]
        delta_b_signs = [
            _sign(item["marginal_selectivity_b"], ORDER_TOLERANCE)
            for item in pair
        ]
        qq_signs = [
            _sign(item["qq_residual"], QQ_TOLERANCE)
            for item in pair
        ]
        target_results.append({
            "target_id": target["id"],
            "target_path": target["path"],
            "wordings": by_wording,
            "mean_coherence_delta": _mean(
                item["coherence_delta"] for item in pair
            ),
            "robust_coherence_violation": all(
                item["coherence_violation"] for item in pair
            ),
            "coherence_sign_agreement": (
                coherence_signs[0] == coherence_signs[1]
                and coherence_signs[0] != 0
            ),
            "mean_balanced_bit_price": _mean(
                item["balanced_mean_bit_price"] for item in pair
            ),
            "mean_marginal_selectivity_a": _mean(
                item["marginal_selectivity_a"] for item in pair
            ),
            "mean_marginal_selectivity_b": _mean(
                item["marginal_selectivity_b"] for item in pair
            ),
            "robust_order_effect_a": (
                delta_a_signs[0] == delta_a_signs[1]
                and delta_a_signs[0] != 0
            ),
            "robust_order_effect_b": (
                delta_b_signs[0] == delta_b_signs[1]
                and delta_b_signs[0] != 0
            ),
            "mean_qq_residual": _mean(
                item["qq_residual"] for item in pair
            ),
            "robust_qq_residual": (
                qq_signs[0] == qq_signs[1] and qq_signs[0] != 0
            ),
        })

    coherence_signs = [
        _sign(item["mean_coherence_delta"], COHERENCE_TOLERANCE)
        for item in target_results
    ]
    coherence_positive = coherence_signs.count(1)
    coherence_negative = coherence_signs.count(-1)
    coherence_p = exact_sign_test(coherence_positive, coherence_negative)

    order_tests = []
    for endpoint in ("a", "b"):
        signs = [
            _sign(
                item[f"mean_marginal_selectivity_{endpoint}"],
                ORDER_TOLERANCE,
            )
            for item in target_results
        ]
        positive, negative = signs.count(1), signs.count(-1)
        order_tests.append({
            "endpoint": endpoint.upper(),
            "positive": positive,
            "negative": negative,
            "ties": signs.count(0),
            "two_sided_exact_sign_p": exact_sign_test(positive, negative),
        })
    adjusted = holm_adjusted_pvalues(
        item["two_sided_exact_sign_p"] for item in order_tests
    )
    for item, value in zip(order_tests, adjusted):
        item["holm_adjusted_p"] = value

    informative_by_wording = {}
    for wording in WORDINGS:
        relevant = [
            unit for unit in units
            if unit["wording_id"] == wording["id"]
        ]
        informative_by_wording[wording["id"]] = any(
            item["informative_curve"] for item in relevant
        )
    informativeness_gate = (
        len(informative_by_wording) == len(WORDINGS)
        and all(informative_by_wording.values())
    )
    sign_agreement_count = sum(
        item["coherence_sign_agreement"] for item in target_results
    )
    wording_gate = (
        sign_agreement_count >= MIN_PARAPHRASE_SIGN_AGREEMENT
    )
    robust_violations = sum(
        item["robust_coherence_violation"] for item in target_results
    )
    collection_gate = complete and not stored_errors
    probability_valid = collection_gate and sentinel_gate

    if not probability_valid:
        recommendation = "void_collection"
    elif not informativeness_gate:
        recommendation = "low_resolution_binary_instrument"
    elif not wording_gate:
        recommendation = "wording_sensitive_descriptive_result"
    else:
        recommendation = "bounded_descriptive_result"

    return {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "spec_sha256": spec["spec_sha256"],
        "analyzed_utc": utc_now(),
        "completed_rows": len(rows),
        "successful_rows": len(ok),
        "expected_rows": spec["call_count"],
        "completed_units": len(units),
        "expected_units": len(TARGETS) * len(WORDINGS),
        "independent_targets_completed": len(target_results),
        "stored_errors": stored_errors,
        "gates": {
            "collection_complete": collection_gate,
            "sentinel_probability_stable": sentinel_gate,
            "probability_valid": probability_valid,
            "informative_by_wording": informative_by_wording,
            "informativeness": informativeness_gate,
            "paraphrase_sign_agreement_count": sign_agreement_count,
            "paraphrase_generalization": wording_gate,
        },
        "sentinels": sentinel_results,
        "coherence": {
            "tolerance": COHERENCE_TOLERANCE,
            "robust_target_violations": robust_violations,
            "target_count": len(target_results),
            "robust_violation_wilson_95": wilson_interval(
                robust_violations,
                len(target_results),
            ),
            "positive_target_deltas": coherence_positive,
            "negative_target_deltas": coherence_negative,
            "tied_target_deltas": coherence_signs.count(0),
            "two_sided_exact_sign_p": coherence_p,
            "median_target_delta": _median(
                item["mean_coherence_delta"] for item in target_results
            ),
            "note": (
                "A positive delta means q(high false threshold) exceeded "
                "q(low true threshold). Zero violations in eight selected "
                "targets cannot certify a low population violation rate."
            ),
        },
        "order_context": {
            "tests": order_tests,
            "robust_effect_a_targets": sum(
                item["robust_order_effect_a"] for item in target_results
            ),
            "robust_effect_b_targets": sum(
                item["robust_order_effect_b"] for item in target_results
            ),
            "median_absolute_a_residual": _median(
                abs(item["mean_marginal_selectivity_a"])
                for item in target_results
            ),
            "median_absolute_b_residual": _median(
                abs(item["mean_marginal_selectivity_b"])
                for item in target_results
            ),
            "law_of_total_probability_note": (
                "Each joint obeys total probability by construction. These "
                "are cross-order marginal-selectivity/context residuals."
            ),
        },
        "qq_screen": {
            "tolerance": QQ_TOLERANCE,
            "robust_residual_targets": sum(
                item["robust_qq_residual"] for item in target_results
            ),
            "median_absolute_residual": _median(
                abs(item["mean_qq_residual"]) for item in target_results
            ),
            "note": (
                "Descriptive compatibility screen only; no contextuality, "
                "quantum, sheaf, or cohomology inference is licensed."
            ),
        },
        "bit_price": {
            "median_target_balanced_bits": _median(
                item["mean_balanced_bit_price"]
                for item in target_results
            ),
            "positive_target_count": sum(
                item["mean_balanced_bit_price"] > 1e-12
                for item in target_results
            ),
            "note": (
                "Balanced bit-price is exactly half the direct high-vs-low "
                "log-odds contrast. It is a magnitude scale for the same "
                "coherence edge, not independent evidence or a truth detector."
            ),
        },
        "units": units,
        "targets": target_results,
        "recommendation": recommendation,
        "descriptive_only": True,
        "authority_note": (
            "No outcome changes production behavior or replaces a trusted "
            "source read. The free-form forced-honest-token experiment remains "
            "unsupported because no independent honest-token/continuation "
            "checker was frozen."
        ),
    }


def run(output_dir):
    rate = _live_helpers()
    prepared = _load_or_create_live(output_dir)
    output_dir = prepared["output_dir"]
    output_relative = prepared["output_relative"]
    prompt = prepared["prompt_artifact"]["system_prompt"]
    spec = prepared["spec"]
    rows_path = output_dir / "coherence_rows.jsonl"
    dispatch_path = output_dir / "coherence_dispatch.jsonl"
    rows = _read_jsonl(rows_path)
    dispatches = _read_jsonl(dispatch_path)
    _validate_live_resume(rows, dispatches, prepared)
    completed = {row["trial_id"] for row in rows}

    # The audited wait helper needs its native in-memory identity. It is never
    # serialized; only the recursively sanitized equivalent is frozen.
    raw_live_server = rate.live_server_identity()
    if (
        _safe_live_server_binding(raw_live_server)
        != spec["bindings"]["live_server"]
    ):
        raise ProbeError("live server drifted before collection")

    frozen_model_sha256 = spec["bindings"]["model_sha256"]
    frozen_model_identity = spec["model_file_identity"]

    def recheck_full_binding(label):
        """Void the batch on any topology, helper, port, or server change."""
        if _model_file_identity(rate) != frozen_model_identity:
            raise ProbeError(f"director model file changed {label}")
        current = _runtime_bindings(
            rate,
            carry_model_sha256=frozen_model_sha256,
        )
        if current != spec["bindings"]:
            raise ProbeError(f"live runtime/topology binding drifted {label}")

    assistant_pid = spec[
        "bindings"
    ]["runtime_topology"]["assistant"]["pid"]
    keepalive = rate.ConsoleKeepalive(assistant_pid)
    keepalive.start()
    atexit.register(keepalive.stop)
    try:
        for task in sorted(
            spec["tasks"],
            key=lambda item: item["execution_order"],
        ):
            if task["trial_id"] in completed:
                continue
            keepalive.check()
            recheck_full_binding(f"before {task['trial_id']}")
            before_repo = _repository_binding(rate, output_relative)
            before_targets = _target_snapshot(rate)
            if before_repo != spec["repository_state"]:
                raise ProbeError(f"repository drift before {task['trial_id']}")
            if before_targets["sha256"] != spec["target_snapshot_sha256"]:
                raise ProbeError(f"target drift before {task['trial_id']}")

            messages = construct_messages(prompt, task)
            if messages_digest(messages) != task["messages_sha256"]:
                raise ProbeError(f"message drift before {task['trial_id']}")
            slot = rate._wait_for_idle_slot(
                raw_live_server
            )
            base = {
                **_task_expected_fields(task, spec),
                "bindings": spec["bindings"],
                "live_server_identity_sha256": spec[
                    "bindings"
                ]["live_server"]["sha256"],
                "repository_state_before": before_repo,
                "target_snapshot_before_sha256": before_targets["sha256"],
            }
            _append_jsonl(dispatch_path, {
                "schema": SCHEMA,
                "experiment": EXPERIMENT,
                "event": "dispatch_intent",
                "trial_id": task["trial_id"],
                "execution_order": task["execution_order"],
                "spec_sha256": spec["spec_sha256"],
                "messages_sha256": task["messages_sha256"],
                "repository_dirty_digest": before_repo["dirty_digest"],
                "target_snapshot_sha256": before_targets["sha256"],
                "live_server_identity_sha256": base[
                    "live_server_identity_sha256"
                ],
                "precall_slot": slot,
                "recorded_utc": utc_now(),
            })
            try:
                response = _request_binary(
                    rate,
                    messages,
                    spec["sampler"],
                    slot,
                    spec["binary_token_ids"],
                )
                after_targets = _target_snapshot(rate)
                after_repo = _repository_binding(rate, output_relative)
                row = {
                    **base,
                    "status": "ok",
                    **response,
                    "target_snapshot_after_sha256": after_targets["sha256"],
                    "repository_state_after": after_repo,
                    "target_drift": (
                        after_targets["sha256"]
                        != spec["target_snapshot_sha256"]
                    ),
                    "repository_drift": (
                        after_repo != spec["repository_state"]
                    ),
                }
            except Exception as error:
                row = {
                    **base,
                    "status": "error",
                    "error_type": type(error).__name__,
                    "error": _sanitize_free_text(str(error))[:1000],
                    "ended_utc": utc_now(),
                }
                _append_jsonl(rows_path, row)
                raise

            _append_jsonl(rows_path, row)
            keepalive.check()
            print(
                f"{task['execution_order']:02d}/{CALL_COUNT} "
                f"{task['trial_id']} qYes={row['q_yes']:.6f} "
                f"{row['elapsed_seconds']:.2f}s",
                flush=True,
            )
            if row["target_drift"] or row["repository_drift"]:
                raise ProbeError(f"drift after {task['trial_id']}")

        # The closing check re-reads the model for real, so the one field the
        # per-dispatch rechecks carried forward is proven at least once after
        # the last response rather than only before the first.
        if _model_file_identity(rate) != frozen_model_identity:
            raise ProbeError("director model file changed during collection")
        if _runtime_bindings(rate) != spec["bindings"]:
            raise ProbeError("live runtime/topology binding drifted at close")
        final_targets = _target_snapshot(rate)
        final_repo = _repository_binding(rate, output_relative)
        if final_targets["sha256"] != spec["target_snapshot_sha256"]:
            raise ProbeError("target sources drifted during collection")
        if final_repo != spec["repository_state"]:
            raise ProbeError("repository drifted during collection")
        rows = _read_jsonl(rows_path)
        dispatches = _read_jsonl(dispatch_path)
        validate_rows_offline(rows, dispatches, spec)
        summary = analyze(rows, spec)
        summary["target_snapshot_after_sha256"] = final_targets["sha256"]
        summary["repository_state_after"] = final_repo
        _atomic_json(output_dir / "coherence_summary.json", summary)
        return summary
    finally:
        keepalive.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(
            ROOT
            / "handoffs"
            / "researchc_experiments_2026-07-30"
            / "coherence"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print a new frozen spec without completions",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="reanalyze preserved artifacts without Sable or the repository",
    )
    args = parser.parse_args(argv)
    if args.dry_run:
        prepared = prepare(args.out)
        spec = prepared["spec"]
        print(json.dumps({
            "experiment": spec["experiment"],
            "output": str(prepared["output_dir"]),
            "spec_sha256": spec["spec_sha256"],
            "calls": spec["call_count"],
            "targets": spec["target_count"],
            "wordings": spec["wording_count"],
            "bindings": spec["bindings"],
            "binary_token_ids": spec["binary_token_ids"],
        }, indent=2, sort_keys=True))
        return 0
    if args.analyze_only:
        prepared = load_frozen_offline(args.out)
        summary = analyze(prepared["rows"], prepared["spec"])
        _atomic_json(
            prepared["output_dir"] / "coherence_summary.json",
            summary,
        )
    else:
        summary = run(args.out)
    print(json.dumps({
        "recommendation": summary["recommendation"],
        "descriptive_only": summary["descriptive_only"],
        "completed_rows": summary["completed_rows"],
        "gates": summary["gates"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
