"""
Generate small, self-contained deliverables under the top-level dump folder.

This is intentionally separate from self-editing. A requested calculator,
script, tiny website, or hardware sketch belongs in dump/, not mixed into the
assistant's own runtime. Generated files are validated and written atomically,
but never executed automatically.
"""

import ast
import json
import os
import re
import shutil
import tempfile
from datetime import datetime

import requests

from core.config import (
    CONTEXT_SIZE,
    DUMP_FOLDER,
    MODEL_REQUEST_HEADERS,
    SERVER_URL,
)
from core.file_utils import save_text
from ui import ui


MAX_FILES = 8
MAX_TOTAL_BYTES = 120_000
MAX_REQUEST_CHARS = 1_800
MAX_TOKENS = 2_400
CONTEXT_MARGIN = 160
TIMEOUT = 300

ALLOWED_EXTENSIONS = {
    ".bat", ".c", ".cpp", ".css", ".csv", ".h", ".hpp", ".html",
    ".ino", ".js", ".json", ".md", ".mjs", ".ps1", ".py", ".sh",
    ".svg", ".toml", ".ts", ".txt", ".yaml", ".yml",
}
ALLOWED_FILENAMES = {
    ".env.example", ".gitignore", "dockerfile", "license", "makefile",
}

SYSTEM = """Create a small, complete project from the developer's request.
Keep it practical enough to fit in at most 8 text files. Include a README with
setup and usage. Do not claim to have run or tested anything.

Return only this plain-text format:

PROJECT_NAME: short project name
SUMMARY: one sentence
=== FILE: relative/path.ext ===
complete file contents
=== END FILE ===

Repeat the FILE block for every file. Use relative paths only. Do not use code
fences and never place the END FILE marker inside file contents. Do not emit
binaries, base64 blobs, secrets, credentials, or files that download and run
remote code."""

_FILE_BLOCK = re.compile(
    r"^=== FILE:\s*(.+?)\s*===\s*\r?\n"
    r"(.*?)"
    r"^=== END FILE ===\s*$",
    re.MULTILINE | re.DOTALL,
)

_PROJECT_REQUEST = re.compile(
    r"^\s*(?:(?:can|could|would)\s+you\s+|please\s+)?"
    r"(?:build|create|make)\s+(?:me\s+)?(?:a|an|the)?\s*"
    r"(?:[a-z0-9_-]+\s+){0,3}"
    r"(?:project|app|application|website|web\s+page|script|program|"
    r"tool|utility|game|dashboard|bot|service|api|sketch|calculator|"
    r"tracker|converter|timer)\b",
    re.IGNORECASE,
)


class ProjectBuildError(Exception):
    pass


def looks_like_project_request(text):
    """Conservative natural-language gate for standalone deliverables."""
    return bool(text and _PROJECT_REQUEST.search(text))


def ensure_dump_folder():
    os.makedirs(DUMP_FOLDER, exist_ok=True)
    return DUMP_FOLDER


def _slug(text):
    value = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (value[:48].strip("-") or "project")


def _count_prompt_tokens(text):
    try:
        response = requests.post(
            SERVER_URL + "/tokenize",
            headers=MODEL_REQUEST_HEADERS,
            json={"content": text},
            timeout=10,
        )
        response.raise_for_status()
        return len(response.json().get("tokens") or [])
    except Exception:
        return max(1, len(text) // 3)


def _generate(request):
    user_text = request.strip()
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_text},
    ]
    prompt_text = SYSTEM + "\n" + user_text
    prompt_tokens = _count_prompt_tokens(prompt_text)
    ui.set_prompt_tokens(prompt_tokens)
    ui.set_status("Generating project files")
    available_output = CONTEXT_SIZE - prompt_tokens - CONTEXT_MARGIN

    if available_output < 400:
        raise ProjectBuildError(
            "The project description leaves too little model context for "
            "generated files. Shorten it or split the project into stages."
        )

    payload = {
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": min(MAX_TOKENS, available_output),
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }

    pieces = []

    try:
        with requests.post(
            SERVER_URL + "/v1/chat/completions",
            headers=MODEL_REQUEST_HEADERS,
            json=payload,
            timeout=TIMEOUT,
            stream=True,
        ) as response:
            response.raise_for_status()
            response.encoding = "utf-8"

            for raw in response.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue

                body = raw[5:].strip()

                if body == "[DONE]":
                    break

                try:
                    chunk = json.loads(body)
                except Exception:
                    continue

                usage = chunk.get("usage") or {}

                if usage.get("completion_tokens") is not None:
                    ui.set_stream_tokens(usage["completion_tokens"])

                choices = chunk.get("choices") or []

                if not choices:
                    continue

                piece = (
                    choices[0].get("delta", {}).get("content")
                    or ""
                )

                if piece:
                    pieces.append(piece)
                    ui.stream_append("", token_increment=1)

    except Exception as e:
        raise ProjectBuildError(f"Could not generate the project: {e}") from e

    raw_project = "".join(pieces).strip()

    if not raw_project:
        raise ProjectBuildError("The model returned an empty project.")

    return raw_project


def _safe_relative_path(path):
    candidate = (path or "").strip().replace("\\", "/")

    if (
        not candidate
        or candidate.startswith("/")
        or re.match(r"^[a-zA-Z]:", candidate)
    ):
        raise ProjectBuildError(f"Unsafe project path: {path!r}")

    normalized = os.path.normpath(candidate).replace("\\", "/")

    if normalized in (".", "..") or normalized.startswith("../"):
        raise ProjectBuildError(f"Project path escapes its folder: {path!r}")

    extension = os.path.splitext(normalized)[1].lower()
    basename = os.path.basename(normalized).lower()

    if (
        extension not in ALLOWED_EXTENSIONS
        and basename not in ALLOWED_FILENAMES
    ):
        raise ProjectBuildError(
            f"Unsupported generated file type {extension or '(none)'}: "
            f"{normalized}"
        )

    return normalized


def _validate_file(path, content):
    if "\x00" in content:
        raise ProjectBuildError(f"{path} contains binary/null data.")

    if path.lower().endswith(".py"):
        try:
            ast.parse(content, filename=path)
        except SyntaxError as e:
            raise ProjectBuildError(
                f"{path} has invalid Python syntax at line {e.lineno}: {e.msg}"
            ) from e

    if path.lower().endswith(".json"):
        try:
            json.loads(content)
        except Exception as e:
            raise ProjectBuildError(f"{path} contains invalid JSON: {e}") from e


def _parse(raw_project):
    ui.set_status("Parsing generated project")

    name_match = re.search(
        r"^PROJECT_NAME:\s*(.+?)\s*$",
        raw_project,
        re.MULTILINE,
    )
    summary_match = re.search(
        r"^SUMMARY:\s*(.+?)\s*$",
        raw_project,
        re.MULTILINE,
    )
    blocks = _FILE_BLOCK.findall(raw_project)

    if not blocks:
        raise ProjectBuildError(
            "The model did not return any valid FILE blocks."
        )

    if len(blocks) > MAX_FILES:
        raise ProjectBuildError(
            f"The model returned {len(blocks)} files; the limit is {MAX_FILES}."
        )

    files = []
    seen = set()
    total_bytes = 0

    for raw_path, raw_content in blocks:
        path = _safe_relative_path(raw_path)
        key = os.path.normcase(path)

        if key in seen:
            raise ProjectBuildError(f"The model returned {path} twice.")

        seen.add(key)
        content = raw_content.rstrip() + "\n"
        total_bytes += len(content.encode("utf-8"))

        if total_bytes > MAX_TOTAL_BYTES:
            raise ProjectBuildError(
                f"Generated project exceeds {MAX_TOTAL_BYTES:,} bytes."
            )

        ui.set_status(f"Validating {path}")
        _validate_file(path, content)
        files.append((path, content))

    name = (
        name_match.group(1).strip()
        if name_match
        else os.path.splitext(files[0][0])[0]
    )
    summary = (
        summary_match.group(1).strip()
        if summary_match
        else "Generated project"
    )

    return name, summary, files


def _write_project(request, name, summary, files):
    ensure_dump_folder()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{stamp}_{_slug(name)}"
    destination = os.path.join(DUMP_FOLDER, base_name)
    counter = 1

    while os.path.exists(destination):
        destination = os.path.join(DUMP_FOLDER, f"{base_name}_{counter}")
        counter += 1

    temp_folder = tempfile.mkdtemp(prefix=".building_", dir=DUMP_FOLDER)

    try:
        for relative, content in files:
            ui.set_status(f"Writing {relative}")
            target = os.path.realpath(os.path.join(temp_folder, relative))
            temp_cmp = os.path.normcase(os.path.realpath(temp_folder))
            target_cmp = os.path.normcase(target)

            if not target_cmp.startswith(temp_cmp + os.sep):
                raise ProjectBuildError(
                    f"Generated path escaped its project folder: {relative}"
                )

            save_text(target, content)

        manifest = (
            f"Project: {name}\n"
            f"Created: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Summary: {summary}\n\n"
            f"Original request:\n{request.strip()}\n\n"
            "Files:\n"
            + "\n".join(f"- {path}" for path, _ in files)
            + "\n\nGenerated files were validated but not executed automatically.\n"
        )
        save_text(os.path.join(temp_folder, "PROJECT_INFO.txt"), manifest)

        ui.set_status("Finalizing dump project")
        os.replace(temp_folder, destination)

    except Exception:
        shutil.rmtree(temp_folder, ignore_errors=True)
        raise

    return {
        "name": name,
        "summary": summary,
        "folder": destination,
        "files": [path for path, _ in files],
    }


def build_project(request):
    if not request or len(request.strip()) < 8:
        return None, "Describe the project in a little more detail."

    if len(request.strip()) > MAX_REQUEST_CHARS:
        return None, (
            f"Project description is too long ({len(request.strip()):,} "
            f"characters; limit {MAX_REQUEST_CHARS:,})."
        )

    ui.set_status("Planning dump project")

    try:
        raw_project = _generate(request)
        name, summary, files = _parse(raw_project)
        return _write_project(request, name, summary, files), None
    except ProjectBuildError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Project build failed: {e}"


def list_projects():
    ensure_dump_folder()
    projects = []

    for name in sorted(os.listdir(DUMP_FOLDER), reverse=True):
        path = os.path.join(DUMP_FOLDER, name)

        if os.path.isdir(path) and not name.startswith(".building_"):
            projects.append(path)

    return projects


def format_result(project, error=None):
    if error:
        return (
            "PROJECT BUILD FAILED\n"
            + "=" * 58 + "\n\n"
            + error
        )

    lines = [
        "PROJECT CREATED",
        "=" * 58,
        "",
        f"Name:    {project['name']}",
        f"Summary: {project['summary']}",
        f"Folder:  {project['folder']}",
        "",
        "Files:",
    ]
    lines.extend(f"  - {path}" for path in project["files"])
    lines.extend([
        "  - PROJECT_INFO.txt",
        "",
        "Generated files were validated but not executed automatically.",
    ])
    return "\n".join(lines)
