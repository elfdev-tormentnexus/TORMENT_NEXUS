"""Conservative semantic recall over persisted conversation exchanges."""

import re

from memory import memory_store
from memory import semantic_index


# Require the stamped line to be followed by the writer's User: marker.
# A timestamp-looking line inside a multiline user message is data, not an
# exchange boundary.
_STAMP = re.compile(
    r"^\[\d{4}-\d{2}-\d{2}[ T].*?\](?=\r?\nUser:\s)",
    re.MULTILINE,
)

MIN_CHUNK_CHARS = 60
MAX_CHUNK_CHARS = 600
CLIP_MARKER = "\n...[middle of exchange clipped]...\n"

HISTORY_MIN_COSINE = 0.60
HISTORY_MIN_MARGIN = 0.06

_EXPLICIT_RECALL_PATTERNS = (
    re.compile(
        r"\b(?:what\s+)?did (?:we|you|i)\s+"
        r"(?:decide|discuss|say|tell|agree|settle|conclude|plan)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:do|can|could) you (?:remember|recall)\s+"
        r"(?:what|when|where|how)\s+(?:we|you|i)\b",
        re.I,
    ),
    re.compile(r"\b(?:remember|recall)\s+(?:what|when)\s+we\b", re.I),
    re.compile(
        r"\bremind me\s+(?:what|when|where|how)\s+(?:we|you|i)\b",
        re.I,
    ),
    re.compile(r"\bwhere did we leave off\b", re.I),
    re.compile(r"\b(?:conversation|chat)\s+history\b", re.I),
    re.compile(
        r"\bwhat was (?:our|the)\s+"
        r"(?:decision|plan|conclusion|agreement)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:earlier|previous(?:ly)?|last time|before)\b.*"
        r"\b(?:chat|conversation|discuss|decid|said|told|talk|agree)",
        re.I,
    ),
    re.compile(
        r"\b(?:you|i)\s+(?:said|told)\b.*"
        r"\b(?:earlier|before|last time|previously)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:discuss|decid|talk|agree|conclud)\w*\b.*"
        r"\b(?:earlier|before|last time|previously)\b",
        re.I,
    ),
)


def explicit_recall_intent(query_text):
    """Whether the operator clearly asked about an earlier conversation."""
    if not isinstance(query_text, str) or not query_text.strip():
        return False

    return any(pattern.search(query_text) for pattern in _EXPLICIT_RECALL_PATTERNS)


def _raw_exchanges():
    text = memory_store.conversation_history

    if not text:
        return []

    stamps = list(_STAMP.finditer(text))
    pieces = []

    for index, stamp in enumerate(stamps):
        start = stamp.start()
        end = stamps[index + 1].start() if index + 1 < len(stamps) else len(text)
        pieces.append(text[start:end].strip())

    return pieces


def _balanced_clip(piece):
    """
    Preserve both the question and the assistant's concluding decision.

    Prefix-only clipping routinely retained a long user request while
    deleting the answer. Equal head/tail budgets keep the exchange useful
    and make the omission explicit.
    """
    if len(piece) <= MAX_CHUNK_CHARS:
        return piece

    available = MAX_CHUNK_CHARS - len(CLIP_MARKER)
    head = (available + 1) // 2
    tail = available - head

    return piece[:head] + CLIP_MARKER + (piece[-tail:] if tail else "")


def _eligible(pieces):
    return [
        _balanced_clip(piece)
        for piece in pieces
        if len(piece) >= MIN_CHUNK_CHARS
    ]


def chunks():
    """The history file as bounded exchange strings, oldest first."""
    return _eligible(_raw_exchanges())


def recallable(live_session_exchanges=0):
    """
    Persisted exchanges outside the current live prompt.

    The caller supplies the number of current session exchanges. After a
    restart that number is zero, so the newest persisted decisions remain
    reachable instead of being unconditionally hidden.
    """
    if (
        not isinstance(live_session_exchanges, int)
        or isinstance(live_session_exchanges, bool)
    ):
        live_session_exchanges = 0

    live_session_exchanges = max(0, live_session_exchanges)
    pieces = _raw_exchanges()

    if live_session_exchanges:
        keep = max(0, len(pieces) - live_session_exchanges)
        pieces = pieces[:keep]

    return _eligible(pieces)


def refresh(live_session_exchanges=0):
    """Queue recallable history for background embedding."""
    semantic_index.note_texts(recallable(live_session_exchanges))


def relevant(
    query_vector,
    query_text="",
    live_session_exchanges=0,
    limit=1,
    min_cosine=HISTORY_MIN_COSINE,
    margin=HISTORY_MIN_MARGIN,
):
    """
    Return at most one high-confidence recalled exchange.

    History participates only after an explicit conversational-recall
    request. The best cached candidate must clear both the 0.60 floor and
    a 0.06 lead over the runner-up; otherwise silence is safer than
    presenting an unrelated old exchange as remembered context.
    """
    if (
        query_vector is None
        or limit <= 0
        or not explicit_recall_intent(query_text)
    ):
        return []

    try:
        floor = max(
            HISTORY_MIN_COSINE,
            min(1.0, max(0.0, float(min_cosine))),
        )
    except (TypeError, ValueError):
        floor = HISTORY_MIN_COSINE

    try:
        required_margin = max(
            HISTORY_MIN_MARGIN,
            min(1.0, max(0.0, float(margin))),
        )
    except (TypeError, ValueError):
        required_margin = HISTORY_MIN_MARGIN

    scored = []

    for index, chunk in enumerate(recallable(live_session_exchanges)):
        vector = semantic_index.vector_for(chunk)

        if vector is None:
            continue

        similarity = semantic_index.cosine(query_vector, vector)

        scored.append((similarity, index, chunk))

    scored.sort(key=lambda row: (-row[0], row[1]))

    if not scored:
        return []

    best_similarity, _index, best_chunk = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else None

    if (
        best_similarity < floor
        or (
            runner_up is not None
            and best_similarity - runner_up < required_margin
        )
    ):
        return []

    return [best_chunk]
