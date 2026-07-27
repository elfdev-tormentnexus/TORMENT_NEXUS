"""Small, rate-limited public music-metadata lookup for the Spotify picker.

The lookup deliberately uses MusicBrainz only for title, artist, release, and
duration metadata. It never reads Spotify profile files, needs no account or
API key, and never downloads or handles audio. A chosen result is handed back
to the installed Spotify client as an ordinary in-app search.
"""

import threading
import time

import requests


SEARCH_URL = "https://musicbrainz.org/ws/2/recording/"
USER_AGENT = (
    "TORMENT_NEXUS/0.1 "
    "(https://github.com/elfdev-tormentnexus/TORMENT_NEXUS)"
)
TIMEOUT_SECONDS = 12
REQUEST_INTERVAL_SECONDS = 1.05
CACHE_SECONDS = 300


class MusicMetadataError(RuntimeError):
    pass


_rate_lock = threading.Lock()
_last_request_at = 0.0
_cache_lock = threading.Lock()
_cache = {}


def _artist_credit_text(credit):
    pieces = []

    for part in credit or []:
        if not isinstance(part, dict):
            continue
        artist = part.get("name") or (part.get("artist") or {}).get("name")
        if artist:
            pieces.append(str(artist))
        if part.get("joinphrase"):
            pieces.append(str(part["joinphrase"]))

    return "".join(pieces).strip() or "unknown artist"


def _recording_summary(recording):
    releases = recording.get("releases") or []
    release = next((item for item in releases if isinstance(item, dict)), {})
    length = recording.get("length") or 0

    try:
        length = max(0, int(length))
    except (TypeError, ValueError):
        length = 0

    return {
        "title": str(recording.get("title") or "unknown track"),
        "artist": _artist_credit_text(recording.get("artist-credit")),
        "release": str(release.get("title") or ""),
        "year": str(release.get("date") or "")[:4],
        "length_ms": length,
    }


def _wait_for_request_slot():
    global _last_request_at

    with _rate_lock:
        delay = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
        if delay > 0:
            time.sleep(delay)
        _last_request_at = time.monotonic()


def search_recordings(query, limit=5):
    """Return up to five MusicBrainz recording summaries for a plain query."""
    query = " ".join((query or "").split())
    if not query:
        raise MusicMetadataError("Give the music search something to look for.")

    try:
        limit = min(max(int(limit), 1), 5)
    except (TypeError, ValueError):
        limit = 5

    cache_key = (query.casefold(), limit)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < CACHE_SECONDS:
            return list(cached[1])

    _wait_for_request_slot()
    try:
        response = requests.get(
            SEARCH_URL,
            params={"query": query, "fmt": "json", "limit": limit, "dismax": "true"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as error:
        raise MusicMetadataError(f"Music metadata search failed: {error}")
    except ValueError as error:
        raise MusicMetadataError(f"Music metadata returned invalid data: {error}")

    results = [
        _recording_summary(recording)
        for recording in (payload.get("recordings") or [])
        if isinstance(recording, dict) and recording.get("title")
    ][:limit]

    with _cache_lock:
        _cache[cache_key] = (time.monotonic(), results)

    return list(results)
