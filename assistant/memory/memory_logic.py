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

def score(memory_item, query_tokens, position, total):
    """
    Higher is more worth injecting. Overlap with what the user just
    said dominates; recency and confidence break ties.
    """
    mem_tokens = tokens(memory_item.get("memory", ""))

    if not mem_tokens:
        return 0.0

    overlap = len(mem_tokens & query_tokens)
    relevance = overlap / len(mem_tokens) if mem_tokens else 0.0

    recency = (position + 1) / total if total else 0.0
    confidence = float(memory_item.get("confidence", 0) or 0)

    return (relevance * 3.0) + (recency * 0.6) + (confidence * 0.4)


def select_relevant(memories, user_input, limit=25):
    """
    The most useful memories for this turn. Returns them in stored
    order so the model sees a stable list rather than a reshuffle
    every message.
    """
    query_tokens = tokens(user_input)
    live = active(memories)

    # Greetings and other content-free turns do not need a bundle of
    # unrelated project facts. Injecting all of them made tiny prompts
    # expensive and nudged replies toward irrelevant old subjects.
    if not query_tokens:
        return []

    live = [
        item for item in live
        if tokens(item.get("memory", "")) & query_tokens
    ]

    if len(live) <= limit:
        return live

    total = len(live)

    ranked = sorted(
        range(total),
        key=lambda i: score(live[i], query_tokens, i, total),
        reverse=True,
    )

    keep = sorted(ranked[:limit])

    return [live[i] for i in keep]
