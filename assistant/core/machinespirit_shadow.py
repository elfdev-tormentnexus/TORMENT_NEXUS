"""Log what anchor space would have retrieved, without letting it decide.

The claim that anchor-space retrieval does not beat pooled cosine rests on
0.689 against 1.000 over an eighteen-chunk corpus. The plan that recorded
that number also said what it indicts: "nothing but the 18-chunk corpus it
ran on." An honest verdict needs evidence at the scale the assistant
actually runs at, and nothing has been generating it.

So this observes. Every hazard-mode retrieval records two rankings of the
same candidates -- the pooled cosine that decided, and the anchor-space
ranking that did not -- along with how much they agreed. Over a few hundred
turns that becomes a real answer to a question currently settled by
eighteen chunks.

Three rules hold this in place, and each is a test rather than a promise:

  It never decides. Nothing here returns to the caller, mutates a
  candidate list, or reorders anything. Retrieval is byte-identical with
  this module present and absent, which a regression asserts in both modes.

  It never takes a turn down. Every entry point swallows its own failures.
  An observation that can break the thing it observes is worse than no
  observation, which is the rule `_update_retrieval_panel` already follows.

  It never writes text. Memories are recorded as SHA-256 digests, the same
  way a stored trajectory records its source. A row says which memory
  ranked where and nothing about what it said.

The file lands in `logs/`, already excluded from git and from release
packaging, and is bounded so a long-running install cannot grow it without
limit.
"""
import hashlib
import json
import os
import time

from core.config import ASSISTANT_ROOT

SHADOW_FILE = os.path.join(ASSISTANT_ROOT, "logs", "machinespirit_shadow.jsonl")

# Comparing beyond the handful that could actually reach a prompt measures
# noise. Five is the panel's own horizon.
TOP_K = 5

# Anchor-space profiling is 184 cosines per candidate, on the foreground
# path of a mode that advertises being slower on purpose. That is still no
# reason to profile a thousand memories to rank four.
MAX_CANDIDATES = 60

# Rows are small. This is about a year of heavy use, not a real ceiling.
MAX_ROWS = 20000


def digest(text):
    """A memory's identity without its content."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _cosine(left, right):
    a = b = dot = 0.0
    for x, y in zip(left, right):
        dot += x * y
        a += x * x
        b += y * y
    if not a or not b:
        return 0.0
    return dot / ((a ** 0.5) * (b ** 0.5))


def coordinates(vector, anchors):
    """A vector re-expressed as its similarities to the shared anchors.

    The relative representation of Moschella et al., which is the whole
    reason two spaces can be compared at all. Here both sides come from the
    same embedder, so this is not translation -- it is the same readout the
    cross-model case uses, applied within one model to see what it costs.
    """
    return [_cosine(vector, anchor) for anchor in anchors]


def ranking(query_vector, candidate_vectors, anchors):
    """Candidates ordered in anchor space. [(score, index)], best first."""
    query = coordinates(query_vector, anchors)
    scored = []

    for index, vector in enumerate(candidate_vectors[:MAX_CANDIDATES]):
        if vector is None:
            continue
        scored.append((_cosine(query, coordinates(vector, anchors)), index))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return scored


def agreement(first, second, k=TOP_K):
    """Top-k overlap between two rankings, or None when either is empty."""
    left = {index for _score, index in first[:k]}
    right = {index for _score, index in second[:k]}
    if not left or not right:
        return None
    return len(left & right) / float(min(len(left), len(right)))


def _rows(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.readlines()
    except OSError:
        return []


def record(row, path=None):
    """Append one row, keeping the file bounded. Never raises."""
    target = path or SHADOW_FILE
    try:
        folder = os.path.dirname(target)
        if folder:
            os.makedirs(folder, exist_ok=True)

        existing = _rows(target)
        line = json.dumps(row, sort_keys=True) + "\n"

        if len(existing) >= MAX_ROWS:
            keep = existing[-(MAX_ROWS - 1):]
            with open(target, "w", encoding="utf-8") as handle:
                handle.writelines(keep)
                handle.write(line)
        else:
            with open(target, "a", encoding="utf-8") as handle:
                handle.write(line)
        return True
    except (OSError, TypeError, ValueError):
        return False


def observe(user_input, candidates, candidate_vectors, query_vector,
            pooled_pairs=None, path=None, clock=time.time):
    """Record both rankings for one retrieval. Returns None, always.

    The return type is the design. There is nothing here for a caller to
    use, so there is nothing for a future edit to accidentally start
    deciding with.
    """
    try:
        from core import machinespirit

        if not machinespirit.configured() or query_vector is None:
            return None

        anchors = machinespirit.anchor_vectors()
        if not anchors:
            return None

        shadow = ranking(query_vector, candidate_vectors, anchors)
        if not shadow:
            return None

        if pooled_pairs is None:
            pooled_pairs = []
            for index, vector in enumerate(candidate_vectors[:MAX_CANDIDATES]):
                if vector is not None:
                    pooled_pairs.append((_cosine(query_vector, vector), index))
            pooled_pairs.sort(key=lambda pair: (-pair[0], pair[1]))

        def named(pairs):
            out = []
            for score, index in pairs[:TOP_K]:
                if 0 <= index < len(candidates):
                    text = candidates[index].get("memory", "")
                    out.append([digest(text), round(float(score), 6)])
            return out

        record({
            "at": clock(),
            "query": digest(user_input),
            "k": TOP_K,
            "candidates": len(shadow),
            "agreement": agreement(pooled_pairs, shadow),
            "pooled": named(pooled_pairs),
            "shadow": named(shadow),
        }, path=path)
    except Exception:
        # An observation that can take a turn down is worse than none.
        return None

    return None
