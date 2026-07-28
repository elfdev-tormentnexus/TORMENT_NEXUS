"""Fast, read-only runtime diagnostics for development and Pi deployment."""

import json
import os
import platform
import shutil

import requests

from core import config
from core import llm_server
from memory import extraction_rules
from voice import offline_voice


GIB = 1024 ** 3


def _line(ok, label, detail):
    return f"{'OK' if ok else 'WARN'}  {label}: {detail}"


def _memory_health(path):
    try:
        with open(path, "r", encoding="utf-8") as source:
            data = json.load(source)
    except Exception as error:
        return False, f"invalid JSON: {error}"

    if not isinstance(data, list):
        return False, "the top-level value is not a list"

    malformed = 0
    stale = 0
    retired = 0

    for item in data:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("memory"), str)
            or not item["memory"].strip()
        ):
            malformed += 1
            continue

        if item.get("superseded"):
            retired += 1
            continue

        if extraction_rules.reject_reason(item["memory"]):
            stale += 1

    if malformed:
        return False, (
            f"{len(data)} entries; {malformed} malformed "
            "(startup will preserve and skip them)"
        )

    if stale:
        return False, (
            f"{len(data)} entries; {stale} no longer meet the current "
            "durability rules (review with 'show memories')"
        )

    active = len(data) - retired
    return True, (
        f"valid JSON store with {active} active "
        f"and {retired} retired entr"
        + ("y" if retired == 1 else "ies")
    )


def _search_health():
    if config.SEARCH_BACKEND == "searxng":
        try:
            response = requests.get(
                config.SEARXNG_URL + "/search",
                params={
                    "q": "SearXNG",
                    "format": "json",
                    "categories": "general",
                },
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results")

            if not isinstance(results, list):
                return False, (
                    "SearXNG answered, but its JSON search endpoint returned "
                    "an unexpected response"
                )

            return True, (
                f"SearXNG JSON search works at {config.SEARXNG_URL} "
                f"({len(results)} results in probe)"
            )
        except Exception as error:
            return False, f"SearXNG unavailable: {error}"

    if config.SEARCH_BACKEND == "brave":
        ok = bool(config.BRAVE_API_KEY)
        return ok, (
            "Brave API key configured"
            if ok
            else "Brave selected but TORMENT_NEXUS_BRAVE_API_KEY is empty"
        )

    return False, f"unknown backend {config.SEARCH_BACKEND!r}"


def validation_blockers():
    """Conditions that must hold before a repair result can be believed.

    ``report()`` deliberately warns about anything an operator would want to
    know: a search backend that is down, a thin disk, missing voice files.
    None of those are code defects, and a self-heal session that treats them
    as such asks a coding model to fix a network service with a patch --
    three times, backing each attempt out again.

    So this is the narrow subset: the pieces without which the fixed
    regression run cannot execute or be trusted. Everything else stays
    advisory and reaches the model as context, never as a repair target.
    """
    problems = []

    if not os.path.isfile(config.LLAMA_SERVER):
        problems.append(f"llama-server is missing at {config.LLAMA_SERVER}")

    if not os.path.isfile(config.MODEL_PATH):
        problems.append(f"the model file is missing at {config.MODEL_PATH}")

    if not llm_server.is_alive(timeout=2):
        problems.append(f"the model API is not responding at {config.SERVER_URL}")
    elif llm_server.accepts_unauthenticated_requests(timeout=2):
        problems.append("the model API is answering without authentication")

    return problems


def advisory_warnings():
    """Environment warnings worth reporting but never worth repairing."""
    warnings = []

    memory_ok, memory_detail = _memory_health(config.MEMORY_FILE)
    if not memory_ok:
        warnings.append(f"memory: {memory_detail}")

    search_ok, search_detail = _search_health()
    if not search_ok:
        warnings.append(f"web search: {search_detail}")

    voice_issues = offline_voice.setup_issues(
        check_devices=False,
        require_microphone=False,
    )
    if voice_issues:
        warnings.append("voice: " + "; ".join(voice_issues))

    try:
        free_bytes = shutil.disk_usage(config.PROJECT_HOME).free
        if free_bytes < GIB:
            warnings.append(f"storage: only {free_bytes / GIB:.1f} GiB free")
    except OSError as error:
        warnings.append(f"storage: {error}")

    return warnings


def report():
    """Return a concise health report without changing project state."""
    lines = [
        "ASSISTANT HEALTH CHECK",
        "=" * 58,
        f"Platform: {platform.system()} {platform.machine()}",
    ]
    warnings = 0

    server_exists = os.path.isfile(config.LLAMA_SERVER)
    lines.append(_line(server_exists, "llama-server", config.LLAMA_SERVER))
    warnings += int(not server_exists)

    model_exists = os.path.isfile(config.MODEL_PATH)
    model_detail = config.MODEL_PATH

    if model_exists:
        model_detail += f" ({os.path.getsize(config.MODEL_PATH) / GIB:.2f} GiB)"

    lines.append(_line(model_exists, "model", model_detail))
    warnings += int(not model_exists)

    server_ready = llm_server.is_alive(timeout=2)
    server_secured = (
        server_ready
        and not llm_server.accepts_unauthenticated_requests(timeout=2)
    )
    lines.append(
        _line(
            server_ready and server_secured,
            "model API",
            (
                f"authenticated and responding at {config.SERVER_URL}"
                if server_ready and server_secured
                else f"responding without authentication at {config.SERVER_URL}"
                if server_ready
                else f"not responding at {config.SERVER_URL}"
            ),
        )
    )
    warnings += int(not (server_ready and server_secured))

    memory_ok, memory_detail = _memory_health(config.MEMORY_FILE)
    lines.append(
        _line(
            memory_ok,
            "memory",
            memory_detail,
        )
    )
    warnings += int(not memory_ok)

    search_ok, search_detail = _search_health()
    lines.append(_line(search_ok, "web search", search_detail))
    warnings += int(not search_ok)

    voice_issues = offline_voice.setup_issues(
        check_devices=False,
        require_microphone=False,
    )
    voice_ok = not voice_issues
    lines.append(
        _line(
            voice_ok,
            "voice",
            "offline speech files and packages ready"
            if voice_ok
            else "; ".join(voice_issues),
        )
    )
    warnings += int(not voice_ok)

    try:
        free_bytes = shutil.disk_usage(config.PROJECT_HOME).free
        disk_ok = free_bytes >= GIB
        disk_detail = f"{free_bytes / GIB:.1f} GiB free"
    except OSError as error:
        disk_ok = False
        disk_detail = str(error)

    lines.append(_line(disk_ok, "storage", disk_detail))
    warnings += int(not disk_ok)

    lines.extend([
        "",
        (
            "Overall: healthy"
            if warnings == 0
            else f"Overall: usable with {warnings} warning"
            + ("s" if warnings != 1 else "")
        ),
    ])

    return "\n".join(lines)
