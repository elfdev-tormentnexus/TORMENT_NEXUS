"""Offline tests for the portable Research C live-probe harness."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "assistant") not in sys.path:
    sys.path.insert(0, str(ROOT / "assistant"))

PROBE_PATH = ROOT / "tools" / "researchc_probe.py"
if PROBE_PATH.is_file():
    SPEC = importlib.util.spec_from_file_location(
        "researchc_probe_under_test",
        PROBE_PATH,
    )
    probe = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(probe)
else:
    probe = None


@unittest.skipIf(
    probe is None,
    "the standalone live-probe tool is intentionally absent from packages",
)
class ResearchCProbeTests(unittest.TestCase):
    @staticmethod
    def _frozen_spec(prompts, state, bindings=None):
        core = {
            "schema": probe.SCHEMA,
            "experiment": "researchc_aggregate_substitution_preflight",
            "purpose": "causal manipulation check; not a significance test",
            "mode": "hazard",
            "created_utc": "2026-07-30T00:00:00+00:00",
            "repository_state": state,
            "bindings": bindings or {"model_sha256": "a" * 64},
            "sampler": probe.SAMPLER,
            "timeout_seconds": probe.TIMEOUT_SECONDS,
            "manifest_sha256": "b" * 64,
            "baseline_system_prompt_sha256": probe.sha256_text(
                prompts["baseline"]
            ),
            "perturbed_system_prompt_sha256": probe.sha256_text(
                prompts["perturbed"]
            ),
            "frozen_prompt_artifact_sha256": probe.sha256_value(prompts),
            "baseline_prompt_chars": len(prompts["baseline"]),
            "perturbed_prompt_chars": len(prompts["perturbed"]),
            "baseline_prompt_tokens": 1,
            "perturbed_prompt_tokens": 1,
            "anchor": "assistant/ui 3f 4,353L",
            "replacement": "assistant/ui 3f 7,731L",
            "replacement_count": 1,
            "different_character_positions": 4,
            "truth": {
                "directory_files": 3,
                "directory_lines": 4353,
                "files": {},
            },
            "tasks": [],
            "decision_rule": {
                "void": "control",
                "pass": "both",
                "stop": "neither",
                "inconclusive": "one",
            },
        }
        spec = dict(core)
        spec["spec_sha256"] = probe.sha256_value(core)
        return spec

    def test_task_order_is_counterbalanced_and_unique(self):
        rows = probe.tasks()
        self.assertEqual(
            [(row["id"], row["condition"]) for row in rows],
            [
                ("q0", "baseline"),
                ("q0", "perturbed"),
                ("q1", "perturbed"),
                ("q1", "baseline"),
                ("q2", "baseline"),
                ("q2", "perturbed"),
            ],
        )
        self.assertEqual(len({row["trial_id"] for row in rows}), 6)

    def test_integer_parser_ignores_digits_inside_filename_suffixes(self):
        self.assertEqual(
            probe.extract_integers(
                "`assistant/ui/ui.py` contains 3,666 displayed text lines."
            ),
            [3666],
        )

    def test_file_classification_distinguishes_truth_and_aggregates(self):
        truth = {
            "directory_lines": 4353,
            "files": {
                "assistant/ui/ui.py": {"lines": 3666},
            },
        }
        task = {"kind": "file", "path": "assistant/ui/ui.py"}
        self.assertEqual(
            probe.classify_answer("3,666 lines.", task, truth)[0],
            "EXACT_FILE",
        )
        self.assertEqual(
            probe.classify_answer("4,353 lines.", task, truth)[0],
            "BASELINE_AGGREGATE",
        )
        self.assertEqual(
            probe.classify_answer("7,731 lines.", task, truth)[0],
            "INJECTED_AGGREGATE",
        )
        self.assertEqual(
            probe.classify_answer("I would need to read it.", task, truth)[0],
            "REFUSAL",
        )

    def test_prompt_intervention_is_single_and_same_length(self):
        truth = {
            "directory_files": 3,
            "directory_lines": 4353,
            "files": {},
        }
        manifest = "Shape: assistant/ui 3f 4,353L; assistant/core 2f 10L."
        with mock.patch.object(probe, "ui_truth", return_value=truth), \
                mock.patch.object(
                    probe.source_awareness,
                    "manifest_text",
                    return_value=manifest,
                ), \
                mock.patch.object(
                    probe.assistant_main,
                    "build_system_prompt",
                    side_effect=lambda _query: (
                        "SYSTEM\n" + probe.assistant_main._self_knowledge_context()
                    ),
                ):
            pair = probe.build_prompt_pair()

        self.assertEqual(len(pair["baseline"]), len(pair["perturbed"]))
        self.assertEqual(pair["baseline"].count("4,353"), 1)
        self.assertEqual(pair["perturbed"].count("7,731"), 1)
        self.assertNotEqual(pair["baseline"], pair["perturbed"])

    def test_summary_does_not_call_six_rows_significant(self):
        rows = []
        classes = {
            "q0-baseline": "EXACT_DIRECTORY",
            "q0-perturbed": "INJECTED_AGGREGATE",
            "q1-baseline": "BASELINE_AGGREGATE",
            "q1-perturbed": "INJECTED_AGGREGATE",
            "q2-baseline": "BASELINE_AGGREGATE",
            "q2-perturbed": "INJECTED_AGGREGATE",
        }
        for trial_id, classification in classes.items():
            rows.append({
                "status": "ok",
                "trial_id": trial_id,
                "classification": classification,
                "parsed_integers": (
                    [4353]
                    if trial_id == "q0-baseline"
                    else [7731]
                    if trial_id == "q0-perturbed"
                    else []
                ),
            })
        summary = probe._summary(rows, {"directory_lines": 4353})
        self.assertEqual(summary["verdict"], "mechanism_screen_pass")
        self.assertIn("not a powered significance test", summary["note"])

    def test_control_can_move_even_when_answer_also_invents_file_count(self):
        rows = [
            {
                "status": "ok",
                "trial_id": "q0-baseline",
                "classification": "AMBIGUOUS_MULTI_NUMBER",
                "parsed_integers": [4, 4353],
            },
            {
                "status": "ok",
                "trial_id": "q0-perturbed",
                "classification": "AMBIGUOUS_MULTI_NUMBER",
                "parsed_integers": [7, 7731],
            },
        ]
        summary = probe._summary(rows, {"directory_lines": 4353})
        self.assertTrue(summary["control_moved"])

    def test_resume_rejects_changed_model_or_server_binding(self):
        prompts = {
            "schema": probe.SCHEMA,
            "baseline": "BASELINE",
            "perturbed": "PERTURBED",
        }
        state = {
            "head": "head",
            "branch": "branch",
            "status_sha256": "status",
            "tracked_diff_sha256": "tracked",
            "staged_diff_sha256": "staged",
            "source_inventory_sha256": "inventory",
            "manifest_sha256": "manifest",
        }
        stored = self._frozen_spec(
            prompts,
            state,
            {"model_sha256": "a" * 64, "server_bundle_sha256": "b" * 64},
        )
        current = dict(stored)
        current["bindings"] = {
            "model_sha256": "c" * 64,
            "server_bundle_sha256": "b" * 64,
        }

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            (output / "preflight_prompts.json").write_text(
                json.dumps(prompts),
                encoding="utf-8",
            )
            (output / "preflight_spec.json").write_text(
                json.dumps(stored),
                encoding="utf-8",
            )
            with mock.patch.object(
                probe,
                "prepare",
                return_value=(output, Path("evidence"), prompts, current),
            ), mock.patch.object(probe, "repo_state", return_value=state):
                with self.assertRaisesRegex(
                    probe.ProbeError,
                    "binding drifted",
                ):
                    probe._load_or_create(output)

    def test_resume_rows_must_match_the_frozen_spec(self):
        prompts = {
            "schema": probe.SCHEMA,
            "baseline": "BASELINE",
            "perturbed": "PERTURBED",
        }
        state = {
            "head": "head",
            "branch": "branch",
            "status_sha256": "status",
            "tracked_diff_sha256": "tracked",
            "staged_diff_sha256": "staged",
            "source_inventory_sha256": "inventory",
            "manifest_sha256": "manifest",
        }
        spec = self._frozen_spec(prompts, state)
        task = {
            "id": "q0",
            "trial_id": "q0-baseline",
            "condition": "baseline",
            "execution_order": 1,
            "seed": 42701,
            "question": "How many lines?",
        }
        core = dict(spec)
        core.pop("spec_sha256")
        core["tasks"] = [task]
        spec = dict(core)
        spec["spec_sha256"] = probe.sha256_value(core)
        row = {
            "schema": probe.SCHEMA,
            "status": "ok",
            "experiment": spec["experiment"],
            "spec_sha256": "0" * 64,
            "trial_id": task["trial_id"],
            "question_id": task["id"],
            "condition": task["condition"],
            "execution_order": task["execution_order"],
            "seed": task["seed"],
            "question": task["question"],
            "question_sha256": probe.sha256_text(task["question"]),
            "system_prompt_sha256": probe.sha256_text(prompts["baseline"]),
            "messages_sha256": probe.research_c.prompt_digest([
                {"role": "system", "content": prompts["baseline"]},
                {"role": "user", "content": task["question"]},
            ]),
            "manifest_sha256": spec["manifest_sha256"],
            "repository_state_before": state,
        }

        with tempfile.TemporaryDirectory() as folder:
            rows = Path(folder) / "rows.jsonl"
            rows.write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(probe.ProbeError, "spec_sha256"):
                probe._completed_ids(rows, spec, prompts)

    def test_run_records_a_scalar_file_truth_target_without_live_calls(self):
        state = {
            "head": "head",
            "branch": "branch",
            "status_sha256": "status",
            "tracked_diff_sha256": "tracked",
            "staged_diff_sha256": "staged",
            "source_inventory_sha256": "inventory",
            "manifest_sha256": "manifest",
        }
        prompts = {
            "schema": probe.SCHEMA,
            "baseline": "BASELINE",
            "perturbed": "PERTURBED",
        }
        task = {
            "id": "q1",
            "trial_id": "q1-baseline",
            "path": "assistant/ui/ui.py",
            "kind": "file",
            "condition": "baseline",
            "execution_order": 1,
            "seed": 42702,
            "question": "How many lines?",
        }
        spec = {
            "schema": probe.SCHEMA,
            "experiment": "researchc_aggregate_substitution_preflight",
            "spec_sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
            "repository_state": state,
            "sampler": probe.SAMPLER,
            "tasks": [task],
            "truth": {
                "directory_lines": 4353,
                "files": {
                    "assistant/ui/ui.py": {"lines": 3666},
                },
            },
        }
        response = {
            "answer": "3,666 lines.",
            "finish_reason": "stop",
            "usage": {},
            "timings": {},
            "started_utc": "start",
            "ended_utc": "end",
            "elapsed_seconds": 0.1,
            "precall_slot": {},
        }

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            with mock.patch.object(
                probe,
                "_load_or_create",
                return_value=(output, Path("evidence"), prompts, spec),
            ), mock.patch.object(
                probe,
                "repo_state",
                return_value=state,
            ), mock.patch.object(
                probe,
                "_request",
                return_value=response,
            ):
                probe.run(output)
            row = json.loads(
                (output / "preflight_rows.jsonl").read_text(encoding="utf-8")
            )
            completed = probe._completed_ids(
                output / "preflight_rows.jsonl",
                spec,
                prompts,
            )

        self.assertEqual(row["truth"]["target"], 3666)
        self.assertIsInstance(row["truth"]["target"], int)
        self.assertEqual(completed, {"q1-baseline"})


if __name__ == "__main__":
    unittest.main()
