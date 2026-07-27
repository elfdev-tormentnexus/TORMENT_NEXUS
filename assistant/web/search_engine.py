"""
Search backend dispatch.

core.config.SEARCH_BACKEND picks which implementation actually runs
("searxng" or "brave") -- both return the same (results, error) shape,
so nothing above this module (main.py, command_handlers.py) needs to
know or care which one is active. Switching backends is a one-line
config change, not a rewiring job.
"""

import html
import re
from urllib.parse import urlparse

from core import config
from web import search_engine_brave
from web import search_engine_searxng


_BACKENDS = {
    "brave": search_engine_brave,
    "searxng": search_engine_searxng,
}

MAX_TITLE_CHARS = 180
MAX_URL_CHARS = 800
MAX_SNIPPET_CHARS = 650
MAX_RESULTS = 8

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_TAG = re.compile(r"<[^>]{1,200}>")


def _clean_text(value, limit):
    text = html.unescape(str(value or ""))
    text = _HTML_TAG.sub(" ", text)
    text = _ANSI_ESCAPE.sub("", text)
    text = _CONTROL.sub(" ", text)
    text = " ".join(text.split())

    if len(text) > limit:
        text = text[:max(1, limit - 1)].rstrip() + "\u2026"

    return text


def _clean_results(results, count):
    """Bound untrusted search data before it reaches the terminal or model."""
    cleaned = []
    seen_urls = set()

    for item in results or []:
        if not isinstance(item, dict):
            continue

        url = _clean_text(item.get("url"), MAX_URL_CHARS)

        try:
            parsed = urlparse(url)
            valid_url = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.netloc)
            )
        except ValueError:
            valid_url = False

        if not valid_url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)
        title = _clean_text(item.get("title"), MAX_TITLE_CHARS)
        snippet = _clean_text(item.get("snippet"), MAX_SNIPPET_CHARS)

        if not title and not snippet:
            continue

        cleaned.append({
            "title": title or parsed.netloc,
            "url": url,
            "snippet": snippet,
        })

        if len(cleaned) >= count:
            break

    return cleaned


def search(query, count=5):
    # Read config.SEARCH_BACKEND live rather than importing the name
    # directly -- a direct "from core.config import SEARCH_BACKEND"
    # would freeze whatever value existed at import time.
    backend = _BACKENDS.get(config.SEARCH_BACKEND)

    if backend is None:
        return None, (
            f"Unknown SEARCH_BACKEND: {config.SEARCH_BACKEND!r}. "
            f"Expected one of: {', '.join(_BACKENDS)}."
        )

    query = " ".join(str(query or "").split())

    if not query:
        return None, "No search query given."

    if len(query) > 300:
        return None, "Search query is too long; keep it under 300 characters."

    try:
        count = max(1, min(MAX_RESULTS, int(count)))
    except (TypeError, ValueError):
        count = 5

    results, error = backend.search(query, count)

    if error:
        return results, error

    return _clean_results(results, count), None
