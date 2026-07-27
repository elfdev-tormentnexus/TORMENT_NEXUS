"""
Spotting "what's the weather like" or "who won the game last night" in
ordinary conversation -- questions that need something the model can't
know from training data or memory: anything current, anything dated,
anything that changes.

Same two-stage shape as editing/edit_intent.py:

1. A cheap regex prefilter. Running a classifier inference on every
   single message would double the cost of normal chat for no reason,
   so most turns never get that far.

2. A classifier call, only on messages that survive the prefilter. It
   decides whether this really needs current information and, if so,
   what to actually search for -- "the latest numpy version" has to
   become a real query, not a restatement of the question.

The prefilter is deliberately loose. A false positive costs one extra
inference and then falls through to normal chat; a false negative
means the answer is missing something it should have had.
"""

import json
import re

import requests

from core.config import DEBUG, MODEL_REQUEST_HEADERS, SERVER_URL


TIMEOUT = 60

_TRIGGER = re.compile(
    r"\b(search|google|look up|latest|current|currently|today|tonight|"
    r"right now|this week|this year|recent|recently|news|price of|cost of|"
    r"weather|forecast|who won|score|release date|is out yet|has released|"
    r"still exist|still around|happened to|what year is it|what's the date)\b",
    re.IGNORECASE,
)


def looks_like_search_request(text):
    """Cheap gate. Needs a plausible trigger phrase to cost an inference."""
    if not text or len(text) < 4:
        return False

    return bool(_TRIGGER.search(text))


SYSTEM = """You decide whether answering a message requires CURRENT
INFORMATION FROM THE INTERNET -- something that changes over time, or
that you cannot know reliably from training alone (prices, scores,
weather, recent events, whether something has shipped yet, current
versions, today's date).

Reply with ONE JSON object and nothing else:

{"needs_search": true/false, "query": "<web search query, or null>"}

It DOES need a search when the answer could plausibly be different
today than it was when you were trained.

It does NOT need a search for: general/stable knowledge, opinions,
coding help, anything about this project's own code, or casual
conversation.

If it needs a search, write "query" as a short, effective web search
query -- not a restatement of the user's sentence."""


def classify(user_message):
    """
    Returns (query, None) if a search is warranted, or (None, reason)
    otherwise -- including when the classifier itself couldn't be
    reached, so callers can fall through to normal chat either way.
    """
    try:
        response = requests.post(
            SERVER_URL + "/v1/chat/completions",
            headers=MODEL_REQUEST_HEADERS,
            json={
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.0,
                "max_tokens": 120,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=TIMEOUT,
        )

        response.raise_for_status()
        result = response.json()

    except Exception as e:
        return None, f"could not reach the model: {e}"

    choices = result.get("choices")

    if not choices:
        return None, "no response from the model"

    raw = (choices[0].get("message", {}).get("content") or "").strip()

    if DEBUG:
        print("\nDEBUG SEARCH INTENT RAW:")
        print(raw)

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:
        return None, "classifier returned no JSON"

    try:
        data = json.loads(raw[start:end + 1])
    except Exception:
        return None, "classifier returned malformed JSON"

    if not data.get("needs_search"):
        return None, "not a search request"

    query = (data.get("query") or "").strip()

    if not query:
        return None, "classifier did not provide a query"

    return query, None
