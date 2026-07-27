"""
SearXNG client -- a local, self-hosted meta-search instance (see
searxng/docker-compose.yml at the project root). No API key, no
per-query cost, but it's a service you run and keep up yourself.

Requires "json" enabled under search.formats in searxng/config/settings.yml
-- SearXNG only serves HTML by default.
"""

import requests

from core.config import SEARXNG_URL


TIMEOUT = 15
DEFAULT_COUNT = 5


def search(query, count=DEFAULT_COUNT):
    """
    Returns (results, error). results is a list of
    {"title", "url", "snippet"} dicts (possibly empty -- a genuine "no
    results" is not an error). Exactly one of the two is meaningful:
    error is None on success.
    """
    if not query or not query.strip():
        return None, "No search query given."

    try:
        response = requests.get(
            SEARXNG_URL + "/search",
            params={"q": query.strip(), "format": "json"},
            timeout=TIMEOUT,
        )
    except Exception as e:
        return None, (
            f"Could not reach SearXNG at {SEARXNG_URL}: {e}\n"
            "Is the container running? (cd searxng && docker compose up -d)"
        )

    if response.status_code != 200:
        return None, f"SearXNG returned HTTP {response.status_code}."

    try:
        data = response.json()
    except Exception:
        return None, (
            "SearXNG returned an unreadable response. Check that 'json' is "
            "listed under search.formats in searxng/config/settings.yml."
        )

    if not isinstance(data, dict):
        return None, "SearXNG returned an unexpected JSON response."

    raw_results = data.get("results") or []

    results = [
        {
            "title": (item.get("title") or "").strip(),
            "url": (item.get("url") or "").strip(),
            "snippet": (item.get("content") or "").strip(),
        }
        for item in raw_results[:count]
        if isinstance(item, dict)
    ]

    return results, None
