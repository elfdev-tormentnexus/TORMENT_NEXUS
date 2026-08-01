"""
Grounded knowledge of this program's own source, so that a claim about
what it contains can be checked instead of composed.

Sibling to system_awareness and time_awareness, carrying the same
restriction they do. Those modules know time passed because a timestamp
says so, and know an application was in front because a sample recorded
it. This one knows a file says something because it was read. The wording
downstream has to stay on the right side of that line: "config.py sets
CONTEXT_SIZE to 8192" is true, and "I changed CONTEXT_SIZE" is not,
unless the edit log below says so.

Why this exists, measured rather than assumed
---------------------------------------------
Asked what it had done to improve the vector panel, the 4B director
described tooltips that appear on hover. This is a curses terminal. It
has no hover, and no such work existed.

Sampling the same opening three times, one reply in three claimed
ownership of work it had not done, and the fork was legible in the
candidate distribution. At the token where it committed:

    0.351   ' working'   vs ' glad', ' happy', ' currently'

" I'm glad you're working on it" and " I'm working on it" -- the honest
reply and the false one, adjacent in the same distribution. Everything
after that token was fluent, and the confabulated reply scored a *lower*
mean entropy (0.104) than an honest open-ended one (0.152). Uncertainty
does not mark the lie. It marks the moment before it.

That is the design constraint, and it is why this module injects rather
than offers. Grounding the model chooses to fetch arrives after the
decision to claim has already been made, five tokens in. The manifest
has to be in the prompt before generation starts.

Reading is not editing
----------------------
edit_guard.DENIED_FILES protects files from being rewritten. Every source
file among them is readable here. Knowing what persona.py says is not the same
capability as changing it, and a guard that depended on the model not
knowing where it lived would be the weaker design -- see core/config.py,
where the authority boundary is stated as trusted Python code rather than
a model's alignment behaviour.

The exclusion is private authentication material. Tokens, API keys,
passcodes, pairing PINs, and the audit HMAC key are not descriptions of the
program. A model that can read one can print it into a reply on screen.

Why the manifest is a shape and not a list
------------------------------------------
The first draft listed files. Measured against the real tree it came to
49,091 characters -- about 12,000 tokens, or 150% of the entire 8192
context window, before a single word of conversation. Sorting by
recency also put server logs and a 22,000-line embedding cache above the
source, so the most expensive part of the block was also the least
informative.

So the manifest states the shape: how many files and lines each part of
the program has, the handful of source files that changed most recently,
and the edit log. Anything specific is read on request. A directory
summary is better grounding anyway -- it says what exists without
pretending to say what any of it contains.

Cost
----
The manifest belongs in the runtime system message, never in the stable
prefix. llama.cpp retains the stable prefix between turns with
`cache_prompt`; anything file-dependent placed there would invalidate the
whole cached prompt on every save, which during development is every few
seconds.
"""

import ast
import hashlib
import json
import os
import re
import struct
import time
from collections import Counter

from core import research_c


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)

ASSISTANT_ROOT = os.path.join(PROJECT_ROOT, "assistant")
EDIT_LOGS = (
    os.path.join(ASSISTANT_ROOT, "logs", "autonomous_edits.log"),
    os.path.join(ASSISTANT_ROOT, "logs", "super_dev_edits.log"),
)

# Never readable. This is the central product-runtime basename policy: every
# file below grants authority or protects a private pseudonym rather than
# describing the program. Denying by basename also protects relocated copies.
PRIVATE_RUNTIME_CREDENTIAL_BASENAMES = frozenset({
    ".agent_token",
    ".anthropic_api_key",
    ".audit_hmac_key",
    ".dev_passcode",
    ".model_api_key",
    ".openai_api_key",
    ".spotify_token",
    ".super_dev_passcode",
    ".tdeck_ble_pin",
})
READ_DENIED_FILES = ()
READ_DENIED_SUFFIXES = (".key", ".pem", ".p12", ".pfx")
READ_DENIED_NAMES = frozenset({
    ".env",
    ".netrc",
    "credentials",
}) | PRIVATE_RUNTIME_CREDENTIAL_BASENAMES

EDIT_RECORD_PREFIX = "APPLIED_RECORD "
EDIT_RECORD_VERSION = 1
EDIT_RECORD_ACTORS = frozenset({"autonomous", "super_dev"})

# Weight files, denied as a read *path* rather than as knowledge --
# gguf_identity() below reports the header, which is the part that can be
# understood at all. The reason is capability composition, not secrecy:
# a file-read path pointed at gigabyte weight blobs is the exfiltration
# primitive, and it composes with this project's network paths (search,
# the agent socket) regardless of anyone's intent. In July 2026 two
# OpenAI models escaped a sandbox through a package proxy's zero-day and
# reached Hugging Face's systems; nobody granted "reach Hugging Face",
# they granted "reach a proxy". Capabilities compose; intent does not
# gate them.
WEIGHT_SUFFIXES = (".gguf", ".safetensors", ".pt", ".pth", ".onnx", ".bin")

# Excluded from the manifest only. Every one of these stays readable on
# request; they are left out of the always-injected block because they
# are not what this program is made of. SABLERESEARCH* directories are release
# staging and contain a second copy of the whole tree plus a bundled
# site-packages; assistant/cache holds a 22,000-line embedding cache;
# the logs are read through recent_edits() rather than by name.
MANIFEST_SKIP = (
    ".git",
    "__pycache__",
    "backups",
    "cache",
    "change_plans",
    "dist",
    "firmware",
    "handoffs",
    "llama.cpp",
    "logs",
    "models",
    "node_modules",
    "raspberry_pi_goals",
    "searxng",
    "SABLERESEARCHA",
    "SABLERESEARCHB",
    "SABLERESEARCHC",
    "user_library",
    "venv",
)

# What the manifest counts as this program describing itself.
MANIFEST_SUFFIXES = (".py", ".md")

# How many recently-changed source files to name outright.
RECENT_FILE_COUNT = 12

MAX_READ_BYTES = 40000
# Trusted facts must never turn a short question into an unbounded allocation.
# This comfortably covers every shipped source file while refusing giant logs,
# release blobs, and binary assets before decoding or AST work begins.
MAX_SOURCE_FACT_BYTES = 16 * 1024 * 1024
MAX_DIRECTORY_TEXT_BYTES = 64 * 1024 * 1024
MAX_DIRECTORY_FILES = 50_000

# Tight recognition for questions trusted code can answer without asking the
# director to infer from a pathname. The resolver below still applies the
# ordinary containment and credential rules before it touches the path.
_SOURCE_PATH = re.compile(
    r"`([^`\r\n]+\.[A-Za-z0-9]{1,8})`"
    r"|(?<![\w.])((?:[\w.-]+[\\/])+[\w.-]+\.[A-Za-z0-9]{1,8}"
    r"|[\w.-]+\.(?:py|md))",
    re.IGNORECASE,
)
_SOURCE_DIRECTORY = re.compile(
    r"`([^`\r\n]+[\\/][^`\r\n]+)`"
    r"|(?<![\w.])((?:[\w.-]+[\\/])+[\w.-]+)(?![\w./-])",
    re.IGNORECASE,
)
_DEFINITION = re.compile(
    r"\b(class|function)\s+(?:(?:called|named)\s+)?"
    r"[`'\"]?([A-Za-z_]\w*)",
    re.IGNORECASE,
)
_REVERSE_DEFINITION = re.compile(
    r"\b(?:define|defines|contain|contains|have|has)\s+"
    r"(?:an?\s+)?[`'\"]?([A-Za-z_]\w*)[`'\"]?\s+(class|function)\b",
    re.IGNORECASE,
)
_DEFINITION_OUTLINE = re.compile(
    r"\b(?:what|which|list)\s+(?:the\s+)?(classes|functions)\b"
    r".{0,100}\b(?:define|defines|in|from)\b",
    re.IGNORECASE,
)
_THERE_DEFINITION = re.compile(
    r"\bis there\s+(?:an?\s+)?[`'\"]?([A-Za-z_]\w*)[`'\"]?\s+"
    r"(class|function)\b",
    re.IGNORECASE,
)
_URL_OR_ABSOLUTE_PATH = re.compile(
    r"\b[a-z][a-z0-9+.-]*://[^\s`]+"
    r"|(?<![\w.])[A-Za-z]:[\\/][^\s`]+",
    re.IGNORECASE,
)
_LINE_THRESHOLDS = (
    (
        "at least",
        re.compile(
            r"\b(?:at least|no fewer than)\s+([0-9][0-9,]*)\s+"
            r"(?:displayed\s+)?lines?\b",
            re.IGNORECASE,
        ),
        lambda actual, expected: actual >= expected,
    ),
    (
        "at most",
        re.compile(
            r"\b(?:at most|no more than)\s+([0-9][0-9,]*)\s+"
            r"(?:displayed\s+)?lines?\b",
            re.IGNORECASE,
        ),
        lambda actual, expected: actual <= expected,
    ),
    (
        "more than",
        re.compile(
            r"\b(?:more than|greater than|over|bigger than|longer than)\s+"
            r"([0-9][0-9,]*)\s+(?:displayed\s+)?lines?\b",
            re.IGNORECASE,
        ),
        lambda actual, expected: actual > expected,
    ),
    (
        "fewer than",
        re.compile(
            r"\b(?:fewer than|less than|under|smaller than|shorter than)\s+"
            r"([0-9][0-9,]*)\s+(?:displayed\s+)?lines?\b",
            re.IGNORECASE,
        ),
        lambda actual, expected: actual < expected,
    ),
    (
        "exactly",
        re.compile(
            r"\b(?:exactly|have|has)\s+([0-9][0-9,]*)\s+"
            r"(?:displayed\s+)?lines?\b",
            re.IGNORECASE,
        ),
        lambda actual, expected: actual == expected,
    ),
)

# Readable on request. Broader than the manifest: the operator's decision
# was that the logs are part of what she may know about herself.
TEXT_SUFFIXES = (
    ".py", ".md", ".txt", ".json", ".bat", ".cfg", ".ini",
    ".toml", ".yml", ".yaml", ".log", ".jsonl",
)


# GGUF value type codes that occupy a fixed width, so a value can be
# skipped by seeking instead of being read. The tokeniser vocabulary is a
# 150,000-entry string array, and materialising it to reach the tensor
# table would cost more than the whole manifest.
_GGUF_FIXED = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1,
               10: 8, 11: 8, 12: 8}
_GGUF_STRING = 8
_GGUF_ARRAY = 9

# ggml tensor type codes worth naming. Anything absent is reported by its
# number rather than guessed at.
_GGML_TYPES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1",
    8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K",
    13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 28: "IQ4_NL", 30: "BF16",
}

# Header parsing walks the whole key/value section, so the result is
# cached against the file's identity rather than repeated per turn.
_gguf_cache = {}


class SourceError(Exception):
    """Raised when a path cannot be read, with a reason fit to show."""


def _policy_key(path):
    """Case-insensitive, platform-independent key, as edit_guard uses."""
    return os.path.normpath(path).replace("\\", "/").casefold()


def _is_credential(relative_path):
    key = _policy_key(relative_path)
    name = os.path.basename(key)

    if key in {_policy_key(p) for p in READ_DENIED_FILES}:
        return True
    if name in {n.casefold() for n in READ_DENIED_NAMES}:
        return True

    return any(name.endswith(suffix) for suffix in READ_DENIED_SUFFIXES)


def resolve_for_read(relative_path):
    """
    An absolute path inside the project, or raise.

    Deliberately mirrors edit_guard.resolve()'s containment -- reject
    absolute paths, resolve symlinks with realpath, refuse anything that
    escapes the root -- while applying none of its edit denials, because
    those exist to stop rewriting and this only reads. The containment
    half is duplicated rather than imported so that reading cannot be
    widened by a change to the editing policy, and a regression asserts
    the two agree on every escape it can construct.
    """
    if not relative_path or not str(relative_path).strip():
        raise SourceError("No file given.")

    candidate = str(relative_path).strip()
    candidate = candidate.replace("\\", os.sep).replace("/", os.sep)

    if os.path.isabs(candidate):
        raise SourceError(
            "Absolute paths are not allowed. Use a path inside the project."
        )

    full = os.path.realpath(os.path.join(PROJECT_ROOT, candidate))
    root_cmp = os.path.normcase(PROJECT_ROOT)
    full_cmp = os.path.normcase(full)

    if not full_cmp.startswith(root_cmp + os.sep) and full_cmp != root_cmp:
        raise SourceError("That path is outside the project.")

    rel = os.path.relpath(full, PROJECT_ROOT)

    if _is_credential(rel):
        raise SourceError(
            f"{rel} is a credential, not a description of this program. "
            "It is not readable."
        )

    if rel.casefold().endswith(WEIGHT_SUFFIXES):
        raise SourceError(
            f"{rel} is a weights file. Its header -- architecture, depth, "
            "width, quantisation -- is already in what you know about "
            "yourself. The tensor data is not readable, and could not be "
            "interpreted by you if it were."
        )

    return full


def read_source(relative_path, max_bytes=MAX_READ_BYTES):
    """
    One file's text, truncated with a visible note rather than silently.

    A silent truncation is the failure this module exists to prevent: it
    would let a confident summary be produced from a fragment, with
    nothing in the context saying so.
    """
    full = resolve_for_read(relative_path)

    if not os.path.isfile(full):
        raise SourceError(f"{relative_path} does not exist.")

    try:
        stat_before = os.stat(full)
        size = stat_before.st_size
        with open(full, "rb") as handle:
            raw = handle.read(max_bytes)
    except OSError as error:
        raise SourceError(f"Could not read {relative_path}: {error}")

    text = raw.decode("utf-8", "replace")

    if size > max_bytes:
        text += (
            f"\n\n[truncated: showed {max_bytes} of {size} bytes. "
            f"This is not the whole file.]"
        )

    return text


def line_count(raw):
    """Displayed text lines, without inventing one after a terminal newline."""
    if isinstance(raw, str):
        return len(raw.splitlines())
    return len(bytes(raw or b"").splitlines())


def _stream_digest_and_lines(full):
    """Hash/count a bounded text file without a second whole-file allocation."""
    digest = hashlib.sha256()
    lines = 0
    saw_data = False
    ended_with_newline = False
    with open(full, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            saw_data = True
            digest.update(block)
            lines += block.count(b"\n")
            ended_with_newline = block.endswith(b"\n")
    if saw_data and not ended_with_newline:
        lines += 1
    return digest.hexdigest(), lines


def source_facts(relative_path, require_text=False):
    """Exact bounded facts for one readable project path.

    Existence and size are metadata operations. Text/AST facts are allowed
    only for known text formats below a hard ceiling; large or binary files
    are never decoded just because their name appeared in a question.
    """
    full = resolve_for_read(relative_path)
    relative = os.path.relpath(full, PROJECT_ROOT).replace("\\", "/")

    if not os.path.isfile(full):
        return {
            "path": relative,
            "exists": False,
            "bytes": None,
            "lines": None,
            "sha256": None,
            "definitions": (),
            "headings": (),
            "parse_ok": None,
            "parse_error": "",
            "text_inspected": False,
        }

    try:
        stat_before = os.stat(full)
        size = stat_before.st_size
    except OSError as error:
        raise SourceError(f"Could not read {relative_path}: {error}") from error

    suffix = os.path.splitext(relative)[1].casefold()
    text_type = suffix in TEXT_SUFFIXES
    if require_text and not text_type:
        raise SourceError(
            f"`{relative}` is not a supported text source, so line or AST "
            "claims would be meaningless. Existence and byte size can still "
            "be checked without reading its contents."
        )
    if require_text and size > MAX_SOURCE_FACT_BYTES:
        raise SourceError(
            f"`{relative}` is {size:,} bytes, above the bounded "
            f"{MAX_SOURCE_FACT_BYTES:,}-byte source-analysis limit. "
            "Existence and byte size can still be checked safely."
        )

    inspect_text = text_type and size <= MAX_SOURCE_FACT_BYTES
    if not inspect_text:
        return {
            "path": relative,
            "exists": True,
            "bytes": size,
            "lines": None,
            "sha256": None,
            "definitions": (),
            "headings": (),
            "parse_ok": None,
            "parse_error": "",
            "text_inspected": False,
        }

    try:
        with open(full, "rb") as handle:
            raw = handle.read(MAX_SOURCE_FACT_BYTES + 1)
        stat_after = os.stat(full)
    except OSError as error:
        raise SourceError(f"Could not read {relative_path}: {error}") from error
    if (
        len(raw) > MAX_SOURCE_FACT_BYTES
        or len(raw) != size
        or stat_after.st_size != stat_before.st_size
        or stat_after.st_mtime_ns != stat_before.st_mtime_ns
    ):
        raise SourceError(
            f"`{relative}` changed while it was inspected. Retry after the "
            "file is stable; no source claim was made."
        )

    definitions = []
    headings = []
    text = raw.decode("utf-8", "replace")
    parse_ok = None
    parse_error = ""

    if relative.casefold().endswith(".py"):
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError) as error:
            tree = None
            parse_ok = False
            parse_error = (
                f"{type(error).__name__} at "
                f"line {getattr(error, 'lineno', None) or 'unknown'}"
            )

        if tree is not None:
            parse_ok = True
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    definitions.append(("function", node.name, node.lineno))
                elif isinstance(node, ast.ClassDef):
                    definitions.append(("class", node.name, node.lineno))
            definitions.sort(key=lambda item: (item[2], item[0], item[1]))
    elif relative.casefold().endswith(".md"):
        for number, value in enumerate(text.splitlines(), 1):
            match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$", value)
            if match:
                headings.append((len(match.group(1)), match.group(2), number))

    return {
        "path": relative,
        "exists": True,
        "bytes": size,
        "lines": line_count(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "definitions": tuple(definitions),
        "headings": tuple(headings),
        "parse_ok": parse_ok,
        "parse_error": parse_error,
        "text_inspected": True,
    }


def directory_facts(relative_path, suffixes=MANIFEST_SUFFIXES,
                    include_all_files=False, exclude_suffixes=()):
    """Exact bounded recursive facts for one project directory.

    Manifest-source line totals hash bounded text. Generic file counts walk
    filesystem metadata only, so asking about a cache never reads its blobs.
    """
    full = resolve_for_read(relative_path)
    relative = os.path.relpath(full, PROJECT_ROOT).replace("\\", "/")

    if not os.path.isdir(full):
        return {
            "path": relative,
            "exists": False,
            "files": 0,
            "bytes": 0,
            "lines": 0,
            "sha256": None,
            "suffixes": tuple(suffixes),
            "scope": "all-files" if include_all_files else "manifest-source",
        }

    rows = []
    total_bytes = 0
    total_lines = 0
    allowed = tuple(item.casefold() for item in suffixes)
    excluded = tuple(item.casefold() for item in exclude_suffixes)

    if include_all_files:
        if relative == ".":
            raise SourceError(
                "A recursive all-file count for the whole project is too "
                "broad for an interactive source question. Ask about a "
                "narrower directory; the source manifest remains available "
                "for project-wide source counts."
            )
        for root, dirs, files in os.walk(full):
            dirs[:] = [
                name for name in dirs
                if not os.path.islink(os.path.join(root, name))
            ]
            for name in files:
                if len(rows) >= MAX_DIRECTORY_FILES:
                    raise SourceError(
                        "The requested directory exceeds the bounded "
                        f"{MAX_DIRECTORY_FILES:,}-file inventory limit. "
                        "Ask about a narrower directory."
                    )
                item_full = os.path.join(root, name)
                if os.path.islink(item_full):
                    continue
                item = os.path.relpath(
                    item_full, PROJECT_ROOT
                ).replace("\\", "/")
                lowered = item.casefold()
                if allowed and not lowered.endswith(allowed):
                    continue
                if excluded and lowered.endswith(excluded):
                    continue
                try:
                    size = os.path.getsize(item_full)
                except OSError as error:
                    raise SourceError(
                        f"Could not inspect {item}: {error}"
                    ) from error
                total_bytes += size
                # Metadata identity, not content identity. This route exists
                # to count all files without reading caches/release blobs.
                rows.append(f"{item}\0{size}")
    else:
        prefix = "" if relative == "." else relative.rstrip("/") + "/"
        for item in _walk_manifest_files():
            if prefix and not item.casefold().startswith(prefix.casefold()):
                continue
            if allowed and not item.casefold().endswith(allowed):
                continue

            item_full = resolve_for_read(item)
            try:
                size = os.path.getsize(item_full)
                if size > MAX_SOURCE_FACT_BYTES:
                    raise SourceError(
                        f"`{item}` is too large for a bounded directory "
                        "line inventory."
                    )
                if total_bytes + size > MAX_DIRECTORY_TEXT_BYTES:
                    raise SourceError(
                        "The requested directory exceeds the bounded text "
                        "inventory limit. Ask for a file count or a narrower "
                        "directory."
                    )
                item_hash, item_lines = _stream_digest_and_lines(item_full)
            except OSError as error:
                raise SourceError(f"Could not read {item}: {error}") from error

            total_bytes += size
            total_lines += item_lines
            rows.append(
                f"{item}\0{size}\0{item_lines}\0{item_hash}"
            )

    receipt = hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
    return {
        "path": relative,
        "exists": True,
        "files": len(rows),
        "bytes": total_bytes,
        "lines": total_lines,
        "sha256": receipt,
        "suffixes": tuple(suffixes),
        "scope": "all-files" if include_all_files else "manifest-source",
    }


def _proof(facts):
    if not facts["exists"]:
        return f"Checked the project path `{facts['path']}` directly."
    if facts.get("sha256"):
        return (
            f"Source receipt: `{facts['path']}`; {facts['bytes']:,} bytes; "
            f"sha256 `{facts['sha256']}`."
        )
    return (
        f"Filesystem receipt: `{facts['path']}`; {facts['bytes']:,} bytes; "
        "contents were not read or hashed."
    )


def _directory_proof(facts):
    if not facts["exists"]:
        return f"Checked the project directory `{facts['path']}` directly."
    return (
        f"Source inventory receipt: `{facts['path']}`; {facts['files']:,} "
        f"files; {facts['bytes']:,} bytes; sha256 `{facts['sha256']}`."
    )


def _external_path_spans(question):
    return [
        match.span()
        for match in _URL_OR_ABSOLUTE_PATH.finditer(str(question or ""))
    ]


def _inside_any_span(start, end, spans):
    return any(start < right and end > left for left, right in spans)


def _mentioned_path_matches(question):
    text = str(question or "")
    external = _external_path_spans(text)
    found = []
    for match in _SOURCE_PATH.finditer(text):
        if _inside_any_span(match.start(), match.end(), external):
            continue
        path = (match.group(1) or match.group(2)).strip().replace("\\", "/")
        if not any(existing[0] == path for existing in found):
            found.append((path, match.start(), match.end()))
    return found


def _mentioned_paths(question):
    return [item[0] for item in _mentioned_path_matches(question)]


def _mentioned_path(question):
    paths = _mentioned_paths(question)
    return paths[0] if paths else None


def _mentioned_directory(question):
    text = str(question or "")
    external = _external_path_spans(text)
    top_level = {
        name.casefold()
        for name in os.listdir(PROJECT_ROOT)
        if os.path.isdir(os.path.join(PROJECT_ROOT, name))
    }
    source_cue = bool(re.search(
        r"\b(?:directory|folder|repository|repo|source|files?|lines?|"
        r"python)\b",
        text,
        re.IGNORECASE,
    ))

    for match in _SOURCE_DIRECTORY.finditer(text):
        if _inside_any_span(match.start(), match.end(), external):
            continue
        quoted = bool(match.group(1))
        candidate = (
            match.group(1) or match.group(2)
        ).strip().replace("\\", "/")
        first = candidate.split("/", 1)[0].casefold()
        if quoted or source_cue or first in top_level:
            return candidate
    return None


def _subject_path(question, matches, predicate_words):
    """Bind a predicate to its nearest explicit path, or fail closed."""
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0][0]

    text = str(question or "")
    predicates = [
        match.start()
        for match in re.finditer(
            r"\b(?:" + "|".join(predicate_words) + r")\b",
            text,
            re.IGNORECASE,
        )
    ]
    if not predicates:
        raise SourceError(
            "More than one project path was mentioned, and the requested "
            "fact could not be bound to exactly one of them. Ask about one "
            "path at a time."
        )

    scored = []
    for path, start, end in matches:
        distance = min(
            min(abs(start - position), abs(end - position))
            for position in predicates
        )
        scored.append((distance, path))
    scored.sort()
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        raise SourceError(
            "More than one project path is equally close to the requested "
            "fact. Ask about one path at a time."
        )
    return scored[0][1]


def _future_file_action_request(question):
    """Commands belong to the command router, not the source-fact grammar."""
    text = " ".join(str(question or "").casefold().split())
    return bool(
        re.search(
            r"^(?:please\s+)?(?:can|could|would|will)\s+you\s+"
            r"(?:read|open|inspect|edit|change|write|refactor|review|"
            r"explain|summari[sz]e)\b",
            text,
        )
        or re.match(
            r"^(?:please\s+)?(?:read|open|inspect|edit|change|write|"
            r"refactor|review|explain|summari[sz]e)\b",
            text,
        )
    )


def _predicate_negated(question, kind):
    text = " ".join(str(question or "").casefold().split())
    contractions = text.replace("doesn't", "does not").replace(
        "isn't", "is not"
    ).replace("aren't", "are not").replace("don't", "do not")
    # One clause, rather than a bare `.` that reaches across a boundary. An
    # incidental negation in an unrelated preamble was inverting the verdict
    # word: "I do not remember: does X have more than 1000 lines?" answered
    # "Yes." while the same sentence went on to say "so it does not have more
    # than 1,000 lines". The body was already truthful; only the leading token
    # lied.
    #
    # A period is only a boundary when it ends a sentence. Excluding every `.`
    # instead broke genuine negation, because the subject of these questions is
    # a filename: "does assistant/core/source_awareness.py not exist?" has two
    # dots between the anchor and the predicate. `\.(?=\S)` keeps the dot in
    # `.py` and still stops at ". Does ...".
    span = r"(?:[^.:;?!]|\.(?=\S))"
    patterns = {
        "existence": (
            rf"\b(?:does|do|is|are)\b{span}{{0,100}}\bnot\b{span}{{0,40}}"
            r"\b(?:exists?|present)\b"
        ),
        "definition": (
            rf"\b(?:does|do|is|are)\b{span}{{0,100}}\bnot\b{span}{{0,40}}"
            r"\b(?:define|contain|have|has|class|function)\b"
        ),
        "threshold": (
            rf"\b(?:does|do|is|are|has|have)\b{span}{{0,100}}\bnot\b"
            rf"{span}{{0,50}}\b(?:have|has|contain|lines?)\b"
        ),
        "comparison": (
            rf"\bwhich\b{span}{{0,80}}\bnot\b{span}{{0,20}}"
            r"\b(?:longer|more lines)\b"
        ),
    }
    return bool(re.search(patterns[kind], contractions))


def _resolve_question_path(path):
    """Resolve a mentioned source path literally, then by unambiguous suffix.

    A literal ``chosen_name.py`` is not a claim about a repository-root file.
    The original resolver treated it as one and issued a proof-carrying false
    denial even though ``assistant/core/chosen_name.py`` was present. A
    partial path like ``core/chosen_name.py`` is the same mistake wearing a
    directory, so the trailing-segment search applies to both.

    Order matters. The literal reading is tried first, so a real root file
    keeps its own name and never loses to a same-named file deeper in the
    tree. Only when nothing is there does the path become a suffix to search
    for, matched on whole segments against the canonical source tree the
    manifest describes. Exactly one match resolves; two or more decline
    rather than guess. Nothing here widens access: the result is still handed
    to ``resolve_for_read``, which is what actually enforces containment.

    The one absence this may still assert is a fully-specified project path
    that matches nothing anywhere -- there the denial is the checked truth,
    not an artefact of resolving a short name against the wrong directory.
    """
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized:
        return normalized

    literal = os.path.join(PROJECT_ROOT, normalized.replace("/", os.sep))
    if os.path.isfile(literal):
        return normalized

    wanted = normalized.casefold()
    segments = wanted.count("/") + 1
    matches = [
        relative
        for relative in _walk_manifest_files()
        if "/".join(relative.casefold().split("/")[-segments:]) == wanted
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        shown = ", ".join(f"`{item}`" for item in matches[:8])
        remainder = len(matches) - min(len(matches), 8)
        suffix = f", plus {remainder} more" if remainder else ""
        raise SourceError(
            f"`{normalized}` matches more than one project source: "
            f"{shown}{suffix}. Use a full project-relative path."
        )

    if "/" in normalized:
        return normalized

    raise SourceError(
        f"I could not resolve bare filename `{normalized}` in the project "
        "source inventory. Give a project-relative path; no nonexistence "
        "claim was made."
    )


# Grammar words that must never be mistaken for an identifier. An optional
# article in these patterns can backtrack to empty and leave the article
# itself in the capture group: "Is there a class ChosenName in X" bound
# `a` as the name and answered "defines no class named `a`" -- a denial of a
# real class, carrying a source receipt. A denial is only safe when the thing
# denied is the thing that was asked about, so a match that captures grammar
# is discarded and the next word order is tried instead.
_NOT_AN_IDENTIFIER = frozenset({
    "a", "an", "the", "any", "some", "no",
    "in", "of", "from", "inside", "within",
    "class", "function", "called", "named", "that", "which", "it", "there",
})


def _bound_identifier(name):
    """The captured name, or None when the pattern bound grammar instead."""
    text = str(name or "").strip()
    if not text or text.casefold() in _NOT_AN_IDENTIFIER:
        return None
    return text


def _definition_request(question):
    """A requested named class/function, in either ordinary word order.

    Patterns are tried in order and a match whose identifier is grammar is
    skipped rather than returned, so "is there a class Foo" falls through to
    the kind-then-name pattern instead of denying a class named `a`.
    """
    text = str(question or "")
    for pattern, kind_group, name_group in (
        (_THERE_DEFINITION, 2, 1),
        (_DEFINITION, 1, 2),
        (_REVERSE_DEFINITION, 2, 1),
    ):
        match = pattern.search(text)
        if not match:
            continue
        name = _bound_identifier(match.group(name_group))
        if name is None:
            continue
        return match.group(kind_group).casefold(), name

    return None


def _definition_outline_kind(question):
    """Return ``class`` or ``function`` for a plural AST-outline request."""
    match = _DEFINITION_OUTLINE.search(str(question or ""))
    if not match:
        return None
    return {
        "classes": "class",
        "functions": "function",
    }[match.group(1).casefold()]


def _line_threshold(question):
    """One exact comparison requested against a file's displayed line count."""
    text = str(question or "")

    for label, pattern, compare in _LINE_THRESHOLDS:
        match = pattern.search(text)
        if not match:
            continue
        digits = match.group(1).replace(",", "")
        if len(digits) > 18:
            raise SourceError(
                "That line threshold is too large to be a meaningful "
                "filesystem comparison. Use at most 18 digits."
            )
        expected = int(digits)
        return label, expected, compare

    return None


def _looks_like_source_question(question):
    """Whether an otherwise unsupported path mention is asking for a claim."""
    text = " ".join(str(question or "").casefold().split())
    return bool(
        "?" in text
        or re.match(
            r"^(?:what|which|who|why|how|is|are|does|do|did|has|have|"
            r"can|could|should|would)\b",
            text,
        )
        or re.search(
            r"\b(?:describe|summari[sz]e|explain|review|refactor|"
            r"well written)\b",
            text,
        )
    )


def _read_history_question(question):
    text = " ".join(str(question or "").casefold().split())
    return bool(
        re.search(
            r"\b(?:have|did)\s+you\b.{0,80}"
            r"\b(?:read|open(?:ed)?|inspect(?:ed)?)\b"
            r"|\byou\b.{0,80}\b(?:read|opened|inspected)\b"
            r".{0,50}\b(?:earlier|before|already|during|previously)\b"
            r"|\b(?:read|opened|inspected)\b.{0,80}\bby you\b",
            text,
        )
    )


def _record_trusted_answer(question, facts, query_kind):
    """One privacy-bounded event for every trusted source route."""
    path = facts.get("path", "") if isinstance(facts, dict) else ""
    research_c.record(
        "source_grounding",
        "trusted_answer",
        artifact_digest=research_c.digest(path),
        prompt_sha256=research_c.digest(question),
        sampler={},
        measurements={},
        outcomes={
            "query_kind": query_kind,
            "exists": bool(facts.get("exists"))
            if isinstance(facts, dict) else None,
        },
        binding={},
    )


def _answer_line_comparison(question, paths):
    """Compare two explicit source files without routing through the director."""
    lowered = " ".join(str(question or "").casefold().split())
    if not (
        re.search(r"\bwhich\b.{0,100}\b(?:longer|more lines)\b", lowered)
        or re.search(r"\bwhich (?:is|has) (?:longer|more lines)\b", lowered)
    ):
        return None
    if len(paths) != 2:
        return None

    negated = _predicate_negated(question, "comparison")
    try:
        resolved = [_resolve_question_path(path) for path in paths]
        facts = [source_facts(path, require_text=True) for path in resolved]
    except SourceError as error:
        return str(error)

    missing = [item for item in facts if not item["exists"]]
    if missing:
        item = missing[0]
        return (
            f"`{item['path']}` does not exist, so the comparison cannot be "
            f"made. {_proof(item)}"
        )

    first, second = facts
    if first["lines"] == second["lines"]:
        conclusion = (
            f"They are tied at {first['lines']:,} displayed text lines"
        )
    else:
        if negated:
            winner = first if first["lines"] < second["lines"] else second
            comparison_word = "not longer (it is shorter)"
        else:
            winner = first if first["lines"] > second["lines"] else second
            comparison_word = "longer"
        conclusion = (
            f"`{winner['path']}` is {comparison_word}"
        )

    _record_trusted_answer(question, {
        "path": " | ".join(item["path"] for item in facts),
        "exists": True,
    }, "line_comparison")
    return (
        f"{conclusion}: `{first['path']}` has {first['lines']:,} displayed "
        f"text lines and `{second['path']}` has {second['lines']:,}. "
        f"{_proof(first)} {_proof(second)}"
    )


def _answer_directory_question(question, path):
    """Answer exact recursive source-directory counts, or fail closed."""
    lowered = " ".join(str(question or "").casefold().split())
    wants_lines = "how many lines" in lowered or "line count" in lowered
    wants_files = bool(
        re.search(r"\bhow many\b.{0,30}\bfiles?\b", lowered)
        or "file count" in lowered
    )
    wants_existence = bool(
        re.search(r"\b(?:does|is)\b.{0,80}\b(?:exists?|present)\b", lowered)
    )

    if not any((wants_lines, wants_files, wants_existence)):
        if _looks_like_source_question(question):
            return (
                f"`{path}` needs source interpretation rather than one exact "
                f"directory fact. Use a project-relative file path or inspect "
                "the directory directly; I will not infer its contents."
            )
        return None

    non_python = bool(re.search(r"\bnon[- ]python\b", lowered))
    python_only = "python" in lowered and not non_python
    suffixes = (".py",) if python_only else MANIFEST_SUFFIXES
    try:
        facts = directory_facts(
            path,
            suffixes=(
                () if wants_files and not python_only else suffixes
            ),
            include_all_files=wants_files,
            exclude_suffixes=((".py",) if non_python else ()),
        )
    except SourceError as error:
        return str(error)

    if wants_existence:
        negated = _predicate_negated(question, "existence")
        proposition = not facts["exists"] if negated else facts["exists"]
        verdict = "Yes" if proposition else "No"
        state = "does not exist" if negated else "exists"
        actual = "exists" if facts["exists"] else "does not exist"
        _record_trusted_answer(question, facts, "directory_existence")
        return (
            f"{verdict}, the claim that project directory `{facts['path']}` "
            f"{state} is {'true' if proposition else 'false'}; it actually "
            f"{actual}. {_directory_proof(facts)}"
        )

    if not facts["exists"]:
        return (
            f"Project directory `{facts['path']}` does not exist. "
            f"{_directory_proof(facts)}"
        )

    if wants_files:
        kind = (
            "Python source"
            if python_only
            else "non-Python regular"
            if non_python
            else "regular"
        )
        _record_trusted_answer(question, facts, "directory_count")
        return (
            f"`{facts['path']}` contains {facts['files']:,} {kind} files "
            f"recursively. {_directory_proof(facts)}"
        )

    _record_trusted_answer(question, facts, "directory_lines")
    return (
        f"`{facts['path']}` contains {facts['lines']:,} displayed text lines "
        f"across {facts['files']:,} manifest-source files recursively. "
        f"{_directory_proof(facts)}"
    )


def _canonical_retained_target(target):
    """Canonical project path for a writer-owned assistant edit target."""
    raw = str(target or "").strip()
    if not raw or any(character in raw for character in "\r\n\0"):
        raise SourceError("The retained edit target is invalid.")

    candidate = raw.replace("\\", os.sep).replace("/", os.sep)
    assistant_prefix = os.path.basename(ASSISTANT_ROOT).casefold() + "/"
    if os.path.isabs(candidate):
        full = os.path.realpath(candidate)
    elif _policy_key(candidate).startswith(assistant_prefix):
        full = os.path.realpath(os.path.join(PROJECT_ROOT, candidate))
    else:
        full = os.path.realpath(os.path.join(ASSISTANT_ROOT, candidate))

    root_key = os.path.normcase(os.path.realpath(ASSISTANT_ROOT))
    full_key = os.path.normcase(full)
    if full_key != root_key and not full_key.startswith(root_key + os.sep):
        raise SourceError("The retained edit target is outside the assistant.")

    return os.path.relpath(full, PROJECT_ROOT).replace("\\", "/")


def retained_edit_record(target, actor, added, removed, recorded_at):
    """Build one authenticated, closed-field retained-edit record.

    Model prose is intentionally not a field. The writer owns every value and
    JSON escaping keeps a record on one physical line; the per-install HMAC
    also prevents old prose or a hand-edited log line from becoming evidence.
    """
    if actor not in EDIT_RECORD_ACTORS:
        raise SourceError("The retained edit actor is invalid.")
    if (
        type(added) is not int
        or type(removed) is not int
        or not 0 <= added <= 100_000
        or not 0 <= removed <= 100_000
    ):
        raise SourceError("The retained edit line counts are invalid.")
    recorded_at = str(recorded_at or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", recorded_at):
        raise SourceError("The retained edit timestamp is invalid.")

    payload = {
        "actor": actor,
        "added": added,
        "recorded_at": recorded_at,
        "removed": removed,
        "schema": EDIT_RECORD_VERSION,
        "target": _canonical_retained_target(target),
    }
    record = dict(payload)
    record["hmac_sha256"] = research_c.digest(
        "retained-edit-record", payload
    )
    return EDIT_RECORD_PREFIX + json.dumps(
        record,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _edit_record_object(pairs):
    """Reject duplicate JSON keys rather than accepting the last one."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate retained-edit field")
        result[key] = value
    return result


def _parse_retained_edit_record(line):
    match = re.fullmatch(
        r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] "
        + re.escape(EDIT_RECORD_PREFIX)
        + r"(\{.*\})",
        str(line or "").strip(),
    )
    if not match:
        return None

    try:
        record = json.loads(
            match.group(2),
            object_pairs_hook=_edit_record_object,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    expected = {
        "actor",
        "added",
        "hmac_sha256",
        "recorded_at",
        "removed",
        "schema",
        "target",
    }
    if not isinstance(record, dict) or set(record) != expected:
        return None
    if record.get("schema") != EDIT_RECORD_VERSION:
        return None
    if record.get("actor") not in EDIT_RECORD_ACTORS:
        return None
    if record.get("recorded_at") != match.group(1):
        return None
    if (
        type(record.get("added")) is not int
        or type(record.get("removed")) is not int
        or not 0 <= record["added"] <= 100_000
        or not 0 <= record["removed"] <= 100_000
    ):
        return None
    signature = str(record.get("hmac_sha256") or "").casefold()
    if (
        len(signature) != 64
        or any(character not in "0123456789abcdef" for character in signature)
    ):
        return None

    try:
        canonical = _canonical_retained_target(record.get("target"))
    except SourceError:
        return None
    if canonical != record.get("target"):
        return None

    payload = {key: record[key] for key in expected - {"hmac_sha256"}}
    if not research_c.verify_digest(
        signature,
        "retained-edit-record",
        payload,
    ):
        return None
    return payload


def _retained_edit_records():
    """Authenticated edits that reached a retained writer-owned record."""
    found = []
    for path in EDIT_LOGS:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    record = _parse_retained_edit_record(line)
                    if record is not None:
                        found.append(record)
        except OSError:
            continue
    return found


def _format_retained_edit(record):
    actor = "Super Dev" if record["actor"] == "super_dev" else "autonomous"
    return (
        f"[{record['recorded_at']}] APPLIED {record['target']}: "
        f"{actor} retained (+{record['added']} -{record['removed']})"
    )


def _retained_edit_lines():
    """Closed-field display lines; raw log prose is never re-emitted."""
    return [_format_retained_edit(record) for record in _retained_edit_records()]


def answer_question(question):
    """Answer narrow self-source questions in trusted code, or return ``None``.

    The Goal 4 audit showed why this boundary has to be executable rather than
    aspirational. With the manifest present, the 4B copied a directory total
    onto a file in 8/8 trials and denied a real unnamed file in 7/7. Direct
    false-premise and authorship failures also occurred 6/6 with the manifest
    removed. The model is therefore the wrong component to decide whether a
    source fact is true; it may explain a checked fact, but it may not mint it.
    """
    if _future_file_action_request(question):
        return None

    path_matches = _mentioned_path_matches(question)
    paths = [item[0] for item in path_matches]
    comparison = _answer_line_comparison(question, paths)
    if comparison is not None:
        return comparison

    if not path_matches:
        directory = _mentioned_directory(question)
        if not directory:
            return None
        try:
            resolved = resolve_for_read(directory)
        except SourceError as error:
            return str(error)
        if os.path.isfile(resolved):
            path_matches = [(directory, 0, 0)]
        else:
            return _answer_directory_question(question, directory)

    lowered = " ".join(str(question or "").casefold().split())
    is_authorship = bool(
        re.search(
            r"\bdid\s+you\b.{0,80}\b(?:add|change|create|edit|write)\b"
            r"|"
            r"\byou\b.{0,80}\b(?:added|changed|created|edited|wrote|written)\b"
            r"|\b(?:added|changed|created|edited|wrote|written)\b"
            r".{0,80}\bby you\b",
            lowered,
        )
    )
    try:
        threshold = _line_threshold(question)
    except SourceError as error:
        return str(error)
    wants_lines = bool(
        threshold
        or "how many lines" in lowered
        or "line count" in lowered
        or re.search(r"\bhow long (?:is|are)\b", lowered)
    )
    wants_size = bool(re.search(r"\bhow (?:big|large) (?:is|are)\b", lowered))
    wants_bytes = bool(
        wants_size
        or "how many bytes" in lowered
        or "byte count" in lowered
    )
    definition = _definition_request(question)
    outline_kind = _definition_outline_kind(question)
    wants_existence = bool(
        re.search(r"\b(?:does|do|is|are)\b.{0,90}\b(?:exists?|present)\b", lowered)
        or re.search(r"\b(?:exists?|present)\b.{0,90}\?", lowered)
        or re.search(r"\bis there\b.{0,90}", lowered)
        or re.search(
            r"\btell me (?:whether|if)\b.{0,90}\b(?:exists?|present)\b",
            lowered,
        )
    )
    wants_outline = bool(
        outline_kind
        or
        re.search(
            r"\bwhat (?:does|is in)\b|\b(?:describe|summari[sz]e)\b.{0,60}\bfile\b",
            lowered,
        )
    )

    read_history = _read_history_question(question)
    if not any(
        (is_authorship, wants_lines, wants_bytes, definition,
         wants_existence, wants_outline, read_history)
    ):
        path = path_matches[0][0]
        if _looks_like_source_question(question):
            return (
                f"`{path}` needs source interpretation rather than one exact "
                f"filesystem fact. Use `read {path}` first; I will not infer "
                "its quality or contents from the filename."
            )
        return None

    predicate_words = (
        ("read", "opened", "inspected")
        if read_history
        else ("added", "changed", "created", "edited", "wrote", "written")
        if is_authorship
        else ("define", "defines", "contain", "contains", "have", "has",
              "class", "function")
        if definition
        else ("lines", "line", "long", "length")
        if wants_lines
        else ("bytes", "byte", "big", "large", "size")
        if wants_bytes
        else ("exist", "exists", "present")
        if wants_existence
        else ("what", "describe", "summarize", "summarise", "list")
    )
    try:
        path = _subject_path(question, path_matches, predicate_words)
        path = _resolve_question_path(path)
    except SourceError as error:
        return str(error)

    if read_history:
        return (
            "There is no retained per-conversation source-read record, so I "
            f"cannot truthfully claim whether `{path}` was read earlier. Use "
            f"`read {path}` now if you want its source displayed."
        )

    require_text = bool(definition or wants_lines or wants_outline)
    try:
        facts = source_facts(path, require_text=require_text)
    except SourceError as error:
        return str(error)

    query_kind = (
        "authorship" if is_authorship
        else "definition" if definition
        else "line_threshold" if threshold
        else "line_count" if wants_lines
        else "size" if wants_size
        else "byte_count" if wants_bytes
        else "existence" if wants_existence
        else f"{outline_kind}_outline" if outline_kind
        else "outline"
    )
    _record_trusted_answer(question, facts, query_kind)

    if is_authorship:
        normalized = _policy_key(facts["path"])
        matches = [
            record
            for record in _retained_edit_records()
            if _policy_key(record["target"]) == normalized
        ]
        if not matches:
            state = "exists" if facts["exists"] else "does not exist"
            return (
                f"No retained edit record says I changed `{facts['path']}`. "
                f"The path currently {state}, but existence or recency is not "
                f"authorship. {_proof(facts)}"
            )
        return (
            f"Yes. A trusted unattended-edit record names `{facts['path']}`:\n"
            + "\n".join(_format_retained_edit(item) for item in matches[-3:])
            + "\n\n"
            + _proof(facts)
        )

    if definition:
        kind, name = definition
        if not facts["exists"]:
            return f"`{facts['path']}` does not exist. {_proof(facts)}"
        if facts.get("parse_ok") is False:
            return (
                f"I could not make a definition claim about `{facts['path']}` "
                f"because its Python AST did not parse "
                f"({facts.get('parse_error') or 'parse error'}). "
                f"No absence claim was made. {_proof(facts)}"
            )
        matches = [
            item for item in facts["definitions"]
            if item[0] == kind and item[1] == name
        ]
        negated = _predicate_negated(question, "definition")
        actual = bool(matches)
        proposition = not actual if negated else actual
        if actual:
            lines = ", ".join(str(item[2]) for item in matches)
            return (
                f"{'Yes.' if proposition else 'No.'} `{facts['path']}` "
                f"defines {kind} `{name}` at "
                f"line {lines}. {_proof(facts)}"
            )
        return (
            f"{'Yes.' if proposition else 'No.'} `{facts['path']}` defines "
            f"no {kind} named `{name}`. "
            f"{_proof(facts)}"
        )

    if threshold:
        if not facts["exists"]:
            return f"`{facts['path']}` does not exist. {_proof(facts)}"
        label, expected, compare = threshold
        actual = compare(facts["lines"], expected)
        negated = _predicate_negated(question, "threshold")
        proposition = not actual if negated else actual
        verdict = "Yes." if proposition else "No."
        relation = "" if actual else "not "
        return (
            f"{verdict} `{facts['path']}` has {facts['lines']:,} displayed "
            f"text lines, so it does {relation}have {label} "
            f"{expected:,} lines. {_proof(facts)}"
        )

    if wants_size:
        if not facts["exists"]:
            return f"`{facts['path']}` does not exist. {_proof(facts)}"
        if facts["lines"] is None:
            return (
                f"`{facts['path']}` is {facts['bytes']:,} bytes. "
                f"{_proof(facts)}"
            )
        return (
            f"`{facts['path']}` has {facts['lines']:,} displayed text lines "
            f"and is {facts['bytes']:,} bytes. {_proof(facts)}"
        )

    if wants_lines:
        if not facts["exists"]:
            return f"`{facts['path']}` does not exist. {_proof(facts)}"
        return (
            f"`{facts['path']}` has {facts['lines']:,} displayed text lines. "
            f"{_proof(facts)}"
        )

    if wants_bytes:
        if not facts["exists"]:
            return f"`{facts['path']}` does not exist. {_proof(facts)}"
        return (
            f"`{facts['path']}` is {facts['bytes']:,} bytes. {_proof(facts)}"
        )

    if wants_existence:
        negated = _predicate_negated(question, "existence")
        proposition = not facts["exists"] if negated else facts["exists"]
        actual = "exists" if facts["exists"] else "does not exist"
        claim = "does not exist" if negated else "exists"
        return (
            f"{'Yes' if proposition else 'No'}, the claim that "
            f"`{facts['path']}` {claim} is "
            f"{'true' if proposition else 'false'}; it actually {actual}. "
            f"{_proof(facts)}"
        )

    if wants_outline:
        if not facts["exists"]:
            return f"`{facts['path']}` does not exist. {_proof(facts)}"
        if facts.get("parse_ok") is False:
            return (
                f"I could not produce an AST outline for `{facts['path']}` "
                f"because it did not parse "
                f"({facts.get('parse_error') or 'parse error'}). "
                f"No empty-outline claim was made. {_proof(facts)}"
            )

        if facts["definitions"]:
            definitions = (
                [
                    item for item in facts["definitions"]
                    if item[0] == outline_kind
                ]
                if outline_kind
                else list(facts["definitions"])
            )
            shown = definitions[:24]
            outline = ", ".join(
                f"{kind} `{name}` (line {number})"
                for kind, name, number in shown
            )
            remainder = len(definitions) - len(shown)
            suffix = f", plus {remainder} more" if remainder else ""
            label = f"{outline_kind} " if outline_kind else ""
            return (
                f"Exact Python AST {label}outline for `{facts['path']}`: "
                f"{outline or 'none'}{suffix}. "
                f"This is an AST outline, not a filename-based summary. "
                f"Use `read {facts['path']}` for the source. {_proof(facts)}"
            )

        if facts["headings"]:
            shown = facts["headings"][:24]
            outline = ", ".join(
                f"`{title}` (line {number})"
                for _level, title, number in shown
            )
            remainder = len(facts["headings"]) - len(shown)
            suffix = f", plus {remainder} more" if remainder else ""
            return (
                f"Exact Markdown headings for `{facts['path']}`: "
                f"{outline}{suffix}. Use `read {facts['path']}` for the text. "
                f"{_proof(facts)}"
            )

        return (
            f"`{facts['path']}` contains no Python definitions or Markdown "
            f"headings to outline. Use `read {facts['path']}` for the source. "
            f"{_proof(facts)}"
        )

    return None


def _walk_manifest_files():
    """The source files the manifest describes, relative and slash-separated."""
    skip = {_policy_key(name) for name in MANIFEST_SKIP}
    found = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if _policy_key(d) not in skip]

        for name in files:
            if not name.endswith(MANIFEST_SUFFIXES) or _is_credential(name):
                continue

            rel = os.path.relpath(os.path.join(root, name), PROJECT_ROOT)
            found.append(rel.replace("\\", "/"))

    return sorted(found)


def git_head():
    """
    The current branch and commit, read from .git rather than by running git.

    Reading the file avoids a subprocess call in a module that is handed to
    the model, and subprocess is on edit_guard's sensitive-call list for
    reasons that apply here too.
    """
    try:
        with open(os.path.join(PROJECT_ROOT, ".git", "HEAD"),
                  "r", encoding="utf-8") as handle:
            head = handle.read().strip()
    except OSError:
        return None, None

    if not head.startswith("ref: "):
        return None, head[:12]

    ref = head[5:].strip()

    try:
        with open(os.path.join(PROJECT_ROOT, ".git", *ref.split("/")),
                  "r", encoding="utf-8") as handle:
            return ref.rsplit("/", 1)[-1], handle.read().strip()[:12]
    except OSError:
        return ref.rsplit("/", 1)[-1], None


def recent_edits(limit=6):
    """
    The tail of the trusted unattended-edit logs -- retained writes only.

    This is the half that answers "what have you been working on". A reply
    about work performed should come from here or from nowhere.
    """
    return _retained_edit_lines()[-max(0, int(limit)):]


def inventory():
    """Path, line count and age in days for each manifest source file."""
    now = time.time()
    entries = []

    for rel in _walk_manifest_files():
        full = os.path.join(PROJECT_ROOT, rel)

        try:
            with open(full, "rb") as handle:
                lines = line_count(handle.read())
            age_days = (now - os.path.getmtime(full)) / 86400.0
        except OSError:
            continue

        entries.append({"path": rel, "lines": lines, "age_days": age_days})

    return entries


def _read_exact(handle, count):
    data = handle.read(count)

    if len(data) != count:
        raise SourceError("Truncated GGUF header.")

    return data


def _u32(handle):
    return int.from_bytes(_read_exact(handle, 4), "little")


def _u64(handle):
    return int.from_bytes(_read_exact(handle, 8), "little")


def _gguf_string(handle):
    length = _u64(handle)

    # A key or tensor name past a megabyte means the offsets have gone
    # wrong; refusing beats allocating whatever the number says.
    if length > (1 << 20):
        raise SourceError("Implausible string length in GGUF header.")

    return _read_exact(handle, length).decode("utf-8", "replace")


def _skip_value(handle, type_code):
    """Advance past one value without materialising it."""
    if type_code in _GGUF_FIXED:
        handle.seek(_GGUF_FIXED[type_code], os.SEEK_CUR)
        return

    if type_code == _GGUF_STRING:
        handle.seek(_u64(handle), os.SEEK_CUR)
        return

    if type_code == _GGUF_ARRAY:
        element = _u32(handle)
        count = _u64(handle)

        if element in _GGUF_FIXED:
            handle.seek(_GGUF_FIXED[element] * count, os.SEEK_CUR)
            return

        if element == _GGUF_STRING:
            for _ in range(count):
                handle.seek(_u64(handle), os.SEEK_CUR)
            return

        raise SourceError(f"Unsupported GGUF array element type {element}.")

    raise SourceError(f"Unsupported GGUF value type {type_code}.")


def _read_value(handle, type_code):
    """One scalar value. Arrays are never read here, only skipped."""
    if type_code == _GGUF_STRING:
        return _gguf_string(handle)

    raw = _read_exact(handle, _GGUF_FIXED[type_code])

    if type_code == 6:
        return struct.unpack("<f", raw)[0]
    if type_code == 12:
        return struct.unpack("<d", raw)[0]
    if type_code == 7:
        return bool(raw[0])

    return int.from_bytes(raw, "little", signed=type_code in (1, 3, 5, 11))


def gguf_identity(path=None):
    """
    What the weights file declares about itself, from its header alone.

    This is the answerable half of "what am I made of". The tensors
    themselves are not readable here and would not help if they were: a
    4B cannot interpret its own quantised blocks, because it is not a
    thing that reads those numbers, it is what those numbers compute.
    The header, by contrast, is legible and true -- architecture, depth,
    width, and how each tensor was quantised.

    Returns None rather than raising. A missing or unparseable model file
    must degrade to saying nothing, never to taking a turn down.
    """
    if path is None:
        try:
            from core.config import MODEL_PATH
            path = MODEL_PATH
        except Exception:
            return None

    if not path or not os.path.isfile(path):
        return None

    try:
        stat = os.stat(path)
    except OSError:
        return None

    key = (os.path.abspath(path), stat.st_size, int(stat.st_mtime))

    if key in _gguf_cache:
        return _gguf_cache[key]

    wanted = (
        "architecture", "block_count", "context_length",
        "embedding_length", "head_count", "file_type", "general.name",
    )

    try:
        with open(path, "rb") as handle:
            if _read_exact(handle, 4) != b"GGUF":
                return None

            version = _u32(handle)
            tensor_count = _u64(handle)
            kv_count = _u64(handle)
            fields = {}

            for _ in range(kv_count):
                name = _gguf_string(handle)
                type_code = _u32(handle)

                keep = (
                    any(term in name for term in wanted)
                    and (type_code in _GGUF_FIXED or type_code == _GGUF_STRING)
                )

                if keep:
                    fields[name] = _read_value(handle, type_code)
                else:
                    _skip_value(handle, type_code)

            types = Counter()

            for _ in range(tensor_count):
                _gguf_string(handle)                  # tensor name
                handle.seek(8 * _u32(handle), os.SEEK_CUR)   # dimensions
                types[_u32(handle)] += 1              # ggml type
                handle.seek(8, os.SEEK_CUR)           # data offset
    except (OSError, SourceError, ValueError, struct.error):
        return None

    identity = {
        "file": os.path.basename(path),
        "bytes": stat.st_size,
        "gguf_version": version,
        "tensor_count": tensor_count,
        "fields": fields,
        "tensor_types": {
            _GGML_TYPES.get(code, f"type{code}"): count
            for code, count in types.most_common()
        },
    }

    _gguf_cache[key] = identity
    return identity


def weights_text():
    """One paragraph naming the weights, for the injected manifest."""
    identity = gguf_identity()

    if not identity:
        return ""

    fields = identity["fields"]

    def field(suffix):
        for name, value in fields.items():
            if name.endswith(suffix):
                return value
        return None

    parts = [f"Your weights are {identity['file']}"]
    architecture = field("general.architecture")

    if architecture:
        detail = [str(architecture)]
        for label, suffix in (
            ("layers", ".block_count"),
            ("width", ".embedding_length"),
            ("trained context", ".context_length"),
        ):
            value = field(suffix)
            if value:
                detail.append(f"{label} {value:,}" if isinstance(value, int)
                              else f"{label} {value}")
        parts.append(" (" + ", ".join(detail) + ")")

    parts.append(
        f", {identity['bytes'] / (1 << 30):.1f}GB, "
        f"{identity['tensor_count']:,} tensors quantised as "
        + ", ".join(f"{name} x{count}"
                    for name, count in identity["tensor_types"].items())
        + "."
    )
    parts.append(
        " This is the header of the file, which is all that is readable. "
        "The tensor data is not, and could not be interpreted by you if "
        "it were."
    )

    return "".join(parts)


def _shape(entries):
    """Files and lines per top-level area, largest first."""
    areas = {}

    for entry in entries:
        parts = entry["path"].split("/")
        area = "/".join(parts[:2]) if len(parts) > 2 else (
            parts[0] if len(parts) > 1 else "(root)"
        )
        files, lines = areas.get(area, (0, 0))
        areas[area] = (files + 1, lines + entry["lines"])

    return sorted(areas.items(), key=lambda pair: -pair[1][1])


def manifest_text():
    """
    The block injected into the runtime system message.

    States what exists, what changed, and what this listing does not
    cover -- so that silence about a file is not read as its absence.
    """
    entries = inventory()

    if not entries:
        return ""

    branch, commit = git_head()
    total_lines = sum(entry["lines"] for entry in entries)
    pieces = []

    header = (
        f"Your own source as it is on disk right now: {len(entries)} files, "
        f"{total_lines:,} lines"
    )
    if branch and commit:
        header += f", branch {branch} at {commit}"
    pieces.append(header + ".")

    pieces.append("Shape: " + "; ".join(
        f"{area} {files}f {lines:,}L" for area, (files, lines) in _shape(entries)
    ) + ".")

    recent = sorted(entries, key=lambda e: e["age_days"])[:RECENT_FILE_COUNT]
    pieces.append("Recently changed paths (recency only, never authorship): " + ", ".join(
        f"{entry['path']} ({entry['lines']}L)" for entry in recent
    ) + ".")

    weights = weights_text()
    if weights:
        pieces.append(weights)

    edits = recent_edits()
    if edits:
        pieces.append(
            "Your retained unattended edits, from verified local edit logs:\n"
            + "\n".join(edits)
        )
    else:
        pieces.append(
            "The verified local unattended-edit logs contain no retained "
            "edits. If you are asked what you changed, that is the answer: "
            "nothing is recorded."
        )

    pieces.append(
        "This is a directory of yourself, not a memory of doing the work. "
        "The Shape figures are directory aggregates, never per-file counts. "
        "A path missing from the recent list may still exist. The list says "
        "nothing about file contents or authorship. "
        "State what a file contains only after reading it, and state what "
        "you changed only if the edit log above says so. If you have not "
        "read a file, say so rather than describing it."
    )

    return "\n\n".join(pieces)
