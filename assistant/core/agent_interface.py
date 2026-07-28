"""
A localhost, read-only window into a running TORMENT_NEXUS.

Codex and Claude interact with this project by reading and writing files.
They cannot ask it anything, query state during a run, or have it report
back -- which is why a whole QC session was spent inferring behaviour from
source rather than asking it. This is the smallest thing that closes that
gap, and it is deliberately the least capable version that does.

WHAT IT IS NOT
--------------
There is no endpoint here that changes anything. No edit, no goal, no
config, no restart, no shutdown. Every handler is a GET that reads. The
plan this comes from says anything that writes goes through dev_auth --
that remains true and unbuilt, because a write surface deserves its own
review rather than arriving attached to a diagnostic one.

WHY IT IS OFF BY DEFAULT
------------------------
It is an authentication boundary and a listening socket. Both belong to
the operator to switch on, not to a release note. Set
TORMENT_NEXUS_AGENT_API=1 to enable it.

WHY IT AUTHENTICATES EVEN THOUGH IT IS READ-ONLY
------------------------------------------------
This project already decided localhost is not a trust boundary. The model
API key exists because llama-server's permissive CORS would otherwise let
any web page open on this computer submit requests to the local model
(core/config.py). The same reasoning applies here and more sharply: one of
these endpoints searches the operator's memories, which are the files
.gitignore and DENY_PATTERNS both work hardest to keep private. A token is
required on every request, including the ones that only read.

The Host header is checked as well. A token stops a page that has not seen
the token file; the Host check stops a DNS-rebinding attempt from being
treated as local in the first place.

The module imports no project state on purpose. It serves what the caller
hands it, so the surface exposed is decided at the call site in main.py
and is visible in one place.
"""

import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


ASSISTANT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ASSISTANT_ROOT, ".agent_token")
CALL_LOG = os.path.join(ASSISTANT_ROOT, "logs", "agent_api.jsonl")

HOST = "127.0.0.1"
DEFAULT_PORT = 8099

# Long enough that guessing is not a strategy, short enough to paste.
TOKEN_BYTES = 32

# A query string is a search term, not a document.
MAX_QUERY_LENGTH = 400

_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


def is_enabled():
    """The operator switches this on; nothing else does."""
    return os.environ.get("TORMENT_NEXUS_AGENT_API", "").strip() == "1"


def configured_port():
    raw = os.environ.get("TORMENT_NEXUS_AGENT_PORT", "").strip()

    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_PORT

    return port if 1024 <= port <= 65535 else DEFAULT_PORT


def load_or_create_token():
    """
    The per-installation bearer token, created 0600 on first use.

    Written to a file rather than printed because the terminal is where
    the operator reads their conversation, and a credential scrolling past
    in it is a credential in a screenshot.
    """
    configured = os.environ.get("TORMENT_NEXUS_AGENT_TOKEN", "").strip()

    if configured:
        return configured

    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
            stored = handle.read().strip()

        if stored:
            return stored
    except FileNotFoundError:
        pass
    except OSError:
        # A read-only installation can still serve; it just gets a token
        # that does not survive a restart.
        return secrets.token_urlsafe(TOKEN_BYTES)

    generated = secrets.token_urlsafe(TOKEN_BYTES)

    try:
        descriptor = os.open(
            TOKEN_FILE,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(generated)
    except FileExistsError:
        with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
            generated = handle.read().strip() or generated
    except OSError:
        pass

    return generated


def _log_call(record):
    """
    Every call, the way autonomous edits are logged.

    An interface that can be queried without leaving a trace is one nobody
    can audit afterwards, which is the property that made autonomous edits
    acceptable in the first place.
    """
    try:
        os.makedirs(os.path.dirname(CALL_LOG), exist_ok=True)

        with open(CALL_LOG, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        pass


class _Handler(BaseHTTPRequestHandler):
    server_version = "TORMENT_NEXUS-agent"
    sys_version = ""

    # Injected by start().
    token = ""
    providers = {}

    def log_message(self, *_args):
        """Silence the default stderr logging; it would corrupt the TUI."""

    # --------------------------------------------------------
    # The only verb
    # --------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        outcome = "ok"

        if not self._host_is_local():
            outcome = "rejected-host"
            self._send(403, {"error": "non-local Host header"})
        elif not self._authorised():
            outcome = "rejected-token"
            self._send(401, {"error": "bearer token required"})
        elif route not in self.providers:
            outcome = "not-found"
            self._send(404, {
                "error": "no such route",
                "routes": sorted(self.providers),
            })
        else:
            query = parse_qs(parsed.query)
            try:
                self._send(200, self.providers[route](
                    {
                        key: values[0][:MAX_QUERY_LENGTH]
                        for key, values in query.items()
                        if values
                    }
                ))
            except Exception as error:
                outcome = "error"
                self._send(500, {"error": f"{type(error).__name__}: {error}"})

        _log_call({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "route": route,
            "outcome": outcome,
            "peer": self.client_address[0] if self.client_address else "",
        })

    def _host_is_local(self):
        host = (self.headers.get("Host") or "").strip()
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host

        return name.strip("[]") in {h.strip("[]") for h in _ALLOWED_HOSTS}

    def _authorised(self):
        header = (self.headers.get("Authorization") or "").strip()
        prefix = "Bearer "

        if not header.startswith(prefix):
            return False

        # Constant time: a comparison that returns early tells an attacker
        # how much of the token they guessed correctly.
        return secrets.compare_digest(header[len(prefix):], self.token)

    def _send(self, status, payload):
        body = json.dumps(payload, default=str).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # Nothing here should be reachable from a page's fetch().
        self.send_header("Access-Control-Allow-Origin", "null")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


class AgentInterface:
    """A running read-only server. Stop it by calling stop()."""

    def __init__(self, server, token, port):
        self._server = server
        self.token = token
        self.port = port

    def stop(self):
        self._server.shutdown()
        self._server.server_close()


def start(providers, port=None, token=None):
    """
    Serve `providers` on loopback. Returns an AgentInterface, or None.

    `providers` maps a route to a callable taking the parsed query mapping
    and returning something JSON-serialisable. The caller decides what is
    exposed; this module never goes looking.
    """
    token = token or load_or_create_token()
    # `is not None`, not `or`: port 0 is a real request for an ephemeral
    # port, and treating it as unset would silently bind the default.
    port = port if port is not None else configured_port()

    handler = type("_BoundHandler", (_Handler,), {
        "token": token,
        "providers": dict(providers),
    })

    # 127.0.0.1, never 0.0.0.0. The difference is whether the rest of the
    # network can reach the operator's memories.
    server = ThreadingHTTPServer((HOST, port), handler)
    server.daemon_threads = True

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    bound = server.server_address[1]

    _log_call({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "route": "<start>",
        "outcome": "listening",
        "peer": f"{HOST}:{bound}",
    })

    return AgentInterface(server, token, bound)
