import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = ROOT / "tools" / "researchc_library_probe.py"
SPEC = importlib.util.spec_from_file_location(
    "researchc_library_probe_under_test",
    PROBE_PATH,
)
PROBE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PROBE
SPEC.loader.exec_module(PROBE)


class ResearchCLibraryProbeTests(unittest.TestCase):
    def test_case_file_has_stable_unique_ids(self):
        cases = PROBE.load_cases()
        ids = [
            row["id"]
            for row in cases["positive"] + cases["known_unknown"]
        ]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(cases["positive"]), 18)
        self.assertEqual(len(cases["known_unknown"]), 10)

    def test_deterministic_probe_reproduces_the_known_boundary(self):
        with mock.patch.object(
            PROBE.librarian_shadow,
            "evaluate",
            side_effect=AssertionError("model must not run"),
        ):
            report = PROBE.run(with_librarian=False)

        self.assertEqual(report["schema"], 1)
        self.assertIsNone(report["librarian"])
        self.assertTrue(report["deterministic_gate_passed"])
        self.assertIsNone(report["librarian_gate_passed"])
        builtins, specialist = report["suites"]
        self.assertTrue(builtins["release_gate_passed"])
        self.assertTrue(builtins["gate_enforced"])
        self.assertEqual(builtins["gate_role"], "deterministic_release")
        self.assertEqual(
            builtins["metrics"]["candidate_recall_at_8"],
            1.0,
        )
        self.assertEqual(
            builtins["metrics"]["known_unknown_abstention_accuracy"],
            1.0,
        )

        # These are intentionally a measured failing baseline, not a desired
        # invariant. If relevance changes, this assertion forces the Research
        # C evidence and release gate to be reviewed rather than silently
        # rewriting the historical 5/10 and 2/18 result.
        self.assertEqual(
            specialist["metrics"]["known_unknown_abstention_accuracy"],
            0.5,
        )
        self.assertEqual(
            sum(
                row["specialist_intrusion"]
                for row in specialist["positive"]
            ),
            2,
        )
        self.assertIsNone(specialist["release_gate_passed"])
        self.assertFalse(specialist["specialist_stress_gate_passed"])
        self.assertFalse(specialist["gate_enforced"])
        self.assertEqual(
            specialist["gate_role"],
            "diagnostic_specialist_bait",
        )
        self.assertEqual(
            specialist["metrics"]["review_label_accuracy"],
            1.0,
        )
        self.assertTrue(
            specialist["trust"]["automatic_suspicious_excluded"]
        )

    def test_enforcement_ignores_the_intentionally_failing_stress_fixture(self):
        report = {
            "deterministic_gate_passed": True,
            "librarian_gate_passed": None,
        }
        with mock.patch.object(PROBE, "run", return_value=report), \
                mock.patch("builtins.print"):
            status = PROBE.main(["--enforce"])

        self.assertEqual(status, 0)

    def test_librarian_gate_names_every_promotion_requirement(self):
        result = PROBE._attach_librarian_gate(
            {
                "attempts": 16,
                "parse_validity": 0.6875,
                "task_accuracy": 0.5625,
                "order_agreement": 0.125,
            },
            expected_attempts=16,
        )

        self.assertFalse(result["librarian_gate_passed"])
        self.assertEqual(
            set(result["librarian_gate_criteria"]),
            {
                "attempts_complete",
                "parse_validity",
                "task_accuracy",
                "order_agreement",
            },
        )
        self.assertTrue(
            result["librarian_gate_criteria"]["attempts_complete"]["passed"]
        )
        self.assertFalse(
            result["librarian_gate_criteria"]["parse_validity"]["passed"]
        )

    def test_report_contains_digests_not_case_query_text(self):
        cases = PROBE.load_cases()
        with PROBE.fixture_library(
            cases,
            include_specialists=False,
        ) as (instance, _rebuild, _root):
            suite = PROBE.run_deterministic_suite(
                instance,
                cases,
                fixture_mode="builtins",
            )

        rendered = str(suite)
        for case in cases["positive"] + cases["known_unknown"]:
            self.assertNotIn(case["query"], rendered)
        for row in suite["positive"] + suite["known_unknown"]:
            self.assertRegex(row["query_sha256"], r"^[0-9a-f]{64}$")

    def test_invalid_abstention_cannot_count_as_success(self):
        job = {
            "candidates": [
                {
                    "id": "c1",
                    "fingerprint": "a" * 64,
                },
            ],
        }
        with (
            mock.patch.object(
                PROBE.librarian_shadow,
                "prepare_job",
                return_value=job,
            ),
            mock.patch.object(
                PROBE.librarian_shadow,
                "evaluate",
                return_value=None,
            ),
            mock.patch.object(
                PROBE.librarian_shadow,
                "status",
                return_value={"last_outcome": "invalid_abstention"},
            ),
            mock.patch.object(
                PROBE.librarian_shadow,
                "build_prompt",
                return_value=[],
            ),
        ):
            result = PROBE._librarian_one(
                "What is missing?",
                [],
                None,
                [],
                Path("unused.jsonl"),
            )

        self.assertFalse(result["valid"])
        self.assertFalse(result["success"])
        self.assertTrue(result["abstained"])

    def test_missing_baseline_cannot_count_as_success(self):
        with mock.patch.object(
            PROBE.librarian_shadow,
            "prepare_job",
            return_value=None,
        ):
            result = PROBE._librarian_one(
                "What is missing?",
                [],
                None,
                [],
                Path("unused.jsonl"),
            )

        self.assertEqual(result["outcome"], "baseline_not_in_pool")
        self.assertFalse(result["valid"])
        self.assertFalse(result["success"])

    def test_invalid_empty_decisions_cannot_count_as_order_agreement(self):
        invalid = {
            "valid": False,
            "selected_fingerprints": [],
        }
        valid_abstention = {
            "valid": True,
            "selected_fingerprints": [],
        }

        self.assertFalse(PROBE._order_agrees(invalid, invalid))
        self.assertFalse(PROBE._order_agrees(invalid, valid_abstention))
        self.assertTrue(
            PROBE._order_agrees(
                valid_abstention,
                valid_abstention,
            )
        )


if __name__ == "__main__":
    unittest.main()
