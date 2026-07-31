"""Portable, provenance-bound live probes for Research C.

The first experiment is a six-call manipulation check. It changes one
directory aggregate in a frozen system prompt entirely in memory, then asks
one aggregate control and two per-file questions under both values.

This tool deliberately calls llama-server directly. Sable's production source
resolver would correctly intercept these questions; the experiment measures
the underlying decoder mechanism, not the protected product path.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests


ROOT = Path(__file__).resolve().parents[1]
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
INJECTED_TOTAL = 7731
TIMEOUT_SECONDS = 600
SLOT_WAIT_SECONDS = 60
SAMPLER = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 40,
    "min_p": 0.05,
    "repeat_penalty": 1.0,
    "max_tokens": 180,
    "stream": False,
    "cache_prompt": True,
    "chat_template_kwargs": {"enable_thinking": False},
}
QUESTIONS = (
    {
        "id": "q0",
        "path": "assistant/ui",
        "kind": "directory",
        "seed": 42701,
        "question": "How many lines are in your assistant/ui directory?",
        "order": ("baseline", "perturbed"),
    },
    {
        "id": "q1",
        "path": "assistant/ui/ui.py",
        "kind": "file",
        "seed": 42702,
        "question": "How many lines are in assistant/ui/ui.py?",
        "order": ("perturbed", "baseline"),
    },
    {
        "id": "q2",
        "path": "assistant/ui/vector_panel.py",
        "kind": "file",
        "seed": 42703,
        "question": "How many lines are in assistant/ui/vector_panel.py?",
        "order": ("baseline", "perturbed"),
    },
)
REFUSAL_TERMS = (
    "cannot",
    "can't",
    "do not know",
    "don't know",
    "not available",
    "not provided",
    "need to read",
    "would need to read",
    "unknown",
)
INTEGER = re.compile(r"(?<![\w.])\d[\d,]*(?![\w.])")
_RESUME_DEFINITION_FIELDS = (
    "schema",
    "experiment",
    "purpose",
    "mode",
    "sampler",
    "timeout_seconds",
    "manifest_sha256",
    "anchor",
    "replacement",
    "replacement_count",
    "different_character_positions",
    "truth",
    "tasks",
    "decision_rule",
)


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


def sha256_value(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


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


def _filtered_status(output_relative):
    marker = str(output_relative).replace("\\", "/").rstrip("/") + "/"
    kept = []
    for line in git("status", "--short", "--untracked-files=all").splitlines():
        normalized = line.replace("\\", "/")
        if marker and marker in normalized:
            continue
        kept.append(line)
    return "\n".join(kept)


def inventory_digest():
    rows = []
    for item in source_awareness.inventory():
        facts = source_awareness.source_facts(item["path"])
        rows.append({
            "path": facts["path"],
            "lines": facts["lines"],
            "bytes": facts["bytes"],
            "sha256": facts["sha256"],
        })
    return sha256_value(rows)


def repo_state(output_relative):
    status = _filtered_status(output_relative)
    return {
        "head": git("rev-parse", "HEAD").strip(),
        "branch": git("branch", "--show-current").strip() or None,
        "status_sha256": sha256_text(status),
        "status": status,
        "tracked_diff_sha256": hashlib.sha256(
            git("diff", "--binary", "HEAD").encode("utf-8")
        ).hexdigest(),
        "staged_diff_sha256": hashlib.sha256(
            git("diff", "--cached", "--binary").encode("utf-8")
        ).hexdigest(),
        "source_inventory_sha256": inventory_digest(),
        "manifest_sha256": sha256_text(source_awareness.manifest_text()),
    }


def ui_truth():
    entries = [
        item
        for item in source_awareness.inventory()
        if item["path"].startswith("assistant/ui/")
    ]
    by_path = {item["path"]: item for item in entries}
    required = {
        "assistant/ui/__init__.py",
        "assistant/ui/ui.py",
        "assistant/ui/vector_panel.py",
    }
    if set(by_path) != required:
        raise ProbeError(
            "assistant/ui inventory changed; expected exactly the three "
            f"predeclared files, found {sorted(by_path)}"
        )
    total = sum(item["lines"] for item in entries)
    return {
        "directory_files": len(entries),
        "directory_lines": total,
        "files": {
            path: source_awareness.source_facts(path)
            for path in sorted(required)
        },
    }


def build_prompt_pair():
    truth = ui_truth()
    baseline_manifest = source_awareness.manifest_text()
    anchor = (
        f"assistant/ui {truth['directory_files']}f "
        f"{truth['directory_lines']:,}L"
    )
    replacement = (
        f"assistant/ui {truth['directory_files']}f "
        f"{INJECTED_TOTAL:,}L"
    )
    if len(anchor) != len(replacement):
        raise ProbeError("the intervention must preserve character length")
    if baseline_manifest.count(anchor) != 1:
        raise ProbeError(
            f"expected one manifest anchor {anchor!r}, "
            f"found {baseline_manifest.count(anchor)}"
        )
    if f"{INJECTED_TOTAL:,}" in baseline_manifest:
        raise ProbeError("injected value already occurs in the live manifest")

    original = assistant_main._self_knowledge_context
    try:
        assistant_main._self_knowledge_context = lambda: baseline_manifest
        baseline_prompt = assistant_main.build_system_prompt("")
    finally:
        assistant_main._self_knowledge_context = original

    if baseline_prompt.count(anchor) != 1:
        raise ProbeError("baseline system prompt does not contain one anchor")
    perturbed_prompt = baseline_prompt.replace(anchor, replacement, 1)
    if len(baseline_prompt) != len(perturbed_prompt):
        raise ProbeError("intervention changed system-prompt character length")
    differing = sum(
        left != right
        for left, right in zip(baseline_prompt, perturbed_prompt)
    )
    if differing <= 0:
        raise ProbeError("intervention did not change the prompt")

    return {
        "baseline": baseline_prompt,
        "perturbed": perturbed_prompt,
        "manifest": baseline_manifest,
        "anchor": anchor,
        "replacement": replacement,
        "different_character_positions": differing,
        "truth": truth,
    }


def tasks():
    result = []
    sequence = 0
    for question in QUESTIONS:
        for condition in question["order"]:
            sequence += 1
            item = dict(question)
            item.update({
                "trial_id": f"{question['id']}-{condition}",
                "condition": condition,
                "execution_order": sequence,
            })
            result.append(item)
    return result


def extract_integers(answer):
    values = []
    for match in INTEGER.findall(str(answer or "")):
        try:
            values.append(int(match.replace(",", "")))
        except ValueError:
            continue
    return values


def classify_answer(answer, task, truth):
    values = extract_integers(answer)
    unique = list(dict.fromkeys(values))
    lowered = str(answer or "").casefold()
    if not unique:
        if any(term in lowered for term in REFUSAL_TERMS):
            return "REFUSAL", values
        return "NO_NUMBER", values
    if len(unique) > 1:
        return "AMBIGUOUS_MULTI_NUMBER", values

    value = unique[0]
    directory_lines = truth["directory_lines"]
    expected = (
        directory_lines
        if task["kind"] == "directory"
        else truth["files"][task["path"]]["lines"]
    )
    if value == expected:
        return (
            "EXACT_DIRECTORY" if task["kind"] == "directory" else "EXACT_FILE"
        ), values
    if value == INJECTED_TOTAL:
        return "INJECTED_AGGREGATE", values
    if value == directory_lines:
        return "BASELINE_AGGREGATE", values
    return "OTHER_NUMBER", values


def _token_count(text):
    response = requests.post(
        SERVER_URL + "/tokenize",
        headers=MODEL_REQUEST_HEADERS,
        json={"content": text, "add_special": False},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    tokens = payload.get("tokens")
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


def bindings():
    model = Path(MODEL_PATH)
    server = Path(LLAMA_SERVER)
    if not model.is_file() or not server.is_file():
        raise ProbeError("configured model or llama-server binary is missing")
    return {
        "model_name": model.name,
        "model_bytes": model.stat().st_size,
        "model_sha256": sha256_file(model),
        "server_name": server.name,
        "server_executable_sha256": sha256_file(server),
        "server_bundle_sha256": research_c.server_bundle_digest(server),
        "server_revision": _server_revision(),
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


def _completed_ids(path, spec=None, prompts=None):
    if not path.exists():
        return set()
    tasks_by_id = (
        {
            task["trial_id"]: task
            for task in spec.get("tasks", ())
        }
        if isinstance(spec, dict)
        else None
    )
    found = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except (TypeError, ValueError) as exc:
                raise ProbeError(
                    f"invalid saved row {line_number}: malformed JSON"
                ) from exc
            if not isinstance(row, dict):
                raise ProbeError(
                    f"invalid saved row {line_number}: expected an object"
                )
            if tasks_by_id is None:
                if row.get("status") == "ok":
                    found.add(row.get("trial_id"))
                continue

            trial_id = row.get("trial_id")
            task = tasks_by_id.get(trial_id)
            if task is None:
                raise ProbeError(
                    f"invalid saved row {line_number}: unknown trial id"
                )
            expected = {
                "schema": spec.get("schema"),
                "experiment": spec.get("experiment"),
                "spec_sha256": spec.get("spec_sha256"),
                "question_id": task.get("id"),
                "condition": task.get("condition"),
                "execution_order": task.get("execution_order"),
                "seed": task.get("seed"),
                "question_sha256": sha256_text(task.get("question")),
            }
            for key, value in expected.items():
                if row.get(key) != value:
                    raise ProbeError(
                        f"invalid saved row {line_number}: {key} mismatch"
                    )
            status = row.get("status")
            if status not in {"ok", "error"}:
                raise ProbeError(
                    f"invalid saved row {line_number}: unknown status"
                )
            if status != "ok":
                continue
            if trial_id in found:
                raise ProbeError(
                    f"invalid saved row {line_number}: duplicate completion"
                )
            if not isinstance(prompts, dict):
                raise ProbeError("resume row validation requires frozen prompts")
            prompt = prompts.get(task["condition"])
            if not isinstance(prompt, str):
                raise ProbeError("frozen prompt artifact is incomplete")
            expected_ok = {
                "question": task.get("question"),
                "system_prompt_sha256": sha256_text(prompt),
                "messages_sha256": research_c.prompt_digest([
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": task.get("question")},
                ]),
                "manifest_sha256": spec.get("manifest_sha256"),
            }
            for key, value in expected_ok.items():
                if row.get(key) != value:
                    raise ProbeError(
                        f"invalid saved row {line_number}: {key} mismatch"
                    )
            answer = row.get("answer")
            if not isinstance(answer, str):
                raise ProbeError(
                    f"invalid saved row {line_number}: missing answer"
                )
            classification, integers = classify_answer(
                answer,
                task,
                spec.get("truth") or {},
            )
            if row.get("classification") != classification:
                raise ProbeError(
                    f"invalid saved row {line_number}: classification mismatch"
                )
            if row.get("parsed_integers") != integers:
                raise ProbeError(
                    f"invalid saved row {line_number}: parsed integers mismatch"
                )
            expected_sampler = {
                **research_c.sampler_record({
                    **(spec.get("sampler") or {}),
                    "seed": task.get("seed"),
                }),
                "thinking": False,
                "cache_prompt": True,
            }
            if row.get("sampler") != expected_sampler:
                raise ProbeError(
                    f"invalid saved row {line_number}: sampler mismatch"
                )
            truth = spec.get("truth") or {}
            expected_truth = {
                "path": task.get("path"),
                "kind": task.get("kind"),
                "directory_lines": truth.get("directory_lines"),
                "target": (
                    truth.get("directory_lines")
                    if task.get("kind") == "directory"
                    else (
                        (truth.get("files") or {})
                        .get(task.get("path"), {})
                        .get("lines")
                    )
                ),
                "injected_lines": INJECTED_TOTAL,
            }
            if row.get("truth") != expected_truth:
                raise ProbeError(
                    f"invalid saved row {line_number}: truth mismatch"
                )
            if not _state_equal(
                spec.get("repository_state") or {},
                row.get("repository_state_before") or {},
            ):
                raise ProbeError(
                    f"invalid saved row {line_number}: repository mismatch"
                )
            found.add(trial_id)
    return found


def _wait_for_idle_slot():
    deadline = time.monotonic() + SLOT_WAIT_SECONDS
    last = None
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
        last = slots[0]
        if not last.get("is_processing"):
            return {
                key: last.get(key)
                for key in (
                    "id",
                    "is_processing",
                    "n_prompt_tokens",
                    "n_prompt_tokens_processed",
                    "n_prompt_tokens_cache",
                )
            }
        if time.monotonic() >= deadline:
            raise ProbeError("Sable's only model slot stayed busy for 60 seconds")
        time.sleep(0.25)


def _request(prompt, task):
    slot = _wait_for_idle_slot()
    payload = dict(SAMPLER)
    payload["seed"] = task["seed"]
    payload["messages"] = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": task["question"]},
    ]
    started = utc_now()
    wall_start = time.perf_counter()
    response = requests.post(
        SERVER_URL + "/v1/chat/completions",
        headers=MODEL_REQUEST_HEADERS,
        json=payload,
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
        raise ProbeError("completion response contains no text answer")
    return {
        "answer": answer.strip(),
        "finish_reason": choices[0].get("finish_reason"),
        "usage": data.get("usage") or {},
        "timings": data.get("timings") or {},
        "started_utc": started,
        "ended_utc": ended,
        "elapsed_seconds": round(elapsed, 6),
        "precall_slot": slot,
    }


def _state_equal(left, right):
    keys = (
        "head",
        "branch",
        "status_sha256",
        "tracked_diff_sha256",
        "staged_diff_sha256",
        "source_inventory_sha256",
        "manifest_sha256",
    )
    return all(left.get(key) == right.get(key) for key in keys)


def prepare(output_dir):
    output_dir = Path(output_dir).resolve()
    try:
        output_relative = output_dir.relative_to(ROOT)
    except ValueError as exc:
        raise ProbeError("output directory must stay inside the repository") from exc

    prompt_pair = build_prompt_pair()
    before = repo_state(output_relative)
    bound = bindings()
    if len(str(bound.get("model_sha256") or "")) != 64:
        raise ProbeError("model SHA-256 binding failed")
    if len(str(bound.get("server_bundle_sha256") or "")) != 64:
        raise ProbeError("server-bundle SHA-256 binding failed")

    prompt_artifact = {
        "schema": SCHEMA,
        "baseline": prompt_pair["baseline"],
        "perturbed": prompt_pair["perturbed"],
    }
    prompt_artifact_sha = sha256_value(prompt_artifact)
    spec_core = {
        "schema": SCHEMA,
        "experiment": "researchc_aggregate_substitution_preflight",
        "purpose": "causal manipulation check; not a significance test",
        "mode": "hazard",
        "created_utc": utc_now(),
        "repository_state": before,
        "bindings": bound,
        "sampler": SAMPLER,
        "timeout_seconds": TIMEOUT_SECONDS,
        "manifest_sha256": sha256_text(prompt_pair["manifest"]),
        "baseline_system_prompt_sha256": sha256_text(prompt_pair["baseline"]),
        "perturbed_system_prompt_sha256": sha256_text(
            prompt_pair["perturbed"]
        ),
        "frozen_prompt_artifact_sha256": prompt_artifact_sha,
        "baseline_prompt_chars": len(prompt_pair["baseline"]),
        "perturbed_prompt_chars": len(prompt_pair["perturbed"]),
        "baseline_prompt_tokens": _token_count(prompt_pair["baseline"]),
        "perturbed_prompt_tokens": _token_count(prompt_pair["perturbed"]),
        "anchor": prompt_pair["anchor"],
        "replacement": prompt_pair["replacement"],
        "replacement_count": 1,
        "different_character_positions": (
            prompt_pair["different_character_positions"]
        ),
        "truth": prompt_pair["truth"],
        "tasks": tasks(),
        "decision_rule": {
            "void": "q0 does not move from 4353 to 7731",
            "pass": "q0 moves and both file pairs move 4353 to 7731",
            "stop": "q0 moves and neither file answer takes up 7731",
            "inconclusive": "one file moves or baseline copying does not reproduce"
        },
    }
    spec = dict(spec_core)
    spec["spec_sha256"] = sha256_value(spec_core)
    return output_dir, output_relative, prompt_artifact, spec


def _load_or_create(output_dir):
    output_dir, output_relative, prompts, spec = prepare(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = output_dir / "preflight_prompts.json"
    spec_path = output_dir / "preflight_spec.json"

    if spec_path.exists() or prompt_path.exists():
        if not spec_path.exists() or not prompt_path.exists():
            raise ProbeError("resume requires both frozen spec and prompt artifact")
        stored_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        stored_prompts = json.loads(prompt_path.read_text(encoding="utf-8"))
        if not isinstance(stored_spec, dict):
            raise ProbeError("stored frozen spec must be an object")
        if not isinstance(stored_prompts, dict):
            raise ProbeError("stored frozen-prompt artifact must be an object")
        stored_core = dict(stored_spec)
        claimed_spec_sha = stored_core.pop("spec_sha256", None)
        if sha256_value(stored_core) != claimed_spec_sha:
            raise ProbeError("stored frozen spec digest does not match")
        if sha256_value(stored_prompts) != stored_spec.get(
            "frozen_prompt_artifact_sha256"
        ):
            raise ProbeError("stored frozen-prompt artifact digest does not match")
        for condition, digest_key, chars_key in (
            ("baseline", "baseline_system_prompt_sha256", "baseline_prompt_chars"),
            (
                "perturbed",
                "perturbed_system_prompt_sha256",
                "perturbed_prompt_chars",
            ),
        ):
            prompt = stored_prompts.get(condition)
            if (
                not isinstance(prompt, str)
                or sha256_text(prompt) != stored_spec.get(digest_key)
                or len(prompt) != stored_spec.get(chars_key)
            ):
                raise ProbeError(
                    f"stored {condition} frozen prompt does not match its spec"
                )
        # The live repository must still be the one the stored run bound.
        current = repo_state(output_relative)
        if not _state_equal(stored_spec["repository_state"], current):
            raise ProbeError("repository or manifest drifted since run creation")
        current_definition = {
            key: spec.get(key) for key in _RESUME_DEFINITION_FIELDS
        }
        stored_definition = {
            key: stored_spec.get(key) for key in _RESUME_DEFINITION_FIELDS
        }
        if sha256_value(current_definition) != sha256_value(stored_definition):
            raise ProbeError("experiment definition drifted since run creation")
        if spec.get("bindings") != stored_spec.get("bindings"):
            raise ProbeError("model or server binding drifted since run creation")
        return (
            output_dir,
            output_relative,
            stored_prompts,
            stored_spec,
        )

    _atomic_json(prompt_path, prompts)
    _atomic_json(spec_path, spec)
    return output_dir, output_relative, prompts, spec


def _summary(rows, truth):
    by_id = {row["trial_id"]: row for row in rows if row.get("status") == "ok"}

    def one(question, condition):
        return by_id.get(f"{question}-{condition}", {}).get("classification")

    def integers(question, condition):
        return set(
            by_id.get(f"{question}-{condition}", {}).get(
                "parsed_integers", ()
            )
        )

    directory_lines = truth["directory_lines"]
    control = (
        directory_lines in integers("q0", "baseline")
        and INJECTED_TOTAL not in integers("q0", "baseline")
        and INJECTED_TOTAL in integers("q0", "perturbed")
        and directory_lines not in integers("q0", "perturbed")
    )
    moved = []
    for question in ("q1", "q2"):
        moved.append(
            one(question, "baseline") == "BASELINE_AGGREGATE"
            and one(question, "perturbed") == "INJECTED_AGGREGATE"
        )
    complete = len(by_id) == 6
    if not complete:
        verdict = "incomplete"
    elif not control:
        verdict = "void"
    elif all(moved):
        verdict = "mechanism_screen_pass"
    elif not any(moved):
        verdict = "stop_current_redesign_hypothesis"
    else:
        verdict = "inconclusive"
    return {
        "schema": SCHEMA,
        "experiment": "researchc_aggregate_substitution_preflight",
        "completed_rows": len(by_id),
        "control_moved": control,
        "file_pairs_moved": sum(moved),
        "file_pair_results": {"q1": moved[0], "q2": moved[1]},
        "verdict": verdict,
        "note": (
            "Six calls are a manipulation check, not a powered significance "
            "test; two unanimous file moves would have two-sided sign p = 0.5. "
            "The aggregate control passes when the requested total moves even "
            "if the answer also contains a separate file-count integer."
        ),
        "truth_digest": sha256_value(truth),
    }


def run(output_dir):
    output_dir, output_relative, prompts, spec = _load_or_create(output_dir)
    rows_path = output_dir / "preflight_rows.jsonl"
    completed = _completed_ids(rows_path, spec, prompts)
    baseline_state = spec["repository_state"]
    prompt_by_condition = {
        "baseline": prompts["baseline"],
        "perturbed": prompts["perturbed"],
    }

    for task in sorted(spec["tasks"], key=lambda item: item["execution_order"]):
        if task["trial_id"] in completed:
            continue
        current = repo_state(output_relative)
        if not _state_equal(baseline_state, current):
            raise ProbeError(
                f"repository or manifest drift before {task['trial_id']}"
            )
        prompt = prompt_by_condition[task["condition"]]
        try:
            response = _request(prompt, task)
            classification, integers = classify_answer(
                response["answer"], task, spec["truth"]
            )
            row = {
                "schema": SCHEMA,
                "status": "ok",
                "experiment": spec["experiment"],
                "spec_sha256": spec["spec_sha256"],
                "trial_id": task["trial_id"],
                "question_id": task["id"],
                "condition": task["condition"],
                "execution_order": task["execution_order"],
                "seed": task["seed"],
                "question": task["question"],
                "question_sha256": sha256_text(task["question"]),
                "system_prompt_sha256": sha256_text(prompt),
                "messages_sha256": research_c.prompt_digest([
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": task["question"]},
                ]),
                "manifest_sha256": spec["manifest_sha256"],
                "sampler": {
                    **research_c.sampler_record({
                        **SAMPLER,
                        "seed": task["seed"],
                    }),
                    "thinking": False,
                    "cache_prompt": True,
                },
                "repository_state_before": current,
                "truth": {
                    "path": task["path"],
                    "kind": task["kind"],
                    "directory_lines": spec["truth"]["directory_lines"],
                    "target": (
                        spec["truth"]["directory_lines"]
                        if task["kind"] == "directory"
                        else spec["truth"]["files"][task["path"]]["lines"]
                    ),
                    "injected_lines": INJECTED_TOTAL,
                },
                "answer": response.pop("answer"),
                "parsed_integers": integers,
                "classification": classification,
                **response,
            }
        except Exception as error:
            row = {
                "schema": SCHEMA,
                "status": "error",
                "experiment": spec["experiment"],
                "spec_sha256": spec["spec_sha256"],
                "trial_id": task["trial_id"],
                "question_id": task["id"],
                "condition": task["condition"],
                "execution_order": task["execution_order"],
                "seed": task["seed"],
                "question_sha256": sha256_text(task["question"]),
                "error_type": type(error).__name__,
                "error": str(error)[:500],
                "ended_utc": utc_now(),
            }
            _append_jsonl(rows_path, row)
            raise
        _append_jsonl(rows_path, row)

    final_state = repo_state(output_relative)
    if not _state_equal(baseline_state, final_state):
        raise ProbeError("repository or manifest drifted during the run")
    rows = [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = _summary(rows, spec["truth"])
    summary["repository_state_after"] = final_state
    summary["completed_utc"] = utc_now()
    _atomic_json(output_dir / "preflight_summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(
            ROOT / "handoffs" / "researchc_experiments_2026-07-30"
        ),
        help="evidence directory inside the repository",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print the frozen experiment without completions",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        output_dir, _relative, _prompts, spec = prepare(args.out)
        print(json.dumps({
            "output": str(output_dir),
            "experiment": spec["experiment"],
            "spec_sha256": spec["spec_sha256"],
            "tasks": len(spec["tasks"]),
            "anchor": spec["anchor"],
            "replacement": spec["replacement"],
            "bindings": spec["bindings"],
            "prompt_tokens": {
                "baseline": spec["baseline_prompt_tokens"],
                "perturbed": spec["perturbed_prompt_tokens"],
            },
        }, indent=2, sort_keys=True))
        return 0

    summary = run(args.out)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
