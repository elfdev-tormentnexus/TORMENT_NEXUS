"""
Validation for extracted memories.

The old validator checked a list of banned phrases with `in`, so they
matched inside unrelated words:

    "where"    fired on  "Nowhere, Ontario"
    "can i"    fired on  "Duncan Industries"
    "when"     fired on  "whenever"
    "guide"    fired on  "guide dog"
    "setup"    fired on  "setup includes three monitors"

Seven of nine legitimate memories were rejected in testing. Worse,
"wants to" was banned while the extraction prompt explicitly asks for
long term goals -- which are almost always phrased "wants to". The
validator was fighting the prompt.

The split now is:

    structural junk  -> rejected here
    semantic junk    -> handled by the extraction prompt's examples

A regex banlist cannot tell a goal from a question. Anchoring and
word boundaries can, and that is all this does.
"""

import re


# A memory is a statement ABOUT the person. If it does not mention
# them, it is a technology fact that wandered in -- "Raspberry Pi
# cameras can detect objects" and the like.
SUBJECT = "developer"

# Questions and instructions, rejected only at the START. "Nowhere"
# contains "where"; a memory beginning "Where" is a question.
QUESTION_STARTS = (
    "how ", "what ", "why ", "where ", "when ", "who ", "which ",
    "can ", "could ", "should ", "would ", "will ", "is ", "are ",
    "do ", "does ", "did ", "explain", "tell me", "help me",
    "show me", "give me", "let me", "please ",
)

# Meta-commentary about the conversation rather than the person.
# Word-bounded so they cannot fire inside longer words.
META = [
    r"\bthe user\b",
    r"\bthe assistant\b",
    r"\buser asked\b",
    r"\bi want to know\b",
    r"\bas an ai\b",
    r"\bi should remember\b",
    r"\bi need to remember\b",
]

# Momentary state, not a durable fact. Deliberately short: over-banning
# is what broke the previous version.
#
# The mood/activity entries below are narrow on purpose -- "feels
# lonely" and "taking a break" are moment-to-moment, but a bare
# "currently" or "feels" would also catch durable facts like "is
# currently building an AI assistant project", which is exactly the
# kind of thing worth keeping.
TRANSIENT = [
    r"\btrying to\b",
    r"\bright now\b",
    r"\bat the moment\b",
    r"\bjust asked\b",
    r"\bcurrently focused on\b",
    r"\btaking a\b.{0,20}\b(break|nap|rest)\b",
    r"\bfeels? (lonely|tired|happy|sad|stressed|anxious|excited|bored|"
    r"frustrated|overwhelmed|down|great|okay|fine|upset|angry|annoyed)\b",
]

MIN_LENGTH = 15
MAX_LENGTH = 250


_META_RE = [re.compile(p, re.IGNORECASE) for p in META]
_TRANSIENT_RE = [re.compile(p, re.IGNORECASE) for p in TRANSIENT]


def reject_reason(fact):
    """
    Why this memory should not be stored, or None if it is fine.
    Returning the reason rather than a bare False makes DEBUG output
    actually diagnostic.
    """
    if not fact or not fact.strip():
        return "empty"

    fact = fact.strip()
    lower = fact.lower()

    if "?" in fact:
        return "is a question"

    if lower.startswith(QUESTION_STARTS):
        return "starts like a question or instruction"

    for rx in _META_RE:
        if rx.search(fact):
            return f"meta-commentary ({rx.pattern})"

    for rx in _TRANSIENT_RE:
        if rx.search(fact):
            return f"transient state ({rx.pattern})"

    if SUBJECT not in lower:
        return "not about the person"

    if len(fact) < MIN_LENGTH:
        return "too short"

    if len(fact) > MAX_LENGTH:
        return "too long"

    return None


def validate_memory(fact):
    return reject_reason(fact) is None


def normalize(fact):
    """Fold first and second person into the stored third person."""
    if not fact:
        return fact

    out = fact.strip()

    for a, b in (
        ("The user", "The developer"),
        ("the user", "the developer"),
        ("The User", "The developer"),
        ("You are", "The developer is"),
        ("you are", "the developer is"),
        ("Your ", "The developer's "),
    ):
        out = out.replace(a, b)

    if out and not out.endswith((".", "!", "\u2026")):
        out += "."

    return out
