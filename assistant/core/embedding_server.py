"""
A second, tiny llama-server that turns sentences into vectors.

The director answers; this one only measures. It serves a small embedding
GGUF (tens of megabytes against the director's gigabytes) with --embedding,
so memory retrieval can recognise that "the radio" and "the T-Deck mesh
transmitter" are about the same thing even though they share no token.

DESIGN CONSTRAINTS, in order:

1. Absence is normal. No model file means no server, no thread, no error --
   retrieval simply stays word-overlap, which is what it was yesterday.
   The Pi has 8GB shared with a 4.6GB director; residency is the
   operator's call, made by placing (or not placing) a file.

2. Nothing here may block the chat path. embed() has a short timeout and
   every failure returns None rather than raising. A missing vector means
   one memory scores without a cosine term for one turn, which is not an
   event worth a stack trace.

3. Same authentication as the director, for the same reason: llama-server's
   permissive CORS would otherwise let any web page open on this computer
   ask the embedder to fingerprint text. The key already exists; reuse it.
"""

import hashlib
import ipaddress
import math
import os
import subprocess
import threading
import time
from urllib.parse import urlparse

import requests

from core.config import (
    EMBED_ENABLED,
    EMBED_MODEL_PATH,
    EMBED_SERVER_HOST,
    EMBED_SERVER_PORT,
    EMBED_SERVER_URL,
    EMBED_TIMEOUT_SECONDS,
    LLAMA_SERVER,
    MODEL_API_KEY,
    MODEL_API_KEY_FILE,
    MODEL_REQUEST_HEADERS,
    SERVER_LOG_FILE,
)


# Sentence embedders need sentences, not documents. Anything longer is
# truncated before sending: a memory is capped at 250 chars by the cleaner
# anyway, and a history chunk that large has stopped being one exchange.
MAX_EMBED_CHARS = 2000

STARTUP_TIMEOUT = 120

# Mean pooling is intentionally retained because it won the project's
# measured retrieval evaluation for this GGUF. BGE's published convention
# is CLS pooling, so this is an empirical deployment choice rather than a
# claim about how the upstream model was trained.
POOLING_MODE = "mean"

_process = None
_log_handle = None
_identity_lock = threading.Lock()
_identity_cache_key = None
_identity_cache_value = None

EMBED_LOG_FILE = os.path.join(
    os.path.dirname(SERVER_LOG_FILE),
    "embed_server.log",
)


def available():
    """A model exists and the operator has not switched this off."""
    return (
        EMBED_ENABLED
        and os.path.isfile(EMBED_MODEL_PATH)
        and _url_is_loopback(EMBED_SERVER_URL)
    )


def _url_is_loopback(url):
    """
    True only for an unambiguous loopback HTTP(S) endpoint.

    Embedding requests contain private memories and history. A typo or an
    inherited environment variable must never turn that local diagnostic
    stream into an outbound request carrying the director's bearer token.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        # Accessing .port performs urllib's numeric/range validation.
        parsed.port

        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            return False

        if host.rstrip(".").lower() == "localhost":
            return True

        return ipaddress.ip_address(host).is_loopback
    except (TypeError, ValueError):
        return False


def _health_responds(timeout=2):
    if not _url_is_loopback(EMBED_SERVER_URL):
        return False

    try:
        response = requests.get(
            EMBED_SERVER_URL + "/health",
            headers=MODEL_REQUEST_HEADERS,
            timeout=timeout,
        )
        return response.status_code == 200
    except Exception:
        return False


def server_alias():
    """The llama-server model id expected from /v1/models."""
    identity = model_identity()
    digest = (
        identity.split(":", 2)[1]
        if identity.startswith("sha256:")
        else "none"
    )
    return f"torment-embed-{digest}-{POOLING_MODE}"


def _advertised_model_ids(timeout=2):
    if not _url_is_loopback(EMBED_SERVER_URL):
        return set()

    try:
        response = requests.get(
            EMBED_SERVER_URL + "/v1/models",
            headers=MODEL_REQUEST_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
        rows = response.json().get("data", [])
    except Exception:
        return set()

    if not isinstance(rows, list):
        return set()

    return {
        row.get("id")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }


def is_alive(timeout=2):
    """
    True only when the endpoint is healthy *and* serves this exact model.

    A health-only check can silently reuse the director or a stale embedder
    left on the same port. The alias binds the running server to the model
    SHA and pooling mode that stamp the vector cache.
    """
    return (
        _health_responds(timeout=timeout)
        and server_alias() in _advertised_model_ids(timeout=timeout)
    )


def start():
    """
    Launch the embedding server, or reuse one already running.

    Returns True when a server is answering afterwards. Failure returns
    False rather than raising: the assistant must start identically with
    or without semantic retrieval.
    """
    global _process, _log_handle

    if not available():
        return False

    if is_alive():
        return True

    # Something else already owns the configured endpoint. Do not race it
    # for the port and, more importantly, do not accept its vector space.
    if _health_responds():
        return False

    if not os.path.isfile(LLAMA_SERVER):
        return False

    folder = os.path.dirname(EMBED_LOG_FILE)

    if folder:
        os.makedirs(folder, exist_ok=True)

    arguments = [
        LLAMA_SERVER,
        "-m", EMBED_MODEL_PATH,
        "--embedding",
        "--pooling", POOLING_MODE,
        "--alias", server_alias(),
        # A sentence embedder never sees long inputs, and a small context
        # keeps its KV allocation near zero next to the director's.
        "-c", "512",
        "-ub", "512",
        "--host", str(EMBED_SERVER_HOST),
        "--port", str(EMBED_SERVER_PORT),
        # CPU on purpose, even on the CUDA desktop: milliseconds of CPU
        # work is not worth contending with the director for VRAM.
        "-ngl", "0",
        "-t", "2",
    ]

    if MODEL_API_KEY_FILE:
        arguments.extend(("--api-key-file", MODEL_API_KEY_FILE))
    else:
        arguments.extend(("--api-key", MODEL_API_KEY))

    try:
        _log_handle = open(EMBED_LOG_FILE, "w", encoding="utf-8")
        _process = subprocess.Popen(
            arguments,
            stdout=_log_handle,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        stop()
        return False

    started_at = time.monotonic()

    while time.monotonic() - started_at < STARTUP_TIMEOUT:
        if is_alive(timeout=2):
            return True

        if _process.poll() is not None:
            stop()
            return False

        time.sleep(0.5)

    stop()
    return False


def stop():
    """Only stops a server this process started; a reused one is left alone."""
    global _process, _log_handle

    if _process is not None:
        try:
            _process.terminate()
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()
        except (OSError, ProcessLookupError):
            pass

        _process = None

    if _log_handle is not None:
        try:
            _log_handle.close()
        except Exception:
            pass

        _log_handle = None


def embed(texts, timeout=None):
    """
    One L2-normalised vector per text, or None for the whole batch.

    All-or-nothing on purpose: a partial result would let two memories be
    compared under different failure conditions, and cosine between a real
    vector and a placeholder is a number that means nothing.
    """
    if not texts:
        return []

    if not _url_is_loopback(EMBED_SERVER_URL):
        return None

    try:
        response = requests.post(
            EMBED_SERVER_URL + "/v1/embeddings",
            headers=MODEL_REQUEST_HEADERS,
            json={
                "input": [text[:MAX_EMBED_CHARS] for text in texts],
                "model": server_alias(),
            },
            timeout=timeout if timeout is not None else EMBED_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        rows = response.json()["data"]
    except Exception:
        return None

    if not isinstance(rows, list) or len(rows) != len(texts):
        return None

    indexed = {}

    for row in rows:
        if not isinstance(row, dict):
            return None

        index = row.get("index")

        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or index >= len(texts)
            or index in indexed
        ):
            return None

        indexed[index] = row.get("embedding")

    vectors = []
    dimension = None

    # The endpoint promises index order, but rebuilding it explicitly keeps
    # a reordered response from attaching the wrong vector to a memory.
    for index in range(len(texts)):
        vector = _normalise_vector(indexed.get(index), dimension)

        if vector is None:
            return None

        dimension = len(vector)
        vectors.append(vector)

    return vectors


def _normalise_vector(vector, expected_dimension=None):
    """Validate numeric/finite shape and return an L2-normalised copy."""
    if not isinstance(vector, list) or not vector:
        return None

    if expected_dimension is not None and len(vector) != expected_dimension:
        return None

    clean = []

    for value in vector:
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            return None

        clean.append(float(value))

    length = math.sqrt(math.fsum(value * value for value in clean))

    if not math.isfinite(length) or length <= 0.0:
        return None

    return [value / length for value in clean]


def _model_sha256():
    """Hash the GGUF once per path/size/mtime tuple."""
    global _identity_cache_key, _identity_cache_value

    try:
        stat = os.stat(EMBED_MODEL_PATH)
        key = (
            os.path.realpath(EMBED_MODEL_PATH),
            stat.st_size,
            stat.st_mtime_ns,
        )
    except OSError:
        return None

    with _identity_lock:
        if key == _identity_cache_key:
            return _identity_cache_value

    digest = hashlib.sha256()

    try:
        with open(EMBED_MODEL_PATH, "rb") as model_file:
            while True:
                block = model_file.read(1024 * 1024)

                if not block:
                    break

                digest.update(block)
    except OSError:
        return None

    value = digest.hexdigest()

    with _identity_lock:
        _identity_cache_key = key
        _identity_cache_value = value

    return value


def model_identity():
    """
    A string naming exactly which embedder produced a vector.

    Stored beside the cache so that swapping the model file invalidates
    every cached vector at once -- two models' spaces are not comparable,
    and mixing them would fail silently in the worst way: plausible
    numbers, meaningless geometry.
    """
    digest = _model_sha256() or "none"
    return f"sha256:{digest}:pooling:{POOLING_MODE}"
