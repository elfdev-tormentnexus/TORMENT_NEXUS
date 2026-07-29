"""Tests for the machinespirit calibration reference.

Every published machinespirit figure is a reading with no scale beside it,
and nothing detected a model or pooling change moving all of them at once.
This corpus is the scale. The properties worth guarding are that its
controls are what they claim to be, that they are identical on every
install, and that a drifted reading is reported rather than absorbed.
"""
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import calibration as cal  # noqa: E402


class FibonacciWordTests(unittest.TestCase):
    """The third control has to demonstrate its own defining property.

    A control that cannot show it is Sturmian is decoration, and the whole
    reason it sits between "periodic" and "random" is that it is aperiodic
    at the minimum complexity any aperiodic sequence can have.
    """

    def test_the_generations_are_the_expected_words(self):
        self.assertEqual(cal.fibonacci_word(1), "a")
        self.assertEqual(cal.fibonacci_word(2), "ab")
        self.assertEqual(cal.fibonacci_word(3), "aba")
        self.assertEqual(cal.fibonacci_word(5), "abaab")
        self.assertEqual(cal.fibonacci_word(8), "abaababa")
        self.assertEqual(cal.fibonacci_word(13), "abaababaabaab")

    def test_it_is_sturmian_exactly_n_plus_one_subwords(self):
        word = cal.fibonacci_word(4000)
        for n in range(1, 13):
            with self.subTest(n=n):
                self.assertEqual(cal.subword_count(word, n), n + 1)
        self.assertTrue(cal.is_sturmian(word))

    def test_the_other_two_controls_are_not_sturmian(self):
        """Which is the point of having three rather than one."""
        self.assertFalse(cal.is_sturmian("a" * 4000))
        noise = "".join(random.Random(4).choice("ab") for _ in range(4000))
        self.assertFalse(cal.is_sturmian(noise))

    def test_it_never_repeats(self):
        """Aperiodic: no prefix of any period tiles the word."""
        word = cal.fibonacci_word(600)
        for period in range(1, 40):
            with self.subTest(period=period):
                self.assertFalse(
                    all(word[i] == word[i % period] for i in range(len(word))))


class ControlDesignTests(unittest.TestCase):
    def test_the_controls_are_identical_on_every_install(self):
        self.assertEqual(cal.control_texts(), cal.control_texts())

    def test_fibonacci_and_random_share_a_phrase_mix(self):
        """The pair exists to check the instrument ignores order.

        Same multiset of phrases, different arrangement. spread() is
        permutation-invariant, so these two must read alike -- and if they
        ever stop doing so, either the invariance broke or the controls did.
        """
        texts = cal.control_texts()
        fib = texts["fibonacci"].count(cal.PHRASE_A), texts["fibonacci"].count(cal.PHRASE_B)
        rnd = texts["random"].count(cal.PHRASE_A), texts["random"].count(cal.PHRASE_B)
        self.assertEqual(fib, rnd)
        self.assertNotEqual(texts["fibonacci"], texts["random"])

    def test_the_periodic_control_deliberately_differs(self):
        """It must NOT match the pair, or it is not a second reference point."""
        texts = cal.control_texts()
        self.assertEqual(texts["periodic"].count(cal.PHRASE_B), 0)
        self.assertNotEqual(texts["periodic"], texts["fibonacci"])

    def test_every_row_has_text(self):
        for name, text in cal.corpus().items():
            with self.subTest(row=name):
                self.assertTrue(text.strip(), name)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def _recorded(self, **overrides):
        from core import machinespirit
        reading = {"text_sha256": cal.digest("x"), "tokens": 10,
                   "effective_rank": 1.5, "entropy": 0.9, "purity": 0.66,
                   "top_anchor": "a", "top_support": 1.0, "anchors_fired": 2}
        reading.update(overrides)
        return {"format": cal.FORMAT,
                "anchor_core_digest": machinespirit.core_digest(),
                "readings": {"row": reading}}

    def _fresh(self, **overrides):
        return {"row": dict(self._recorded()["readings"]["row"], **overrides)}

    def test_an_unchanged_instrument_reports_nothing(self):
        self.assertEqual(cal.compare(self._recorded(), self._fresh()), [])

    def test_a_drifted_reading_is_reported(self):
        problems = cal.compare(self._recorded(), self._fresh(effective_rank=1.9))
        self.assertEqual(len(problems), 1)
        self.assertIn("effective_rank", problems[0])

    def test_a_reading_inside_tolerance_is_not_reported(self):
        self.assertEqual(
            cal.compare(self._recorded(), self._fresh(effective_rank=1.51)), [])

    def test_a_changed_anchor_digest_is_reported_alone(self):
        """Every row differing is expected then, and would bury the one fact."""
        recorded = self._recorded()
        recorded["anchor_core_digest"] = "0" * 64
        problems = cal.compare(recorded, self._fresh(effective_rank=9.0))
        self.assertEqual(len(problems), 1)
        self.assertIn("anchor dictionary changed", problems[0])

    def test_a_changed_reference_text_is_reported_as_such(self):
        problems = cal.compare(self._recorded(),
                               self._fresh(text_sha256=cal.digest("different")))
        self.assertIn("reference text itself changed", problems[0])

    def test_a_missing_row_is_reported(self):
        self.assertIn("missing", cal.compare(self._recorded(), {})[0])

    def test_nothing_recorded_is_said_rather_than_passed(self):
        self.assertTrue(cal.compare(None, self._fresh()))
        self.assertTrue(cal.compare(self._recorded(), None))


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.path = os.path.join(self.folder, "cal.json")

    def test_a_foreign_format_is_refused_rather_than_read(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"format": "SOMETHING_ELSE", "readings": {}}, handle)
        self.assertIsNone(cal.load(self.path))

    def test_a_damaged_file_reads_as_no_reference(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertIsNone(cal.load(self.path))

    def test_a_missing_file_reads_as_no_reference(self):
        self.assertIsNone(cal.load(os.path.join(self.folder, "absent.json")))

    def test_the_shipped_reference_loads_and_names_its_model(self):
        """The record is only a reference if it says what produced it."""
        shipped = cal.load()
        self.assertIsNotNone(shipped, "calibration_v1.json should ship")
        self.assertTrue(shipped.get("embedding_model"))
        self.assertTrue(shipped.get("anchor_core_digest"))
        self.assertEqual(shipped.get("pooling"), "mean")
        for row in cal.corpus():
            self.assertIn(row, shipped["readings"])

    def test_the_shipped_reference_matches_the_texts_it_claims(self):
        """A recorded reading must belong to the text still in the corpus."""
        shipped = cal.load()
        for name, text in cal.corpus().items():
            with self.subTest(row=name):
                self.assertEqual(shipped["readings"][name]["text_sha256"],
                                 cal.digest(text))


if __name__ == "__main__":
    unittest.main()
