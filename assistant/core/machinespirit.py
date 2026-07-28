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

ANCHORS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "anchors_v1.json")

_lock = threading.Lock()
_anchors = None
_anchor_vectors = None


def _load_anchors():
    global _anchors
    if _anchors is None:
        with open(ANCHORS_FILE, encoding="utf-8") as fh:
            _anchors = json.load(fh)
    return _anchors


def anchor_texts(include_project=True):
    data = _load_anchors()
    texts = list(data["core"])
    if include_project:
        texts += list(data["project"])
    return texts


def core_digest():
    return _load_anchors()["core_digest"]


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


def anchor_vectors(include_project=True, timeout=120):
    """Embed the dictionary once per process, through the pooled embedder."""
    global _anchor_vectors
    from core import embedding_server

    with _lock:
        if _anchor_vectors is None:
            if not embedding_server.available():
                return None
            vectors = embedding_server.embed(anchor_texts(True), timeout=timeout)
            if not vectors:
                return None
            _anchor_vectors = vectors

    if include_project:
        return _anchor_vectors
    return _anchor_vectors[:len(_load_anchors()["core"])]


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


def trace(text, top=1, include_project=True):
    """Which concept appeared at which token. None when unavailable."""
    path = trajectory(text)
    if not path:
        return None
    vectors = anchor_vectors(include_project)
    if not vectors:
        return None
    texts = anchor_texts(include_project)
    vectors = vectors[:len(texts)]
    return [(index, profile(token, vectors, texts, top))
            for index, token in enumerate(path)]


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
    global _anchor_vectors
    with _lock:
        _anchor_vectors = None
