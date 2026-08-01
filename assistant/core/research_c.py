"""Research C uncertainty sidecars and privacy-safe measurement records.

The sidecar describes one model call. It never enters an embedding and never
authorizes an action. Research C's first job is to collect the held-out table
that could justify a refusal or routing threshold later; until that table
exists, every existing deterministic guard remains the decision-maker.

Only per-install HMAC pseudonyms, sampler settings, numeric measurements,
timings, and bounded outcome labels are written. Prompt, response, source,
and memory text are not.
"""

import hashlib
import hmac
import json
import math
import os
import secrets
import threading
import time
from datetime import datetime, timezone


ASSISTANT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ASSISTANT_ROOT)
LOG_FILE = os.path.join(ASSISTANT_ROOT, "logs", "research_c.jsonl")
AUDIT_HMAC_KEY_FILE = os.path.join(ASSISTANT_ROOT, ".audit_hmac_key")
_AUDIT_HMAC_KEY_ENV = "TORMENT_NEXUS_AUDIT_HMAC_KEY"
_configured_audit_hmac_key = os.environ.get(_AUDIT_HMAC_KEY_ENV, "").strip()
SCHEMA = 1
PRIVATE_DIGEST_SCHEME = "hmac-sha256-install-v1"
PROCESS_PRIVATE_DIGEST_SCHEME = "hmac-sha256-process-v1"

_audit_hmac_key_cache = None
_audit_hmac_key_persistent = None
_audit_hmac_key_lock = threading.Lock()
_AUDIT_HMAC_FILE_LOCK_SECONDS = 10.0
_AUDIT_HMAC_FILE_LOCK_POLL_SECONDS = 0.01

_MODES = {"off": 0, "top2": 2, "top10": 10}
_DEFAULT_MODE = "top2"
_MODEL_DIGEST_ENV = "TORMENT_NEXUS_RESEARCHC_MODEL_SHA256"
_WORKER_MODEL_DIGEST_ENV = "TORMENT_NEXUS_RESEARCHC_WORKER_SHA256"
_SERVER_REVISION_ENV = "TORMENT_NEXUS_LLAMA_REVISION"
_SAFE_WORKFLOWS = {
    "durable_memory",
    "edit",
    "source_grounding",
    "super_dev",
    "test",
}
_SAFE_STAGES = {
    "binding",
    "deterministic_gate",
    "extraction",
    "measurement",
    "patch",
    "plan",
    "privacy",
    "trusted_answer",
}
_SAFE_METADATA_KEYS = {
    # Sampler controls.
    "cache_prompt",
    "max_tokens",
    "min_p",
    "repeat_penalty",
    "seed",
    "temperature",
    "top_k",
    "top_p",
    # Span uncertainty.
    "margin_token_count",
    "mean_surprisal",
    "mean_top1_top2_margin",
    "minimum_top1_top2_margin",
    "peak_surprisal",
    "token_count",
    "worst_decile_surprisal",
    # Deterministic outcomes.
    "below_confidence_floor",
    "capability_guard",
    "category",
    "changed_lines",
    "declined",
    "deterministic_rejection",
    "draft_parseable",
    "emitted_memory",
    "empty_find",
    "exists",
    "kept",
    "no_op",
    "occurrences",
    "parseable",
    "patch_applied_to_snapshot",
    "query_kind",
    "reason",
    "regression_gate",
    "retained",
    "self_reported_confidence",
    "staged",
    "syntax_valid",
    "unique_patch",
    "valid_item",
    "valid_target",
    "valid_types",
    "validated_target",
    "within_line_cap",
    # Local and llama.cpp timing fields.
    "cache_n",
    "candidate_wall_seconds",
    "draft_n",
    "draft_n_accepted",
    "predicted_ms",
    "predicted_n",
    "predicted_per_second",
    "predicted_per_token_ms",
    "prompt_ms",
    "prompt_n",
    "prompt_per_second",
    "prompt_per_token_ms",
    "server",
    "wall_seconds",
}
_SAFE_OUTCOME_LABELS = {
    "authorship",
    "byte_count",
    "definition",
    "directory_count",
    "directory_existence",
    "directory_lines",
    "empty",
    "existence",
    "fact",
    "goal",
    "hardware",
    "instruction",
    "line_count",
    "line_comparison",
    "line_threshold",
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
    "size",
    "class_outline",
    "function_outline",
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


def _encoded_parts(parts):
    return json.dumps(
        parts,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8", "replace")


def _decoded_audit_hmac_key(value):
    """Return one exact 256-bit key, or ``None`` for malformed storage."""
    try:
        value = value.decode("ascii") if isinstance(value, bytes) else str(value)
    except (UnicodeDecodeError, ValueError):
        return None
    value = value.strip()
    if len(value) != 64:
        return None
    try:
        decoded = bytes.fromhex(value)
    except ValueError:
        return None
    return decoded if len(decoded) == 32 else None


def _lock_audit_hmac_descriptor(descriptor):
    """Hold an inter-process exclusive lock over the key's first byte."""
    deadline = time.monotonic() + _AUDIT_HMAC_FILE_LOCK_SECONDS
    if os.name == "nt":
        import msvcrt

        while True:
            try:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                return "windows"
            except OSError:
                if time.monotonic() >= deadline:
                    raise OSError("timed out waiting for the audit-key lock")
                time.sleep(_AUDIT_HMAC_FILE_LOCK_POLL_SECONDS)

    import fcntl

    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return "posix"
        except OSError:
            if time.monotonic() >= deadline:
                raise OSError("timed out waiting for the audit-key lock")
            time.sleep(_AUDIT_HMAC_FILE_LOCK_POLL_SECONDS)


def _unlock_audit_hmac_descriptor(descriptor, lock_kind):
    if lock_kind == "windows":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    elif lock_kind == "posix":
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _read_audit_hmac_descriptor(descriptor):
    os.lseek(descriptor, 0, os.SEEK_SET)
    return _decoded_audit_hmac_key(os.read(descriptor, 4096))


def _write_audit_hmac_descriptor(descriptor, key):
    """Replace malformed storage while the caller owns the file lock."""
    payload = key.hex().encode("ascii")
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    written = 0
    while written < len(payload):
        count = os.write(descriptor, payload[written:])
        if count <= 0:
            raise OSError("audit-key write made no progress")
        written += count
    os.fsync(descriptor)
    if _read_audit_hmac_descriptor(descriptor) != key:
        raise OSError("audit-key verification failed after writing")


def _read_audit_hmac_path():
    """Best-effort read for an installation mounted without write access."""
    try:
        with open(AUDIT_HMAC_KEY_FILE, "rb") as source:
            return _decoded_audit_hmac_key(source.read(4096))
    except OSError:
        return None


def _remember_audit_hmac_key(key, persistent):
    global _audit_hmac_key_cache, _audit_hmac_key_persistent
    # Publish the classification before the key. The lock-free fast path uses
    # a non-None key as its ready flag, so the reverse order creates a tiny
    # window in which another thread can mislabel an ephemeral key as an
    # installation-persistent one.
    _audit_hmac_key_persistent = bool(persistent)
    _audit_hmac_key_cache = key
    return _audit_hmac_key_cache


def _audit_hmac_key():
    """Return this installation's private pseudonym key.

    The key is created lazily so importing the measurement module remains a
    read-only operation.  An installation mounted read-only still gets a
    process-local random key; its pseudonyms simply will not join across a
    restart.  There is deliberately no deterministic fallback.
    """
    global _audit_hmac_key_cache, _audit_hmac_key_persistent
    if _audit_hmac_key_cache is not None:
        if _audit_hmac_key_persistent is None:
            # Test and embedding callers historically supplied an in-memory
            # installation key directly. Production paths below always set
            # this state together with the key.
            _audit_hmac_key_persistent = True
        return _audit_hmac_key_cache

    # ``flock`` is process-scoped on some platforms, so the Python lock is
    # not redundant: it also prevents two threads in this interpreter from
    # observing different first-use keys before the cache is populated.
    with _audit_hmac_key_lock:
        if _audit_hmac_key_cache is not None:
            return _audit_hmac_key_cache

        configured = _decoded_audit_hmac_key(_configured_audit_hmac_key)
        if configured is not None:
            return _remember_audit_hmac_key(configured, persistent=True)

        descriptor = None
        lock_kind = None
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            descriptor = os.open(AUDIT_HMAC_KEY_FILE, flags, 0o600)
            lock_kind = _lock_audit_hmac_descriptor(descriptor)

            # Every cooperating process reads only while holding this lock.
            # A creator may therefore make the path visible at zero bytes
            # without exposing a usable partial key to another process.
            stored = _read_audit_hmac_descriptor(descriptor)
            if stored is not None:
                return _remember_audit_hmac_key(stored, persistent=True)

            generated = secrets.token_bytes(32)
            for _attempt in range(3):
                try:
                    _write_audit_hmac_descriptor(descriptor, generated)
                    return _remember_audit_hmac_key(
                        generated,
                        persistent=True,
                    )
                except OSError:
                    # fsync can report failure after every byte reached the
                    # file. Re-read under the lock before deciding this key
                    # is ephemeral, so waiters never choose a different one.
                    stored = _read_audit_hmac_descriptor(descriptor)
                    if stored is not None:
                        return _remember_audit_hmac_key(
                            stored,
                            persistent=True,
                        )

            # A writable-looking installation can still run out of space or
            # reject a write. Preserve the documented privacy-safe fallback:
            # random for this process, never a deterministic guess. A later
            # launch will repair the invalid/partial file under the same lock.
            return _remember_audit_hmac_key(generated, persistent=False)
        except OSError:
            # A genuinely read-only installation may still contain a valid
            # key. Use it if available; otherwise comparability is limited to
            # this process rather than weakened with a deterministic key.
            stored = _read_audit_hmac_path()
            return _remember_audit_hmac_key(
                stored or secrets.token_bytes(32),
                persistent=stored is not None,
            )
        finally:
            if descriptor is not None:
                if lock_kind is not None:
                    try:
                        _unlock_audit_hmac_descriptor(descriptor, lock_kind)
                    except OSError:
                        pass
                os.close(descriptor)


def private_digest_status():
    """Describe whether current pseudonyms survive a process restart."""
    _audit_hmac_key()
    persistent = bool(_audit_hmac_key_persistent)
    return {
        "persistent": persistent,
        "scheme": (
            PRIVATE_DIGEST_SCHEME
            if persistent
            else PROCESS_PRIVATE_DIGEST_SCHEME
        ),
    }


def legacy_digest(*parts):
    """The pre-Research-C-release deterministic digest, for old evidence.

    New private identifiers must use :func:`digest`.  Keeping this verifier
    explicit lets an operator inspect already-frozen local artifacts without
    silently continuing to publish dictionary-testable prompt hashes.
    """
    encoded = json.dumps(
        parts,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def digest(*parts):
    """Per-install HMAC pseudonym for text that must never enter a log."""
    return hmac.new(
        _audit_hmac_key(),
        _encoded_parts(parts),
        hashlib.sha256,
    ).hexdigest()


def verify_digest(expected, *parts):
    """Verify a current private pseudonym without exposing its key."""
    return hmac.compare_digest(str(expected or ""), digest(*parts))


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
    """The packaged launcher digest, retained for schema compatibility."""
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


def _server_runtime_component(name):
    """Whether a sibling binary participates in llama-server inference."""
    name = os.path.basename(str(name or "")).casefold()
    if name in {"llama-server", "llama-server.exe"}:
        return True
    if name.startswith(("llama-server-impl.", "libllama-server-impl.")):
        return True
    if name.startswith(("llama-common.", "libllama-common.")):
        return True
    if name.startswith(("mtmd.", "libmtmd.")):
        return name.endswith((".dll", ".so", ".dylib"))
    if name.startswith(("ggml", "libggml")):
        return name.endswith((".dll", ".so", ".dylib"))
    if name.startswith(("llama.", "libllama.")):
        return name.endswith((".dll", ".so", ".dylib"))
    return False


def _bundle_digest(records):
    """Digest component names and content hashes as one serving bundle."""
    components = []
    for record in records or ():
        name = os.path.basename(str(
            record.get("path") or record.get("name") or ""
        )).casefold()
        value = str(record.get("sha256") or "").casefold()
        if (
            _server_runtime_component(name)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        ):
            components.append((name, value))

    if not components:
        return None

    canonical = json.dumps(
        sorted(set(components)),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _manifest_server_bundle_digest():
    """Bind every packaged library that implements llama-server inference."""
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

        bundled = _bundle_digest(payload.get("files") or ())
        if bundled:
            return bundled
    return None


def _sha256_file(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            value.update(block)
    return value.hexdigest()


def server_bundle_digest(server_path=None):
    """Exact local serving-bundle digest, or a packaged digest if available."""
    if not server_path:
        try:
            from core.config import LLAMA_SERVER
            server_path = LLAMA_SERVER
        except Exception:
            server_path = None
    if not server_path or not os.path.isfile(server_path):
        return _manifest_server_bundle_digest()

    directory = os.path.dirname(os.path.abspath(server_path))
    paths = []
    try:
        names = os.listdir(directory)
    except OSError:
        return _manifest_server_bundle_digest()

    for name in names:
        if not _server_runtime_component(name):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        paths.append(path)

    records = []
    for path in paths:
        try:
            records.append({
                "name": os.path.basename(path),
                "sha256": _sha256_file(path),
            })
        except OSError:
            return None
    return _bundle_digest(records)


def model_binding(model_path=None, *, role="director", server_path=None):
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
        "server_bundle_sha256": server_bundle_digest(server_path),
    }


def _safe_metadata_key(value):
    """Keep registered keys and HMAC-alias every unknown private key."""
    key = str(value)
    if key in _SAFE_METADATA_KEYS:
        return key
    return "unknown_" + digest("metadata-key", key)[:16]


def _safe_event_identifier(value, allowed):
    value = str(value or "").strip().casefold()
    return value if value in allowed else "unknown"


def _hex_digest(value):
    value = str(value or "").strip().casefold()
    if (
        len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return None


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
            _safe_metadata_key(key): _numeric_metadata(item)
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
    server_bundle_sha256 = str(
        binding.get("server_bundle_sha256") or ""
    ).casefold()
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
        "server_bundle_sha256": (
            server_bundle_sha256
            if len(server_bundle_sha256) == 64
            and all(
                character in "0123456789abcdef"
                for character in server_bundle_sha256
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
        "private_digest_scheme": private_digest_status()["scheme"],
        "workflow": _safe_event_identifier(workflow, _SAFE_WORKFLOWS),
        "stage": _safe_event_identifier(stage, _SAFE_STAGES),
        "artifact_digest": _hex_digest(artifact_digest),
        "prompt_sha256": _hex_digest(prompt_sha256),
        "sampler": _numeric_metadata(dict(sampler or {})),
        "measurements": _numeric_metadata(dict(measurements or {})),
        "outcomes": {
            _safe_metadata_key(key): _outcome_metadata(value)
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
