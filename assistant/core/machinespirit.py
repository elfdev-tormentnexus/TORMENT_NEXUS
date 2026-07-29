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

# Reentrant because anchor_vectors() holds this and then reaches
# anchor_texts() -> _load_anchors(), which needs it for the same reason.
# A plain Lock made the inner cache the unguarded one by default.
_lock = threading.RLock()
_anchors = None
_anchors_loaded_version = None
_anchor_vectors = None
_anchor_vectors_key = None


def anchors_file(version=None):
    return os.path.join(_HERE, f"anchors_v{version or ANCHOR_VERSION}.json")


def _load_anchors():
    global _anchors, _anchors_loaded_version
    with _lock:
        if _anchors is None or _anchors_loaded_version != ANCHOR_VERSION:
            with open(anchors_file(), encoding="utf-8") as fh:
                loaded = json.load(fh)
            _anchors = loaded
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
        # Snapshot inside the lock. Reading the global again on the way out
        # let a concurrent reset_cache() replace it with None between the
        # two, and _select_sections would slice that.
        rows = _anchor_vectors

    return _select_sections(rows, include_project, include_life)


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


def _centred_anchors(vectors):
    """The anchor frame: mean removed, and each anchor's norm kept.

    This depends only on the dictionary, so it is the same for every token
    in a path. It used to be rebuilt per token -- the mean over all 184
    anchors, a full copy of the anchor matrix, and then a fresh norm for
    every anchor inside every cosine. On a 512-token trajectory that is the
    identical work done 512 times, and it is the readout, not the model,
    that the operator waits on.
    """
    mean = [sum(column) / len(vectors) for column in zip(*vectors)]
    centred = [[x - m for x, m in zip(a, mean)] for a in vectors]
    norms = [math.sqrt(sum(x * x for x in a)) or 1.0 for a in centred]
    return mean, centred, norms


def _profile_in_frame(vector, frame, texts, top):
    """One token against an already-centred dictionary."""
    mean, centred, norms = frame
    target = [x - m for x, m in zip(vector, mean)]
    scale = math.sqrt(sum(x * x for x in target)) or 1.0
    scored = sorted(
        ((sum(x * y for x, y in zip(target, anchor)) / (scale * norm), text)
         for anchor, norm, text in zip(centred, norms, texts)),
        reverse=True)
    return scored[:top]


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
    return _profile_in_frame(vector, _centred_anchors(vectors), texts, top)


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
    # Centre the dictionary once, then read every token against it.
    frame = _centred_anchors(vectors)
    return [(index, _profile_in_frame(token, frame, texts, top))
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
    """Where each concept appeared, ordered by how much of the trace backs it.

    Two different questions live here and they were being answered by one
    number. *Where* a concept sits is its strongest position, and that is
    what the row reports. *Which* concepts to rank first is a different
    question, and ranking by that same strongest position was measured to
    cost 13 points: on 30 labelled paraphrases, ordering by the single best
    position identifies the right concept 77% of the time, and ordering the
    identical data by summed evidence gets 90%.

    The reason is the one already recorded for the dictionary growing: a max
    over positions gives every additional anchor another chance at one
    lucky spike, and a lucky spike is indistinguishable from a real one when
    only the best is kept. A sum has to be earned across the sentence.

    So the ordering is by total support and the reported position is still
    the peak, because "this concept, at this token" is the claim the feature
    exists to make and summing must not blur where it happened.
    """
    best = {}
    support = {}
    for index, hits in rows or []:
        for score, anchor in hits:
            support[anchor] = support.get(anchor, 0.0) + score
            if anchor not in best or score > best[anchor][0]:
                best[anchor] = (score, index)
    return sorted(((anchor, score, index)
                   for anchor, (score, index) in best.items()),
                  key=lambda row: -support[row[0]])


# --- the second moment ------------------------------------------------
#
# Prior art first, as everything else here does it. The matrix below is the
# uncentred second moment of a trajectory's tokens. Statistics calls it a
# covariance; quantum mechanics calls it a density matrix and brings a
# worked vocabulary of scalar observables for it -- purity, participation
# ratio, von Neumann entropy. Both names describe the same arithmetic and
# neither is ours. What is measured here is what those observables read on
# this project's own traces.
#
# The reason to want it: pooling keeps the FIRST moment and discards the
# spread. rho keeps the second. So "how much ground did this text cover" is
# a question the pooled vector cannot answer and this can.
#
# What it cannot do, stated where it cannot be missed: rho is a sum over
# tokens, so it is permutation-invariant. Shuffle the sentence and every
# number below is identical. It answers how much ground, never in what
# order. trace() and peaks() remain the only things that speak to position.


def _unit(vector):
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else list(vector)


def gram(path):
    """(1/n) V Vt for a trajectory, each token normalised first.

    rho = (1/n) sum |v><v| is 384x384. This is n x n, n is usually a few
    dozen, and the two carry the same nonzero eigenvalues -- so every
    observable below reads off the small matrix and the big one is never
    built. Trace is 1 because the tokens are unit vectors.
    """
    tokens = [_unit(v) for v in path]
    n = len(tokens)
    rows = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            value = sum(x * y for x, y in zip(tokens[i], tokens[j])) / n
            rows[i][j] = value
            rows[j][i] = value
    return rows


def purity(matrix):
    """Tr(rho^2). 1.0 when every token sits in one place, 1/n when they are
    mutually orthogonal. No eigendecomposition: for a symmetric matrix this
    is the sum of its squared entries."""
    return sum(value * value for row in matrix for value in row)


def effective_rank(matrix):
    """1 / Tr(rho^2) -- roughly how many directions the text actually used.

    Bounded by 1 and the token count. The participation ratio under its
    other name.
    """
    weight = purity(matrix)
    return 1.0 / weight if weight else 0.0


def _eigenvalues_symmetric(matrix, sweeps=60, tolerance=1e-12):
    """Cyclic Jacobi. Small symmetric matrices only, which is all this has.

    Written out rather than imported because this module is deliberately
    stdlib and pure `math`, like the cosine above it.
    """
    a = [row[:] for row in matrix]
    n = len(a)

    for _ in range(sweeps):
        off = sum(a[i][j] * a[i][j]
                  for i in range(n) for j in range(n) if i != j)
        if off <= tolerance:
            break

        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) <= tolerance:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
                sign = 1.0 if theta >= 0 else -1.0
                t = sign / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c

                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk

    return sorted((a[i][i] for i in range(n)), reverse=True)


def von_neumann_entropy(matrix):
    """-sum lambda ln lambda over the spectrum. Zero for a pure state."""
    total = 0.0
    for value in _eigenvalues_symmetric(matrix):
        if value > 1e-12:
            total -= value * math.log(value)
    return total


def spread(text, path=None):
    """How much ground a text covered, as the density matrix reads it.

    Returns None when unavailable, like everything else here, rather than
    guessing. `truncated` is carried in the result because a spread over
    the first 512 tokens of a longer input is a spread of part of it, and
    the caller should not have to ask twice to find that out.
    """
    if path is None:
        path = trajectory(text)
    if not path:
        return None

    matrix = gram(path)
    tokens = len(path)
    entropy = von_neumann_entropy(matrix)

    return {
        "tokens": tokens,
        "purity": purity(matrix),
        "effective_rank": effective_rank(matrix),
        "entropy": entropy,
        "entropy_normalised": (entropy / math.log(tokens)
                               if tokens > 1 else 0.0),
        "truncated": looks_truncated(path),
    }


# --- the trail -------------------------------------------------------
#
# A trace is n x 184 numbers and grows with the sentence. What it is
# actually asked are two questions -- which concepts are here, and where
# did each one sit -- and neither needs the whole grid.
#
# So record, per anchor, only what happened at the tokens where that anchor
# was the nearest one: how much support it accumulated there, its single
# strongest reading, and the position of that reading. Anchors that never
# won record nothing. The result is bounded by the anchor count rather than
# the token count, so a long input leaves the same size of wake as a short
# one.
#
# Two measurements make this safe rather than hopeful, and both are already
# in the notes. Collapsing each token to its single winning anchor scores
# 90%/0.933 against 90%/0.920 for keeping all 184 coordinates, so the
# argmax is not where information is lost. And ranking by summed support
# rather than by one best position is what took the trace from 77% to 90%,
# which is why support is stored and not just the peak -- a trail carrying
# only maxima would be the version that was measured to be worse.
#
# The claim is therefore narrow and testable: a trail reproduces peaks()
# exactly, at a size that does not grow with the input. A test asserts the
# equality rather than the docstring asserting it.


def trail(text, path=None, include_project=True, include_life=True):
    """Per anchor, what happened where it was nearest. None when unavailable.

    Rows are `{anchor, support, peak, at, hits}`, ordered the way peaks()
    orders them: by total support, reporting the strongest position.
    """
    if path is None:
        path = trajectory(text)
    if not path:
        return None

    vectors = anchor_vectors(include_project, include_life)
    if not vectors:
        return None

    texts = anchor_texts(include_project, include_life)
    vectors = vectors[:len(texts)]
    mean, centred, norms = _centred_anchors(vectors)

    support = {}
    best = {}
    hits = {}

    for index, token in enumerate(path):
        target = [x - m for x, m in zip(token, mean)]
        scale = math.sqrt(sum(x * x for x in target)) or 1.0

        winner = None
        for position, (anchor, norm) in enumerate(zip(centred, norms)):
            score = (sum(x * y for x, y in zip(target, anchor))
                     / (scale * norm))
            if winner is None or score > winner[0]:
                winner = (score, position)

        score, position = winner
        name = texts[position]
        support[name] = support.get(name, 0.0) + score
        hits[name] = hits.get(name, 0) + 1
        if name not in best or score > best[name][0]:
            best[name] = (score, index)

    rows = [{"anchor": name, "support": support[name],
             "peak": best[name][0], "at": best[name][1],
             "hits": hits[name]}
            for name in support]
    rows.sort(key=lambda row: -row["support"])
    return rows


def trail_peaks(rows, top=None):
    """The same triples peaks() returns, read off a trail.

    Exists so the equivalence can be asserted against peaks() directly
    rather than compared by eye.
    """
    ordered = [(row["anchor"], row["peak"], row["at"]) for row in rows or []]
    return ordered if top is None else ordered[:top]


def trail_cost(rows, tokens, dimensions):
    """What the trail saved, stated rather than assumed.

    Three numbers per surviving anchor against a token count times a
    dimension count. Returned as a dict so a caller reports the measurement
    instead of an adjective.
    """
    stored = len(rows or []) * 3
    raw = tokens * dimensions
    return {"trail_values": stored, "trajectory_values": raw,
            "ratio": (raw / stored) if stored else None}


def reset_cache():
    """Drop the embedded dictionary; used by tests and after a model swap."""
    global _anchor_vectors, _anchor_vectors_key, _anchors
    global _anchors_loaded_version
    with _lock:
        _anchor_vectors = None
        _anchor_vectors_key = None
        _anchors = None
        _anchors_loaded_version = None
