"""machinespirit: per-token trajectories read against a concept dictionary.

A sentence embedding is a mean over its token vectors. The mean says what a
sentence is about; it cannot say *where* in the sentence a meaning appeared,
because averaging destroys exactly that. machinespirit keeps the path and
profiles every token position against a fixed anchor dictionary, so the
readout is in chosen English and attached to a position.

SABLE7 is the container that stores such a path. machinespirit is the
representation it carries. They are named separately because they version
separately.

What this is honestly for, and not for:

  - It DOES locate a concept at a token. Two sentences measured, both land
    where they should. The pooled vector cannot do this at all.
  - It DOES NOT improve retrieval. Late interaction over trajectories
    returned the same documents as plain pooled cosine, and anchor-space
    coordinates scored 0.689 against uint8 absolute's perfect 1.000. So
    nothing here touches how the assistant retrieves. See
    docs/VECTOR_TRANSLATION_RESEARCH.md.

llama.cpp fixes pooling at server launch, so a trajectory cannot come from
the ordinary pooled embedder. This needs a second instance of the same
model started with `--pooling none`, which the hazard launcher does. When
that server is absent, every entry point here reports unavailable rather
than guessing -- an unavailable readout is a missing feature, but a guessed
one would be a fluent account of something that did not happen, which is
the failure this project exists to avoid.
"""
import json
import math
import os
import threading
from urllib.parse import urlparse

import requests

from core.config import (
    MACHINESPIRIT_KEY,
    MACHINESPIRIT_URL,
)

_HERE = os.path.dirname(os.path.abspath(__file__))

# v2 adds a `life` section and changes nothing else: its core and project
# lists are byte-identical to v1 and carry v1's digests, so a stone built on
# v1's core stays comparable. The default is v2 because v1 was measured to
# have no coverage for what a stored memory is about -- four unrelated
# entries all profiled strongest against the same self-editing anchor, and
# both hardware entries against the same voice-synthesis one. v1 remains
# loadable, and every published figure that names a digest still reproduces
# against the file it was computed from.
ANCHOR_VERSION = os.environ.get("TORMENT_NEXUS_ANCHOR_VERSION", "2").strip()

# Both embedding servers are launched with -c 512. llama.cpp truncates a
# longer input rather than refusing it, and a truncated path is
# indistinguishable from a complete one by shape alone, so the token count
# is checked rather than assumed.
CONTEXT_TOKENS = 512

_lock = threading.Lock()
_anchors = None
_anchors_loaded_version = None
_anchor_vectors = None
_anchor_vectors_key = None


def anchors_file(version=None):
    return os.path.join(_HERE, f"anchors_v{version or ANCHOR_VERSION}.json")


def _load_anchors():
    global _anchors, _anchors_loaded_version
    if _anchors is None or _anchors_loaded_version != ANCHOR_VERSION:
        with open(anchors_file(), encoding="utf-8") as fh:
            _anchors = json.load(fh)
        _anchors_loaded_version = ANCHOR_VERSION
    return _anchors


def anchor_texts(include_project=True, include_life=True):
    """The ordered dictionary. Order is the coordinate system, not a detail.

    Sections always appear core, project, life, so a shorter selection is a
    prefix of a longer one and an index keeps its meaning across them.
    """
    data = _load_anchors()
    texts = list(data["core"])
    if include_project:
        texts += list(data.get("project") or [])
    if include_life:
        texts += list(data.get("life") or [])
    return texts


def core_digest():
    return _load_anchors()["core_digest"]


def dictionary():
    """What is loaded, for anything that reports rather than computes."""
    data = _load_anchors()
    return {
        "version": data.get("version"),
        "core": len(data.get("core") or []),
        "project": len(data.get("project") or []),
        "life": len(data.get("life") or []),
        "core_digest": data.get("core_digest"),
    }


def looks_truncated(path):
    """True when a trajectory ran into the server's context window.

    Equality rather than greater-than: the server stops at the window, so a
    path exactly that long is the signature of an input that did not fit.
    """
    return bool(path) and len(path) >= CONTEXT_TOKENS


def _url_is_loopback(url):
    """Same boundary the embedding server holds: never a remote host.

    A trajectory is per-token, so sending text here would be an unusually
    direct way to leak the input to somewhere it should not go.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        parsed.port
    except (ValueError, AttributeError):
        return False
    return host in {"127.0.0.1", "localhost", "::1"}


def configured():
    return bool(MACHINESPIRIT_URL) and _url_is_loopback(MACHINESPIRIT_URL)


def available(timeout=2):
    """True only when an unpooled server is actually answering."""
    if not configured():
        return False
    try:
        headers = {}
        if MACHINESPIRIT_KEY:
            headers["Authorization"] = "Bearer " + MACHINESPIRIT_KEY
        response = requests.get(MACHINESPIRIT_URL.rstrip("/") + "/health",
                                headers=headers, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False


def trajectory(text, timeout=60):
    """Per-token vectors for one text, or None when unavailable.

    Uses llama.cpp's own /embeddings route. The OpenAI-compatible one
    refuses pooling=none outright.
    """
    if not configured():
        return None
    headers = {}
    if MACHINESPIRIT_KEY:
        headers["Authorization"] = "Bearer " + MACHINESPIRIT_KEY
    try:
        response = requests.post(MACHINESPIRIT_URL.rstrip("/") + "/embeddings",
                                 headers=headers, json={"content": text},
                                 timeout=timeout)
        if response.status_code != 200:
            return None
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    if isinstance(payload, list):
        if not payload:
            return None
        payload = payload[0]
    if not isinstance(payload, dict):
        return None

    embedding = payload.get("embedding") or payload.get("data")
    if not embedding:
        return None
    path = embedding if isinstance(embedding[0], list) else [embedding]
    return path if path and path[0] else None


def cosine(left, right):
    a = math.sqrt(sum(x * x for x in left)) or 1.0
    b = math.sqrt(sum(x * x for x in right)) or 1.0
    return sum(x * y for x, y in zip(left, right)) / (a * b)


def anchor_vectors(include_project=True, include_life=True, timeout=120):
    """Embed the dictionary once per process, through the POOLED embedder.

    Note which server this is: anchors are ordinary sentence embeddings and
    come from 8082, while trajectories come from the unpooled 8084. Both are
    required. A trace that fails because the pooled embedder is absent looks
    identical to one that fails because the unpooled one is -- see
    diagnose(), which exists so the two are not reported as each other.
    """
    global _anchor_vectors, _anchor_vectors_key
    from core import embedding_server

    with _lock:
        if _anchor_vectors is None or _anchor_vectors_key != ANCHOR_VERSION:
            if not embedding_server.available():
                return None
            vectors = embedding_server.embed(anchor_texts(True, True),
                                             timeout=timeout)
            if not vectors:
                return None
            _anchor_vectors = vectors
            _anchor_vectors_key = ANCHOR_VERSION

    return _select_sections(_anchor_vectors, include_project, include_life)


def _select_sections(rows, include_project, include_life):
    """Take the same sections from a full-length list that anchor_texts does.

    Deliberately not a prefix slice: dropping project while keeping life is
    a legal selection and is not a prefix of anything, so a length-based cut
    would return project's vectors under life's labels -- plausible numbers
    against the wrong words, which is the failure mode this module exists to
    refuse.
    """
    data = _load_anchors()
    core = len(data.get("core") or [])
    project = len(data.get("project") or [])
    life = len(data.get("life") or [])
    out = list(rows[:core])
    if include_project:
        out += list(rows[core:core + project])
    if include_life:
        out += list(rows[core + project:core + project + life])
    return out


def profile(vector, vectors, texts, top=3):
    """Strongest anchors for one vector, common direction removed.

    Sentence embeddings are anisotropic: they sit in a narrow cone, so raw
    cosine ranks by which anchors are generally popular rather than by
    subject. Subtracting the mean anchor vector from both sides changes the
    geometry. Standardising the scores instead would be monotonic and could
    not reorder anything.
    """
    if not vectors:
        return []
    mean = [sum(column) / len(vectors) for column in zip(*vectors)]
    centred = [[x - m for x, m in zip(a, mean)] for a in vectors]
    target = [x - m for x, m in zip(vector, mean)]
    scored = sorted(zip((cosine(target, a) for a in centred), texts),
                    reverse=True)
    return scored[:top]


def trace(text, top=1, include_project=True, include_life=True):
    """Which concept appeared at which token. None when unavailable."""
    path = trajectory(text)
    if not path:
        return None
    vectors = anchor_vectors(include_project, include_life)
    if not vectors:
        return None
    texts = anchor_texts(include_project, include_life)
    vectors = vectors[:len(texts)]
    return [(index, profile(token, vectors, texts, top))
            for index, token in enumerate(path)]


def diagnose(text=None):
    """Which part is missing, rather than that something is.

    trace() returns None for four different reasons and a caller cannot tell
    them apart: no configuration, the unpooled server absent, the pooled
    server absent, or a request that failed. While machinespirit was one
    command that distinction was cosmetic. For anything that leans on it,
    reporting a pooled-server outage as an unpooled one sends the operator
    to restart the wrong process.

    Returns a dict; `ready` is true only when a trace would actually work.
    """
    from core import embedding_server

    status = {
        "configured": configured(),
        "unpooled": False,
        "pooled": bool(embedding_server.available()),
        "dictionary": dictionary(),
        "tokens": None,
        "truncated": False,
        "ready": False,
        "reason": None,
    }

    if not status["configured"]:
        status["reason"] = (
            "No unpooled embedding server is configured. llama.cpp fixes "
            "pooling when the process starts, so trajectories need a second "
            "instance started with --pooling none; the hazard launcher "
            "starts one on 8084."
        )
        return status

    status["unpooled"] = available()
    if not status["unpooled"]:
        status["reason"] = (
            "The unpooled server is configured but did not answer on "
            f"{MACHINESPIRIT_URL}. Nothing is guessed in its absence."
        )
        return status

    if not status["pooled"]:
        status["reason"] = (
            "The unpooled server is answering, but the ordinary embedding "
            "server is not, and the anchor dictionary is embedded through "
            "that one. Both are required: 8084 supplies the path, 8082 "
            "supplies the words it is read against."
        )
        return status

    if text:
        path = trajectory(text)
        if not path:
            status["reason"] = (
                "Both servers are up, but the trajectory request failed."
            )
            return status
        status["tokens"] = len(path)
        status["truncated"] = looks_truncated(path)
        if status["truncated"]:
            status["reason"] = (
                f"The input filled the server's {CONTEXT_TOKENS}-token "
                "window, so the path covers only as much of it as fit. A "
                "trace of part of an input is not a trace of the input."
            )

    status["ready"] = True
    return status


def peaks(rows):
    """Strongest position for each concept that appeared in a trace."""
    best = {}
    for index, hits in rows or []:
        for score, anchor in hits:
            if anchor not in best or score > best[anchor][0]:
                best[anchor] = (score, index)
    return sorted(((anchor, score, index)
                   for anchor, (score, index) in best.items()),
                  key=lambda row: -row[1])


def reset_cache():
    """Drop the embedded dictionary; used by tests and after a model swap."""
    global _anchor_vectors, _anchor_vectors_key, _anchors
    global _anchors_loaded_version
    with _lock:
        _anchor_vectors = None
        _anchor_vectors_key = None
        _anchors = None
        _anchors_loaded_version = None
