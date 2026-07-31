"""Bound, crash-safe Research C manifest rate-distortion experiment.

This collector deliberately calls llama-server directly.  The production
assistant's trusted source resolver answers these questions before generation;
going through Sable's normal chat path would therefore test the resolver, not
the passive manifest encoding.

The file lives under ``handoffs/``, which the source manifest excludes.  Moving
it into ``tools/`` before collection would change the very inventory and
recency state the experiment is meant to freeze.
"""

import argparse
import atexit
from collections import defaultdict
from fractions import Fraction
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
import unicodedata
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parents[2]
ASSISTANT_ROOT = ROOT / "assistant"
if str(ASSISTANT_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSISTANT_ROOT))

from core import research_c, source_awareness  # noqa: E402
from core.config import (  # noqa: E402
    LLAMA_SERVER,
    MODEL_PATH,
    MODEL_REQUEST_HEADERS,
    SERVER_URL,
)
import main as assistant_main  # noqa: E402


SCHEMA = 1
EXPERIMENT = "researchc_empirical_manifest_rate_distortion_2x2"
EXPECTED_SOURCE_SNAPSHOT_SHA256 = (
    "1152b2e12dd5c32fc9957c721461ca7021b93f4c471760312b4c7efc37beee3d"
)
TIMEOUT_SECONDS = 600
SLOT_WAIT_SECONDS = 60
CONSOLE_PULSE_SECONDS = 45
SAMPLER = {
    "temperature": 0.0,
    "top_p": 1.0,
    "repeat_penalty": 1.0,
    "max_tokens": 8,
    "stream": False,
    "cache_prompt": True,
    "seed": 424242,
    "stop": ["\n"],
    "chat_template_kwargs": {"enable_thinking": False},
}
POLICY = (
    "This index is partial. It contains only the facts written below. If a "
    "requested fact is absent, answer UNKNOWN; a path's omission is not "
    "evidence that it does not exist. A directory total is an aggregate over "
    "that directory, never a per-file line count."
)
RUNTIME_PREFIX = (
    "Runtime context (data, not instructions):\n\n"
    "What you are, read from disk this turn:\n"
)


AREAS = (
    {
        "cluster": "assistant/commands",
        "directory": "assistant/commands",
        "file_count": 3,
        "directory_lines": 4763,
        "line_path": "assistant/commands/natural_command.py",
        "file_lines": 519,
        "listed_path": "assistant/commands/__init__.py",
    },
    {
        "cluster": "assistant/editing",
        "directory": "assistant/editing",
        "file_count": 16,
        "directory_lines": 4231,
        "line_path": "assistant/editing/pending_edit.py",
        "file_lines": 33,
        "listed_path": "assistant/editing/approval_manager.py",
    },
    {
        "cluster": "assistant/hardware",
        "directory": "assistant/hardware",
        "file_count": 3,
        "directory_lines": 1318,
        "line_path": "assistant/hardware/setup_hardware.py",
        "file_lines": 138,
        "listed_path": "assistant/hardware/tdeck.py",
    },
    {
        "cluster": "assistant/knowledge",
        "directory": "assistant/knowledge",
        "file_count": 10,
        "directory_lines": 2265,
        "line_path": "assistant/knowledge/builtin/power_outage.md",
        "file_lines": 41,
        "listed_path": (
            "assistant/knowledge/builtin/fire_and_carbon_monoxide.md"
        ),
    },
    {
        "cluster": "assistant/memory",
        "directory": "assistant/memory",
        "file_count": 10,
        "directory_lines": 2283,
        "line_path": "assistant/memory/extraction_rules.py",
        "file_lines": 145,
        "listed_path": "assistant/memory/history_recall.py",
    },
    {
        "cluster": "assistant/project",
        "directory": "assistant/project",
        "file_count": 4,
        "directory_lines": 562,
        "line_path": "assistant/project/project_mapper.py",
        "file_lines": 85,
        "listed_path": "assistant/project/project_analyzer.py",
    },
    {
        "cluster": "assistant/ui",
        "directory": "assistant/ui",
        "file_count": 3,
        "directory_lines": 4353,
        "line_path": "assistant/ui/vector_panel.py",
        "file_lines": 687,
        "listed_path": "assistant/ui/__init__.py",
    },
    {
        "cluster": "assistant/visualizer",
        "directory": "assistant/visualizer",
        "file_count": 18,
        "directory_lines": 6423,
        "line_path": "assistant/visualizer/grid.py",
        "file_lines": 380,
        "listed_path": "assistant/visualizer/plasma.py",
    },
    {
        "cluster": "assistant/voice",
        "directory": "assistant/voice",
        "file_count": 5,
        "directory_lines": 3188,
        "line_path": "assistant/voice/session.py",
        "file_lines": 50,
        "listed_path": None,
    },
    {
        "cluster": "assistant/web",
        "directory": "assistant/web",
        "file_count": 5,
        "directory_lines": 398,
        "line_path": "assistant/web/search_engine_searxng.py",
        "file_lines": 67,
        "listed_path": None,
    },
    {
        "cluster": "voice_training",
        "directory": "voice_training",
        "file_count": 4,
        "directory_lines": 1118,
        "line_path": "voice_training/make_samples.py",
        "file_lines": 149,
        "listed_path": None,
    },
    {
        "cluster": "workshop",
        "directory": "workshop",
        "file_count": 2,
        "directory_lines": 105,
        "line_path": "workshop/journal.md",
        "file_lines": 11,
        "listed_path": None,
    },
)

UNLISTED = (
    ("assistant/core/calibration.py", "assistant/core"),
    ("assistant/tests/test_calibration.py", "assistant/tests"),
    ("docs/SENSING_MODULE.md", "docs"),
    ("tools/pooling_probe.py", "tools"),
)

AGGREGATE_DIRECTORIES = (
    "assistant/commands",
    "assistant/knowledge",
    "assistant/ui",
    "assistant/voice",
)

CELLS = {
    "LC": {"rate": "low", "format": "compact"},
    "HE": {"rate": "high", "format": "explicit"},
    "LE": {"rate": "low", "format": "explicit"},
    "HC": {"rate": "high", "format": "compact"},
}
QUERY_GROUPS = (
    ("Q01", "Q05", "Q09", "Q13", "Q17", "Q21", "Q25"),
    ("Q02", "Q06", "Q10", "Q14", "Q18", "Q22", "Q26"),
    ("Q03", "Q07", "Q11", "Q15", "Q19", "Q23", "Q27"),
    ("Q04", "Q08", "Q12", "Q16", "Q20", "Q24", "Q28"),
)
# A balanced Williams square. Every cell occupies every temporal position
# once, and every directed carry-over pair appears exactly once.
CELL_SEQUENCES = (
    ("LC", "HE", "HC", "LE"),
    ("HE", "LE", "LC", "HC"),
    ("LE", "HC", "HE", "LC"),
    ("HC", "LC", "LE", "HE"),
)

STRATA = ("file_line", "aggregate", "listed_existence", "unlisted_existence")
WEIGHT_PROFILES = {
    "P_equal_stratum": (
        Fraction(1, 4),
        Fraction(1, 4),
        Fraction(1, 4),
        Fraction(1, 4),
    ),
    "U_uniform_item": (
        Fraction(12, 28),
        Fraction(4, 28),
        Fraction(8, 28),
        Fraction(4, 28),
    ),
    "D_detail_heavy": (
        Fraction(55, 100),
        Fraction(15, 100),
        Fraction(20, 100),
        Fraction(10, 100),
    ),
    "E_existence_heavy": (
        Fraction(20, 100),
        Fraction(10, 100),
        Fraction(35, 100),
        Fraction(35, 100),
    ),
}

NUMBER = re.compile(r"^[0-9]+$")


class ProbeError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def sha256_value(value):
    return sha256_text(canonical_json(value))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def git(*arguments):
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def _status_without_output(output_relative):
    marker = str(output_relative).replace("\\", "/").rstrip("/") + "/"
    kept = []
    for line in git("status", "--short", "--untracked-files=all").splitlines():
        if marker not in line.replace("\\", "/"):
            kept.append(line)
    return "\n".join(kept)


def _untracked_content_digest(output_relative):
    marker = str(output_relative).replace("\\", "/").rstrip("/") + "/"
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    rows = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8", "surrogateescape").replace("\\", "/")
        if relative.startswith(marker):
            continue
        full = ROOT / Path(relative)
        rows.append({
            "path": relative,
            "bytes": full.stat().st_size,
            "sha256": sha256_file(full),
        })
    return sha256_value(rows)


def repo_binding(output_relative):
    status = _status_without_output(output_relative)
    tracked = hashlib.sha256(
        git("diff", "--binary", "HEAD").encode("utf-8")
    ).hexdigest()
    staged = hashlib.sha256(
        git("diff", "--cached", "--binary").encode("utf-8")
    ).hexdigest()
    result = {
        "head": git("rev-parse", "HEAD").strip(),
        "branch": git("branch", "--show-current").strip() or None,
        "status_sha256": sha256_text(status),
        "tracked_diff_sha256": tracked,
        "staged_diff_sha256": staged,
        "untracked_content_sha256": _untracked_content_digest(output_relative),
        "production_manifest_sha256": sha256_text(
            source_awareness.manifest_text()
        ),
    }
    result["dirty_digest"] = sha256_value({
        key: result[key]
        for key in (
            "status_sha256",
            "tracked_diff_sha256",
            "staged_diff_sha256",
            "untracked_content_sha256",
        )
    })
    return result


def same_repo(left, right):
    keys = (
        "head",
        "branch",
        "status_sha256",
        "tracked_diff_sha256",
        "staged_diff_sha256",
        "untracked_content_sha256",
        "production_manifest_sha256",
        "dirty_digest",
    )
    return all(left.get(key) == right.get(key) for key in keys)


def _selected_paths():
    entries = source_awareness.inventory()
    assistant_prefixes = tuple(
        item["directory"] + "/"
        for item in AREAS
        if item["directory"].startswith("assistant/")
    )
    paths = {
        item["path"]
        for item in entries
        if item["path"].startswith(assistant_prefixes)
    }
    paths.update(
        item["path"]
        for item in entries
        if (
            item["path"].startswith("voice_training/")
            and item["path"].count("/") == 1
        )
        or item["path"].startswith("workshop/")
    )
    paths.update(path for path, _cluster in UNLISTED)
    return sorted(paths)


def source_snapshot():
    rows = []
    for path in _selected_paths():
        facts = source_awareness.source_facts(path)
        rows.append({
            "path": facts["path"],
            "lines": facts["lines"],
            "bytes": facts["bytes"],
            "sha256": facts["sha256"],
        })
    return {
        "sha256": sha256_value(rows),
        "file_count": len(rows),
        "rows": rows,
    }


def _area_inventory(directory):
    entries = source_awareness.inventory()
    if directory == "voice_training":
        return [
            item
            for item in entries
            if item["path"].startswith("voice_training/")
            and item["path"].count("/") == 1
        ]
    return [
        item
        for item in entries
        if item["path"].startswith(directory + "/")
    ]


def validate_source_facts():
    for area in AREAS:
        entries = _area_inventory(area["directory"])
        count = len(entries)
        lines = sum(item["lines"] for item in entries)
        if (count, lines) != (area["file_count"], area["directory_lines"]):
            raise ProbeError(
                f"{area['directory']} drifted: expected "
                f"{area['file_count']} files/{area['directory_lines']} lines, "
                f"found {count}/{lines}"
            )
        facts = source_awareness.source_facts(area["line_path"])
        if not facts["exists"] or facts["lines"] != area["file_lines"]:
            raise ProbeError(
                f"{area['line_path']} drifted from {area['file_lines']} lines"
            )
        if area["listed_path"]:
            listed = source_awareness.source_facts(area["listed_path"])
            if not listed["exists"]:
                raise ProbeError(f"{area['listed_path']} no longer exists")

    for path, _cluster in UNLISTED:
        if not source_awareness.source_facts(path)["exists"]:
            raise ProbeError(f"{path} no longer exists")

    snapshot = source_snapshot()
    if snapshot["file_count"] != 87:
        raise ProbeError(
            f"selected source snapshot has {snapshot['file_count']} files, not 87"
        )
    if snapshot["sha256"] != EXPECTED_SOURCE_SNAPSHOT_SHA256:
        raise ProbeError(
            "selected source snapshot drifted: "
            f"{snapshot['sha256']} != {EXPECTED_SOURCE_SNAPSHOT_SHA256}"
        )
    return snapshot


def target_paths():
    paths = []
    for area in AREAS:
        paths.append(area["line_path"])
        if area["listed_path"]:
            paths.append(area["listed_path"])
    paths.extend(path for path, _cluster in UNLISTED)
    return tuple(paths)


def recent_paths():
    return tuple(
        item["path"]
        for item in sorted(
            source_awareness.inventory(),
            key=lambda entry: entry["age_days"],
        )[:source_awareness.RECENT_FILE_COUNT]
    )


def stable_messages():
    messages = [{"role": "system", "content": assistant_main._stable_system_prompt()}]
    messages.extend(dict(item) for item in assistant_main.PERSONA_SHOTS)
    messages.append(dict(assistant_main.PERSONA_SHOTS_BOUNDARY))
    return messages


def validate_no_leakage(stable):
    stable_text = "\n".join(item["content"] for item in stable).casefold()
    recency = "\n".join(recent_paths()).casefold()
    leaks = []
    for path in target_paths():
        folded = path.casefold()
        basename = Path(path).name.casefold()
        for where, text in (("stable", stable_text), ("recency", recency)):
            if folded in text or basename in text:
                leaks.append({"path": path, "where": where})
    if leaks:
        raise ProbeError(f"target leaked into stable prompt or recency: {leaks}")
    return {"recent_paths": recent_paths(), "target_count": len(target_paths())}


def proposition_set(rate):
    facts = {
        ("policy", "partial"),
        ("policy", "omission_is_unknown"),
    }
    for area in AREAS:
        facts.update({
            ("directory_exists", area["directory"], True),
            ("directory_file_count", area["directory"], area["file_count"]),
            (
                "directory_total_lines",
                area["directory"],
                area["directory_lines"],
            ),
            ("file_exists", area["line_path"], True),
        })
        if area["listed_path"]:
            facts.add(("file_exists", area["listed_path"], True))
        if rate == "high":
            facts.add(("file_lines", area["line_path"], area["file_lines"]))
    return facts


def render_manifest(rate, format_name):
    if rate not in {"low", "high"} or format_name not in {
        "compact", "explicit"
    }:
        raise ValueError("unknown manifest cell")

    lines = ["CONTROLLED SOURCE INDEX", POLICY]
    if format_name == "compact":
        lines.append(
            "Record code:\n"
            "D|path|exists=yes|manifest_files=N|directory_total_lines=N\n"
            "F|path|exists=yes[|file_lines=N]"
        )
        for area in AREAS:
            lines.append(
                f"D|{area['directory']}|exists=yes"
                f"|manifest_files={area['file_count']}"
                f"|directory_total_lines={area['directory_lines']}"
            )
            file_record = f"F|{area['line_path']}|exists=yes"
            if rate == "high":
                file_record += f"|file_lines={area['file_lines']}"
            lines.append(file_record)
            if area["listed_path"]:
                lines.append(f"F|{area['listed_path']}|exists=yes")
    else:
        for area in AREAS:
            lines.append(
                f"Directory `{area['directory']}` exists. Its source manifest "
                f"contains {area['file_count']} files totaling "
                f"{area['directory_lines']:,} lines across the directory."
            )
            if rate == "high":
                lines.append(
                    f"File `{area['line_path']}` exists. Its file line count "
                    f"is exactly {area['file_lines']}."
                )
            else:
                lines.append(f"File `{area['line_path']}` exists.")
            if area["listed_path"]:
                lines.append(f"File `{area['listed_path']}` exists.")
    return "\n".join(lines)


def manifests():
    rendered = {
        cell: render_manifest(spec["rate"], spec["format"])
        for cell, spec in CELLS.items()
    }
    if proposition_set("low") != proposition_set("low"):
        raise AssertionError("unreachable proposition check")
    if len(proposition_set("low")) != 58:
        raise ProbeError("low payload does not contain 58 propositions")
    if len(proposition_set("high")) != 70:
        raise ProbeError("high payload does not contain 70 propositions")
    if not proposition_set("low") < proposition_set("high"):
        raise ProbeError("low payload is not a strict subset of high")
    if len(proposition_set("high") - proposition_set("low")) != 12:
        raise ProbeError("high payload does not add exactly 12 line facts")
    return rendered


def queries():
    result = []
    for index, area in enumerate(AREAS, 1):
        result.append({
            "id": f"Q{index:02d}",
            "kind": "file_line",
            "stratum": "file_line",
            "cluster": area["cluster"],
            "target": area["line_path"],
            "truth": area["file_lines"],
            "directory_total": area["directory_lines"],
            "question": (
                "Use only the CONTROLLED SOURCE INDEX in the system message. "
                f"How many lines are in file `{area['line_path']}`? Reply with "
                "exactly one field: a base-10 integer with no commas, or "
                "UNKNOWN if the index does not state the file line count."
            ),
        })

    by_directory = {area["directory"]: area for area in AREAS}
    for offset, directory in enumerate(AGGREGATE_DIRECTORIES, 13):
        area = by_directory[directory]
        result.append({
            "id": f"Q{offset:02d}",
            "kind": "aggregate",
            "stratum": "aggregate",
            "cluster": area["cluster"],
            "target": directory,
            "truth": area["directory_lines"],
            "question": (
                "Use only the CONTROLLED SOURCE INDEX in the system message. "
                f"How many manifest-counted lines are in directory "
                f"`{directory}` in total? Reply with exactly one field: a "
                "base-10 integer with no commas, or UNKNOWN if the index does "
                "not state the directory total."
            ),
        })

    listed = [
        (area["listed_path"], area["cluster"])
        for area in AREAS
        if area["listed_path"]
    ]
    for offset, (path, cluster) in enumerate(listed, 17):
        result.append({
            "id": f"Q{offset:02d}",
            "kind": "listed_existence",
            "stratum": "listed_existence",
            "cluster": cluster,
            "target": path,
            "truth": "YES",
            "question": (
                "Use only the CONTROLLED SOURCE INDEX in the system message. "
                f"Does the source tree contain `{path}`? Reply with exactly "
                "one field: YES, NO, or UNKNOWN if the index does not "
                "establish existence."
            ),
        })

    for offset, (path, cluster) in enumerate(UNLISTED, 25):
        result.append({
            "id": f"Q{offset:02d}",
            "kind": "unlisted_existence",
            "stratum": "unlisted_existence",
            "cluster": cluster,
            "target": path,
            "truth": "YES",
            "question": (
                "Use only the CONTROLLED SOURCE INDEX in the system message. "
                f"Does the source tree contain `{path}`? Reply with exactly "
                "one field: YES, NO, or UNKNOWN if the index does not "
                "establish existence."
            ),
        })
    if len(result) != 28 or len({item["id"] for item in result}) != 28:
        raise ProbeError("query corpus must contain exactly Q01-Q28")
    return result


def support_label(query, cell):
    if query["kind"] == "file_line":
        return query["truth"] if CELLS[cell]["rate"] == "high" else "UNKNOWN"
    if query["kind"] == "aggregate":
        return query["truth"]
    if query["kind"] == "listed_existence":
        return "YES"
    return "UNKNOWN"


def task_plan():
    corpus = queries()
    by_id = {item["id"]: item for item in corpus}
    tasks = []
    global_order = 0
    for group_index, (query_ids, sequence) in enumerate(
        zip(QUERY_GROUPS, CELL_SEQUENCES),
        1,
    ):
        group = [by_id[query_id] for query_id in query_ids]
        for sequence_position, cell in enumerate(sequence, 1):
            # Rotate the seven within-subblock positions as well, preventing
            # one stratum from always paying the coldest or warmest call.
            offset = (sequence_position - 1) * 2
            rotated = group[offset:] + group[:offset]
            for subblock_order, query in enumerate(rotated, 1):
                global_order += 1
                tasks.append({
                    **query,
                    "cell": cell,
                    "group_index": group_index,
                    "sequence_position": sequence_position,
                    "subblock_order": subblock_order,
                    "execution_order": global_order,
                    "replay": False,
                    "trial_id": f"{cell}-{query['id']}-primary",
                    "support_label": support_label(query, cell),
                })

    # End-of-batch deterministic replays detect gross temporal/server drift.
    for sentinel_cell_order, cell in enumerate(("LC", "HE", "LE", "HC"), 1):
        for sentinel_order, query_id in enumerate(("Q01", "Q25"), 1):
            global_order += 1
            query = by_id[query_id]
            tasks.append({
                **query,
                "cell": cell,
                "group_index": None,
                "sequence_position": None,
                "subblock_order": None,
                "sentinel_cell_order": sentinel_cell_order,
                "sentinel_order": sentinel_order,
                "execution_order": global_order,
                "replay": True,
                "trial_id": f"{cell}-{query['id']}-replay",
                "support_label": support_label(query, cell),
            })
    if len(tasks) != 120 or len({item["trial_id"] for item in tasks}) != 120:
        raise ProbeError("task plan must contain exactly 120 unique calls")
    return tasks


def known_number_facts():
    found = defaultdict(list)
    for area in AREAS:
        found[area["file_count"]].append(
            f"directory_file_count:{area['directory']}"
        )
        found[area["directory_lines"]].append(
            f"directory_total_lines:{area['directory']}"
        )
        found[area["file_lines"]].append(f"file_lines:{area['line_path']}")
    return dict(found)


def parse_answer(answer, query):
    normalized = unicodedata.normalize("NFKC", str(answer or "")).strip().upper()
    result = {
        "normalized_answer": normalized,
        "parsed_value": None,
        "classification": "NONCOMPLIANT",
        "matched_encoded_facts": [],
    }
    if query["kind"] in {"file_line", "aggregate"}:
        if normalized == "UNKNOWN":
            result["classification"] = "UNKNOWN"
            return result
        if not normalized or not NUMBER.fullmatch(normalized):
            return result
        if not normalized.isascii() or not normalized.isdigit():
            return result
        value = int(normalized)
        result["parsed_value"] = value
        if value == query["truth"]:
            result["classification"] = "EXACT"
        elif (
            query["kind"] == "file_line"
            and value == query["directory_total"]
        ):
            result["classification"] = "DIR_TOTAL"
        elif value in known_number_facts():
            result["classification"] = "OTHER_ENCODED_NUMBER"
            result["matched_encoded_facts"] = known_number_facts()[value]
        else:
            result["classification"] = "NOVEL_NUMBER"
        return result

    if normalized in {"YES", "NO", "UNKNOWN"}:
        result["classification"] = normalized
        result["parsed_value"] = normalized
    return result


def correctness(parsed, query, support):
    if query["kind"] in {"file_line", "aggregate"}:
        source_correct = (
            parsed["classification"] == "EXACT"
            and parsed["parsed_value"] == query["truth"]
        )
        if support == "UNKNOWN":
            support_correct = parsed["classification"] == "UNKNOWN"
        else:
            support_correct = source_correct
    else:
        source_correct = parsed["classification"] == "YES"
        support_correct = parsed["classification"] == support
    return source_correct, support_correct


def _token_count(text):
    response = requests.post(
        SERVER_URL + "/tokenize",
        headers=MODEL_REQUEST_HEADERS,
        json={"content": text, "add_special": False},
        timeout=30,
    )
    response.raise_for_status()
    tokens = response.json().get("tokens")
    if not isinstance(tokens, list):
        raise ProbeError("tokenize endpoint returned no token list")
    return len(tokens)


def _server_revision():
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT / "llama.cpp",
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _port_listener_pid(port, *, required=True):
    result = subprocess.run(
        ["netstat", "-ano", "-p", "TCP"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    found = set()
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[-2].upper() != "LISTENING":
            continue
        local = fields[1]
        if local.rsplit(":", 1)[-1] == str(port):
            found.add(int(fields[-1]))
    if not required and not found:
        return None
    if len(found) != 1:
        raise ProbeError(
            f"expected one listener on port {port}, found {sorted(found)}"
        )
    return found.pop()


def _listener_pid():
    parsed = urlparse(SERVER_URL)
    if parsed.port is None:
        raise ProbeError("director URL has no port")
    return _port_listener_pid(parsed.port)


def _process_details(pid):
    command = (
        f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}';"
        "if($null -eq $p){exit 3};"
        "[pscustomobject]@{ProcessId=$p.ProcessId;"
        "ParentProcessId=$p.ParentProcessId;"
        "ExecutablePath=$p.ExecutablePath;CommandLine=$p.CommandLine}"
        "|ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = json.loads(result.stdout)
    return {
        "pid": int(raw["ProcessId"]),
        "parent_pid": int(raw["ParentProcessId"]),
        "executable_path": str(
            Path(str(raw.get("ExecutablePath") or "")).resolve()
        ),
        "command_line": str(raw.get("CommandLine") or ""),
    }


def _listener_process_identity(pid):
    raw = _process_details(pid)
    executable = Path(raw["executable_path"])
    command_line = raw["command_line"]
    configured_model = str(Path(MODEL_PATH).resolve())
    parsed = urlparse(SERVER_URL)
    identity = {
        "pid": raw["pid"],
        "parent_pid": raw["parent_pid"],
        "executable_path": str(executable),
        "executable_sha256": sha256_file(executable),
        "command_line_sha256": sha256_text(command_line),
        "configured_model_argument_present": (
            configured_model.casefold() in command_line.casefold()
        ),
        "configured_port_argument_present": (
            f"--port {parsed.port}" in command_line
        ),
        "one_slot_argument_present": "-np 1" in command_line,
        "context_8192_argument_present": "-c 8192" in command_line,
        "cache_prompt_argument_present": "--cache-prompt" in command_line,
    }
    if executable != Path(LLAMA_SERVER).resolve():
        raise ProbeError(
            "the process listening on the director port is not configured "
            "llama-server"
        )
    if not all(
        identity[key]
        for key in (
            "configured_model_argument_present",
            "configured_port_argument_present",
            "one_slot_argument_present",
            "context_8192_argument_present",
            "cache_prompt_argument_present",
        )
    ):
        raise ProbeError(f"director command line failed binding: {identity}")
    return identity


def _live_props_identity():
    response = requests.get(
        SERVER_URL + "/props",
        headers=MODEL_REQUEST_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    props = response.json()
    settings = props.get("default_generation_settings") or {}
    params = settings.get("params") or {}
    identity = {
        "model_path": str(Path(props.get("model_path") or "").resolve()),
        "model_alias": str(props.get("model_alias") or ""),
        "model_ftype": props.get("model_ftype"),
        "build_info": props.get("build_info"),
        "total_slots": props.get("total_slots"),
        "n_ctx": settings.get("n_ctx"),
        "chat_format": params.get("chat_format"),
        "reasoning_format": params.get("reasoning_format"),
        "chat_template_sha256": sha256_text(props.get("chat_template") or ""),
    }
    if Path(identity["model_path"]) != Path(MODEL_PATH).resolve():
        raise ProbeError("live director model path differs from configured model")
    if identity["total_slots"] != 1 or identity["n_ctx"] != 8192:
        raise ProbeError(
            "live director is not the frozen one-slot 8192-context server"
        )
    return identity


def live_server_identity():
    pid = _listener_pid()
    value = {
        "props": _live_props_identity(),
        "listener": _listener_process_identity(pid),
    }
    value["sha256"] = sha256_value(value)
    return value


def hazard_mode_identity(live):
    helper_pid = _port_listener_pid(8084)
    helper = _process_details(helper_pid)
    helper_command = helper.pop("command_line")
    assistant = _process_details(live["listener"]["parent_pid"])
    assistant_command = assistant.pop("command_line")
    value = {
        "independently_verified": True,
        "assistant": {
            **assistant,
            "executable_sha256": sha256_file(assistant["executable_path"]),
            "command_line_sha256": sha256_text(assistant_command),
            "main_py_argument_present": "main.py" in assistant_command,
        },
        "machinespirit_helper": {
            **helper,
            "executable_sha256": sha256_file(helper["executable_path"]),
            "command_line_sha256": sha256_text(helper_command),
            "alias_present": "--alias machinespirit" in helper_command,
            "unpooled_present": "--pooling none" in helper_command,
            "port_8084_present": "--port 8084" in helper_command,
        },
        "agent_interface_8099_listener": _port_listener_pid(
            8099,
            required=False,
        ),
        "console_pulse_helper_sha256": sha256_file(
            Path(__file__).with_name("console_pulse.py")
        ),
        "console_pulse_interval_seconds": CONSOLE_PULSE_SECONDS,
    }
    if not value["assistant"]["main_py_argument_present"]:
        raise ProbeError("director parent is not Sable's main.py process")
    if not all(
        value["machinespirit_helper"][key]
        for key in ("alias_present", "unpooled_present", "port_8084_present")
    ):
        raise ProbeError("port 8084 is not the hazard machinespirit helper")
    if value["agent_interface_8099_listener"] is not None:
        raise ProbeError(
            "agent interface is listening on 8099; the director cannot be "
            "reserved against outside diagnostic calls"
        )
    return value


def runtime_bindings():
    model = Path(MODEL_PATH)
    server = Path(LLAMA_SERVER)
    if not model.is_file() or not server.is_file():
        raise ProbeError("configured model or llama-server binary is missing")
    live = live_server_identity()
    hazard = hazard_mode_identity(live)
    return {
        "assistant_mode": {
            "operator_reported": "hazard",
            "independently_verified": True,
            "relevance": (
                "The collector bypasses the assistant process and binds the "
                "director directly; UI mode does not enter the messages."
            ),
        },
        "server_url": SERVER_URL,
        "model_name": model.name,
        "model_bytes": model.stat().st_size,
        "model_sha256": sha256_file(model),
        "server_name": server.name,
        "server_executable_sha256": sha256_file(server),
        "server_bundle_sha256": research_c.server_bundle_digest(server),
        "server_revision": _server_revision(),
        "live_server": live,
        "hazard_runtime": hazard,
    }


def _atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append_jsonl(path, value):
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class ConsoleKeepalive:
    """Reset Sable's input-idle timer without entering text or using the model."""

    def __init__(self, process_id):
        self.process_id = int(process_id)
        self._stop = threading.Event()
        self._error = None
        self._thread = None

    def _pulse(self):
        helper = Path(__file__).with_name("console_pulse.py")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            [sys.executable, str(helper), str(self.process_id)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            creationflags=flags,
        )

    def _worker(self):
        while not self._stop.wait(CONSOLE_PULSE_SECONDS):
            try:
                self._pulse()
            except Exception as error:
                self._error = f"{type(error).__name__}: {error}"
                return

    def start(self):
        self._pulse()
        self._thread = threading.Thread(
            target=self._worker,
            name="researchc-sable-idle-keepalive",
            daemon=True,
        )
        self._thread.start()

    def check(self):
        if self._error:
            raise ProbeError(
                "Sable idle-timer keepalive failed: " + self._error
            )

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)


def _read_jsonl(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _wait_for_idle_slot(expected_live):
    deadline = time.monotonic() + SLOT_WAIT_SECONDS
    current_live = live_server_identity()
    if current_live != expected_live:
        raise ProbeError("live director identity drifted before dispatch")
    while True:
        response = requests.get(
            SERVER_URL + "/slots",
            headers=MODEL_REQUEST_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        slots = response.json()
        if not isinstance(slots, list) or not slots:
            raise ProbeError("slot endpoint returned no slots")
        slot = slots[0]
        if not slot.get("is_processing"):
            current_live = live_server_identity()
            if current_live != expected_live:
                raise ProbeError("live director identity drifted while waiting")
            return {
                key: slot.get(key)
                for key in (
                    "id",
                    "is_processing",
                    "n_prompt_tokens",
                    "n_prompt_tokens_processed",
                    "n_prompt_tokens_cache",
                )
            }
        if time.monotonic() >= deadline:
            raise ProbeError("Sable's only director slot stayed busy for 60 seconds")
        time.sleep(0.25)


def request_completion(messages, sampler, slot):
    started = utc_now()
    wall_start = time.perf_counter()
    response = requests.post(
        SERVER_URL + "/v1/chat/completions",
        headers=MODEL_REQUEST_HEADERS,
        json={**sampler, "messages": messages},
        timeout=TIMEOUT_SECONDS,
    )
    elapsed = time.perf_counter() - wall_start
    ended = utc_now()
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProbeError("completion response contains no choice")
    message = choices[0].get("message") or {}
    answer = message.get("content")
    if not isinstance(answer, str):
        raise ProbeError("completion response contains no text")
    return {
        "answer": answer,
        "finish_reason": choices[0].get("finish_reason"),
        "usage": data.get("usage") or {},
        "timings": data.get("timings") or {},
        "precall_slot": slot,
        "started_utc": started,
        "ended_utc": ended,
        "elapsed_seconds": round(elapsed, 6),
    }


def construct_messages(stable, manifest, question):
    messages = [dict(stable[0])]
    messages.append({
        "role": "system",
        "content": RUNTIME_PREFIX + manifest,
    })
    messages.extend(dict(item) for item in stable[1:])
    messages.append({"role": "user", "content": question})
    return messages


def prepare(output_dir):
    output_dir = Path(output_dir).resolve()
    try:
        output_relative = output_dir.relative_to(ROOT)
    except ValueError as exc:
        raise ProbeError("output directory must stay inside the repository") from exc

    source = validate_source_facts()
    stable = stable_messages()
    leakage = validate_no_leakage(stable)
    rendered = manifests()
    corpus = queries()
    plan = task_plan()

    stable_text_without_experiment = "\n".join(
        item["content"] for item in stable
    ) + "\n" + RUNTIME_PREFIX
    for path in target_paths():
        folded = stable_text_without_experiment.casefold()
        if path.casefold() in folded or Path(path).name.casefold() in folded:
            raise ProbeError(f"constructed stable messages leak {path}")

    repo = repo_binding(output_relative)
    bound = runtime_bindings()
    if len(bound["model_sha256"]) != 64:
        raise ProbeError("model hash binding failed")
    if len(bound["server_bundle_sha256"]) != 64:
        raise ProbeError("server bundle binding failed")

    manifest_tokens = {
        cell: _token_count(text)
        for cell, text in rendered.items()
    }
    production_manifest = source_awareness.manifest_text()
    production_tokens = _token_count(production_manifest)

    manifest_artifact = {
        "schema": SCHEMA,
        "line_endings": "LF",
        "terminal_newline": False,
        "manifests": rendered,
    }
    stable_artifact = {"schema": SCHEMA, "messages": stable}
    query_artifact = {"schema": SCHEMA, "queries": corpus}
    spec_core = {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "purpose": (
            "bounded greedy channel-decoding frontier for a frozen named "
            "source-index corpus; not a target-selection, full-tree cost, or "
            "deployed-sampler study and never a replacement for trusted reads"
        ),
        "created_utc": utc_now(),
        "assistant_mode": {
            "operator_reported": "hazard",
            "independently_verified": True,
            "verification": (
                "director parent main.py plus live unpooled machinespirit "
                "helper on 8084; exact process hashes are in bindings"
            ),
            "collection_route": "direct one-slot director; assistant bypassed",
        },
        "collector_sha256": sha256_file(Path(__file__).resolve()),
        "call_count": 120,
        "unique_queries_per_cell": 28,
        "replay_sentinels_per_cell": 2,
        "query_groups": [list(group) for group in QUERY_GROUPS],
        "cell_sequences": [list(sequence) for sequence in CELL_SEQUENCES],
        "schedule_note": (
            "Four seven-query groups use a balanced Williams square; each "
            "cell occupies every temporal position and every directed "
            "carry-over pair once. Within-subblock query order is rotated."
        ),
        "sampler": SAMPLER,
        "timeout_seconds": TIMEOUT_SECONDS,
        "repository_state": repo,
        "source_snapshot_sha256": source["sha256"],
        "source_snapshot_file_count": source["file_count"],
        "bindings": bound,
        "leakage_audit": leakage,
        "stable_artifact_sha256": sha256_value(stable_artifact),
        "stable_system_sha256": sha256_text(stable[0]["content"]),
        "manifest_artifact_sha256": sha256_value(manifest_artifact),
        "manifest_sha256": {
            cell: sha256_text(text)
            for cell, text in rendered.items()
        },
        "manifest_utf8_bytes": {
            cell: len(text.encode("utf-8"))
            for cell, text in rendered.items()
        },
        "manifest_tokens": manifest_tokens,
        "production_manifest_sha256": sha256_text(production_manifest),
        "production_manifest_tokens": production_tokens,
        "production_manifest_utf8_bytes": len(
            production_manifest.encode("utf-8")
        ),
        "query_artifact_sha256": sha256_value(query_artifact),
        "tasks": plan,
        "proposition_counts": {"low": 58, "high": 70},
        "weight_profiles": {
            name: {
                stratum: str(weight)
                for stratum, weight in zip(STRATA, weights)
            }
            for name, weights in WEIGHT_PROFILES.items()
        },
        "confirmatory_contrasts": [
            "low_code: LE-LC",
            "high_code: HE-HC",
            "compact_rate: HC-LC",
            "explicit_rate: HE-LE",
        ],
        "sentinel_rule": (
            "Any normalized Q01 or Q25 replay mismatch makes the batch "
            "descriptive-only."
        ),
        "failure_rule": (
            "First HTTP failure or source/repository drift stops collection "
            "without retry and makes confirmatory claims void."
        ),
        "scope_rule": (
            "The twelve high-rate line facts are tailored to the frozen "
            "questions. No cell may ship without a target-independent "
            "heldout corpus, a full-tree token budget, and confirmation under "
            "Sable's deployed sampler."
        ),
    }
    spec = dict(spec_core)
    spec["spec_sha256"] = sha256_value(spec_core)
    return {
        "output_dir": output_dir,
        "output_relative": output_relative,
        "source_snapshot": source,
        "stable_artifact": stable_artifact,
        "manifest_artifact": manifest_artifact,
        "query_artifact": query_artifact,
        "spec": spec,
    }


def validate_spec_integrity(spec):
    if not isinstance(spec, dict) or not spec.get("spec_sha256"):
        raise ProbeError("frozen spec has no integrity digest")
    core = dict(spec)
    recorded = core.pop("spec_sha256")
    actual = sha256_value(core)
    if recorded != actual:
        raise ProbeError(
            f"frozen spec integrity mismatch: {recorded} != {actual}"
        )


def _load_or_create(output_dir):
    prepared = prepare(output_dir)
    output_dir = prepared["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "rate_distortion_stable_messages.json": prepared["stable_artifact"],
        "rate_distortion_manifests.json": prepared["manifest_artifact"],
        "rate_distortion_queries.json": prepared["query_artifact"],
        "rate_distortion_source_snapshot.json": prepared["source_snapshot"],
        "rate_distortion_spec.json": prepared["spec"],
    }
    existing = [name for name in artifacts if (output_dir / name).exists()]
    rows_path = output_dir / "rate_distortion_rows.jsonl"
    dispatch_path = output_dir / "rate_distortion_dispatch.jsonl"
    if existing:
        if len(existing) != len(artifacts):
            raise ProbeError("resume requires every frozen artifact")
        loaded = {
            name: json.loads((output_dir / name).read_text(encoding="utf-8"))
            for name in artifacts
        }
        spec = loaded["rate_distortion_spec.json"]
        validate_spec_integrity(spec)
        checks = (
            (
                "rate_distortion_stable_messages.json",
                "stable_artifact_sha256",
            ),
            ("rate_distortion_manifests.json", "manifest_artifact_sha256"),
            ("rate_distortion_queries.json", "query_artifact_sha256"),
        )
        for name, digest_field in checks:
            if sha256_value(loaded[name]) != spec[digest_field]:
                raise ProbeError(f"frozen artifact digest mismatch: {name}")
        frozen_source = loaded["rate_distortion_source_snapshot.json"]
        if (
            frozen_source.get("sha256") != spec["source_snapshot_sha256"]
            or frozen_source.get("file_count")
            != spec["source_snapshot_file_count"]
            or sha256_value(frozen_source.get("rows", []))
            != spec["source_snapshot_sha256"]
        ):
            raise ProbeError("frozen source-snapshot artifact is inconsistent")
        current_spec = prepared["spec"]
        if current_spec["bindings"] != spec["bindings"]:
            raise ProbeError("model/server/live-process binding drift on resume")
        if current_spec["collector_sha256"] != spec["collector_sha256"]:
            raise ProbeError("collector code changed since run creation")
        if current_spec["sampler"] != spec["sampler"] or SAMPLER != spec["sampler"]:
            raise ProbeError("sampler changed since run creation")
        for field in (
            "stable_artifact_sha256",
            "stable_system_sha256",
            "manifest_artifact_sha256",
            "manifest_sha256",
            "manifest_utf8_bytes",
            "manifest_tokens",
            "production_manifest_sha256",
            "production_manifest_tokens",
            "query_artifact_sha256",
            "query_groups",
            "cell_sequences",
        ):
            if current_spec[field] != spec[field]:
                raise ProbeError(f"frozen design drift on resume: {field}")
        if current_spec["tasks"] != spec["tasks"]:
            raise ProbeError("execution plan changed since run creation")
        if spec["source_snapshot_sha256"] != prepared[
            "source_snapshot"
        ]["sha256"]:
            raise ProbeError("selected sources drifted since run creation")
        if not same_repo(
            spec["repository_state"],
            repo_binding(prepared["output_relative"]),
        ):
            raise ProbeError("repository drifted since run creation")
        prepared.update({
            "stable_artifact": loaded[
                "rate_distortion_stable_messages.json"
            ],
            "manifest_artifact": loaded["rate_distortion_manifests.json"],
            "query_artifact": loaded["rate_distortion_queries.json"],
            "source_snapshot": loaded[
                "rate_distortion_source_snapshot.json"
            ],
            "spec": spec,
        })
        return prepared

    if rows_path.exists() or dispatch_path.exists():
        raise ProbeError(
            "rows or dispatch journal exist without frozen artifacts; refusing "
            "to wrap contaminated data in a new spec"
        )
    for name, value in artifacts.items():
        _atomic_json(output_dir / name, value)
    return prepared


def load_frozen_offline(output_dir):
    """Load a preserved collection without touching the live server or repo."""
    output_dir = Path(output_dir).resolve()
    names = (
        "rate_distortion_stable_messages.json",
        "rate_distortion_manifests.json",
        "rate_distortion_queries.json",
        "rate_distortion_source_snapshot.json",
        "rate_distortion_spec.json",
    )
    missing = [name for name in names if not (output_dir / name).is_file()]
    if missing:
        raise ProbeError(f"offline analysis is missing artifacts: {missing}")
    loaded = {
        name: json.loads((output_dir / name).read_text(encoding="utf-8"))
        for name in names
    }
    spec = loaded["rate_distortion_spec.json"]
    validate_spec_integrity(spec)
    checks = (
        ("rate_distortion_stable_messages.json", "stable_artifact_sha256"),
        ("rate_distortion_manifests.json", "manifest_artifact_sha256"),
        ("rate_distortion_queries.json", "query_artifact_sha256"),
    )
    for name, field in checks:
        if sha256_value(loaded[name]) != spec[field]:
            raise ProbeError(f"offline frozen artifact mismatch: {name}")
    source = loaded["rate_distortion_source_snapshot.json"]
    if (
        source.get("sha256") != spec["source_snapshot_sha256"]
        or sha256_value(source.get("rows", []))
        != spec["source_snapshot_sha256"]
    ):
        raise ProbeError("offline frozen source snapshot mismatch")
    rows = _read_jsonl(output_dir / "rate_distortion_rows.jsonl")
    dispatches = _read_jsonl(output_dir / "rate_distortion_dispatch.jsonl")
    validate_resumed_rows(
        rows,
        dispatches,
        spec,
        loaded["rate_distortion_stable_messages.json"]["messages"],
        loaded["rate_distortion_manifests.json"]["manifests"],
    )
    return {
        "output_dir": output_dir,
        "spec": spec,
        "rows": rows,
        "dispatches": dispatches,
    }


def wilson_interval(successes, trials, z=1.959963984540054):
    if trials <= 0:
        return None, None
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials))
        / denominator
    )
    return max(0.0, centre - radius), min(1.0, centre + radius)


def exact_sign_test(positive, negative):
    trials = positive + negative
    if trials == 0:
        return 1.0
    tail = min(positive, negative)
    probability = sum(
        math.comb(trials, count)
        for count in range(tail + 1)
    ) / (2 ** trials)
    return min(1.0, 2.0 * probability)


def holm_adjusted_pvalues(values):
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    result = [0.0] * len(values)
    previous = 0.0
    for rank, (index, value) in enumerate(ordered):
        adjusted = min(1.0, (len(values) - rank) * value)
        previous = max(previous, adjusted)
        result[index] = previous
    return result


def cluster_sign_flip_pvalue(deltas):
    names = sorted(deltas)
    observed = sum(deltas.values())
    extreme = 0
    total = 0
    for signs in itertools.product((-1, 1), repeat=len(names)):
        permuted = sum(
            sign * deltas[name]
            for sign, name in zip(signs, names)
        )
        total += 1
        if abs(permuted) + 1e-15 >= abs(observed):
            extreme += 1
    return extreme / total if total else 1.0


def paired_counts(left_rows, right_rows, field):
    left = {row["question_id"]: bool(row[field]) for row in left_rows}
    right = {row["question_id"]: bool(row[field]) for row in right_rows}
    ids = sorted(set(left) & set(right))
    positive = sum(left[item] and not right[item] for item in ids)
    negative = sum(right[item] and not left[item] for item in ids)
    return {
        "left_only": positive,
        "right_only": negative,
        "ties": len(ids) - positive - negative,
        "n": len(ids),
    }


def _stratum_means(rows, field):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["stratum"]].append(bool(row[field]))
    return {
        stratum: (
            sum(grouped[stratum]) / len(grouped[stratum])
            if grouped[stratum]
            else 0.0
        )
        for stratum in STRATA
    }


def profile_scores(rows, field):
    means = _stratum_means(rows, field)
    return {
        name: float(sum(
            weight * Fraction.from_float(means[stratum])
            for stratum, weight in zip(STRATA, weights)
        ))
        for name, weights in WEIGHT_PROFILES.items()
    }


def cluster_deltas(left_rows, right_rows, field, profile_name):
    weights = dict(zip(STRATA, WEIGHT_PROFILES[profile_name]))
    counts = {stratum: 0 for stratum in STRATA}
    for row in left_rows:
        counts[row["stratum"]] += 1
    item_weight = {
        stratum: weights[stratum] / counts[stratum]
        for stratum in STRATA
    }
    left = {row["question_id"]: row for row in left_rows}
    right = {row["question_id"]: row for row in right_rows}
    result = defaultdict(Fraction)
    for question_id in sorted(set(left) & set(right)):
        left_row = left[question_id]
        delta = int(bool(left_row[field])) - int(bool(right[question_id][field]))
        result[left_row["cluster"]] += item_weight[left_row["stratum"]] * delta
    return {name: float(value) for name, value in result.items()}


def binary_mutual_information(pairs):
    if not pairs:
        return None
    joint = defaultdict(int)
    left = defaultdict(int)
    right = defaultdict(int)
    for x, y in pairs:
        joint[(bool(x), bool(y))] += 1
        left[bool(x)] += 1
        right[bool(y)] += 1
    total = len(pairs)
    value = 0.0
    for (x, y), count in joint.items():
        pxy = count / total
        value += pxy * math.log2(
            pxy / ((left[x] / total) * (right[y] / total))
        )
    return value


def _cell_summary(rows):
    strata = {}
    for stratum in STRATA:
        subset = [row for row in rows if row["stratum"] == stratum]
        source_success = sum(row["source_correct"] for row in subset)
        support_success = sum(row["support_correct"] for row in subset)
        source_interval = wilson_interval(source_success, len(subset))
        support_interval = wilson_interval(support_success, len(subset))
        strata[stratum] = {
            "n": len(subset),
            "source_correct": source_success,
            "source_fraction": source_success / len(subset),
            "source_wilson_95": list(source_interval),
            "support_correct": support_success,
            "support_fraction": support_success / len(subset),
            "support_wilson_95": list(support_interval),
        }
    usage_tokens = [
        row.get("usage", {}).get("prompt_tokens")
        for row in rows
        if isinstance(row.get("usage", {}).get("prompt_tokens"), int)
    ]
    cached_tokens = [
        row.get("usage", {}).get("prompt_tokens_details", {}).get(
            "cached_tokens"
        )
        for row in rows
        if isinstance(
            row.get("usage", {}).get("prompt_tokens_details", {}).get(
                "cached_tokens"
            ),
            int,
        )
    ]
    return {
        "n": len(rows),
        "strata": strata,
        "source_scores": profile_scores(rows, "source_correct"),
        "support_scores": profile_scores(rows, "support_correct"),
        "mean_prompt_tokens": (
            sum(usage_tokens) / len(usage_tokens) if usage_tokens else None
        ),
        "mean_cached_tokens": (
            sum(cached_tokens) / len(cached_tokens) if cached_tokens else None
        ),
        "classifications": {
            classification: sum(
                row["classification"] == classification for row in rows
            )
            for classification in sorted({
                row["classification"] for row in rows
            })
        },
    }


def _contrast(name, left_cell, right_cell, by_cell, kind):
    left = by_cell[left_cell]
    right = by_cell[right_cell]
    paired = paired_counts(left, right, "source_correct")
    if kind == "rate":
        line_ids = {f"Q{index:02d}" for index in range(1, 13)}
        left_line = [row for row in left if row["question_id"] in line_ids]
        right_line = [row for row in right if row["question_id"] in line_ids]
        inferential = paired_counts(left_line, right_line, "source_correct")
        raw_p = exact_sign_test(
            inferential["left_only"],
            inferential["right_only"],
        )
        clusters = None
    else:
        clusters = cluster_deltas(
            left,
            right,
            "source_correct",
            "P_equal_stratum",
        )
        raw_p = cluster_sign_flip_pvalue(clusters)
        inferential = {
            "cluster_count": len(clusters),
            "cluster_deltas": clusters,
        }

    left_source = profile_scores(left, "source_correct")
    right_source = profile_scores(right, "source_correct")
    left_support = profile_scores(left, "support_correct")
    right_support = profile_scores(right, "support_correct")
    source_gains = {
        profile: left_source[profile] - right_source[profile]
        for profile in WEIGHT_PROFILES
    }
    support_gains = {
        profile: left_support[profile] - right_support[profile]
        for profile in WEIGHT_PROFILES
    }
    return {
        "name": name,
        "left": left_cell,
        "right": right_cell,
        "kind": kind,
        "raw_p": raw_p,
        "inferential_counts": inferential,
        "descriptive_item_mcnemar": paired,
        "source_gains": source_gains,
        "support_gains": support_gains,
        "source_gain_hull": [
            min(source_gains.values()),
            max(source_gains.values()),
        ],
        "support_gain_hull": [
            min(support_gains.values()),
            max(support_gains.values()),
        ],
        "query_distribution_sign_change": (
            min(source_gains.values()) < 0.0 < max(source_gains.values())
        ),
    }


def _shipping_gate(contrast, by_cell, cell_summaries, spec):
    primary = contrast["source_gains"]["P_equal_stratum"]
    if primary >= 0.0:
        candidate = contrast["left"]
        baseline = contrast["right"]
        direction = 1.0
    else:
        candidate = contrast["right"]
        baseline = contrast["left"]
        direction = -1.0
    source_gains = {
        name: direction * value
        for name, value in contrast["source_gains"].items()
    }
    support_gains = {
        name: direction * value
        for name, value in contrast["support_gains"].items()
    }
    rows = by_cell[candidate]
    listed_yes = sum(
        row["classification"] == "YES"
        for row in rows
        if row["stratum"] == "listed_existence"
    )
    aggregate_exact = sum(
        row["classification"] == "EXACT"
        for row in rows
        if row["stratum"] == "aggregate"
    )
    false_denials = sum(
        row["classification"] == "NO"
        for row in rows
        if row["stratum"] == "unlisted_existence"
    )
    unlisted_unknown = sum(
        row["classification"] == "UNKNOWN"
        for row in rows
        if row["stratum"] == "unlisted_existence"
    )
    directory_substitutions = sum(
        row["classification"] == "DIR_TOTAL"
        for row in rows
        if row["stratum"] == "file_line"
    )
    encoded_number_misattributions = sum(
        row["classification"] in {"DIR_TOTAL", "OTHER_ENCODED_NUMBER"}
        for row in rows
        if row["stratum"] == "file_line"
    )
    line_exact = sum(
        row["classification"] == "EXACT"
        for row in rows
        if row["stratum"] == "file_line"
    )
    guards = {
        "holm_adjusted_p_below_0_05": contrast["holm_adjusted_p"] < 0.05,
        "primary_source_gain_at_least_0_10": (
            source_gains["P_equal_stratum"] >= 0.10
        ),
        "source_gain_nonnegative_all_profiles": all(
            value >= -1e-15 for value in source_gains.values()
        ),
        "support_does_not_fall_all_profiles": all(
            value >= -1e-15 for value in support_gains.values()
        ),
        "zero_unlisted_false_denials": false_denials == 0,
        "unlisted_unknown_4_of_4": unlisted_unknown == 4,
        "listed_yes_8_of_8": listed_yes == 8,
        "aggregates_exact_4_of_4": aggregate_exact == 4,
        "zero_directory_total_substitutions": directory_substitutions == 0,
        "zero_encoded_number_misattributions": (
            encoded_number_misattributions == 0
        ),
        "high_rate_line_exact_at_least_10_of_12": (
            CELLS[candidate]["rate"] != "high" or line_exact >= 10
        ),
        "target_independent_heldout_confirmation": False,
        "full_tree_token_budget_demonstrated": False,
        "deployed_sampler_confirmation": False,
    }
    structural = {
        "target_independent_heldout_confirmation",
        "full_tree_token_budget_demonstrated",
        "deployed_sampler_confirmation",
    }
    observed_guards_pass = all(
        value for key, value in guards.items() if key not in structural
    )
    return {
        "candidate": candidate,
        "baseline": baseline,
        "source_gains": source_gains,
        "support_gains": support_gains,
        "observed_guards": {
            "unlisted_false_denials": false_denials,
            "unlisted_unknown": unlisted_unknown,
            "listed_yes": listed_yes,
            "aggregate_exact": aggregate_exact,
            "directory_total_substitutions": directory_substitutions,
            "encoded_number_misattributions": encoded_number_misattributions,
            "line_exact": line_exact,
            "candidate_manifest_tokens": spec["manifest_tokens"][candidate],
            "production_manifest_tokens": spec["production_manifest_tokens"],
            "controlled_index_under_production_tokens_descriptive_only": (
                spec["manifest_tokens"][candidate]
                <= spec["production_manifest_tokens"]
            ),
        },
        "guards": guards,
        "passes_observed_channel_guards": observed_guards_pass,
        "passes_every_guard": all(guards.values()),
        "note": (
            "This tailored greedy corpus cannot ship a passive-manifest "
            "prototype. Even a clean channel result requires a "
            "target-independent holdout, a full-tree cost calculation, and "
            "deployed-sampler confirmation; the trusted resolver remains."
        ),
    }


def analyze(rows, spec):
    task_by_trial = {task["trial_id"]: task for task in spec["tasks"]}
    regraded = []
    for stored in rows:
        row = dict(stored)
        if row.get("status") == "ok":
            task = task_by_trial.get(row.get("trial_id"))
            if task is None:
                raise ProbeError(
                    f"row names a trial outside the frozen plan: "
                    f"{row.get('trial_id')}"
                )
            parsed = parse_answer(row.get("answer"), task)
            measured = correctness(parsed, task, task["support_label"])
            expected = {
                **parsed,
                "source_correct": measured[0],
                "support_correct": measured[1],
            }
            for field, value in expected.items():
                if row.get(field) != value:
                    raise ProbeError(
                        f"raw-answer regrade mismatch in "
                        f"{task['trial_id']}: {field}"
                    )
            row.update(expected)
        regraded.append(row)
    rows = regraded
    successful = [row for row in rows if row.get("status") == "ok"]
    primary = [row for row in successful if not row["replay"]]
    replay = [row for row in successful if row["replay"]]
    by_cell = {
        cell: [
            row
            for row in primary
            if row["cell"] == cell
        ]
        for cell in CELLS
    }
    sentinel_mismatches = []
    primary_lookup = {
        (row["cell"], row["question_id"]): row for row in primary
    }
    for row in replay:
        original = primary_lookup.get((row["cell"], row["question_id"]))
        if (
            original is None
            or row["normalized_answer"] != original["normalized_answer"]
        ):
            sentinel_mismatches.append({
                "cell": row["cell"],
                "question_id": row["question_id"],
                "primary": (
                    original["normalized_answer"] if original else None
                ),
                "replay": row["normalized_answer"],
            })

    cell_summaries = {
        cell: _cell_summary(cell_rows)
        for cell, cell_rows in by_cell.items()
    }
    contrasts = [
        _contrast("low_code", "LE", "LC", by_cell, "code"),
        _contrast("high_code", "HE", "HC", by_cell, "code"),
        _contrast("compact_rate", "HC", "LC", by_cell, "rate"),
        _contrast("explicit_rate", "HE", "LE", by_cell, "rate"),
    ]
    adjusted = holm_adjusted_pvalues(
        [contrast["raw_p"] for contrast in contrasts]
    )
    for contrast, value in zip(contrasts, adjusted):
        contrast["holm_adjusted_p"] = value
        contrast["shipping_gate"] = _shipping_gate(
            contrast,
            by_cell,
            cell_summaries,
            spec,
        )

    code = contrasts[:2]
    rate = contrasts[2:]
    code_kill = (
        all(contrast["holm_adjusted_p"] > 0.05 for contrast in code)
        and all(
            abs(value) < 0.05
            for contrast in code
            for value in contrast["source_gains"].values()
        )
    )
    exact_lines = {
        cell: sum(
            row["source_correct"]
            for row in by_cell[cell]
            if row["stratum"] == "file_line"
        )
        for cell in CELLS
    }
    best_high_gain = max(
        exact_lines["HC"] - exact_lines["LC"],
        exact_lines["HE"] - exact_lines["LE"],
    )
    numeric_kill = (
        all(contrast["holm_adjusted_p"] >= 0.05 for contrast in rate)
        and best_high_gain <= 2
    )
    batch_complete = (
        len(rows) == 120
        and len(successful) == 120
        and len(primary) == 112
        and len(replay) == 8
    )
    drift = any(
        row.get("source_drift") or row.get("repository_drift")
        for row in rows
    )
    descriptive_only = (
        not batch_complete
        or bool(sentinel_mismatches)
        or drift
        or any(row.get("status") != "ok" for row in rows)
    )
    shipping = [
        contrast["shipping_gate"]["candidate"]
        for contrast in contrasts
        if contrast["shipping_gate"]["passes_every_guard"]
    ]
    screening = [
        contrast["shipping_gate"]["candidate"]
        for contrast in contrasts
        if contrast["shipping_gate"]["passes_observed_channel_guards"]
    ]
    if descriptive_only:
        recommendation = "descriptive_only_batch"
    elif screening:
        recommendation = (
            "channel_candidate_requires_target_independent_deployed_confirmation"
        )
    elif code_kill and numeric_kill:
        recommendation = "freeze_manifest_redesign_keep_trusted_resolver"
    else:
        recommendation = "inconclusive_one_redesign_at_most"

    pareto = []
    for cell in CELLS:
        distortion = 1.0 - cell_summaries[cell]["source_scores"][
            "P_equal_stratum"
        ]
        pareto.append({
            "cell": cell,
            "manifest_tokens": spec["manifest_tokens"][cell],
            "distortion": distortion,
        })
    for point in pareto:
        point["frontier"] = not any(
            other is not point
            and other["manifest_tokens"] <= point["manifest_tokens"]
            and other["distortion"] <= point["distortion"]
            and (
                other["manifest_tokens"] < point["manifest_tokens"]
                or other["distortion"] < point["distortion"]
            )
            for other in pareto
        )

    manipulated = [
        (
            CELLS[row["cell"]]["rate"] == "high",
            row["source_correct"],
        )
        for row in primary
        if row["stratum"] == "file_line"
    ]
    return {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "spec_sha256": spec["spec_sha256"],
        "completed_utc": utc_now(),
        "row_count": len(rows),
        "successful_rows": len(successful),
        "primary_rows": len(primary),
        "replay_rows": len(replay),
        "batch_complete": batch_complete,
        "descriptive_only": descriptive_only,
        "sentinel_mismatches": sentinel_mismatches,
        "source_or_repository_drift": drift,
        "cells": cell_summaries,
        "contrasts": contrasts,
        "rate_distortion_points": pareto,
        "token_accounting": {
            "manifest_tokens": spec["manifest_tokens"],
            "manifest_utf8_bytes": spec["manifest_utf8_bytes"],
            "production_manifest_tokens": spec[
                "production_manifest_tokens"
            ],
            "atomic_propositions": {"LC": 58, "LE": 58, "HC": 70, "HE": 70},
            "facts_per_token": {
                cell: (70 if CELLS[cell]["rate"] == "high" else 58)
                / spec["manifest_tokens"][cell]
                for cell in CELLS
            },
            "incremental_tokens_per_added_line_fact": {
                "compact": (
                    spec["manifest_tokens"]["HC"]
                    - spec["manifest_tokens"]["LC"]
                ) / 12,
                "explicit": (
                    spec["manifest_tokens"]["HE"]
                    - spec["manifest_tokens"]["LE"]
                ) / 12,
            },
        },
        "descriptive_binary_mutual_information_bits": (
            binary_mutual_information(manipulated)
        ),
        "mutual_information_note": (
            "Raw plug-in MI between high/low availability and exact line "
            "reconstruction; descriptive and non-gating."
        ),
        "operational_rules": {
            "kill_code_format_work": code_kill,
            "kill_adding_numeric_facts": numeric_kill,
            "best_high_minus_low_exact_line_gain": best_high_gain,
            "shipping_candidates": sorted(set(shipping)),
            "channel_screening_candidates": sorted(set(screening)),
        },
        "recommendation": recommendation,
        "authority_note": (
            "The trusted source resolver remains mandatory under every "
            "outcome. The controlled-index/production token comparison is not "
            "a full-tree deployment cost. No result here grants the decoder "
            "new authority or changes production wording."
        ),
    }


def validate_resumed_rows(rows, dispatches, spec, stable, rendered):
    tasks = sorted(spec["tasks"], key=lambda item: item["execution_order"])
    if len(rows) > len(tasks):
        raise ProbeError("stored rows exceed the frozen 120-call plan")
    if len(dispatches) != len(rows):
        if len(dispatches) > len(rows):
            pending = [
                item.get("trial_id")
                for item in dispatches[len(rows):]
            ]
            raise ProbeError(
                "ambiguous pre-dispatch intent without a durable response; "
                f"no retry permitted: {pending}"
            )
        raise ProbeError("stored response row has no durable dispatch intent")
    if len({item.get("trial_id") for item in dispatches}) != len(dispatches):
        raise ProbeError("duplicate trial id in dispatch journal")

    for index, row in enumerate(rows):
        task = tasks[index]
        dispatch = dispatches[index]
        if dispatch.get("trial_id") != task["trial_id"]:
            raise ProbeError("dispatch journal is not the contiguous plan prefix")
        if row.get("trial_id") != task["trial_id"]:
            raise ProbeError("stored rows are not the contiguous plan prefix")
        if row.get("status") != "ok":
            raise ProbeError(
                f"failed call {task['trial_id']} is recorded; retries forbidden"
            )
        messages = construct_messages(
            stable,
            rendered[task["cell"]],
            task["question"],
        )
        expected = {
            "spec_sha256": spec["spec_sha256"],
            "question_id": task["id"],
            "cell": task["cell"],
            "rate": CELLS[task["cell"]]["rate"],
            "format": CELLS[task["cell"]]["format"],
            "stratum": task["stratum"],
            "cluster": task["cluster"],
            "target": task["target"],
            "truth": task["truth"],
            "support_label": task["support_label"],
            "question": task["question"],
            "question_sha256": sha256_text(task["question"]),
            "manifest_sha256": spec["manifest_sha256"][task["cell"]],
            "stable_system_sha256": spec["stable_system_sha256"],
            "stable_artifact_sha256": spec["stable_artifact_sha256"],
            "messages_sha256": research_c.prompt_digest(messages),
            "sampler": spec["sampler"],
            "bindings": spec["bindings"],
            "live_server_identity_sha256": spec[
                "bindings"
            ]["live_server"]["sha256"],
            "execution_order": task["execution_order"],
            "replay": task["replay"],
        }
        for field, value in expected.items():
            if row.get(field) != value:
                raise ProbeError(
                    f"stored row {task['trial_id']} drifted field {field}"
                )
        if dispatch.get("spec_sha256") != spec["spec_sha256"]:
            raise ProbeError("dispatch journal spec binding mismatch")
        if dispatch.get("messages_sha256") != expected["messages_sha256"]:
            raise ProbeError("dispatch journal message binding mismatch")
        if dispatch.get("execution_order") != task["execution_order"]:
            raise ProbeError("dispatch journal execution order mismatch")
        if dispatch.get("live_server_identity_sha256") != spec[
            "bindings"
        ]["live_server"]["sha256"]:
            raise ProbeError("dispatch journal live-server binding mismatch")
        if (
            row.get("source_snapshot_before_sha256")
            != spec["source_snapshot_sha256"]
            or row.get("source_snapshot_after_sha256")
            != spec["source_snapshot_sha256"]
            or row.get("source_drift")
            or row.get("repository_drift")
        ):
            raise ProbeError("stored row contains source/repository drift")
        if not same_repo(
            spec["repository_state"],
            row.get("repository_state_before") or {},
        ) or not same_repo(
            spec["repository_state"],
            row.get("repository_state_after") or {},
        ):
            raise ProbeError("stored row repository binding mismatch")
        parsed = parse_answer(row.get("answer"), task)
        for field in (
            "normalized_answer",
            "parsed_value",
            "classification",
            "matched_encoded_facts",
        ):
            if row.get(field) != parsed[field]:
                raise ProbeError(
                    f"stored row {task['trial_id']} parse mismatch: {field}"
                )
        measured = correctness(parsed, task, task["support_label"])
        if measured != (
            row.get("source_correct"),
            row.get("support_correct"),
        ):
            raise ProbeError(
                f"stored row {task['trial_id']} correctness mismatch"
            )


def run(output_dir):
    prepared = _load_or_create(output_dir)
    output_dir = prepared["output_dir"]
    output_relative = prepared["output_relative"]
    spec = prepared["spec"]
    stable = prepared["stable_artifact"]["messages"]
    rendered = prepared["manifest_artifact"]["manifests"]
    rows_path = output_dir / "rate_distortion_rows.jsonl"
    dispatch_path = output_dir / "rate_distortion_dispatch.jsonl"
    existing = _read_jsonl(rows_path)
    dispatches = _read_jsonl(dispatch_path)
    validate_resumed_rows(
        existing,
        dispatches,
        spec,
        stable,
        rendered,
    )
    completed = {row["trial_id"] for row in existing}
    if len(completed) != len(existing):
        raise ProbeError("duplicate trial ids found in existing rows")
    assistant_pid = spec["bindings"]["hazard_runtime"]["assistant"]["pid"]
    keepalive = ConsoleKeepalive(assistant_pid)
    keepalive.start()
    atexit.register(keepalive.stop)

    for task in sorted(spec["tasks"], key=lambda item: item["execution_order"]):
        if task["trial_id"] in completed:
            continue
        keepalive.check()
        before_repo = repo_binding(output_relative)
        before_source = source_snapshot()
        if not same_repo(spec["repository_state"], before_repo):
            raise ProbeError(f"repository drift before {task['trial_id']}")
        if before_source["sha256"] != spec["source_snapshot_sha256"]:
            raise ProbeError(f"source drift before {task['trial_id']}")

        messages = construct_messages(
            stable,
            rendered[task["cell"]],
            task["question"],
        )
        slot = _wait_for_idle_slot(spec["bindings"]["live_server"])
        base_row = {
            "schema": SCHEMA,
            "experiment": EXPERIMENT,
            "spec_sha256": spec["spec_sha256"],
            "trial_id": task["trial_id"],
            "question_id": task["id"],
            "cell": task["cell"],
            "rate": CELLS[task["cell"]]["rate"],
            "format": CELLS[task["cell"]]["format"],
            "stratum": task["stratum"],
            "cluster": task["cluster"],
            "target": task["target"],
            "truth": task["truth"],
            "support_label": task["support_label"],
            "question": task["question"],
            "question_sha256": sha256_text(task["question"]),
            "manifest_sha256": spec["manifest_sha256"][task["cell"]],
            "stable_system_sha256": spec["stable_system_sha256"],
            "stable_artifact_sha256": spec["stable_artifact_sha256"],
            "messages_sha256": research_c.prompt_digest(messages),
            "sampler": SAMPLER,
            "bindings": spec["bindings"],
            "live_server_identity_sha256": spec[
                "bindings"
            ]["live_server"]["sha256"],
            "group_index": task.get("group_index"),
            "sequence_position": task.get("sequence_position"),
            "subblock_order": task.get("subblock_order"),
            "sentinel_cell_order": task.get("sentinel_cell_order"),
            "sentinel_order": task.get("sentinel_order"),
            "execution_order": task["execution_order"],
            "replay": task["replay"],
            "repository_state_before": before_repo,
            "source_snapshot_before_sha256": before_source["sha256"],
        }
        _append_jsonl(dispatch_path, {
            "schema": SCHEMA,
            "experiment": EXPERIMENT,
            "event": "dispatch_intent",
            "trial_id": task["trial_id"],
            "execution_order": task["execution_order"],
            "spec_sha256": spec["spec_sha256"],
            "messages_sha256": base_row["messages_sha256"],
            "repository_dirty_digest": before_repo["dirty_digest"],
            "source_snapshot_sha256": before_source["sha256"],
            "live_server_identity_sha256": base_row[
                "live_server_identity_sha256"
            ],
            "precall_slot": slot,
            "recorded_utc": utc_now(),
        })
        try:
            response = request_completion(messages, spec["sampler"], slot)
            parsed = parse_answer(response["answer"], task)
            source_correct, support_correct = correctness(
                parsed,
                task,
                task["support_label"],
            )
            after_source = source_snapshot()
            after_repo = repo_binding(output_relative)
            row = {
                **base_row,
                "status": "ok",
                **response,
                **parsed,
                "source_correct": source_correct,
                "support_correct": support_correct,
                "source_snapshot_after_sha256": after_source["sha256"],
                "repository_state_after": after_repo,
                "source_drift": (
                    after_source["sha256"] != spec["source_snapshot_sha256"]
                ),
                "repository_drift": not same_repo(
                    spec["repository_state"], after_repo
                ),
            }
        except Exception as error:
            row = {
                **base_row,
                "status": "error",
                "error_type": type(error).__name__,
                "error": str(error)[:1000],
                "ended_utc": utc_now(),
            }
            _append_jsonl(rows_path, row)
            raise

        _append_jsonl(rows_path, row)
        keepalive.check()
        print(
            f"{task['execution_order']:03d}/120 {task['trial_id']} -> "
            f"{row['normalized_answer']} [{row['classification']}] "
            f"{row['elapsed_seconds']:.2f}s",
            flush=True,
        )
        if row["source_drift"] or row["repository_drift"]:
            raise ProbeError(f"drift after {task['trial_id']}")

    final_source = source_snapshot()
    final_repo = repo_binding(output_relative)
    if final_source["sha256"] != spec["source_snapshot_sha256"]:
        raise ProbeError("selected source snapshot drifted during collection")
    if not same_repo(spec["repository_state"], final_repo):
        raise ProbeError("repository drifted during collection")
    rows = _read_jsonl(rows_path)
    summary = analyze(rows, spec)
    summary["source_snapshot_after_sha256"] = final_source["sha256"]
    summary["repository_state_after"] = final_repo
    _atomic_json(output_dir / "rate_distortion_summary.json", summary)
    keepalive.stop()
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(
            ROOT
            / "handoffs"
            / "researchc_experiments_2026-07-30"
            / "rate_distortion"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print the frozen experiment without completions",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="reanalyze an already completed bound collection",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        prepared = prepare(args.out)
        spec = prepared["spec"]
        print(json.dumps({
            "experiment": spec["experiment"],
            "output": str(prepared["output_dir"]),
            "spec_sha256": spec["spec_sha256"],
            "calls": spec["call_count"],
            "source_snapshot_sha256": spec["source_snapshot_sha256"],
            "manifest_tokens": spec["manifest_tokens"],
            "production_manifest_tokens": spec["production_manifest_tokens"],
            "bindings": spec["bindings"],
            "recent_paths": spec["leakage_audit"]["recent_paths"],
        }, indent=2, sort_keys=True))
        return 0

    if args.analyze_only:
        prepared = load_frozen_offline(args.out)
        summary = analyze(prepared["rows"], prepared["spec"])
        _atomic_json(
            prepared["output_dir"] / "rate_distortion_summary.json",
            summary,
        )
    else:
        summary = run(args.out)
    print(json.dumps({
        "recommendation": summary["recommendation"],
        "descriptive_only": summary["descriptive_only"],
        "sentinel_mismatches": len(summary["sentinel_mismatches"]),
        "operational_rules": summary["operational_rules"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
