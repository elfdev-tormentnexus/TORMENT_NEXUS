"""
Memory comparison, superseding and selection.

Split out from memory_store so the storage layer stays about reading
and writing, and the judgement calls live in one testable place.

Three problems this fixes:

1. Duplicate detection was word-overlap over the NEW memory's length,
   with a 0.55 threshold and no stopword removal. Since every memory
   starts "The developer ...", the boilerplate alone pushed unrelated
   facts over the line. "owns a Raspberry Pi camera" and "owns a 3D
   printer" scored as duplicates; the second was silently dropped.

2. Nothing ever superseded anything. Replace your GPU and you keep
   both cards in memory forever, and the model is told both are true.

3. Every memory went into every prompt. Fine at 20, ruinous at 200.
"""

import math
import re


# "developer" is in essentially every memory, so for comparison
# purposes it carries no information and only inflates overlap.
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "will", "would", "should",
    "can", "could", "of", "to", "in", "on", "at", "for", "with", "and",
    "or", "but", "that", "this", "it", "its", "their", "there", "they",
    "he", "she", "his", "her", "developer", "user", "currently", "also",
}

# Above this, two memories say the same thing.
DUPLICATE_THRESHOLD = 0.58

# Between this and DUPLICATE_THRESHOLD, they might be the same fact
# with a changed value -- a candidate for superseding.
SUPERSEDE_MIN = 0.45

# How alike the non-numeric parts must be before a numeric difference
# counts as an update rather than a separate fact.
FRAME_THRESHOLD = 0.70


_WORD = re.compile(r"[a-z0-9_.\-]+")


def tokens(text):
    if not text:
        return set()

    found = _WORD.findall(text.lower())
    return {t.strip(".-_") for t in found if t.strip(".-_") and t not in STOPWORDS}


def _numeric(tok_set):
    """Tokens carrying a number: 4090, pi5, q4_k_m, v2, 3d."""
    return {t for t in tok_set if any(c.isdigit() for c in t)}


def _deburr(tok):
    """
    Strip the digits out of a token to expose its shape, so
    "qwen3-8b" and "qwen3-4b" both reduce to "qwen-b" and can be
    recognised as the same thing with a different number.
    """
    return "".join(c for c in tok if not c.isdigit()).strip("-_.")


def _frame(tok_set):
    """Wording around the numbers, with the numbers removed."""
    out = set()

    for t in tok_set:
        d = _deburr(t)

        # Single leftover letters ("3d" -> "d") are noise, not wording.
        if len(d) >= 2:
            out.add(d)

    return out


def similarity(a, b):
    """Jaccard overlap. Symmetric, unlike the old ratio."""
    ta = tokens(a)
    tb = tokens(b)

    if not ta or not tb:
        return 0.0

    return len(ta & tb) / len(ta | tb)


def is_duplicate(new_text, existing_text, threshold=DUPLICATE_THRESHOLD):
    # A changed value is an update, never a duplicate. Checked first
    # so "RTX 3080" -> "RTX 4090" is not merged away.
    if is_update_of(new_text, existing_text):
        return False

    return similarity(new_text, existing_text) >= threshold


def is_update_of(new_text, old_text):
    """
    True when these look like the same fact with a changed value:
    the wording around it matches, but the numbers differ.

        "owns an NVIDIA RTX 3080" -> "owns an NVIDIA RTX 4090"   yes
        "runs Qwen3-4B"           -> "runs Qwen3-8B"             yes
        "owns a Raspberry Pi 5"   -> "owns a 3D printer"         no

    Judged on the FRAME (wording with digits stripped) rather than raw
    overlap, because a compound like "qwen3-4b" is a single token and
    barely overlaps its own successor.
    """
    ta = tokens(new_text)
    tb = tokens(old_text)

    if not ta or not tb:
        return False

    na = _numeric(ta)
    nb = _numeric(tb)

    # Both sides must carry a number, and they must differ.
    if not na or not nb or na == nb:
        return False

    fa = _frame(ta)
    fb = _frame(tb)

    if not fa or not fb:
        return False

    frame = len(fa & fb) / len(fa | fb)

    return frame >= FRAME_THRESHOLD


def find_conflicts(new_text, memories):
    """
    Indices of stored memories this one appears to replace.

    Used to gate on the stored category matching the new fact's
    category, on the theory that a hardware change should never
    overwrite a preference. In practice the category is guessed fresh
    by the extractor on every message with no consistency guarantee,
    so the same real-world fact can land in "hardware" once and
    "project" the next time -- and the category gate then silently
    blocked the supersession it was meant to help with, leaving both
    the stale and new fact active forever. is_update_of() is already
    the real safety check here: it requires a shared, mostly-matching
    wording frame *and* a differing number, which unrelated facts
    essentially never satisfy by chance -- so category adds a false
    sense of extra safety without actually preventing bad merges.
    """
    hits = []

    for i, item in enumerate(memories):
        if item.get("superseded"):
            continue

        if is_update_of(new_text, item.get("memory", "")):
            hits.append(i)

    return hits


def find_duplicate(new_text, memories):
    """Index of an existing memory saying the same thing, or None."""
    for i, item in enumerate(memories):
        if item.get("superseded"):
            continue

        if is_duplicate(new_text, item.get("memory", "")):
            return i

    return None


def active(memories):
    """Memories that should still be treated as true."""
    return [m for m in memories if not m.get("superseded")]


# ============================================================
# RELEVANCE
# ============================================================

# Automatic semantic-only retrieval is deliberately conservative. The
# measured evaluation for the shipped embedder found that 0.38 admitted
# hundreds of unrelated pairs; 0.55 plus a 0.06 lead over the runner-up
# produced no false automatic recalls in the checked probe set.
AUTOMATIC_SEMANTIC_MIN_COSINE = 0.55
AUTOMATIC_SEMANTIC_MARGIN = 0.06

SEMANTIC_MODE_AUTOMATIC = "automatic"
SEMANTIC_MODE_EXPLICIT = "explicit"

_TRANSIENT_EXACT = {
    "hi",
    "hey",
    "hello",
    "hello there",
    "hey there",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "how are you",
    "how is it going",
    "hows it going",
    "thanks",
    "thank you",
    "thanks so much",
    "thank you so much",
    "nice to see you",
    "okay",
    "ok",
    "okay sounds good",
    "ok sounds good",
    "sounds good",
    "that sounds good",
    "got it",
    "all right",
    "alright",
    "sure",
    "yes",
    "no",
    "what can you do",
    "who are you",
}


def is_transient_query(text):
    """
    True for a whole-turn greeting, acknowledgement or capability pleasantry.

    Matching the normalized *whole* message keeps "sounds good, where is the
    radio?" meaningful while stopping multiword small talk from opening a
    semantic lane merely because it has two content tokens.
    """
    if not text:
        return True

    normalized = re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()
    normalized = normalized.replace("'", "")
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized in _TRANSIENT_EXACT


def _cosine(a, b):
    """Finite dot product for equal-dimension numeric vectors, else None."""
    if (
        not isinstance(a, (list, tuple))
        or not isinstance(b, (list, tuple))
        or not a
        or len(a) != len(b)
    ):
        return None

    values = []

    for x, y in zip(a, b):
        if (
            not isinstance(x, (int, float))
            or isinstance(x, bool)
            or not math.isfinite(x)
            or not isinstance(y, (int, float))
            or isinstance(y, bool)
            or not math.isfinite(y)
        ):
            return None

        values.append(x * y)

    result = math.fsum(values)
    return result if math.isfinite(result) else None


def score(memory_item, query_tokens, position, total, semantic=0.0):
    """
    Higher is more worth injecting. Overlap with what the user just
    said dominates; recency and confidence break lexical ties.

    `semantic` remains an accepted argument for compatibility, but is
    intentionally not mixed into this score. Semantic-only candidates use
    a separate lane so recency cannot knock out the best cosine match.
    """
    mem_tokens = tokens(memory_item.get("memory", ""))

    if not mem_tokens:
        return 0.0

    overlap = len(mem_tokens & query_tokens)
    relevance = overlap / len(mem_tokens) if mem_tokens else 0.0

    recency = (position + 1) / total if total else 0.0
    confidence = float(memory_item.get("confidence", 0) or 0)

    return (
        (relevance * 3.0)
        + (recency * 0.6)
        + (confidence * 0.4)
    )


def select_relevant(
    memories,
    user_input,
    limit=25,
    query_vector=None,
    memory_vectors=None,
    min_cosine=AUTOMATIC_SEMANTIC_MIN_COSINE,
    semantic_mode=SEMANTIC_MODE_AUTOMATIC,
    semantic_margin=AUTOMATIC_SEMANTIC_MARGIN,
):
    """
    Select memories through distinct lexical and semantic lanes.

    Automatic chat injection keeps exact token matches, then reserves at
    most one slot for a zero-overlap semantic result only when it clears
    both the 0.55 floor and a 0.06 lead over the next candidate. Explicit
    search returns cosine-ranked candidates best-first with no recency
    term; callers should label those as candidates rather than facts.
    """
    if limit <= 0:
        return []

    query_tokens = tokens(user_input)
    live = active(memories)

    if semantic_mode not in {
        SEMANTIC_MODE_AUTOMATIC,
        SEMANTIC_MODE_EXPLICIT,
    }:
        raise ValueError(f"Unknown semantic retrieval mode: {semantic_mode}")

    # Whole-turn greetings and acknowledgements stay retrieval-free even
    # when they contain several words ("thanks so much", "good morning").
    if (
        semantic_mode == SEMANTIC_MODE_AUTOMATIC
        and (not query_tokens or is_transient_query(user_input))
    ):
        return []

    if memory_vectors is not None and len(memory_vectors) == len(memories):
        vector_of = {
            id(item): vector
            for item, vector in zip(memories, memory_vectors)
        }
    else:
        vector_of = {}

    semantic_pairs = []

    if query_vector is not None:
        for index, item in enumerate(live):
            similarity = _cosine(query_vector, vector_of.get(id(item)))

            if similarity is not None:
                semantic_pairs.append((similarity, index))

    if semantic_mode == SEMANTIC_MODE_EXPLICIT and semantic_pairs:
        semantic_pairs.sort(key=lambda pair: (-pair[0], pair[1]))
        return [live[index] for _similarity, index in semantic_pairs[:limit]]

    # Without semantic vectors, an explicit search still gets the exact
    # word-overlap behavior rather than an empty answer.
    lexical_indices = [
        index for index, item in enumerate(live)
        if tokens(item.get("memory", "")) & query_tokens
    ]

    semantic_choice = None

    if query_vector is not None and len(query_tokens) >= 2:
        lexical_set = set(lexical_indices)
        zero_overlap = [
            pair for pair in semantic_pairs if pair[1] not in lexical_set
        ]
        zero_overlap.sort(key=lambda pair: (-pair[0], pair[1]))

        try:
            floor = max(
                AUTOMATIC_SEMANTIC_MIN_COSINE,
                min(1.0, max(0.0, float(min_cosine))),
            )
        except (TypeError, ValueError):
            floor = AUTOMATIC_SEMANTIC_MIN_COSINE

        try:
            margin = max(
                AUTOMATIC_SEMANTIC_MARGIN,
                min(1.0, max(0.0, float(semantic_margin))),
            )
        except (TypeError, ValueError):
            margin = AUTOMATIC_SEMANTIC_MARGIN

        if zero_overlap:
            best_similarity, best_index = zero_overlap[0]
            runner_up = zero_overlap[1][0] if len(zero_overlap) > 1 else None

            if (
                best_similarity >= floor
                and (
                    runner_up is None
                    or best_similarity - runner_up >= margin
                )
            ):
                semantic_choice = best_index

    # A one-item budget belongs to an exact lexical hit. With wider prompt
    # budgets the confident semantic rescue gets one reserved slot.
    if semantic_choice is not None and lexical_indices and limit == 1:
        semantic_choice = None

    lexical_capacity = limit - (1 if semantic_choice is not None else 0)
    total = len(live)
    ranked_lexical = sorted(
        lexical_indices,
        key=lambda index: score(
            live[index],
            query_tokens,
            index,
            total,
        ),
        reverse=True,
    )
    chosen = set(ranked_lexical[:max(0, lexical_capacity)])

    if semantic_choice is not None:
        chosen.add(semantic_choice)

    # Automatic prompt injection remains stable in stored order.
    return [item for index, item in enumerate(live) if index in chosen]
