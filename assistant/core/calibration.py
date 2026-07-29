"""A fixed reference the instrument can be checked against.

Every machinespirit number published so far is a reading with no scale
beside it. An effective rank of 1.694 is low, but only because other
sentences were run next to it in the same session. Nothing detects a model
swap, a requantisation, or a pooling change quietly moving every figure --
`VECTOR_PIXEL_RESEARCH.md` §6a names the file-level version of that defect
("a file carries no evidence of its own origin"); this is the behavioural
version. Not *which model wrote this*, but *does it still read the same*.

So: a fixed corpus, its readings recorded once under a named model, and a
comparison that says what moved.

Three of the rows are controls, and the middle one is the reason this
module exists rather than being a list of sentences.

    periodic    one phrase repeated. Maximal structure, the ceiling.
    fibonacci   two phrases ordered by the Fibonacci word. Aperiodic,
                deterministic, and of the minimum complexity any
                aperiodic sequence can have.
    random      the same two phrases in a fixed shuffled order. The floor.

The Fibonacci word is the interesting control. The infinite word is
Sturmian: for every length n it contains exactly n + 1 distinct subwords,
the minimum complexity of an aperiodic infinite sequence. It is
deterministic but not periodic, so it sits between "periodic" and "noise"
without being reachable from either. A basis that finds structure in the
periodic row and nothing in the random row still has to say something about
this one; it is neither a polynomial trend nor a finite periodic signal.

The finite release control cannot prove a theorem about the infinite word.
`is_sturmian()` instead checks the expected n + 1 subword signature through
the declared finite range, and the test runs it on a long prefix together
with the periodic and seeded-random controls, which fail it. The 13-term
row that ships is a prefix of that word; a word that short carries the
signature only through n = 6, which is what a 13-letter word can hold. A
control that cannot demonstrate its defining signature is decoration.

The physics is real rather than an analogy: one-dimensional quasicrystals
are modelled as Fibonacci chains, and aperiodic order is a genuine state of
matter. That is the honest version of wanting a non-classical structure --
it comes with mathematics rather than with a metaphor.

Nothing here changes retrieval, and nothing here decides anything. It
measures, records, and compares.
"""
import hashlib
import json
import os
import random

from core.config import ASSISTANT_ROOT

FORMAT = "SABLE_CALIBRATION1"

RECORD_FILE = os.path.join(ASSISTANT_ROOT, "core", "calibration_v1.json")

# Two phrases far enough apart that an ordering between them is visible in
# anchor space at all. Concrete and unrelated, from the anchor decree's own
# register.
PHRASE_A = "water boils at one hundred degrees celsius"
PHRASE_B = "a funeral on a cold morning"

# Long enough to carry structure, short enough to stay inside the 512-token
# embedding window with room to spare.
CONTROL_TERMS = 13

# A reading is a float from a model. Even repeated runs of the same build can
# move the final decimal place; this is loose enough to survive that and tight
# enough to catch a swap, a requantisation, or a pooling change.
TOLERANCE = 0.02


def fibonacci_word(length):
    """The Fibonacci word: a -> ab, b -> a, from a.

    a, ab, aba, abaab, abaababa, ... whose lengths are the Fibonacci
    numbers, which is where the name comes from. The property that matters
    here is not the lengths but the complexity -- see is_sturmian().
    """
    word = "a"
    while len(word) < length:
        word = "".join("ab" if letter == "a" else "a" for letter in word)
    return word[:length]


def subword_count(word, n):
    """How many distinct subwords of length n the word contains."""
    if n <= 0 or n > len(word):
        return 0
    return len({word[i:i + n] for i in range(len(word) - n + 1)})


def is_sturmian(word, upto=12):
    """Check the finite Sturmian complexity signature through ``upto``.

    This verifies p(n) = n + 1 over the tested range. A finite prefix cannot
    prove the infinite word is Sturmian, and a prefix shorter than ``upto``
    cannot even carry the signature -- a word of length L has only L - n + 1
    windows of length n, so p(n) = n + 1 is unreachable once n exceeds about
    L / 2. The test runs this on a long prefix; the 13-term corpus row is a
    prefix of that word and carries the signature through n = 6.
    """
    return all(subword_count(word, n) == n + 1 for n in range(1, upto + 1))


def _from_word(word):
    return " ".join(PHRASE_A if letter == "a" else PHRASE_B for letter in word)


def control_texts():
    """The three controls, deterministic and identical on every install."""
    fib = fibonacci_word(CONTROL_TERMS)

    shuffled = list(fib)
    random.Random(20260729).shuffle(shuffled)

    return {
        "periodic": _from_word("a" * CONTROL_TERMS),
        "fibonacci": _from_word(fib),
        "random": _from_word("".join(shuffled)),
    }


REFERENCE_TEXTS = {
    "one-concrete-fact": "The cat sat on the mat.",
    "one-technical-fact": "Water boils at one hundred degrees celsius.",
    "four-unrelated": (
        "Water boils at one hundred degrees celsius. A funeral on a cold "
        "morning. The stock market fell sharply on Tuesday. Debugging a "
        "program at two in the morning."
    ),
    "project-prose": (
        "The pixels are the payload, in raster order across frames. "
        "Re-encoding this image destroys it."
    ),
}


def corpus():
    """Every row, controls first so a reader meets the scale before the data."""
    rows = dict(control_texts())
    rows.update(REFERENCE_TEXTS)
    return rows


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def measure(rows=None):
    """Read the whole corpus. None when the servers are not both up.

    Returns readings only -- no verdict. Comparing is compare()'s job, and
    keeping them apart means a recorded reading can be re-examined later
    against a tolerance nobody had thought of yet.
    """
    from core import machinespirit

    if not machinespirit.configured():
        return None

    rows = rows or corpus()
    readings = {}

    for name, text in rows.items():
        path = machinespirit.trajectory(text)
        if not path:
            return None

        spread = machinespirit.spread(text, path=path)
        trail = machinespirit.trail(text, path=path)
        if spread is None or trail is None:
            return None

        readings[name] = {
            "text_sha256": digest(text),
            "tokens": spread["tokens"],
            "effective_rank": round(spread["effective_rank"], 6),
            "entropy": round(spread["entropy"], 6),
            "purity": round(spread["purity"], 6),
            "top_anchor": trail[0]["anchor"] if trail else None,
            "top_support": round(trail[0]["support"], 6) if trail else None,
            "anchors_fired": len(trail),
        }

    return readings


def record(readings, path=None):
    """Write the reference, stamped with what produced it.

    A reading without the model that produced it is not a reference, it is
    a number. The model filename (including its quantization label), pooling,
    and anchor digest travel with it, because any of them changing invalidates
    every row. Behavioural drift remains the check; this is not a live-server
    identity attestation.
    """
    from core import machinespirit
    from core.config import EMBED_MODEL_PATH

    target = path or RECORD_FILE
    document = {
        "format": FORMAT,
        "anchor_version": machinespirit.ANCHOR_VERSION,
        "anchor_core_digest": machinespirit.core_digest(),
        "embedding_model": os.path.basename(EMBED_MODEL_PATH or ""),
        "pooling": "mean",
        "phrase_a": PHRASE_A,
        "phrase_b": PHRASE_B,
        "control_terms": CONTROL_TERMS,
        "readings": readings,
    }

    with open(target, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=1, sort_keys=True)
    return target


def load(path=None):
    try:
        with open(path or RECORD_FILE, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        return None
    return document if document.get("format") == FORMAT else None


def compare(recorded, fresh, tolerance=TOLERANCE):
    """What moved. Empty list means the instrument reads as it did.

    Anchor digest mismatch is reported first and on its own: if the
    dictionary changed, every row differing is expected rather than
    informative, and listing them all would bury the one fact that matters.
    """
    problems = []

    # None and {} are different facts. None means the measurement could not
    # be taken; an empty dict means it was taken and found nothing, which
    # should be reported row by row rather than as one vague sentence.
    if recorded is None:
        return ["no reference is recorded for this install"]
    if fresh is None:
        return ["nothing was measured to compare against the reference"]

    old_digest = recorded.get("anchor_core_digest")
    from core import machinespirit
    if old_digest and old_digest != machinespirit.core_digest():
        return ["the anchor dictionary changed, so every reading below it "
                "is expected to differ. Re-record rather than compare."]

    previous = recorded.get("readings") or {}

    for name, was in sorted(previous.items()):
        now = fresh.get(name)
        if now is None:
            problems.append(f"{name}: missing from this measurement")
            continue
        if now["text_sha256"] != was["text_sha256"]:
            problems.append(f"{name}: the reference text itself changed")
            continue
        for field in ("tokens", "anchors_fired", "top_anchor"):
            if now[field] != was[field]:
                problems.append(
                    f"{name}: {field} {was[field]!r} -> {now[field]!r}")
        for field in (
            "effective_rank", "entropy", "purity", "top_support",
        ):
            if now[field] is None or was[field] is None:
                if now[field] != was[field]:
                    problems.append(
                        f"{name}: {field} {was[field]!r} -> {now[field]!r}")
                continue
            drift = abs(now[field] - was[field])
            if drift > tolerance:
                problems.append(
                    f"{name}: {field} {was[field]:.4f} -> {now[field]:.4f} "
                    f"(moved {drift:.4f}, tolerance {tolerance})")

    return problems
