"""
Brave Search API client.

One job: turn a query into a short list of results, or a clear error.
Whether to search at all and what query to use live in
search_intent.py instead -- this module doesn't decide anything.
"""

import requests

from core.config import BRAVE_API_KEY, BRAVE_SEARCH_URL


TIMEOUT = 15
DEFAULT_COUNT = 5


def search(query, count=DEFAULT_COUNT):
    """
    Returns (results, error). results is a list of
    {"title", "url", "snippet"} dicts (possibly empty -- a genuine "no
    results" is not an error). Exactly one of the two is meaningful:
    error is None on success.
    """
    if not BRAVE_API_KEY:
        return None, "No Brave API key configured (core/config.py: BRAVE_API_KEY)."

    if not query or not query.strip():
        return None, "No search query given."

    try:
        response = requests.get(
            BRAVE_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            params={"q": query.strip(), "count": count},
            timeout=TIMEOUT,
        )
    except Exception as e:
        return None, f"Could not reach Brave Search: {e}"

    if response.status_code == 401:
        return None, "Brave Search rejected the API key (401). Check BRAVE_API_KEY."

    if response.status_code == 429:
        return None, "Brave Search rate limit hit (429). Try again shortly."

    if response.status_code != 200:
        return None, f"Brave Search returned HTTP {response.status_code}."

    try:
        data = response.json()
    except Exception:
        return None, "Brave Search returned an unreadable response."

    if not isinstance(data, dict):
        return None, "Brave Search returned an unexpected JSON response."

    web_data = data.get("web")
    raw_results = (
        web_data.get("results") or []
        if isinstance(web_data, dict)
        else []
    )

    results = [
        {
            "title": (item.get("title") or "").strip(),
            "url": (item.get("url") or "").strip(),
            "snippet": (item.get("description") or "").strip(),
        }
        for item in raw_results[:count]
        if isinstance(item, dict)
    ]

    return results, None
