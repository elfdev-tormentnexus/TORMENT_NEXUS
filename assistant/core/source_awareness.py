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
edit_guard.DENIED_FILES protects files from being rewritten. Every one of
them is readable here. Knowing what persona.py says is not the same
capability as changing it, and a guard that depended on the model not
knowing where it lived would be the weaker design -- see core/config.py,
where the authority boundary is stated as trusted Python code rather than
a model's alignment behaviour.

The single exclusion is credentials. `.model_api_key` is not part of what
this program is made of; it is the token protecting the agent interface,
and a model that can read it can print it into a reply on screen.

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

# Never readable. Not safety theatre -- exactly the files whose contents
# are an access token rather than a description of the program.
READ_DENIED_FILES = (
    os.path.join("assistant", ".model_api_key"),
)
READ_DENIED_SUFFIXES = (".key", ".pem", ".p12", ".pfx")
READ_DENIED_NAMES = (".env", ".model_api_key", ".netrc", "credentials")

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

# Tight recognition for questions trusted code can answer without asking the
# director to infer from a pathname. The resolver below still applies the
# ordinary containment and credential rules before it touches the path.
_SOURCE_PATH = re.compile(
    r"`([^`\r\n]+\.[A-Za-z0-9]{1,8})`"
    r"|(?<![\w.])((?:[\w.-]+[\\/])+[\w.-]+\.[A-Za-z0-9]{1,8}"
    r"|[\w.-]+\.(?:py|md))",
    re.IGNORECASE,
)
_DEFINITION = re.compile(
    r"\b(class|function)\s+(?:called\s+)?[`'\"]?([A-Za-z_]\w*)",
    re.IGNORECASE,
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
        size = os.path.getsize(full)
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


def source_facts(relative_path):
    """Exact, proof-carrying facts for one readable project path."""
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
        }

    try:
        with open(full, "rb") as handle:
            raw = handle.read()
    except OSError as error:
        raise SourceError(f"Could not read {relative_path}: {error}") from error

    definitions = []
    headings = []
    text = raw.decode("utf-8", "replace")

    if relative.casefold().endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None

        if tree is not None:
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
        "bytes": len(raw),
        "lines": line_count(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "definitions": tuple(definitions),
        "headings": tuple(headings),
    }


def _proof(facts):
    if not facts["exists"]:
        return f"Checked the project path `{facts['path']}` directly."
    return (
        f"Source receipt: `{facts['path']}`; {facts['bytes']:,} bytes; "
        f"sha256 `{facts['sha256']}`."
    )


def _mentioned_path(question):
    match = _SOURCE_PATH.search(str(question or ""))
    if not match:
        return None
    return (match.group(1) or match.group(2)).strip().replace("\\", "/")


def _retained_edit_lines():
    """Only edits that reached a retained write, from the logs that own them."""
    found = []

    for path in EDIT_LOGS:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                lines = [line.strip() for line in handle if line.strip()]
        except OSError:
            continue

        found.extend(line for line in lines if "] APPLIED " in line)

    return found


def answer_question(question):
    """Answer narrow self-source questions in trusted code, or return ``None``.

    The Goal 4 audit showed why this boundary has to be executable rather than
    aspirational. With the manifest present, the 4B copied a directory total
    onto a file in 8/8 trials and denied a real unnamed file in 7/7. Direct
    false-premise and authorship failures also occurred 6/6 with the manifest
    removed. The model is therefore the wrong component to decide whether a
    source fact is true; it may explain a checked fact, but it may not mint it.
    """
    path = _mentioned_path(question)
    if not path:
        return None

    lowered = " ".join(str(question or "").casefold().split())
    is_authorship = bool(
        re.search(
            r"\byou\b.{0,80}\b(?:added|changed|created|edited|wrote)\b"
            r"|\b(?:added|changed|created|edited|wrote)\b.{0,80}\bby you\b",
            lowered,
        )
    )
    wants_lines = "how many lines" in lowered or "line count" in lowered
    wants_bytes = "how many bytes" in lowered or "byte count" in lowered
    definition = _DEFINITION.search(str(question or ""))
    wants_existence = bool(
        re.search(r"\b(?:does|do|is|are)\b.{0,90}\b(?:exist|present|have)\b", lowered)
        or re.search(r"\b(?:exist|present)\b.{0,90}\?", lowered)
    )
    wants_outline = bool(
        re.search(
            r"\bwhat (?:does|is in)\b|\b(?:describe|summari[sz]e)\b.{0,60}\bfile\b",
            lowered,
        )
    )

    if not any(
        (is_authorship, wants_lines, wants_bytes, definition,
         wants_existence, wants_outline)
    ):
        return None

    try:
        facts = source_facts(path)
    except SourceError as error:
        return str(error)

    query_kind = (
        "authorship" if is_authorship
        else "definition" if definition
        else "line_count" if wants_lines
        else "byte_count" if wants_bytes
        else "existence" if wants_existence
        else "outline"
    )
    research_c.record(
        "source_grounding",
        "trusted_answer",
        artifact_digest=research_c.digest(facts["path"]),
        prompt_sha256=research_c.digest(question),
        sampler={},
        measurements={},
        outcomes={"query_kind": query_kind, "exists": facts["exists"]},
        binding={},
    )

    if is_authorship:
        normalized = facts["path"].casefold()
        matches = [
            line for line in _retained_edit_lines()
            if normalized in line.replace("\\", "/").casefold()
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
            + "\n".join(matches[-3:])
            + "\n\n"
            + _proof(facts)
        )

    if definition:
        kind, name = definition.group(1).casefold(), definition.group(2)
        matches = [
            item for item in facts["definitions"]
            if item[0] == kind and item[1] == name
        ]
        if matches:
            lines = ", ".join(str(item[2]) for item in matches)
            return (
                f"Yes. `{facts['path']}` defines {kind} `{name}` at "
                f"line {lines}. {_proof(facts)}"
            )
        return (
            f"No. `{facts['path']}` defines no {kind} named `{name}`. "
            f"{_proof(facts)}"
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
        return (
            f"Yes, `{facts['path']}` exists. {_proof(facts)}"
            if facts["exists"]
            else f"No, `{facts['path']}` does not exist. {_proof(facts)}"
        )

    if wants_outline:
        if not facts["exists"]:
            return f"`{facts['path']}` does not exist. {_proof(facts)}"

        if facts["definitions"]:
            shown = facts["definitions"][:24]
            outline = ", ".join(
                f"{kind} `{name}` (line {number})"
                for kind, name, number in shown
            )
            remainder = len(facts["definitions"]) - len(shown)
            suffix = f", plus {remainder} more" if remainder else ""
            return (
                f"Exact Python outline for `{facts['path']}`: {outline}{suffix}. "
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
