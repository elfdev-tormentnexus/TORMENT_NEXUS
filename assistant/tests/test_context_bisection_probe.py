"""Pure checks for the context-bisection trajectory experiment."""

import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import context_bisection_probe as probe  # noqa: E402


class ContextBisectionTests(unittest.TestCase):
    def test_word_midpoint_keeps_whole_words(self):
        self.assertEqual(probe.split_at_word_midpoint("one two three four"),
                         ("one two", "three four", 8))

    def test_one_word_text_is_refused(self):
        with self.assertRaises(ValueError):
            probe.split_at_word_midpoint("alone")

    def test_matching_halves_are_scored_against_full_positions(self):
        paths = {
            "red blue green yellow": [
                [0, 0], [1, 0], [0, 1], [1, 1], [1, -1], [0, 0],
            ],
            "red blue": [[0, 0], [1, 0], [0, 1], [0, 0]],
            "green yellow": [[0, 0], [1, 1], [1, -1], [0, 0]],
        }
        result = probe.analyse("red blue green yellow", paths.__getitem__)
        self.assertEqual(result["prefix"]["content_tokens"], 2)
        self.assertEqual(result["suffix"]["content_tokens"], 2)
        self.assertAlmostEqual(result["mean_drift"], 0.0)

    def test_changed_token_accounting_is_refused(self):
        paths = {
            "red blue green yellow": [[0], [1], [2], [3], [4], [0]],
            "red blue": [[0], [1], [2], [0]],
            "green yellow": [[0], [3], [0]],
        }
        with self.assertRaises(ValueError):
            probe.analyse("red blue green yellow", paths.__getitem__)


if __name__ == "__main__":
    unittest.main()
