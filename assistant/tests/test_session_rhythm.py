"""Tests for session rhythm measurement.

The property these exist to protect is that every clause the assistant can
say about a session corresponds to a number that was actually counted. A
warm sentence is fine; an unverifiable one is not, and the difference is
whether the file backs it up.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import session_rhythm as sr  # noqa: E402


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def plain_duration(seconds):
    return f"{int(seconds)}s"


class SessionTests(unittest.TestCase):
    def test_a_new_session_has_no_turns_and_no_duration(self):
        clock = FakeClock()
        session = sr.Session(clock)
        self.assertEqual(session.seconds(), 0.0)
        self.assertEqual(session.summary()["turns"], 0)

    def test_duration_follows_the_clock(self):
        clock = FakeClock()
        session = sr.Session(clock)
        clock.advance(3600)
        self.assertAlmostEqual(session.seconds(), 3600.0)

    def test_the_first_turn_has_no_gap_before_it(self):
        clock = FakeClock()
        session = sr.Session(clock)
        self.assertIsNone(session.note_turn())

    def test_the_gap_is_the_time_since_the_previous_turn(self):
        clock = FakeClock()
        session = sr.Session(clock)
        session.note_turn()
        clock.advance(45)
        self.assertAlmostEqual(session.note_turn(), 45.0)

    def test_a_long_gap_counts_as_a_break_not_a_pause(self):
        # Mixing a lunch break into typical reply time makes the median
        # describe nothing.
        clock = FakeClock()
        session = sr.Session(clock)
        session.note_turn()
        clock.advance(30)
        session.note_turn()
        clock.advance(sr.BREAK_SECONDS + 60)
        session.note_turn()
        self.assertEqual(session.pauses(), [30.0])
        self.assertEqual(len(session.breaks()), 1)

    def test_median_pause_ignores_breaks(self):
        clock = FakeClock()
        session = sr.Session(clock)
        for gap in (10, 20, 30, sr.BREAK_SECONDS + 100):
            session.note_turn()
            clock.advance(gap)
        session.note_turn()
        self.assertEqual(session.summary()["median_pause"], 20.0)


class MedianTests(unittest.TestCase):
    def test_no_values(self):
        self.assertIsNone(sr._median([]))

    def test_odd_count(self):
        self.assertEqual(sr._median([3, 1, 2]), 2)

    def test_even_count_averages_the_middle(self):
        self.assertEqual(sr._median([1, 2, 3, 4]), 2.5)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "rhythm.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_missing_file_reads_as_no_history(self):
        self.assertEqual(sr.load(self.path), [])

    def test_a_damaged_file_reads_as_no_history_rather_than_raising(self):
        # Losing a comparison is small. Refusing to start over it is not.
        open(self.path, "w", encoding="utf-8").write("{ not json")
        self.assertEqual(sr.load(self.path), [])

    def test_a_recorded_session_reads_back(self):
        sr.record({"seconds": 120.0, "turns": 3}, self.path)
        history = sr.load(self.path)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["seconds"], 120.0)

    def test_the_file_is_bounded(self):
        for index in range(sr.MAX_SESSIONS + 25):
            sr.record({"seconds": float(index)}, self.path)
        self.assertEqual(len(sr.load(self.path)), sr.MAX_SESSIONS)

    def test_the_oldest_entries_are_the_ones_dropped(self):
        for index in range(sr.MAX_SESSIONS + 5):
            sr.record({"seconds": float(index)}, self.path)
        history = sr.load(self.path)
        self.assertEqual(history[-1]["seconds"], float(sr.MAX_SESSIONS + 4))
        self.assertGreater(history[0]["seconds"], 0.0)

    def test_no_text_is_recorded(self):
        sr.record({"seconds": 60.0, "turns": 2}, self.path)
        blob = open(self.path, encoding="utf-8").read()
        for banned in ("message", "content", "text", "title"):
            self.assertNotIn(banned, blob)


class RankTests(unittest.TestCase):
    def test_no_history_gives_no_rank(self):
        # "The longest session so far" is not a fact when it is the only one.
        self.assertEqual(sr.rank(100.0, []), (None, 0))

    def test_longest_ranks_first(self):
        history = [{"seconds": 10.0}, {"seconds": 50.0}]
        self.assertEqual(sr.rank(100.0, history), (1, 2))

    def test_shortest_ranks_last(self):
        history = [{"seconds": 10.0}, {"seconds": 50.0}]
        self.assertEqual(sr.rank(1.0, history), (3, 2))

    def test_malformed_entries_are_ignored(self):
        history = [{"seconds": "long"}, {}, {"seconds": 10.0}]
        self.assertEqual(sr.rank(100.0, history), (1, 1))


class DescribeTests(unittest.TestCase):
    def _session(self, seconds, turns=0, gap=30):
        clock = FakeClock()
        session = sr.Session(clock)
        for _ in range(turns):
            session.note_turn()
            clock.advance(gap)
        clock.advance(max(0, seconds - turns * gap))
        return session

    def test_it_states_the_duration(self):
        text = sr.describe(self._session(3600), history=[],
                           describe_duration=plain_duration)
        self.assertIn("3600s", text)

    def test_it_claims_longest_only_with_something_to_compare_against(self):
        text = sr.describe(self._session(3600), history=[],
                           describe_duration=plain_duration)
        self.assertNotIn("longest", text)

    def test_it_claims_longest_when_it_is(self):
        text = sr.describe(self._session(3600),
                           history=[{"seconds": 60.0}],
                           describe_duration=plain_duration)
        self.assertIn("longest", text)

    def test_it_does_not_claim_longest_when_it_is_not(self):
        text = sr.describe(self._session(60),
                           history=[{"seconds": 99999.0}],
                           describe_duration=plain_duration)
        self.assertNotIn("longest", text)

    def test_a_break_is_described_as_clock_reading_not_as_waiting(self):
        clock = FakeClock()
        session = sr.Session(clock)
        session.note_turn()
        clock.advance(sr.BREAK_SECONDS + 60)
        session.note_turn()
        text = sr.describe(session, history=[],
                           describe_duration=plain_duration)
        self.assertIn("nothing ran in between", text)
        for claim in ("waited", "felt", "watched", "thought about"):
            self.assertNotIn(claim, text)

    def test_nothing_it_says_asserts_an_inner_state(self):
        session = self._session(7200, turns=6)
        text = sr.describe(session, history=[{"seconds": 60.0}],
                           describe_duration=plain_duration).lower()
        for claim in ("i felt", "i experienced", "i waited", "seemed like",
                      "dragged", "flew by"):
            self.assertNotIn(claim, text)


if __name__ == "__main__":
    unittest.main()
