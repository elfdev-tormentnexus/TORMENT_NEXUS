"""Research C uncertainty sidecars and privacy-safe measurement records.

The sidecar describes one model call. It never enters an embedding and never
authorizes an action. Research C's first job is to collect the held-out table
that could justify a refusal or routing threshold later; until that table
exists, every existing deterministic guard remains the decision-maker.

Only digests, sampler settings, numeric measurements, timings, and bounded
outcome labels are written. Prompt, response, source, and memory text are not.
"""

import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone


ASSISTANT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ASSISTANT_ROOT)
LOG_FILE = os.path.join(ASSISTANT_ROOT, "logs", "research_c.jsonl")
SCHEMA = 1

_MODES = {"off": 0, "top2": 2, "top10": 10}
_DEFAULT_MODE = "top2"
_MODEL_DIGEST_ENV = "TORMENT_NEXUS_RESEARCHC_MODEL_SHA256"
_WORKER_MODEL_DIGEST_ENV = "TORMENT_NEXUS_RESEARCHC_WORKER_SHA256"
_SERVER_REVISION_ENV = "TORMENT_NEXUS_LLAMA_REVISION"
_SAFE_OUTCOME_LABELS = {
    "authorship",
    "byte_count",
    "definition",
    "empty",
    "existence",
    "fact",
    "goal",
    "hardware",
    "instruction",
    "line_count",
    "meta_commentary",
    "not_about_person",
    "other",
    "outline",
    "personal",
    "preference",
    "project",
    "question",
    "too_long",
    "too_short",
    "transient_state",
    "unknown",
}


def mode():
    """Configured candidate depth; top-2 is the measured default."""
    selected = os.environ.get(
        "TORMENT_NEXUS_RESEARCHC_LOGPROBS", _DEFAULT_MODE
    ).strip().casefold()
    return selected if selected in _MODES else _DEFAULT_MODE


def request_fields(selected=None):
    """OpenAI-compatible request fields, or nothing when measurement is off."""
    selected = mode() if selected is None else str(selected).casefold()
    top = _MODES.get(selected, _MODES[_DEFAULT_MODE])
    if top <= 0:
        return {}
    return {"logprobs": True, "top_logprobs": top}


def digest(*parts):
    """One opaque identifier for text that must never enter the log."""
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def prompt_digest(messages):
    return digest(messages)


def sampler_record(payload):
    """Only serving controls that can change the reported distribution."""
    return {
        key: payload.get(key)
        for key in (
            "temperature",
            "top_k",
            "top_p",
            "min_p",
            "repeat_penalty",
            "seed",
            "max_tokens",
        )
        if key in payload
    }


def _content(logprobs):
    if isinstance(logprobs, dict):
        logprobs = logprobs.get("content")
    return logprobs if isinstance(logprobs, list) else []


def _positions(entries, response_text):
    """Best-effort character intervals for llama.cpp's rendered tokens."""
    cursor = 0
    positions = []
    text = str(response_text or "")

    for entry in entries:
        token = entry.get("token")
        if not isinstance(token, str):
            positions.append(None)
            continue

        if text.startswith(token, cursor):
            start = cursor
        else:
            start = text.find(token, cursor)
            if start < 0:
                positions.append(None)
                continue

        cursor = start + len(token)
        positions.append((start, cursor))

    return positions


def _span_intervals(response_text, spans):
    intervals = []
    text = str(response_text or "")

    for span in spans or ():
        span = str(span or "")
        if not span:
            continue
        start = 0
        while True:
            found = text.find(span, start)
            if found < 0:
                break
            intervals.append((found, found + len(span)))
            start = found + max(1, len(span))

    return intervals


def measure(logprobs, response_text="", spans=None):
    """Chosen-token surprisal and top-one/top-two margin for selected spans."""
    entries = _content(logprobs)
    if not entries:
        return None

    selected = entries
    intervals = _span_intervals(response_text, spans)
    if spans:
        positions = _positions(entries, response_text)
        selected = [
            entry
            for entry, position in zip(entries, positions)
            if position is not None
            and any(
                position[0] < end and start < position[1]
                for start, end in intervals
            )
        ]

    surprisals = []
    margins = []
    for entry in selected:
        try:
            chosen = float(entry["logprob"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(chosen):
            surprisals.append(max(0.0, -chosen))

        candidates = []
        for candidate in entry.get("top_logprobs") or ():
            try:
                value = float(candidate["logprob"])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(value):
                candidates.append(value)
        if len(candidates) >= 2:
            candidates.sort(reverse=True)
            margins.append(
                max(0.0, math.exp(candidates[0]) - math.exp(candidates[1]))
            )

    if not surprisals:
        return None

    worst_count = max(1, math.ceil(len(surprisals) * 0.1))
    worst = sorted(surprisals, reverse=True)[:worst_count]
    return {
        "token_count": len(surprisals),
        "mean_surprisal": sum(surprisals) / len(surprisals),
        "worst_decile_surprisal": sum(worst) / len(worst),
        "peak_surprisal": max(surprisals),
        "mean_top1_top2_margin": (
            sum(margins) / len(margins) if margins else None
        ),
        "minimum_top1_top2_margin": min(margins) if margins else None,
        "margin_token_count": len(margins),
    }


def _manifest_model_digest(model_path):
    """Read a packaged content hash without hashing a multi-gigabyte file."""
    candidates = (
        os.path.join(PROJECT_ROOT, "RELEASE_MANIFEST.json"),
        os.path.join(PROJECT_ROOT, "release_manifest.json"),
    )
    wanted = os.path.basename(str(model_path or "")).casefold()

    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            continue

        records = payload.get("model_artifacts") or payload.get("models") or ()
        for record in records:
            name = os.path.basename(str(
                record.get("path") or record.get("name") or ""
            )).casefold()
            value = str(record.get("sha256") or "").casefold()
            if name == wanted and len(value) == 64:
                return value

    return None


def _manifest_server_digest():
    """Bind packaged serving behavior to the shipped llama-server binary."""
    candidates = (
        os.path.join(PROJECT_ROOT, "RELEASE_MANIFEST.json"),
        os.path.join(PROJECT_ROOT, "release_manifest.json"),
    )
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            continue

        for record in payload.get("files") or ():
            name = os.path.basename(str(record.get("path") or "")).casefold()
            value = str(record.get("sha256") or "").casefold()
            if (
                name in {"llama-server", "llama-server.exe"}
                and len(value) == 64
            ):
                return value
    return None


def model_binding(model_path=None, *, role="director"):
    """Model identity with an exact content digest when one is available."""
    digest_env = (
        _WORKER_MODEL_DIGEST_ENV
        if str(role).casefold() == "worker"
        else _MODEL_DIGEST_ENV
    )
    supplied = os.environ.get(digest_env, "").strip().casefold()
    content_digest = (
        supplied
        if len(supplied) == 64
        and all(character in "0123456789abcdef" for character in supplied)
        else _manifest_model_digest(model_path)
    )
    try:
        stat = os.stat(model_path) if model_path else None
    except OSError:
        stat = None

    return {
        "role": "worker" if str(role).casefold() == "worker" else "director",
        "model_name": os.path.basename(str(model_path or "")) or None,
        "model_sha256": content_digest,
        "model_bytes": stat.st_size if stat else None,
        "server_revision": os.environ.get(
            _SERVER_REVISION_ENV, ""
        ).strip() or None,
        "server_sha256": _manifest_server_digest(),
    }


def _numeric_metadata(value):
    """Recursively retain only finite numeric serving telemetry."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {
            str(key)[:64]: _numeric_metadata(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_numeric_metadata(item) for item in value[:64]]
    return None


def _outcome_metadata(value):
    """Bound outcome values to scalars and registered non-private labels."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        label = value.strip().casefold().replace("-", "_").replace(" ", "_")
        return label if label in _SAFE_OUTCOME_LABELS else "unknown"
    return None


def _binding_metadata(binding):
    """Keep exact identity fields without accepting arbitrary caller text."""
    binding = binding if isinstance(binding, dict) else {}
    sha256 = str(binding.get("model_sha256") or "").casefold()
    revision = str(binding.get("server_revision") or "").strip()
    server_sha256 = str(binding.get("server_sha256") or "").casefold()
    role = str(binding.get("role") or "").casefold()
    return {
        "role": role if role in {"director", "worker"} else None,
        "model_name": os.path.basename(
            str(binding.get("model_name") or "")
        )[:160] or None,
        "model_sha256": (
            sha256
            if len(sha256) == 64
            and all(character in "0123456789abcdef" for character in sha256)
            else None
        ),
        "model_bytes": _numeric_metadata(binding.get("model_bytes")),
        "server_revision": (
            revision[:80]
            if revision
            and all(
                character.isalnum() or character in ".-_+"
                for character in revision
            )
            else None
        ),
        "server_sha256": (
            server_sha256
            if len(server_sha256) == 64
            and all(
                character in "0123456789abcdef"
                for character in server_sha256
            )
            else None
        ),
    }


def record(
    workflow,
    stage,
    *,
    artifact_digest,
    prompt_sha256,
    sampler,
    measurements,
    outcomes,
    timing=None,
    binding=None,
    path=LOG_FILE,
):
    """Append one metadata-only event. Failures never affect the workflow."""
    if mode() == "off":
        return False

    # The API intentionally has no prompt/response/text argument. Enforce the
    # boundary again here so a future caller cannot turn an outcome, timing,
    # or sampler field into an accidental text channel.
    event = {
        "schema": SCHEMA,
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "workflow": str(workflow)[:64],
        "stage": str(stage)[:64],
        "artifact_digest": str(artifact_digest)[:64],
        "prompt_sha256": str(prompt_sha256)[:64],
        "sampler": _numeric_metadata(dict(sampler or {})),
        "measurements": _numeric_metadata(dict(measurements or {})),
        "outcomes": {
            str(key)[:64]: _outcome_metadata(value)
            for key, value in dict(outcomes or {}).items()
        },
        "timing": _numeric_metadata(dict(timing or {})),
        "binding": _binding_metadata(binding),
    }

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True
    except OSError:
        return False


class Timer:
    """Small monotonic timer so callers report wall time consistently."""

    def __init__(self):
        self.started = time.perf_counter()

    def elapsed(self):
        return max(0.0, time.perf_counter() - self.started)
