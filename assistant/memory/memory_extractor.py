"""
LLM-based memory extraction.

Three changes from the old ask_memory_ai():

1. Uses /v1/chat/completions instead of raw /completion, so the chat
   template enforces where the model's turn ends. Same fix as the main
   reply loop.

2. Teaches by example instead of by rule. A 4B follows demonstrations
   far more reliably than a list of prohibitions -- the same lesson the
   persona work produced.

3. Returns a LIST. "I got a 4090 and I'm building a robot arm" is two
   facts; the old version could only ever keep one of them.
"""

import json
import re
import requests

from core import research_c
from core.config import DEBUG, MODEL_PATH, MODEL_REQUEST_HEADERS, SERVER_URL
from memory import extraction_rules as rules


MAX_MEMORIES_PER_TURN = 3
TIMEOUT = 60
_CATEGORIES = {"hardware", "project", "goal", "preference", "personal"}


def _category_label(value):
    value = str(value or "").strip().casefold()
    return value if value in _CATEGORIES else "other"


def _rejection_label(reason):
    """Stable, privacy-safe class for a deterministic memory refusal."""
    lowered = str(reason or "").casefold()
    if lowered == "empty":
        return "empty"
    if lowered == "is a question":
        return "question"
    if lowered == "starts like a question or instruction":
        return "instruction"
    if lowered.startswith("meta-commentary"):
        return "meta_commentary"
    if lowered.startswith("transient state"):
        return "transient_state"
    if lowered == "not about the person":
        return "not_about_person"
    if lowered == "too short":
        return "too_short"
    if lowered == "too long":
        return "too_long"
    return "unknown"


_DURABLE_HINTS = re.compile(
    r"\b("
    r"i (?:own|have|bought|purchased|use|prefer|like|love|hate|live|work|"
    r"am building|am developing|am making|plan|want|need)"
    r"|i['\u2019]m (?:building|developing|making|planning)"
    r"|my (?:project|goal|computer|pc|raspberry pi|hardware|setup|home|"
    r"job|work|pet|cat|dog|name|preference)"
    r"|we (?:are building|are developing|plan|want)"
    r")\b",
    re.IGNORECASE,
)


def looks_like_durable_fact(user_message):
    """
    Cheap gate before spending a full inference on memory extraction.
    Greetings, acknowledgements and ordinary questions cannot contain
    a durable personal fact, so sending every one of them to the model
    only burns time and destroys the foreground prompt cache.
    """
    if not user_message or len(user_message.strip()) < 12:
        return False

    return bool(_DURABLE_HINTS.search(user_message))


SYSTEM = """Extract only durable personal facts that should remain true for
months: owned hardware, ongoing projects, long-term goals, lasting
preferences, or stable personal details. Ignore questions, temporary states,
conversation details, and facts about the assistant.

Return only JSON:
{"memories":[{"memory":"The developer ...","category":"hardware|project|goal|preference|personal","confidence":0.0}]}
Use {"memories":[]} when there is nothing durable."""


# Actual turns, not prose in the system prompt. The model pattern
# matches these far more reliably than it follows the rules above.
SHOTS = [
    {"role": "user", "content": "just picked up a 4090, gonna use it for local inference"},
    {"role": "assistant", "content": '{"memories":[{"memory":"The developer owns an NVIDIA RTX 4090.","category":"hardware","confidence":0.95}]}'},

    {"role": "user", "content": "im building a robot arm and i have a raspberry pi 5 to drive it"},
    {"role": "assistant", "content": '{"memories":[{"memory":"The developer is building a robot arm.","category":"project","confidence":0.95},{"memory":"The developer owns a Raspberry Pi 5.","category":"hardware","confidence":0.9}]}'},

    {"role": "user", "content": "keep it short, i hate when models pad their answers"},
    {"role": "assistant", "content": '{"memories":[{"memory":"The developer prefers short responses without padding.","category":"preference","confidence":0.9}]}'},
]


def _extract_json(raw):
    """Pull the JSON object out of whatever the model wrapped it in."""
    if not raw:
        return None

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return None


def extract_memories(user_message, min_confidence=0.75):
    """
    Durable facts from one user message. Returns [] on any failure --
    a missed memory is never worth taking the chat down.
    """
    if not user_message or not user_message.strip():
        return []

    messages = [{"role": "system", "content": SYSTEM}]
    messages.extend(SHOTS)
    messages.append({"role": "user", "content": user_message})
    payload = {
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 200,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    payload.update(research_c.request_fields())
    timer = research_c.Timer()

    try:
        response = requests.post(
            SERVER_URL + "/v1/chat/completions",
            headers=MODEL_REQUEST_HEADERS,
            json=payload,
            timeout=TIMEOUT,
        )

        response.raise_for_status()
        result = response.json()

    except Exception as e:
        if DEBUG:
            print("Memory extraction failed:", e)
        return []

    choices = result.get("choices")

    if not choices:
        return []

    choice = choices[0]
    raw = (choice.get("message", {}).get("content") or "").strip()

    def record(outcomes, spans=()):
        research_c.record(
            "durable_memory",
            "extraction",
            artifact_digest=research_c.digest(user_message),
            prompt_sha256=research_c.prompt_digest(messages),
            sampler=research_c.sampler_record(payload),
            measurements=research_c.measure(
                choice.get("logprobs"),
                raw,
                spans=spans or None,
            ),
            outcomes=outcomes,
            timing={
                "wall_seconds": timer.elapsed(),
                "server": result.get("timings"),
            },
            binding=research_c.model_binding(MODEL_PATH),
        )

    if DEBUG:
        print("\nDEBUG EXTRACTION RAW:")
        print(raw)

    data = _extract_json(raw)

    if not data:
        record({"parseable": False, "emitted_memory": False, "kept": False})
        if DEBUG:
            print("[No JSON found in extraction]")
        return []

    found = data.get("memories")

    # Tolerate the single-object shape the old prompt produced.
    if isinstance(data.get("memory"), str):
        found = [data]

    if not isinstance(found, list):
        record({"parseable": True, "emitted_memory": False, "kept": False})
        return []

    kept = []

    if not found:
        record({"parseable": True, "emitted_memory": False, "kept": False})

    for item in found[:MAX_MEMORIES_PER_TURN]:
        if not isinstance(item, dict):
            record(
                {
                    "parseable": True,
                    "valid_item": False,
                    "emitted_memory": False,
                    "kept": False,
                }
            )
            continue

        text = item.get("memory")

        if not isinstance(text, str) or not text.strip():
            record(
                {
                    "parseable": True,
                    "valid_item": False,
                    "emitted_memory": False,
                    "kept": False,
                }
            )
            continue

        text = rules.normalize(text)

        reason = rules.reject_reason(text)

        if reason:
            record(
                {
                    "parseable": True,
                    "valid_item": True,
                    "emitted_memory": True,
                    "deterministic_rejection": _rejection_label(reason),
                    "kept": False,
                },
                spans=(text, str(item.get("category", ""))),
            )
            if DEBUG:
                print(f"[Rejected: {reason}] {text}")
            continue

        try:
            confidence = float(item.get("confidence", 0) or 0)
        except Exception:
            confidence = 0.0

        if confidence < min_confidence:
            record(
                {
                    "parseable": True,
                    "valid_item": True,
                    "emitted_memory": True,
                    "self_reported_confidence": confidence,
                    "category": _category_label(item.get("category")),
                    "below_confidence_floor": True,
                    "kept": False,
                },
                spans=(text, str(item.get("category", ""))),
            )
            if DEBUG:
                print(f"[Confidence {confidence:.2f} too low] {text}")
            continue

        record(
            {
                "parseable": True,
                "valid_item": True,
                "emitted_memory": True,
                "self_reported_confidence": confidence,
                "category": _category_label(item.get("category")),
                "deterministic_rejection": None,
                "kept": True,
            },
            spans=(text, str(item.get("category", ""))),
        )
        kept.append({
            "memory": text,
            "category": item.get("category", "other"),
            "confidence": confidence,
        })

    return kept
