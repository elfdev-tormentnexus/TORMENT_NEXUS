"""
Hand one hard question to a frontier model, on the operator's keys.

TORMENT_NEXUS is offline-first; that is its identity, not a limitation to
be engineered away. This module is the one deliberate, visible exception:
when the operator explicitly asks, the exact text they typed -- and nothing
else -- is sent to a cloud model, and the answer is shown attributed to
that model rather than to the local director.

The consent design mirrors the agent interface's:

- OFF unless the operator sets TORMENT_NEXUS_ESCALATION=1. A key on disk
  is necessary but never sufficient; going online is a decision, not a
  side effect of a file existing.
- The key lives in a 0600 file that .gitignore and DENY_PATTERNS both
  exclude, exactly like the model API key and the agent token.
- What is sent is the escalate command's argument only. No conversation
  history, no memories, no persona, no system context. The privacy
  boundary is describable in one sentence: "it sends what you typed after
  the word 'escalate'."
- Every call is logged (provider, model, sizes -- never content), the way
  autonomous edits and agent calls are logged: an action nobody can audit
  afterwards is the kind this project does not take.

Two providers, because the two agents that work on this tree live behind
them: "claude" speaks the Anthropic Messages API, "openai" speaks any
OpenAI-compatible /v1/chat/completions endpoint. Raw requests rather than
vendor SDKs on purpose -- requests is already a dependency of everything
here, and the release packager ships a curated environment where every new
package is a decision.
"""

import json
import os
import re
import time
from urllib.parse import urlparse

import requests


ASSISTANT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALL_LOG = os.path.join(ASSISTANT_ROOT, "logs", "escalation.jsonl")

ANTHROPIC_KEY_FILE = os.path.join(ASSISTANT_ROOT, ".anthropic_api_key")
OPENAI_KEY_FILE = os.path.join(ASSISTANT_ROOT, ".openai_api_key")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Server-side fallback: if the model's safety classifiers decline a benign
# question (it happens to security-adjacent work), Anthropic re-runs it on
# the recommended fallback model inside the same call instead of returning
# an empty refusal.
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"

DEFAULT_CLAUDE_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"
DEFAULT_OPENAI_URL = "https://api.openai.com/v1/responses"

MAX_ANSWER_TOKENS = 1024
REQUEST_TIMEOUT = 120

PROVIDERS = ("claude", "openai")
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-_])"
)


def is_enabled():
    """The operator switches this on; a key alone never does."""
    return os.environ.get("TORMENT_NEXUS_ESCALATION", "").strip() == "1"


def default_provider():
    configured = os.environ.get(
        "TORMENT_NEXUS_ESCALATION_PROVIDER", ""
    ).strip().lower()

    return configured if configured in PROVIDERS else "claude"


def _read_key_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _openai_url():
    return (
        os.environ.get("TORMENT_NEXUS_ESCALATION_OPENAI_URL", "").strip()
        or DEFAULT_OPENAI_URL
    )


def _official_openai_url(url):
    try:
        return (urlparse(url).hostname or "").lower() == "api.openai.com"
    except ValueError:
        return False


def _validate_openai_url(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False, "The OpenAI endpoint URL is malformed."

    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        return False, "The OpenAI endpoint must be a normal HTTP(S) URL."
    if parsed.scheme != "https" and host not in _LOOPBACK_HOSTS:
        return False, (
            "A non-local OpenAI-compatible endpoint must use HTTPS so the "
            "question and billing key are not sent in clear text."
        )
    return True, ""


def _key_for(provider):
    if provider == "claude":
        return (
            os.environ.get("TORMENT_NEXUS_ANTHROPIC_KEY", "").strip()
            or os.environ.get("ANTHROPIC_API_KEY", "").strip()
            or _read_key_file(ANTHROPIC_KEY_FILE)
        )

    explicit = (
        os.environ.get("TORMENT_NEXUS_OPENAI_KEY", "").strip()
        or _read_key_file(OPENAI_KEY_FILE)
    )
    if explicit:
        return explicit

    # OPENAI_API_KEY is a broad ambient credential. It may be used with
    # OpenAI itself, but never silently forwarded to a custom host. Custom
    # providers require the TORMENT_NEXUS-specific key or protected key file.
    if _official_openai_url(_openai_url()):
        return os.environ.get("OPENAI_API_KEY", "").strip()
    return ""


def availability(provider=None):
    """
    (ready, reason). reason explains a False in operator language.

    Split from escalate() so the command can refuse before printing any
    "going online" banner: announcing a connection and then failing to
    make one would be the worst of both.
    """
    provider = provider or default_provider()

    if provider not in PROVIDERS:
        return False, f"Unknown provider '{provider}'. Use: {', '.join(PROVIDERS)}."

    if not is_enabled():
        return False, (
            "Escalation is off. It goes online, so it starts by decision: "
            "set TORMENT_NEXUS_ESCALATION=1 and restart."
        )

    if provider == "openai":
        valid, reason = _validate_openai_url(_openai_url())
        if not valid:
            return False, reason

    if not _key_for(provider):
        key_file = (
            ANTHROPIC_KEY_FILE if provider == "claude" else OPENAI_KEY_FILE
        )
        return False, (
            f"No {provider} API key. Put one in "
            f"{os.path.basename(key_file)} beside main.py, or set the "
            "environment variable."
        )

    return True, ""


def _log_call(record):
    """Provider, model, sizes and outcome. Never the text either way."""
    try:
        os.makedirs(os.path.dirname(CALL_LOG), exist_ok=True)

        with open(CALL_LOG, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        pass


def _ask_claude(question, key):
    model = (
        os.environ.get("TORMENT_NEXUS_ESCALATION_CLAUDE_MODEL", "").strip()
        or DEFAULT_CLAUDE_MODEL
    )

    response = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "anthropic-beta": ANTHROPIC_FALLBACK_BETA,
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": MAX_ANSWER_TOKENS,
            "fallbacks": "default",
            "messages": [{"role": "user", "content": question}],
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()

    # A refusal arrives as HTTP 200 with empty or partial content; reading
    # content[0] unconditionally is the documented way to crash on one.
    if body.get("stop_reason") == "refusal":
        details = body.get("stop_details") or {}
        why = details.get("explanation") or "no explanation given"
        return body.get("model", model), f"[declined by the provider: {why}]"

    parts = [
        block.get("text", "")
        for block in body.get("content", [])
        if block.get("type") == "text"
    ]

    return body.get("model", model), "\n".join(parts).strip()


def _response_text(body):
    if isinstance(body.get("output_text"), str):
        return body["output_text"].strip()

    pieces = []
    for item in body.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"}:
                pieces.append(content.get("text", ""))
    return "\n".join(piece for piece in pieces if piece).strip()


def _ask_openai(question, key):
    model = (
        os.environ.get("TORMENT_NEXUS_ESCALATION_OPENAI_MODEL", "").strip()
        or DEFAULT_OPENAI_MODEL
    )
    url = _openai_url()
    valid, reason = _validate_openai_url(url)
    if not valid:
        raise EscalationError(reason)

    configured_api = os.environ.get(
        "TORMENT_NEXUS_ESCALATION_OPENAI_API", ""
    ).strip().lower()
    use_responses = (
        configured_api == "responses"
        or (
            configured_api != "chat"
            and urlparse(url).path.rstrip("/").endswith("/responses")
        )
    )

    if use_responses:
        payload = {
            "model": model,
            "input": question,
            "max_output_tokens": MAX_ANSWER_TOKENS,
            # The bridge is one-shot by design. Do not create provider-side
            # conversation state for an offline-first application.
            "store": False,
        }
    else:
        payload = {
            "model": model,
            "max_completion_tokens": MAX_ANSWER_TOKENS,
            "messages": [{"role": "user", "content": question}],
        }

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "content-type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()

    if use_responses:
        answer = _response_text(body)
    else:
        answer = body["choices"][0]["message"]["content"] or ""

    return body.get("model", model), answer.strip()


def sanitize_external_text(text):
    """Remove terminal control sequences while preserving readable spacing."""
    text = _ANSI.sub("", str(text or ""))
    return "".join(
        character
        for character in text
        if character in "\n\t" or ord(character) >= 32
    ).strip()


def escalate(question, provider=None):
    """
    Send `question` -- exactly and only `question` -- to the provider.

    Returns (provider, model, answer). Raises EscalationError with an
    operator-readable message on any failure; callers show it rather than
    a traceback, because a network error during an optional feature is
    conversation, not crash.
    """
    provider = provider or default_provider()
    ready, reason = availability(provider)

    if not ready:
        raise EscalationError(reason)

    key = _key_for(provider)
    started = time.time()
    outcome = "ok"
    model = ""
    answer = ""

    try:
        if provider == "claude":
            model, answer = _ask_claude(question, key)
        else:
            model, answer = _ask_openai(question, key)

        answer = sanitize_external_text(answer)

        if not answer:
            outcome = "empty"
            raise EscalationError(
                f"The {provider} endpoint answered with nothing usable."
            )

        return provider, model, answer
    except EscalationError:
        raise
    except requests.exceptions.HTTPError as error:
        outcome = f"http-{error.response.status_code if error.response is not None else '?'}"
        raise EscalationError(
            f"The {provider} endpoint refused the request ({outcome}). "
            "Check the key and model name."
        ) from error
    except requests.exceptions.RequestException as error:
        outcome = "network"
        raise EscalationError(
            f"Could not reach the {provider} endpoint: {error}"
        ) from error
    finally:
        _log_call({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "provider": provider,
            "model": model,
            "question_chars": len(question),
            "answer_chars": len(answer),
            "seconds": round(time.time() - started, 2),
            "outcome": outcome,
        })


class EscalationError(Exception):
    """A failure the operator should read, not a bug to trace."""
