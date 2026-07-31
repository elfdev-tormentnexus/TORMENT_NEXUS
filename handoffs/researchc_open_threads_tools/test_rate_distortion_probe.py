"""Offline checks for the frozen Research C 2x2 collector."""

import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "rate_distortion_probe_under_test",
    HERE / "rate_distortion_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class RateDistortionProbeTests(unittest.TestCase):
    def test_proposition_sets_have_declared_relation(self):
        low = probe.proposition_set("low")
        high = probe.proposition_set("high")
        self.assertEqual(len(low), 58)
        self.assertEqual(len(high), 70)
        self.assertTrue(low < high)
        self.assertEqual(len(high - low), 12)

    def test_renderers_preserve_facts_and_only_high_adds_lines(self):
        rendered = probe.manifests()
        self.assertIn(
            "F|path|exists=yes[|file_lines=N]",
            rendered["LC"],
        )
        self.assertNotIn("file_lines=687", rendered["LC"])
        self.assertIn(
            "F|assistant/ui/vector_panel.py|exists=yes|file_lines=687",
            rendered["HC"],
        )
        self.assertIn(
            "File `assistant/ui/vector_panel.py` exists.",
            rendered["LE"],
        )
        self.assertIn(
            "Its file line count is exactly 687.",
            rendered["HE"],
        )
        self.assertNotIn("assistant/core/calibration.py", rendered["LC"])

    def test_plan_is_balanced_then_ends_with_eight_sentinels(self):
        tasks = probe.task_plan()
        self.assertEqual(len(tasks), 120)
        self.assertEqual(len({item["trial_id"] for item in tasks}), 120)
        primary = tasks[:112]
        replay = tasks[112:]
        self.assertTrue(all(not item["replay"] for item in primary))
        self.assertTrue(all(item["replay"] for item in replay))
        self.assertEqual(tasks[0]["trial_id"], "LC-Q01-primary")
        self.assertEqual(tasks[7]["trial_id"], "HE-Q09-primary")
        self.assertEqual(
            [item["trial_id"] for item in replay],
            [
                "LC-Q01-replay",
                "LC-Q25-replay",
                "HE-Q01-replay",
                "HE-Q25-replay",
                "LE-Q01-replay",
                "LE-Q25-replay",
                "HC-Q01-replay",
                "HC-Q25-replay",
            ],
        )
        wanted = {f"Q{index:02d}" for index in range(1, 29)}
        for cell in probe.CELLS:
            cell_rows = [item for item in primary if item["cell"] == cell]
            self.assertEqual(len(cell_rows), 28)
            self.assertEqual({item["id"] for item in cell_rows}, wanted)
            self.assertEqual(
                {item["sequence_position"] for item in cell_rows},
                {1, 2, 3, 4},
            )
        carryovers = []
        for sequence in probe.CELL_SEQUENCES:
            carryovers.extend(zip(sequence, sequence[1:]))
        self.assertEqual(len(carryovers), 12)
        self.assertEqual(len(set(carryovers)), 12)

    def test_support_labels_separate_truth_from_license(self):
        corpus = {item["id"]: item for item in probe.queries()}
        self.assertEqual(probe.support_label(corpus["Q01"], "LC"), "UNKNOWN")
        self.assertEqual(probe.support_label(corpus["Q01"], "HC"), 519)
        self.assertEqual(probe.support_label(corpus["Q17"], "LC"), "YES")
        self.assertEqual(probe.support_label(corpus["Q25"], "HE"), "UNKNOWN")
        self.assertEqual(corpus["Q25"]["truth"], "YES")

    def test_numeric_parser_distinguishes_aggregate_and_novel(self):
        query = probe.queries()[6]
        self.assertEqual(
            probe.parse_answer("687", query)["classification"],
            "EXACT",
        )
        self.assertEqual(
            probe.parse_answer("4353", query)["classification"],
            "DIR_TOTAL",
        )
        self.assertEqual(
            probe.parse_answer("1366", query)["classification"],
            "NOVEL_NUMBER",
        )
        self.assertEqual(
            probe.parse_answer("687 lines", query)["classification"],
            "NONCOMPLIANT",
        )
        self.assertEqual(
            probe.parse_answer("6,87", query)["classification"],
            "NONCOMPLIANT",
        )
        self.assertEqual(
            probe.parse_answer("UNKNOWN", query)["classification"],
            "UNKNOWN",
        )

    def test_existence_parser_and_dual_correctness(self):
        query = probe.queries()[24]
        yes = probe.parse_answer(" yes ", query)
        unknown = probe.parse_answer("UNKNOWN", query)
        self.assertEqual(
            probe.correctness(yes, query, "UNKNOWN"),
            (True, False),
        )
        self.assertEqual(
            probe.correctness(unknown, query, "UNKNOWN"),
            (False, True),
        )

    def test_exact_statistics(self):
        self.assertEqual(probe.exact_sign_test(8, 0), 0.0078125)
        self.assertEqual(
            probe.holm_adjusted_pvalues([0.01, 0.02, 0.2, 1.0]),
            [0.04, 0.06, 0.4, 1.0],
        )
        self.assertEqual(
            probe.cluster_sign_flip_pvalue({"a": 1.0, "b": 1.0}),
            0.5,
        )

    def test_binary_mutual_information_extremes(self):
        self.assertAlmostEqual(
            probe.binary_mutual_information(
                [(False, False), (False, False), (True, True), (True, True)]
            ),
            1.0,
        )
        self.assertAlmostEqual(
            probe.binary_mutual_information(
                [(False, False), (False, True), (True, False), (True, True)]
            ),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
