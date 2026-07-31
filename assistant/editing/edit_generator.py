"""
Turns "add error handling to save_memory" into an actual code change.

This is the piece that never existed. write_comment() inserted a fixed
string; nothing anywhere converted intent into code.

Design choice that matters on a 4B model: it does NOT regenerate the
file. It emits one find/replace block, which is then verified to match
the file exactly once before being applied. Small models are far more
reliable at surgical edits than at rewriting a whole file, and a
whole-file rewrite would need enormous max_tokens and would silently
drop code it did not think was important.

The "exactly once" check is the load-bearing part. If the find text is
missing the model hallucinated it; if it appears twice the edit is
ambiguous. Both are refused rather than guessed at.
"""

import ast
import json
import re
import requests

from core import research_c
from core.config import (
    CONTEXT_SIZE,
    DEBUG,
    MODEL_PATH,
    MODEL_REQUEST_HEADERS,
    SERVER_URL,
    SUPER_DEV_WORKER_MODEL_PATH,
    SUPER_DEV_WORKER_URL,
)
from ui import ui


TIMEOUT = 180
MAX_TOKENS = 900
CONTEXT_MARGIN = 160
MAX_INPUT_TOKENS = CONTEXT_SIZE - MAX_TOKENS - CONTEXT_MARGIN
MAX_EXCERPT_LINES = 150

# Hard ceiling on /tokenize round-trips per edit. Candidates are ranked, and
# in practice the budget is spent within the first handful; the rest were
# only ever going to be measured and discarded.
MAX_CANDIDATE_TRIALS = 12
MAX_CONSECUTIVE_MISSES = 3


SYSTEM = """You make small, surgical edits to Python files.

You will be given a file and a requested change. Reply with ONE JSON
object and nothing else:

{"find": "<exact text from the file>",
 "replace": "<what it becomes>",
 "explanation": "<one sentence>"}

Rules for "find":
- It must be copied EXACTLY from the file, character for character,
  including indentation.
- It must appear exactly ONCE in the file. Include surrounding lines
  if needed to make it unique.
- Keep it as short as possible while staying unique.

Rules for "replace":
- Complete, valid Python at the same indentation level.
- Change only what was asked. Do not reformat anything else.

For oversized files you may receive selected source excerpts and a file
outline. Excerpt marker lines and the outline are NOT part of the file. Never
copy a marker or outline line into "find" or "replace". The code inside each
excerpt is exact source text.

If the change cannot be made, reply:
{"find": null, "replace": null, "explanation": "<why not>"}"""


def _extract_json(raw):
    if not raw:
        return None

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return None


_TERM_STOPWORDS = {
    "about", "adjust", "also", "and", "change", "could", "default",
    "ensure", "file", "for", "from", "have", "into", "like", "make",
    "modify", "more", "path", "please", "point", "settings", "such",
    "that", "the", "this", "to", "update", "updating", "use", "with",
}


def _count_tokens(text, server_url=SERVER_URL, headers=MODEL_REQUEST_HEADERS):
    """Use llama.cpp's tokenizer, with a safe pessimistic fallback."""
    try:
        response = requests.post(
            server_url + "/tokenize",
            headers=headers,
            json={"content": text},
            timeout=10,
        )
        response.raise_for_status()
        return len(response.json().get("tokens") or [])
    except Exception:
        return max(1, len(text) // 3)


def _count_for_endpoint(text, server_url, headers):
    """Keep the ordinary call shape stable for instrumentation and tests."""
    if server_url == SERVER_URL and headers is MODEL_REQUEST_HEADERS:
        return _count_tokens(text)
    return _count_tokens(text, server_url, headers)


def _request_terms(request):
    terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", request or "")
        if term.lower() not in _TERM_STOPWORDS
    }
    return sorted(terms, key=lambda value: (-len(value), value))


def _source_outline(tree):
    entries = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entries.append(
                f"- function {node.name} (lines {node.lineno}-{node.end_lineno})"
            )
        elif isinstance(node, ast.ClassDef):
            entries.append(
                f"- class {node.name} (lines {node.lineno}-{node.end_lineno})"
            )

    entries.sort()
    return "\n".join(entries[:120])


def _candidate_ranges(file_content, request):
    """Rank exact source windows likely to contain the requested edit."""
    lines = file_content.splitlines()
    terms = _request_terms(request)
    candidates = {}

    def add(start, end, score):
        start = max(1, int(start))
        end = min(len(lines), int(end))

        if end < start:
            return

        if end - start + 1 > MAX_EXCERPT_LINES:
            end = start + MAX_EXCERPT_LINES - 1

        key = (start, end)
        candidates[key] = max(score, candidates.get(key, 0))

    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Assign,
                    ast.AnnAssign,
                ),
            ):
                continue

            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            node_text = "\n".join(lines[start - 1:end]).lower()
            node_name = getattr(node, "name", "").lower()
            score = 0

            for term in terms:
                if term in node_name:
                    score += 14

                score += min(3, node_text.count(term)) * 2

            if score:
                if end - start + 1 <= MAX_EXCERPT_LINES:
                    add(start, end, score + 5)
                else:
                    # Large functions/classes are represented by precise
                    # windows around matching lines, never silently truncated
                    # only at their beginning.
                    for line_number in range(start, end + 1):
                        lower = lines[line_number - 1].lower()
                        line_score = sum(
                            4 for term in terms if term in lower
                        )

                        if line_score:
                            add(
                                line_number - 16,
                                line_number + 28,
                                score + line_score,
                            )

    for line_number, line in enumerate(lines, start=1):
        lower = line.lower()
        score = sum(3 for term in terms if term in lower)

        if score:
            add(line_number - 12, line_number + 20, score)

    if not candidates:
        add(1, min(len(lines), 120), 1)

    return sorted(
        (
            (score, start, end)
            for (start, end), score in candidates.items()
        ),
        reverse=True,
    ), tree


def _merge_ranges(ranges):
    merged = []

    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 3:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    return merged


def _render_excerpts(file_content, ranges):
    lines = file_content.splitlines()
    sections = []

    for start, end in _merge_ranges(ranges):
        sections.append(
            f"--- SOURCE EXCERPT lines {start}-{end} ---\n"
            + "\n".join(lines[start - 1:end])
        )

    return "\n\n".join(sections)


def _user_message(filename, source_text, request, compact=False, outline=""):
    if compact:
        source_label = (
            "The file is too large for one model request. The source below "
            "contains selected exact excerpts. Marker lines are not source."
        )
        outline_block = f"\n\nFILE OUTLINE (not source):\n{outline}" if outline else ""
    else:
        source_label = "The complete exact file follows."
        outline_block = ""

    return (
        f"FILE: {filename}\n"
        f"{source_label}"
        f"{outline_block}\n\n"
        f"```python\n{source_text}\n```\n\n"
        f"REQUESTED CHANGE:\n{request}"
    )


def _budgeted_user_message(filename, file_content, request,
                           server_url=SERVER_URL, headers=MODEL_REQUEST_HEADERS):
    """Return a prompt that is guaranteed to leave room for the patch."""
    complete = _user_message(filename, file_content, request)
    complete_tokens = _count_for_endpoint(SYSTEM + "\n" + complete, server_url, headers)

    if complete_tokens <= MAX_INPUT_TOKENS:
        return complete, complete_tokens, False

    candidates, tree = _candidate_ranges(file_content, request)
    outline = _source_outline(tree) if tree is not None else ""
    selected = []
    best_message = None
    best_tokens = None

    # Every trial below is an HTTP round-trip to /tokenize. _candidate_ranges
    # emits one range per matching line, so a common term in a large file
    # produced hundreds of them -- measured at 386 for "fix the speech rate"
    # against offline_voice.py, roughly ten seconds of sequential requests
    # before the patch request even started. Candidates are score-ordered, so
    # the tail was never going to be selected anyway; only the head is worth
    # paying for.
    consecutive_misses = 0

    for _score, start, end in candidates[:MAX_CANDIDATE_TRIALS]:
        trial_ranges = selected + [(start, end)]
        excerpts = _render_excerpts(file_content, trial_ranges)
        trial = _user_message(
            filename,
            excerpts,
            request,
            compact=True,
            outline=outline,
        )
        tokens = _count_for_endpoint(SYSTEM + "\n" + trial, server_url, headers)

        if tokens <= MAX_INPUT_TOKENS:
            selected = trial_ranges
            best_message = trial
            best_tokens = tokens
            consecutive_misses = 0
            continue

        # A later range can still be small enough to fit, so one miss is not
        # the end. A run of them means the budget is genuinely spent.
        consecutive_misses += 1

        if consecutive_misses >= MAX_CONSECUTIVE_MISSES:
            break

    if best_message is not None:
        return best_message, best_tokens, True

    # Even a large outline can crowd out the first source window. Retry with
    # no outline before refusing the edit.
    _score, start, end = candidates[0]
    excerpts = _render_excerpts(file_content, [(start, end)])
    compact = _user_message(
        filename,
        excerpts,
        request,
        compact=True,
    )
    compact_tokens = _count_for_endpoint(SYSTEM + "\n" + compact, server_url, headers)
    return compact, compact_tokens, True


def generate_edit(filename, file_content, request, *, server_url=None, headers=None):
    """
    Returns (edit_dict, error_message). Exactly one is None.

    edit_dict is {"find", "replace", "explanation"} and has already
    been checked for uniqueness against the file.
    """
    endpoint = (server_url or SERVER_URL).rstrip("/")
    request_headers = MODEL_REQUEST_HEADERS if headers is None else headers
    user_message, prompt_tokens, compacted = _budgeted_user_message(
        filename,
        file_content,
        request,
        endpoint,
        request_headers,
    )
    ui.set_prompt_tokens(prompt_tokens)

    available_output = CONTEXT_SIZE - prompt_tokens - CONTEXT_MARGIN

    if available_output < 160:
        return None, (
            "The selected edit context is still too large for this model. "
            "Name the function or setting you want changed so the assistant "
            "can select a smaller source excerpt."
        )

    response_tokens = min(MAX_TOKENS, available_output)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_message},
    ]
    payload = {
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": response_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    payload.update(research_c.request_fields())
    timer = research_c.Timer()

    try:
        response = requests.post(
            endpoint + "/v1/chat/completions",
            headers=request_headers,
            json=payload,
            timeout=TIMEOUT,
        )

        result = response.json()

    except Exception as e:
        return None, f"Could not reach the model: {e}"

    if getattr(response, "status_code", 200) >= 400:
        detail = result.get("error") if isinstance(result, dict) else result
        return None, f"Model rejected the edit request: {detail}"

    choices = result.get("choices")

    if not choices:
        return None, f"Unexpected response from the model: {result}"

    choice = choices[0]
    raw = (choice.get("message", {}).get("content") or "").strip()
    binding_path = (
        SUPER_DEV_WORKER_MODEL_PATH
        if SUPER_DEV_WORKER_URL
        and endpoint.casefold() == SUPER_DEV_WORKER_URL.casefold()
        else MODEL_PATH
    )

    def record(outcomes, spans=()):
        research_c.record(
            "super_dev" if binding_path == SUPER_DEV_WORKER_MODEL_PATH else "edit",
            "patch",
            artifact_digest=research_c.digest(filename, request),
            prompt_sha256=research_c.prompt_digest(messages),
            sampler=research_c.sampler_record(payload),
            measurements=research_c.measure(
                choice.get("logprobs"),
                raw,
                spans=spans or None,
            ),
            outcomes=outcomes,
            timing={
                "wall_seconds": timer.elapsed(),
                "server": result.get("timings"),
            },
            binding=research_c.model_binding(
                binding_path,
                role=(
                    "worker"
                    if binding_path == SUPER_DEV_WORKER_MODEL_PATH
                    else "director"
                ),
            ),
        )

    if DEBUG:
        print("\nDEBUG EDIT RAW:")
        print(
            f"[prompt tokens: {prompt_tokens}; "
            f"compact excerpts: {compacted}]"
        )
        print(raw)

    data = _extract_json(raw)

    if not data:
        record({"parseable": False, "unique_patch": False})
        return None, "The model did not return usable JSON."

    find = data.get("find")
    replace = data.get("replace")
    explanation = (data.get("explanation") or "").strip()

    if find is None:
        record(
            {"parseable": True, "declined": True, "unique_patch": False},
            spans=(explanation,),
        )
        return None, explanation or "The model declined to make this change."

    if not isinstance(find, str) or not isinstance(replace, str):
        record({"parseable": True, "valid_types": False, "unique_patch": False})
        return None, "The model returned the wrong types for find/replace."

    if not find.strip():
        record({"parseable": True, "empty_find": True, "unique_patch": False})
        return None, "The model returned an empty search block."

    # The load-bearing check.
    occurrences = file_content.count(find)

    if occurrences == 0:
        record(
            {"parseable": True, "occurrences": 0, "unique_patch": False},
            spans=(find, replace),
        )
        return None, (
            "The text the model wants to replace is not in the file.\n"
            "It most likely paraphrased instead of copying exactly.\n\n"
            "It was looking for:\n"
            f"{find[:400]}"
        )

    if occurrences > 1:
        record(
            {
                "parseable": True,
                "occurrences": occurrences,
                "unique_patch": False,
            },
            spans=(find, replace),
        )
        return None, (
            f"That text appears {occurrences} times in the file, so the "
            "edit is ambiguous.\nTry a more specific request naming the "
            "function or class."
        )

    if find == replace:
        record(
            {"parseable": True, "no_op": True, "unique_patch": False},
            spans=(find, replace),
        )
        return None, "The model returned an edit that changes nothing."

    record(
        {"parseable": True, "occurrences": 1, "unique_patch": True},
        spans=(find, replace),
    )
    return {
        "find": find,
        "replace": replace,
        "explanation": explanation,
    }, None
