import re


# ============================================================
# DIRECT MEMORY DETECTION
# ============================================================

# "i have"/"i own" are greedy enough to grab filler that isn't a fact at
# all, e.g. "I have to go now" or "I have no idea". Skip those.
_FILLER_STARTS = (
    "to ", "no ", "not ", "nothing", "none", "enough", "plenty",
)


def _remembered_statement(fact):
    """Turn common first-person phrasing into a durable stored fact."""
    replacements = (
        (r"^i am\b", "The developer is"),
        (r"^i'm\b", "The developer is"),
        (r"^i want\b", "The developer wants"),
        (r"^i have\b", "The developer has"),
        (r"^i own\b", "The developer owns"),
        (r"^i prefer\b", "The developer prefers"),
        (r"^i like\b", "The developer likes"),
        (r"^my\b", "The developer's"),
    )

    for pattern, replacement in replacements:
        updated, count = re.subn(pattern, replacement, fact, count=1, flags=re.IGNORECASE)
        if count:
            return updated

    return f"The developer wants this remembered: {fact}"


def extract_direct_memory(text):
    patterns = [
        (r"remember this[: ]+(.+)", "project", None),
        (r"i am building (.+?)(?:\.|$)", "project", "The developer is building {}"),
        (r"i'm building (.+?)(?:\.|$)", "project", "The developer is building {}"),
        (r"my project is (.+?)(?:\.|$)", "project", "The developer's project is {}"),
        (r"i have (?:a |an )?(.+?)(?:\.|$)", "hardware", "The developer has {}"),
        (r"i own (?:a |an )?(.+?)(?:\.|$)", "hardware", "The developer owns {}"),
        (r"i prefer (.+?)(?:\.|$)", "preference", "The developer prefers {}"),
        (r"i like (.+?)(?:\.|$)", "preference", "The developer likes {}"),
    ]

    for pattern, category, template in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            fact = match.group(1).strip()

            if fact.lower().startswith(_FILLER_STARTS):
                continue

            fact = _remembered_statement(fact) if template is None else template.format(fact)

            if not fact.endswith("."):
                fact += "."

            return {
                "memory": fact,
                "category": category,
                "confidence": 1.0,
            }

    return None
