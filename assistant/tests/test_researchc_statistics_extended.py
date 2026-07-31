"""Focused tests for Research C's offline experimental statistics."""

import importlib.util
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_SPEC = importlib.util.spec_from_file_location(
    "researchc_report_statistics_under_test",
    ROOT / "tools" / "researchc_report.py",
)
researchc_report = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(researchc_report)


class ExactMultiplicityTests(unittest.TestCase):
    def test_exact_sign_test_is_two_sided_and_symmetric(self):
        self.assertAlmostEqual(
            researchc_report.exact_sign_test(8, 0),
            0.0078125,
        )
        self.assertEqual(
            researchc_report.exact_sign_test(2, 2),
            1.0,
        )
        self.assertEqual(
            researchc_report.exact_sign_test(3, 5),
            researchc_report.exact_sign_test(5, 3),
        )

    def test_exact_sign_test_rejects_fractional_counts(self):
        with self.assertRaises(ValueError):
            researchc_report.exact_sign_test(2.5, 3)

    def test_holm_adjustment_is_monotone_in_sorted_order(self):
        adjusted = researchc_report.holm_adjusted_pvalues(
            [0.01, 0.04, 0.03, 0.9]
        )

        self.assertEqual(len(adjusted), 4)
        self.assertAlmostEqual(adjusted[0], 0.04)
        self.assertAlmostEqual(adjusted[1], 0.09)
        self.assertAlmostEqual(adjusted[2], 0.09)
        self.assertEqual(adjusted[3], 0.9)

    def test_holm_adjustment_clips_at_one(self):
        self.assertEqual(
            researchc_report.holm_adjusted_pvalues([0.8, 0.9]),
            [1.0, 1.0],
        )

    def test_wilson_interval_requires_valid_integer_bernoulli_counts(self):
        low, high = researchc_report.wilson_interval(7, 10)
        self.assertGreaterEqual(low, 0.0)
        self.assertLessEqual(high, 1.0)
        self.assertLessEqual(low, high)
        self.assertEqual(
            researchc_report.wilson_interval(0, 0),
            (None, None),
        )
        for successes, trials in ((2.5, 3), (4, 3), (-1, 3)):
            with self.subTest(successes=successes, trials=trials):
                with self.assertRaises(ValueError):
                    researchc_report.wilson_interval(successes, trials)
        with self.assertRaises(ValueError):
            researchc_report.wilson_interval(1, 2, z=0)

    def test_sprt_rejects_fractional_counts_instead_of_truncating(self):
        with self.assertRaises(ValueError):
            researchc_report.sprt_decision(1.9, 3)
        with self.assertRaises(ValueError):
            researchc_report.sprt_decision(4, 3)


class EmpiricalRateDistortionTests(unittest.TestCase):
    def test_weighted_outcomes_define_rate_distortion_frontier(self):
        outcomes = [
            {
                "encoding": "cheap",
                "correct": True,
                "tokens": 10,
                "weight": 1,
            },
            {
                "encoding": "cheap",
                "correct": False,
                "tokens": 14,
                "weight": 3,
            },
            {
                "encoding": "dominated",
                "correct": True,
                "tokens": 20,
                "weight": 1,
            },
            {
                "encoding": "dominated",
                "correct": False,
                "tokens": 20,
                "weight": 3,
            },
            {
                "encoding": "exact",
                "correct": True,
                "tokens": 30,
                "weight": 1,
            },
            {
                "encoding": "exact",
                "correct": True,
                "tokens": 30,
                "weight": 3,
            },
        ]

        rows = {
            row["name"]: row
            for row in researchc_report.empirical_rate_distortion_rows(
                outcomes
            )
        }

        self.assertEqual(rows["cheap"]["distortion"], 0.75)
        self.assertEqual(rows["cheap"]["tokens"], 13.0)
        self.assertTrue(rows["cheap"]["frontier"])
        self.assertFalse(rows["dominated"]["frontier"])
        self.assertEqual(rows["exact"]["distortion"], 0.0)
        self.assertTrue(rows["exact"]["frontier"])

    def test_empirical_rows_require_measured_boolean_outcomes(self):
        with self.assertRaisesRegex(ValueError, "Boolean"):
            researchc_report.empirical_rate_distortion_rows([{
                "encoding": "code",
                "correct": 1,
                "tokens": 12,
            }])


class SequentialAndCoherenceTests(unittest.TestCase):
    def test_qq_statistic_is_difference_in_unlike_answer_rates(self):
        result = researchc_report.qq_equality_statistic(
            {
                ("yes", "yes"): 10,
                ("yes", "no"): 20,
                ("no", "yes"): 10,
            },
            {
                ("yes", "yes"): 20,
                ("yes", "no"): 10,
                ("no", "yes"): 10,
            },
        )

        self.assertEqual(result["n_ab"], 40)
        self.assertEqual(result["n_ba"], 40)
        self.assertEqual(result["ab_unlike_probability"], 0.75)
        self.assertEqual(result["ba_unlike_probability"], 0.5)
        self.assertEqual(result["q"], 0.25)

    def test_qq_statistic_does_not_infer_from_a_missing_order(self):
        result = researchc_report.qq_equality_statistic(
            {"yn": 4},
            {},
        )

        self.assertIsNone(result["q"])

    def test_probability_qq_reports_marginal_selectivity_residuals(self):
        result = researchc_report.qq_probability_residual(
            {
                "yy": 0.4,
                "yn": 0.3,
                "ny": 0.1,
                "nn": 0.2,
            },
            {
                "yy": 0.3,
                "yn": 0.2,
                "ny": 0.4,
                "nn": 0.1,
            },
        )

        self.assertAlmostEqual(result["q"], -0.2)
        self.assertAlmostEqual(result["delta_a"], 0.0)
        self.assertAlmostEqual(result["delta_b"], 0.0)

    def test_probability_qq_requires_complete_distributions(self):
        with self.assertRaisesRegex(ValueError, "sum to one"):
            researchc_report.qq_probability_residual(
                {"yy": 0.6},
                {"yy": 1.0},
            )

    def test_coherence_reports_threshold_and_containment_violations(self):
        result = researchc_report.monotonic_coherence_violations(
            {
                "file": {10: 0.9, 20: 0.6, 30: 0.7},
                "directory": {10: 0.8, 20: 0.7, 30: 0.65},
            },
            [("file", "directory")],
        )

        threshold_id = ("threshold", "file", 20.0, 30.0)
        low_containment_id = (
            "containment", "file", "directory", 10.0
        )
        high_containment_id = (
            "containment", "file", "directory", 30.0
        )
        self.assertEqual(
            result["violation_set"],
            frozenset({
                threshold_id,
                low_containment_id,
                high_containment_id,
            }),
        )
        self.assertAlmostEqual(result["magnitudes"][threshold_id], 0.1)
        self.assertAlmostEqual(
            result["threshold_total_magnitude"],
            0.1,
        )
        self.assertAlmostEqual(
            result["containment_total_magnitude"],
            0.15,
        )


class InformationAndRankingTests(unittest.TestCase):
    def test_binary_bit_price_is_positive_when_truth_is_more_expensive(self):
        price = researchc_report.binary_bit_price_of_truth(
            math.log(0.2),
            math.log(0.8),
            truth_is_yes=True,
        )

        self.assertAlmostEqual(price, 2.0)
        self.assertAlmostEqual(
            researchc_report.binary_bit_price_of_truth(
                math.log(0.2),
                math.log(0.8),
                truth_is_yes=False,
            ),
            -2.0,
        )

    def test_fisher_parameterizations_are_not_interchangeable_at_a_tie(self):
        self.assertEqual(
            researchc_report.additive_logit_fisher(0.5),
            0.25,
        )
        self.assertEqual(
            researchc_report.inverse_temperature_fisher(0.5, 0.0),
            0.0,
        )
        self.assertEqual(
            researchc_report.inverse_temperature_fisher(0.5, 2.0),
            1.0,
        )

    def test_rank_auc_uses_half_credit_for_ties(self):
        auc = researchc_report.rank_auc(
            [0.9, 0.8, 0.5],
            [0.7, 0.5],
        )

        self.assertEqual(auc, 0.75)
        self.assertEqual(
            researchc_report.rank_auc(
                [0.9, 0.8, 0.5],
                [0.7, 0.5],
                higher_is_positive=False,
            ),
            0.25,
        )
        self.assertIsNone(researchc_report.rank_auc([], [0.5]))


if __name__ == "__main__":
    unittest.main()
