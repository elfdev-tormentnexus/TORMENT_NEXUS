"""Pure checks for the hazard-only counterfactual trajectory instrument."""

import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import token_contrast_probe as probe  # noqa: E402


class TokenContrastProbeTests(unittest.TestCase):
    def test_word_spans_keep_source_coordinates(self):
        text = "Don't erase a promise."
        self.assertEqual(probe.word_spans(text),
                         [(0, 5, "Don't"), (6, 11, "erase"),
                          (12, 13, "a"), (14, 21, "promise")])

    def test_one_edit_changes_only_the_declared_source_span(self):
        self.assertEqual(probe.replace_span("one two three", 4, 7),
                         "one [MASK] three")
        with self.assertRaises(ValueError):
            probe.replace_span("one", 2, 1)

    def test_contrast_uses_the_deployed_mean_all_rule(self):
        paths = {
            "red blue": [[1.0, 0.0], [1.0, 0.0]],
            "[MASK] blue": [[0.0, 1.0], [0.0, 1.0]],
            "red [MASK]": [[1.0, 0.0], [1.0, 0.0]],
        }
        rows = probe.contrast_rows("red blue", paths.__getitem__)
        self.assertEqual([row["word"] for row in rows], ["red", "blue"])
        self.assertAlmostEqual(rows[0]["contrast"], 1.0)
        self.assertAlmostEqual(rows[1]["contrast"], 0.0)

    def test_empty_or_misaligned_paths_refuse_to_score(self):
        with self.assertRaises(ValueError):
            probe.mean_all([])
        with self.assertRaises(ValueError):
            probe.cosine([1.0], [1.0, 0.0])


if __name__ == "__main__":
    unittest.main()
