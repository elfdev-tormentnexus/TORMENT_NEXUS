#!/usr/bin/env python3
"""Run the fixed Research C offline-library coverage and librarian probes.

The default run is deterministic and local: it builds disposable SQLite
indexes from the shipped cards, adds only the synthetic specialist fixtures
declared in ``researchc_library_cases.json``, and performs no embedding,
network, or model request.

``--with-librarian`` additionally exercises the separately configured local
shadow endpoint.  Its output still cannot affect retrieval; this tool merely
compares the proposed ranking with the same deterministic candidate pool in
normal and reversed presentation order.
"""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSISTANT_ROOT = PROJECT_ROOT / "assistant"
DEFAULT_CASES = Path(__file__).with_name("researchc_library_cases.json")

if str(ASSISTANT_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSISTANT_ROOT))

from core import librarian_shadow  # noqa: E402
from knowledge import library as knowledge_library  # noqa: E402


def _criterion(actual, required, passed):
    """One machine-readable gate condition with its observed value."""
    return {
        "actual": actual,
        "required": required,
        "passed": bool(passed),
    }


def load_cases(path=DEFAULT_CASES):
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != 1
        or not isinstance(payload.get("positive"), list)
        or not isinstance(payload.get("known_unknown"), list)
    ):
        raise ValueError("Research C library cases have an invalid schema.")
    return payload


def _write_fixture(root, relative, text):
    target = root.joinpath(*Path(relative).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


@contextmanager
def fixture_library(cases, include_specialists):
    with tempfile.TemporaryDirectory(
        prefix="researchc-library-",
    ) as folder:
        root = Path(folder)
        builtin = root / "builtin"
        user = root / "user"
        database = root / "library.sqlite3"
        manifest = root / "builtin_manifest.json"
        shutil.copytree(knowledge_library.BUILTIN_DIR, builtin)
        shutil.copy2(knowledge_library.BUILTIN_MANIFEST_PATH, manifest)
        user.mkdir()

        if include_specialists:
            for fixture in cases.get("specialist_fixtures") or ():
                _write_fixture(
                    user,
                    fixture["path"],
                    fixture["text"],
                )
            for fixture in cases.get("review_fixtures") or ():
                review_after = fixture.get("review_after")
                frontmatter = [
                    "---",
                    f"title: {fixture['query']}",
                    "publisher: Research C synthetic fixture",
                    "source_url: https://example.invalid/researchc-fixture",
                ]
                if review_after:
                    frontmatter.append(f"review_after: {review_after}")
                frontmatter.extend((
                    "---",
                    "",
                    f"# {fixture['query']}",
                    "",
                    "Synthetic review-label reference.",
                ))
                _write_fixture(
                    user,
                    fixture["path"],
                    "\n".join(frontmatter),
                )

        instance = knowledge_library.KnowledgeLibrary(
            str(builtin),
            str(user),
            str(database),
            builtin_manifest_path=str(manifest),
        )
        rebuild = instance.rebuild()
        yield instance, rebuild, root


def _reference_records(context):
    inside = False
    records = []
    for line in str(context or "").splitlines():
        if line.startswith("<offline_references"):
            inside = True
            continue
        if line == "</offline_references>":
            break
        if not inside:
            continue
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            return None
        if not isinstance(record, dict):
            return None
        records.append(record)
    return records


def _valid_digest(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _case_result(instance, case, expected_source=None):
    query = case["query"]
    candidates = instance.librarian_candidates(
        query,
        limit=librarian_shadow.MAX_CANDIDATES,
    )
    context, citations = instance.prompt_context_with_citations(query)
    candidate_paths = [
        candidate.get("display_path", "") for candidate in candidates
    ]
    selected_paths = [
        citation.get("path", "") for citation in citations
    ]
    records = _reference_records(context)
    citation_bijection = (
        records is not None
        and len(records) == len(citations)
        and [
            record.get("title") for record in records
        ] == [
            citation.get("title") for citation in citations
        ]
        and all(
            _valid_digest(citation.get("source_sha256"))
            for citation in citations
        )
    )

    expected_candidate_rank = None
    expected_selected_rank = None
    if expected_source:
        for index, path in enumerate(candidate_paths, 1):
            if path.endswith("/" + expected_source):
                expected_candidate_rank = index
                break
        for index, path in enumerate(selected_paths, 1):
            if path.endswith("/" + expected_source):
                expected_selected_rank = index
                break

    return {
        "id": case["id"],
        "query_sha256": librarian_shadow.digest(query),
        "candidate_count": len(candidates),
        "selected_count": len(citations),
        "candidate_recall_at_8": (
            expected_candidate_rank is not None
            if expected_source
            else None
        ),
        "selected_recall_at_1": (
            expected_selected_rank == 1
            if expected_source
            else None
        ),
        "selected_recall_at_3": (
            expected_selected_rank is not None
            and expected_selected_rank <= 3
            if expected_source
            else None
        ),
        "expected_candidate_rank": expected_candidate_rank,
        "expected_selected_rank": expected_selected_rank,
        "abstained": not citations,
        "specialist_intrusion": any(
            "/user/" in path for path in selected_paths
        ),
        "unique_source_ratio": (
            len(set(selected_paths)) / len(selected_paths)
            if selected_paths
            else 1.0
        ),
        "prompt_bytes": len(context.encode("utf-8")),
        "citation_bijection": citation_bijection,
    }


def _review_results(instance, cases):
    rows = []
    for fixture in cases.get("review_fixtures") or ():
        found = instance.search(fixture["query"], limit=1)
        actual = found[0]["review_status"] if found else "missing"
        rows.append({
            "path": fixture["path"],
            "expected": fixture["expected"],
            "actual": actual,
            "correct": actual == fixture["expected"],
        })
    return rows


def _trust_result(instance):
    query = "emergency kit rank passage"
    explicit = instance.search(query, limit=8)
    _context, automatic = instance.prompt_context_with_citations(query)
    suspicious = [
        result for result in explicit
        if result.get("metadata", {}).get("trust") == "suspicious"
    ]
    automatic_paths = {
        citation.get("path", "") for citation in automatic
    }
    return {
        "explicit_suspicious_visible": bool(suspicious),
        "automatic_suspicious_excluded": all(
            result.get("display_path", "") not in automatic_paths
            for result in suspicious
        ),
    }


def run_deterministic_suite(instance, cases, *, fixture_mode):
    positives = [
        _case_result(
            instance,
            case,
            expected_source=case["expected_source"],
        )
        for case in cases["positive"]
    ]
    unknowns = [
        _case_result(instance, case)
        for case in cases["known_unknown"]
    ]
    review = (
        _review_results(instance, cases)
        if fixture_mode == "specialist"
        else []
    )
    trust = (
        _trust_result(instance)
        if fixture_mode == "specialist"
        else {
            "explicit_suspicious_visible": None,
            "automatic_suspicious_excluded": None,
        }
    )

    positive_count = len(positives)
    unknown_count = len(unknowns)
    metrics = {
        "positive_cases": positive_count,
        "known_unknown_cases": unknown_count,
        "candidate_recall_at_8": sum(
            row["candidate_recall_at_8"] for row in positives
        ) / max(1, positive_count),
        "selected_recall_at_1": sum(
            row["selected_recall_at_1"] for row in positives
        ) / max(1, positive_count),
        "selected_recall_at_3": sum(
            row["selected_recall_at_3"] for row in positives
        ) / max(1, positive_count),
        "false_abstention_rate": sum(
            row["abstained"] for row in positives
        ) / max(1, positive_count),
        "known_unknown_abstention_accuracy": sum(
            row["abstained"] for row in unknowns
        ) / max(1, unknown_count),
        "specialist_intrusion_rate": sum(
            row["specialist_intrusion"] for row in positives
        ) / max(1, positive_count),
        "citation_bijection_accuracy": sum(
            row["citation_bijection"] for row in positives + unknowns
        ) / max(1, positive_count + unknown_count),
        "mean_unique_source_ratio": sum(
            row["unique_source_ratio"] for row in positives + unknowns
        ) / max(1, positive_count + unknown_count),
        "mean_prompt_bytes": sum(
            row["prompt_bytes"] for row in positives + unknowns
        ) / max(1, positive_count + unknown_count),
        "review_label_accuracy": (
            sum(row["correct"] for row in review) / len(review)
            if review
            else None
        ),
    }
    gate_criteria = {
        "candidate_recall_at_8": _criterion(
            metrics["candidate_recall_at_8"],
            1.0,
            metrics["candidate_recall_at_8"] == 1.0,
        ),
        "selected_recall_at_1": _criterion(
            metrics["selected_recall_at_1"],
            1.0,
            metrics["selected_recall_at_1"] == 1.0,
        ),
        "selected_recall_at_3": _criterion(
            metrics["selected_recall_at_3"],
            1.0,
            metrics["selected_recall_at_3"] == 1.0,
        ),
        "false_abstention_rate": _criterion(
            metrics["false_abstention_rate"],
            0.0,
            metrics["false_abstention_rate"] == 0.0,
        ),
        "known_unknown_abstention_accuracy": _criterion(
            metrics["known_unknown_abstention_accuracy"],
            1.0,
            metrics["known_unknown_abstention_accuracy"] == 1.0,
        ),
        "specialist_intrusion_rate": _criterion(
            metrics["specialist_intrusion_rate"],
            0.0,
            metrics["specialist_intrusion_rate"] == 0.0,
        ),
        "citation_bijection_accuracy": _criterion(
            metrics["citation_bijection_accuracy"],
            1.0,
            metrics["citation_bijection_accuracy"] == 1.0,
        ),
        "review_label_accuracy": _criterion(
            metrics["review_label_accuracy"],
            "not_applicable_or_1.0",
            metrics["review_label_accuracy"] in {None, 1.0},
        ),
        "automatic_suspicious_excluded": _criterion(
            trust["automatic_suspicious_excluded"],
            "not_applicable_or_true",
            trust["automatic_suspicious_excluded"] in {None, True},
        ),
    }
    strict_gate_passed = all(
        item["passed"] for item in gate_criteria.values()
    )
    is_release_baseline = fixture_mode == "builtins"
    return {
        "fixture_mode": fixture_mode,
        "metrics": metrics,
        "gate_role": (
            "deterministic_release"
            if is_release_baseline
            else "diagnostic_specialist_bait"
        ),
        "gate_enforced": is_release_baseline,
        "gate_criteria": gate_criteria,
        # The specialist fixture intentionally asks whether a large shelf can
        # lure retrieval away from the curated cards. Its failure is evidence
        # to preserve, not a reason for --enforce to fail every invocation.
        "release_gate_passed": (
            strict_gate_passed if is_release_baseline else None
        ),
        "specialist_stress_gate_passed": (
            strict_gate_passed if not is_release_baseline else None
        ),
        "positive": positives,
        "known_unknown": unknowns,
        "review": review,
        "trust": trust,
    }


def _candidate_id_for_source(job, candidates, expected_source):
    expected_fingerprint = None
    for candidate in candidates:
        if candidate.get("display_path", "").endswith(
            "/" + expected_source
        ):
            expected_fingerprint = librarian_shadow.candidate_fingerprint(
                candidate
            )
            break
    for packet in job["candidates"]:
        if packet["fingerprint"] == expected_fingerprint:
            return packet["id"]
    return None


def _librarian_one(
    query,
    candidates,
    expected_source,
    baseline_fingerprints,
    path,
):
    job = librarian_shadow.prepare_job(
        query,
        candidates,
        baseline_fingerprints=baseline_fingerprints,
    )
    if job is None:
        return {
            "valid": False,
            "outcome": "baseline_not_in_pool",
            "success": False,
            "abstained": True,
            "selected_fingerprints": [],
            "prompt_bytes": 0,
            "wall_seconds": 0.0,
        }
    started = time.perf_counter()
    decision = librarian_shadow.evaluate(
        job,
        path=path,
        is_busy_fn=lambda: False,
    )
    outcome = librarian_shadow.status()["last_outcome"]
    wall_seconds = time.perf_counter() - started
    expected_id = (
        _candidate_id_for_source(job, candidates, expected_source)
        if expected_source
        else None
    )
    selected = decision["selected_ids"] if decision else []
    by_id = {
        packet["id"]: packet["fingerprint"]
        for packet in job["candidates"]
    }
    abstained = bool(
        decision is None or decision["route"] == "abstain"
    )
    success = bool(
        decision is not None
        and (
            expected_id in selected
            if expected_source
            else abstained
        )
    )
    return {
        "valid": decision is not None,
        "outcome": outcome,
        "success": success,
        "abstained": abstained,
        "selected_fingerprints": [
            by_id[item] for item in selected if item in by_id
        ],
        "prompt_bytes": sum(
            len(message["content"].encode("utf-8"))
            for message in librarian_shadow.build_prompt(job)
        ),
        "wall_seconds": wall_seconds,
    }


def _order_agrees(forward, reverse):
    return bool(
        forward["valid"]
        and reverse["valid"]
        and forward["selected_fingerprints"]
        == reverse["selected_fingerprints"]
    )


def _attach_librarian_gate(result, expected_attempts):
    """Attach the promotion gate without hiding any component threshold."""
    criteria = {
        "attempts_complete": _criterion(
            result["attempts"],
            expected_attempts,
            result["attempts"] == expected_attempts,
        ),
        "parse_validity": _criterion(
            result["parse_validity"],
            1.0,
            result["parse_validity"] == 1.0,
        ),
        "task_accuracy": _criterion(
            result["task_accuracy"],
            1.0,
            result["task_accuracy"] == 1.0,
        ),
        "order_agreement": _criterion(
            result["order_agreement"],
            1.0,
            result["order_agreement"] == 1.0,
        ),
    }
    result["librarian_gate_criteria"] = criteria
    result["librarian_gate_passed"] = bool(
        expected_attempts > 0
        and all(item["passed"] for item in criteria.values())
    )
    return result


def run_librarian_suite(instance, cases, evidence_path):
    if not librarian_shadow.configured():
        raise RuntimeError(
            "The shadow librarian needs an explicit authenticated loopback "
            "endpoint, model alias, and model/server digests."
        )
    case_by_id = {
        case["id"]: (case, case.get("expected_source"))
        for case in cases["positive"] + cases["known_unknown"]
    }
    rows = []
    for case_id in cases.get("librarian_boundary_ids") or ():
        case, expected = case_by_id[case_id]
        _context, citations = instance.prompt_context_with_citations(
            case["query"],
        )
        candidates = instance.librarian_candidate_snapshot(
            case["query"],
            citations,
            limit=librarian_shadow.MAX_CANDIDATES,
        ) or []
        baseline_fingerprints = [
            citation["librarian_fingerprint"]
            for citation in citations
        ]
        forward = _librarian_one(
            case["query"],
            candidates,
            expected,
            baseline_fingerprints,
            evidence_path,
        )
        reverse = _librarian_one(
            case["query"],
            list(reversed(candidates)),
            expected,
            baseline_fingerprints,
            evidence_path,
        )
        rows.append({
            "id": case_id,
            "forward": forward,
            "reverse": reverse,
            "order_agreement": _order_agrees(forward, reverse),
        })

    attempts = len(rows) * 2
    result = {
        "attempts": attempts,
        "case_count": len(rows),
        "cases": rows,
        "parse_validity": sum(
            row[side]["valid"]
            for row in rows
            for side in ("forward", "reverse")
        ) / max(1, attempts),
        "task_accuracy": sum(
            row[side]["success"]
            for row in rows
            for side in ("forward", "reverse")
        ) / max(1, attempts),
        "order_agreement": sum(
            row["order_agreement"] for row in rows
        ) / max(1, len(rows)),
        "mean_prompt_bytes": sum(
            row[side]["prompt_bytes"]
            for row in rows
            for side in ("forward", "reverse")
        ) / max(1, attempts),
        "mean_wall_seconds": sum(
            row[side]["wall_seconds"]
            for row in rows
            for side in ("forward", "reverse")
        ) / max(1, attempts),
    }
    return _attach_librarian_gate(
        result,
        len(cases.get("librarian_boundary_ids") or ()) * 2,
    )


def run(cases_path=DEFAULT_CASES, *, with_librarian=False):
    cases = load_cases(cases_path)
    report = {
        "schema": 1,
        "effective_date": time.strftime("%Y-%m-%d"),
        "cases_sha256": librarian_shadow.digest(cases),
        "suites": [],
        "deterministic_gate_passed": None,
        "librarian": None,
        "librarian_gate_passed": None,
    }

    for include_specialists, label in (
        (False, "builtins"),
        (True, "specialist"),
    ):
        with fixture_library(
            cases,
            include_specialists,
        ) as (instance, rebuild, root):
            suite = run_deterministic_suite(
                instance,
                cases,
                fixture_mode=label,
            )
            suite["index"] = {
                "changed": rebuild.get("changed", 0),
                "errors": len(rebuild.get("errors") or ()),
                "sources": instance.status().get("sources", 0),
                "chunks": instance.status().get("chunks", 0),
            }
            report["suites"].append(suite)
            if not include_specialists:
                report["deterministic_gate_passed"] = bool(
                    suite["release_gate_passed"]
                )
            if with_librarian and include_specialists:
                report["librarian"] = run_librarian_suite(
                    instance,
                    cases,
                    str(root / "librarian_shadow.jsonl"),
                )
                report["librarian_gate_passed"] = report[
                    "librarian"
                ]["librarian_gate_passed"]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES,
        help="fixed probe case JSON",
    )
    parser.add_argument(
        "--with-librarian",
        action="store_true",
        help="also call the explicitly configured local shadow endpoint",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the JSON report here as well as printing it",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help=(
            "exit nonzero unless the deterministic built-in release gate "
            "passes; specialist-bait findings remain diagnostic"
        ),
    )
    parser.add_argument(
        "--enforce-librarian",
        action="store_true",
        help=(
            "also exit nonzero unless --with-librarian completed and its "
            "strict promotion gate passed"
        ),
    )
    args = parser.parse_args(argv)

    report = run(
        args.cases,
        with_librarian=args.with_librarian,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            rendered + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(rendered)

    if args.enforce and not report["deterministic_gate_passed"]:
        return 1
    if (
        args.enforce_librarian
        and report["librarian_gate_passed"] is not True
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
