"""Tests for the anchor-space shadow log.

The whole value of this module is that it is inert. It exists to generate
evidence about a question currently settled by an eighteen-chunk corpus,
and it is worth nothing if generating that evidence changes the answer.

So the tests that matter are the negative ones: retrieval must be identical
with it present and absent, a failure inside it must not reach the turn,
and no row it writes may contain text.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import machinespirit_shadow as shadow  # noqa: E402
from memory import memory_logic  # noqa: E402


def _vec(*values):
    return list(values)


class RankingTests(unittest.TestCase):
    ANCHORS = [_vec(1.0, 0.0, 0.0), _vec(0.0, 1.0, 0.0), _vec(0.0, 0.0, 1.0)]

    def test_the_nearest_candidate_ranks_first(self):
        query = _vec(1.0, 0.1, 0.0)
        candidates = [_vec(0.0, 0.0, 1.0), _vec(1.0, 0.0, 0.0)]
        order = shadow.ranking(query, candidates, self.ANCHORS)
        self.assertEqual(order[0][1], 1)

    def test_a_missing_vector_is_skipped_rather_than_scored(self):
        order = shadow.ranking(_vec(1.0, 0.0, 0.0),
                               [None, _vec(1.0, 0.0, 0.0), None],
                               self.ANCHORS)
        self.assertEqual([index for _score, index in order], [1])

    def test_agreement_is_the_top_k_overlap(self):
        first = [(0.9, 0), (0.8, 1), (0.7, 2)]
        same = [(0.5, 0), (0.4, 1), (0.3, 2)]
        self.assertEqual(shadow.agreement(first, same, k=3), 1.0)
        disjoint = [(0.5, 7), (0.4, 8), (0.3, 9)]
        self.assertEqual(shadow.agreement(first, disjoint, k=3), 0.0)

    def test_agreement_is_none_when_there_is_nothing_to_compare(self):
        self.assertIsNone(shadow.agreement([], [(0.5, 1)]))


class InertnessTests(unittest.TestCase):
    """The property the module exists to preserve."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.path = os.path.join(self.folder, "shadow.jsonl")

    def test_retrieval_is_identical_with_the_shadow_present_and_absent(self):
        """Risk #4, asserted rather than promised."""
        memories = [
            {"memory": "the operator likes pineapple pizza"},
            {"memory": "a single-board computer bought for a project"},
            {"memory": "the assistant runs entirely offline"},
        ]
        query = "tell me about the project computer"

        before = memory_logic.select_relevant(memories, query, limit=4)
        shadow.observe(query, memories, [None] * 3, _vec(1.0, 0.0, 0.0),
                       path=self.path)
        after = memory_logic.select_relevant(memories, query, limit=4)

        self.assertEqual(before, after)
        self.assertEqual([m["memory"] for m in before],
                         [m["memory"] for m in after])

    def test_observe_returns_nothing_a_caller_could_start_using(self):
        self.assertIsNone(
            shadow.observe("q", [], [], _vec(1.0), path=self.path))

    def test_a_failure_inside_it_never_reaches_the_turn(self):
        broken = [{"memory": "x"}]
        # A vector of the wrong shape, an unwritable path, and a candidate
        # list shorter than the vectors -- none may raise.
        shadow.observe("q", broken, ["not a vector"], _vec(1.0),
                       path=os.path.join(self.folder, "no", "such", "dir.jsonl"))
        shadow.observe("q", broken, [None], None, path=self.path)

    def test_an_unconfigured_machinespirit_writes_nothing(self):
        shadow.observe("q", [{"memory": "x"}], [_vec(1.0)], _vec(1.0),
                       path=self.path)
        self.assertFalse(os.path.exists(self.path))


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.path = os.path.join(self.folder, "shadow.jsonl")

    def test_a_row_round_trips_as_json(self):
        shadow.record({"at": 1.0, "query": "abc", "agreement": 0.5},
                      path=self.path)
        with open(self.path, encoding="utf-8") as handle:
            row = json.loads(handle.readline())
        self.assertEqual(row["query"], "abc")

    def test_no_row_carries_text(self):
        """A digest is an identity. The memory itself must never appear."""
        secret = "the operator's mother is named Rosalind"
        shadow.record({"at": 1.0, "query": shadow.digest(secret),
                       "pooled": [[shadow.digest(secret), 0.9]]},
                      path=self.path)
        with open(self.path, encoding="utf-8") as handle:
            written = handle.read()
        self.assertNotIn("Rosalind", written)
        self.assertNotIn("operator", written)

    def test_the_file_is_bounded(self):
        original = shadow.MAX_ROWS
        try:
            shadow.MAX_ROWS = 5
            for index in range(12):
                shadow.record({"n": index}, path=self.path)
            with open(self.path, encoding="utf-8") as handle:
                rows = handle.readlines()
            self.assertLessEqual(len(rows), 5)
            self.assertEqual(json.loads(rows[-1])["n"], 11)
        finally:
            shadow.MAX_ROWS = original

    def test_a_missing_log_directory_is_created_rather_than_refused(self):
        deep = os.path.join(self.folder, "logs", "nested", "shadow.jsonl")
        self.assertTrue(shadow.record({"n": 1}, path=deep))
        self.assertTrue(os.path.exists(deep))

    def test_an_unwritable_path_is_reported_rather_than_raised(self):
        """A file standing where the log directory needs to be."""
        blocker = os.path.join(self.folder, "blocker")
        with open(blocker, "w", encoding="utf-8") as handle:
            handle.write("not a directory")
        self.assertFalse(
            shadow.record({"n": 1}, path=os.path.join(blocker, "x.jsonl")))

    def test_a_value_json_cannot_encode_is_reported_rather_than_raised(self):
        self.assertFalse(shadow.record({"n": object()}, path=self.path))

    def test_the_digest_is_stable_and_not_reversible_to_text(self):
        self.assertEqual(shadow.digest("hello"), shadow.digest("hello"))
        self.assertNotEqual(shadow.digest("hello"), shadow.digest("hellp"))
        self.assertEqual(len(shadow.digest("hello")), 16)


if __name__ == "__main__":
    unittest.main()
