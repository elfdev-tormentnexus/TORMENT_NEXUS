"""
Cached embeddings for memories and history, computed off the chat path.

Persistent vectors and foreground query vectors deliberately live in
separate stores. A stream of one-off questions therefore cannot evict
memory/history embeddings, and private query text is never serialized.

The retrieval lock protects only small in-memory mutations and snapshots.
JSON serialization, flushing and fsync all happen after that lock is
released, so a cache checkpoint can never stall vector_for().
"""

from collections import OrderedDict
import hashlib
import math
import threading
import time

from core import embedding_server
from core.config import EMBED_CACHE_FILE
from core.file_utils import load_json, save_json
from memory import memory_logic


# The store caps memories at 500 and history chunks are bounded by the
# 20k-character history file. This is a defensive ceiling, not a target.
MAX_CACHE_ENTRIES = 4000
MAX_VECTOR_DIMENSION = 65536

# Queries are short-lived lookup keys, not durable knowledge. Keeping a
# small LRU makes repeated phrasing free without letting chat traffic
# compete with the persistent memory/history index.
MAX_QUERY_CACHE_ENTRIES = 256

POLL_SECONDS = 5.0

_lock = threading.Lock()
_load_lock = threading.Lock()
_write_lock = threading.Lock()

_vectors = {}
_query_vectors = OrderedDict()
_loaded = False
_loaded_identity = None
_dimension = None
_revision = 0

_pending = set()
_poke = threading.Event()
_stop = threading.Event()
_thread = None
_is_busy_fn = None


def _key(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _validated_vector(vector, expected_dimension=None):
    """Return a finite L2-normalised list, or None for malformed input."""
    if not isinstance(vector, list) or not vector:
        return None

    if (
        len(vector) > MAX_VECTOR_DIMENSION
        or (
            expected_dimension is not None
            and len(vector) != expected_dimension
        )
    ):
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

    norm = math.sqrt(math.fsum(value * value for value in clean))

    if not math.isfinite(norm) or norm <= 0.0:
        return None

    return [value / norm for value in clean]


def _parse_cache(raw, identity):
    """Validate a cache document without holding the retrieval lock."""
    if not isinstance(raw, dict) or raw.get("model") != identity:
        return {}, None

    dimension = raw.get("dimension")

    if (
        not isinstance(dimension, int)
        or isinstance(dimension, bool)
        or dimension <= 0
        or dimension > MAX_VECTOR_DIMENSION
    ):
        return {}, None

    stored = raw.get("vectors")

    if not isinstance(stored, dict):
        return {}, None

    vectors = {}

    for key, value in stored.items():
        if (
            not isinstance(key, str)
            or len(key) != 64
            or any(char not in "0123456789abcdef" for char in key)
        ):
            continue

        clean = _validated_vector(value, dimension)

        if clean is not None:
            vectors[key] = clean

    return vectors, dimension if vectors else None


def _ensure_loaded():
    """
    Load or invalidate the persistent cache for the current model identity.

    Disk I/O and JSON parsing happen under a dedicated initialization lock,
    never the lock used by vector_for() after initialization.
    """
    global _loaded, _loaded_identity, _vectors, _dimension, _revision

    identity = embedding_server.model_identity()

    with _lock:
        if _loaded and _loaded_identity == identity:
            return

    with _load_lock:
        identity = embedding_server.model_identity()

        with _lock:
            if _loaded and _loaded_identity == identity:
                return

        raw = load_json(EMBED_CACHE_FILE)
        vectors, dimension = _parse_cache(raw, identity)

        with _lock:
            _vectors = vectors
            _query_vectors.clear()
            _loaded = True
            _loaded_identity = identity
            _dimension = dimension
            _revision += 1


def _trim_locked():
    while len(_vectors) > MAX_CACHE_ENTRIES:
        # Dict insertion order makes this a simple oldest-first eviction.
        _vectors.pop(next(iter(_vectors)))


def _snapshot_locked():
    """A shallow immutable-enough snapshot for serialization elsewhere."""
    _trim_locked()
    return {
        "version": 2,
        "model": _loaded_identity,
        "dimension": _dimension,
        "vectors": dict(_vectors),
    }, _revision


def _persist_snapshot(snapshot, revision):
    """
    Save a snapshot only while it is still current.

    The writer lock orders checkpoints. The retrieval lock is held only for
    a revision comparison; save_json performs JSON work and fsync after it
    has been released.
    """
    with _write_lock:
        with _lock:
            if revision != _revision:
                return False

        try:
            save_json(EMBED_CACHE_FILE, snapshot)
        except OSError:
            return False

    return True


def enabled():
    return embedding_server.available()


def cosine(a, b):
    """Finite cosine for validated, equal-dimension vectors; else zero."""
    clean_a = _validated_vector(a)

    if clean_a is None:
        return 0.0

    clean_b = _validated_vector(b, len(clean_a))

    if clean_b is None:
        return 0.0

    value = math.fsum(x * y for x, y in zip(clean_a, clean_b))
    return value if math.isfinite(value) else 0.0


def vector_for(text):
    """The cached persistent vector for this exact text, or None."""
    if not text:
        return None

    _ensure_loaded()

    with _lock:
        return _vectors.get(_key(text))


def _query_cache_get_locked(key):
    vector = _query_vectors.get(key)

    if vector is not None:
        _query_vectors.move_to_end(key)

    return vector


def _query_cache_put_locked(key, vector):
    _query_vectors[key] = vector
    _query_vectors.move_to_end(key)

    while len(_query_vectors) > MAX_QUERY_CACHE_ENTRIES:
        _query_vectors.popitem(last=False)


def query_vector(text, allow_transient=False):
    """
    Embed a foreground query with one bounded local request.

    Automatic chat retrieval refuses greetings and acknowledgements before
    crossing the socket. An explicit search surface may opt in by passing
    allow_transient=True.
    """
    global _dimension

    if (
        not text
        or not enabled()
        or (not allow_transient and memory_logic.is_transient_query(text))
    ):
        return None

    _ensure_loaded()
    key = _key(text)

    with _lock:
        persistent = _vectors.get(key)

        if persistent is not None:
            return persistent

        cached = _query_cache_get_locked(key)

        if cached is not None:
            return cached

        expected_dimension = _dimension
        identity = _loaded_identity

    vectors = embedding_server.embed([text])

    if not vectors:
        return None

    vector = _validated_vector(vectors[0], expected_dimension)

    if vector is None:
        return None

    with _lock:
        # A model swap while the request was in flight makes its result
        # incomparable with the newly loaded cache.
        if _loaded_identity != identity:
            return None

        if _dimension is None:
            _dimension = len(vector)
        elif len(vector) != _dimension:
            return None

        _query_cache_put_locked(key, vector)

    return vector


def note_texts(texts):
    """Queue persistent memory/history texts for background embedding."""
    if not enabled():
        return

    fresh = {text for text in texts if text}

    if not fresh:
        return

    _ensure_loaded()

    with _lock:
        missing = {
            text for text in fresh
            if _key(text) not in _vectors
        }
        _pending.update(missing)

    if missing:
        _poke.set()


def purge_texts(texts):
    """
    Remove derived vectors for exact forgotten texts.

    Callers can purge a memory/history item at the same time they forget the
    source text. The persistent checkpoint happens outside the retrieval
    lock; query-cache and pending entries are removed as well.
    """
    global _revision

    forgotten = {text for text in texts if text}

    if not forgotten:
        return 0

    _ensure_loaded()
    keys = {_key(text) for text in forgotten}
    removed = 0
    snapshot = None
    revision = None
    persistent_removed = False

    with _lock:
        for key in keys:
            if _vectors.pop(key, None) is not None:
                removed += 1
                persistent_removed = True

            if _query_vectors.pop(key, None) is not None:
                removed += 1

        before_pending = len(_pending)
        _pending.difference_update(forgotten)
        removed += before_pending - len(_pending)

        if persistent_removed:
            _revision += 1
            snapshot, revision = _snapshot_locked()

    if snapshot is not None:
        _persist_snapshot(snapshot, revision)

    return removed


def missing_count():
    with _lock:
        return len(_pending)


def _drain_once():
    global _dimension, _revision

    _ensure_loaded()

    with _lock:
        batch = list(_pending)[:32]
        expected_dimension = _dimension
        identity = _loaded_identity

    if not batch:
        return False

    vectors = embedding_server.embed(batch, timeout=30)

    if vectors is None or len(vectors) != len(batch):
        return False

    clean_vectors = []
    batch_dimension = expected_dimension

    for vector in vectors:
        clean = _validated_vector(vector, batch_dimension)

        if clean is None:
            return False

        batch_dimension = len(clean)
        clean_vectors.append(clean)

    with _lock:
        if _loaded_identity != identity:
            return False

        if _dimension is None:
            _dimension = batch_dimension
        elif batch_dimension != _dimension:
            return False

        for text, vector in zip(batch, clean_vectors):
            _vectors[_key(text)] = vector
            _pending.discard(text)

        _revision += 1
        snapshot, revision = _snapshot_locked()

    _persist_snapshot(snapshot, revision)
    return True


def _worker():
    while not _stop.is_set():
        _poke.wait(POLL_SECONDS)
        _poke.clear()

        if _stop.is_set():
            break

        while (
            _is_busy_fn is not None
            and _is_busy_fn()
            and not _stop.is_set()
        ):
            time.sleep(0.2)

        while _drain_once():
            if _stop.is_set():
                break


def start_worker(is_busy_fn=None):
    """Idempotent; a no-op when no embedder is available."""
    global _thread, _is_busy_fn

    if _thread is not None or not enabled():
        return

    _is_busy_fn = is_busy_fn
    _stop.clear()
    _thread = threading.Thread(target=_worker, daemon=True)
    _thread.start()


def stop_worker():
    global _thread

    _stop.set()
    _poke.set()

    if _thread is not None:
        _thread.join(timeout=2.0)

        if not _thread.is_alive():
            _thread = None


def reset_for_tests():
    """Return the module to its just-imported state. Tests only."""
    global _vectors, _query_vectors, _loaded, _loaded_identity
    global _dimension, _revision, _is_busy_fn

    stop_worker()

    with _lock:
        _vectors = {}
        _query_vectors = OrderedDict()
        _loaded = False
        _loaded_identity = None
        _dimension = None
        _revision = 0
        _pending.clear()

    _is_busy_fn = None
    _stop.clear()
    _poke.clear()
