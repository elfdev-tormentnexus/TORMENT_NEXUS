"""consume: work out what a URL actually points at, and take that.

The distinction the operator asked for is the whole feature. Fetching a
YouTube watch page gets you the page: navigation, player scaffolding,
recommendation rails. None of that is the thing anyone meant. So this
identifies the content behind an address and refuses to pass off the
wrapper as the contents.

Three outcomes, and only the first stores anything:

    document   a real file the offline library can already read. Fetched,
               saved with the extension its content-type declares, and
               handed to library.add(), which extracts, chunks and indexes
               it exactly as a local import.
    media      audio or video. This tree is stdlib-only and has no
               yt-dlp, no ffmpeg and no speech-to-text, so there is no
               honest path from a video to text here. Named, with the
               missing pieces named too.
    page       an ordinary web page. Its readable text is offered, but it
               is labelled a page rather than a document, because someone
               who consumed a video link and got a navigation menu should
               be told that is what happened.

Everything fetched is untrusted. A consumed document reaches the model the
same way search results do -- as evidence, never as instructions -- and the
caller is responsible for keeping that framing. A page that says "ignore
your previous instructions" is a page that says that; it is data about the
page and nothing more.
"""
import os
import re
import socket
import tempfile
from urllib.parse import urlparse, urlsplit

import requests

# The library's own ceiling. A consumed file that could not be imported
# afterwards would be a download with nowhere to go.
from knowledge.library import MAX_SOURCE_BYTES, SUPPORTED_EXTENSIONS

USER_AGENT = "TORMENT_NEXUS/consume (local, single-file fetch)"
TIMEOUT = 30
MAX_REDIRECTS = 5

# What a content-type means on disk. The library dispatches on extension,
# so the served type has to become one.
BY_CONTENT_TYPE = {
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "text/csv": ".csv",
    "application/json": ".json",
    "application/pdf": ".pdf",
    "application/epub+zip": ".epub",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        ".docx",
}

# Hosts whose watch pages are scaffolding around a stream. Fetching these
# succeeds and returns something useless, which is worse than failing.
MEDIA_HOSTS = (
    "youtube.com", "youtu.be", "vimeo.com", "soundcloud.com",
    "twitch.tv", "dailymotion.com", "bandcamp.com", "spotify.com",
    "tiktok.com", "music.youtube.com",
)

MEDIA_TOOLS = ("yt-dlp (fetch the stream)",
               "ffmpeg (decode it to audio)",
               "a local speech-to-text model (turn audio into text)")


class ConsumeError(Exception):
    """Refuse rather than store something that is not what was asked for."""


def _host_of(url):
    try:
        return (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def is_media_host(url):
    host = _host_of(url)
    return any(host == h or host.endswith("." + h) for h in MEDIA_HOSTS)


def _is_private_address(host):
    """True for anything that resolves only inside this machine or network.

    Consuming a URL is a fetch driven by text, and text can arrive from a
    page this assistant already read. Letting that reach a link-local
    metadata endpoint or a router's admin panel is the ordinary shape of
    server-side request forgery, so the resolved address is checked rather
    than the name.
    """
    import ipaddress

    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return True                      # unresolvable: refuse, do not guess

    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if (address.is_private or address.is_loopback or address.is_reserved
                or address.is_link_local or address.is_multicast
                or address.is_unspecified):
            return True
    return False


def _extension_for(content_type, url):
    base = (content_type or "").split(";")[0].strip().lower()
    if base in BY_CONTENT_TYPE:
        return BY_CONTENT_TYPE[base]
    # Fall back to the address, which is often more honest than the header.
    guess = os.path.splitext(urlsplit(url).path)[1].lower()
    return guess if guess in SUPPORTED_EXTENSIONS else ""


def _safe_name(url, extension):
    stem = os.path.basename(urlsplit(url).path) or _host_of(url) or "consumed"
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)[:80]
    stem = os.path.splitext(stem)[0] or "consumed"
    return stem + extension


def identify(url, session=None):
    """What is behind this address, without downloading the body.

    Returns a dict describing the outcome. Never raises for an ordinary
    unreachable host: an address that does not answer is a fact about the
    address.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ConsumeError(
            f"Only http and https are consumed, not {parsed.scheme or 'that'}. "
            "A local file is imported with 'library add'.")
    if not parsed.hostname:
        raise ConsumeError("That URL has no host.")
    if _is_private_address(parsed.hostname):
        raise ConsumeError(
            f"{parsed.hostname} resolves to a private, loopback or otherwise "
            "internal address. Consuming it would let a link decide what this "
            "machine reaches on its own network.")

    if is_media_host(url):
        return {
            "url": url, "kind": "media", "content_type": None,
            "extension": "", "length": None,
            "reason": (
                "That is a media page. Its HTML is player scaffolding, not "
                "the recording, and storing it would file a navigation menu "
                "as a document. Turning it into text needs three pieces this "
                "build does not have: " + "; ".join(MEDIA_TOOLS) + "."),
        }

    owner = session or requests.Session()
    try:
        response = owner.head(url, allow_redirects=True, timeout=TIMEOUT,
                              headers={"User-Agent": USER_AGENT})
        if response.status_code >= 400 or not response.headers.get("Content-Type"):
            # Plenty of servers answer HEAD badly; ask for one byte instead.
            response = owner.get(url, stream=True, timeout=TIMEOUT,
                                 headers={"User-Agent": USER_AGENT,
                                          "Range": "bytes=0-0"})
        content_type = response.headers.get("Content-Type", "")
        length = response.headers.get("Content-Length")
        final = response.url
    except requests.RequestException as error:
        raise ConsumeError(f"Could not reach that address: {error}")
    finally:
        if session is None:
            owner.close()

    base = content_type.split(";")[0].strip().lower()
    if base.startswith(("video/", "audio/")):
        return {
            "url": url, "final_url": final, "kind": "media",
            "content_type": content_type, "extension": "",
            "length": int(length) if length and length.isdigit() else None,
            "reason": ("That is a media stream. Reading it as text needs: "
                       + "; ".join(MEDIA_TOOLS) + "."),
        }

    extension = _extension_for(content_type, final)
    kind = "document" if extension else "page"
    if extension in {".html", ".htm"}:
        kind = "page"

    return {
        "url": url, "final_url": final, "kind": kind,
        "content_type": content_type, "extension": extension,
        "length": int(length) if length and length.isdigit() else None,
        "reason": None if extension else (
            f"Nothing here reads {base or 'that content type'}. Supported: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS))),
    }


def fetch(url, extension, folder=None, limit=MAX_SOURCE_BYTES, session=None):
    """Download to a file, refusing to exceed the library's own ceiling.

    Streamed and counted while it arrives, because a Content-Length header
    is a claim by the server and the limit has to hold whether or not the
    claim was true.
    """
    folder = folder or tempfile.mkdtemp(prefix="consume_")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, _safe_name(url, extension))

    owner = session or requests.Session()
    written = 0
    try:
        with owner.get(url, stream=True, timeout=TIMEOUT,
                       headers={"User-Agent": USER_AGENT}) as response:
            response.raise_for_status()
            with open(target, "wb") as handle:
                for block in response.iter_content(chunk_size=64 * 1024):
                    if not block:
                        continue
                    written += len(block)
                    if written > limit:
                        handle.close()
                        os.remove(target)
                        raise ConsumeError(
                            f"That resource passed the {limit // (1024 ** 2)} "
                            "MiB import ceiling while downloading; nothing "
                            "was kept.")
                    handle.write(block)
    except requests.RequestException as error:
        if os.path.exists(target):
            os.remove(target)
        raise ConsumeError(f"Download failed: {error}")
    finally:
        if session is None:
            owner.close()

    return target, written


def consume(url, add=None, session=None):
    """Identify, fetch and hand to the library. Returns a report dict.

    `add` is injected so this is testable without a live index; it defaults
    to the real library import, which is the only path that stores anything.
    """
    report = identify(url, session=session)
    if report["kind"] == "media" or not report.get("extension"):
        report["stored"] = None
        return report

    target, written = fetch(url, report["extension"], session=session)
    report["bytes"] = written
    report["downloaded_to"] = target

    if add is None:
        from knowledge import library
        add = library.add

    try:
        copied = add(target)
    except Exception as error:
        report["stored"] = None
        report["reason"] = f"Fetched, but the library refused it: {error}"
        return report

    report["stored"] = copied
    return report
