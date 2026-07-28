"""Tests for the token-trajectory beam.

No network here. The parts that need a live `--pooling none` server are
run by hand and recorded in docs/VECTOR_PIXEL_RESEARCH.md.

The claim these guard is the one the whole idea rests on: the trajectory
contains the pooled vector, so keeping the path loses nothing that the
current format holds. Everything else about the beam is a rendering.
"""
import importlib.util
import math
import os
import shutil
import tempfile
import unittest

_BEAM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tools",
    "vector_beam.py",
)
_spec = importlib.util.spec_from_file_location("_vector_beam_under_test", _BEAM)
vb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vb)


class ContainmentTests(unittest.TestCase):
    def test_pooled_is_the_mean_of_the_path(self):
        path = [[1.0, 0.0], [0.0, 1.0], [2.0, 2.0]]
        self.assertEqual(vb.pooled(path), [1.0, 1.0])

    def test_a_single_token_path_pools_to_itself(self):
        self.assertEqual(vb.pooled([[0.3, 0.7]]), [0.3, 0.7])

    def test_the_path_contains_what_the_current_format_stores(self):
        # If this ever fails, the beam is not a superset of the pooled
        # vector and the whole justification for keeping it collapses.
        path = [[0.2, 0.9, 0.1], [0.4, 0.1, 0.8], [0.9, 0.2, 0.3]]
        recovered = vb.pooled(path)
        expected = [sum(c) / len(path) for c in zip(*path)]
        for a, b in zip(recovered, expected):
            self.assertAlmostEqual(a, b, places=12)


class MeasureTests(unittest.TestCase):
    def test_a_stationary_path_has_no_length(self):
        path = [[1.0, 0.0]] * 4
        stats = vb.measure(path)
        self.assertAlmostEqual(stats["path_length"], 0.0, places=9)
        self.assertAlmostEqual(stats["flattened_range"], 0.0, places=9)

    def test_a_moving_path_has_length(self):
        path = [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]
        self.assertGreater(vb.measure(path)["path_length"], 0.5)

    def test_token_count_and_dims_are_reported(self):
        stats = vb.measure([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        self.assertEqual(stats["tokens"], 2)
        self.assertEqual(stats["dims"], 3)

    def test_flattened_range_is_never_negative(self):
        path = [[1.0, 0.2], [0.3, 0.9], [0.5, 0.5], [0.1, 0.1]]
        self.assertGreaterEqual(vb.measure(path)["flattened_range"], 0.0)


class ColourTests(unittest.TestCase):
    def test_the_same_path_always_renders_the_same_colours(self):
        # A beam that changed colour between runs would be decoration
        # pretending to be a readout.
        path = [[0.1, 0.9, 0.3], [0.8, 0.2, 0.5], [0.4, 0.4, 0.9]]
        self.assertEqual(vb.colours(path), vb.colours(path))

    def test_one_colour_per_token(self):
        path = [[0.1, 0.9], [0.8, 0.2], [0.4, 0.4], [0.2, 0.7]]
        self.assertEqual(len(vb.colours(path)), len(path))

    def test_colours_are_in_range(self):
        path = [[0.1, 0.9, 0.3], [0.8, 0.2, 0.5], [0.4, 0.4, 0.9]]
        for rgb in vb.colours(path):
            self.assertEqual(len(rgb), 3)
            for channel in rgb:
                self.assertGreaterEqual(channel, 0)
                self.assertLessEqual(channel, 255)

    def test_a_different_seed_gives_a_different_projection(self):
        path = [[0.1, 0.9, 0.3], [0.8, 0.2, 0.5], [0.4, 0.4, 0.9]]
        self.assertNotEqual(vb.colours(path, seed=1),
                            vb.colours(path, seed=2))

    def test_projection_axes_are_unit_length(self):
        for axis in vb._projection(16, seed=5):
            self.assertAlmostEqual(math.sqrt(sum(x * x for x in axis)), 1.0,
                                   places=9)


class Sable7ContainerTests(unittest.TestCase):
    """The container's job is to keep order and to say that it does.

    A trajectory that loses its order is not a degraded trajectory, it is a
    bag of numbers -- so the format declares itself and the reader refuses
    to guess.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = [
            [0.10, 0.90, 0.30, 0.50],
            [0.80, 0.20, 0.50, 0.10],
            [0.40, 0.40, 0.90, 0.70],
            [0.05, 0.65, 0.15, 0.95],
        ]

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _out(self, name="b.png"):
        return os.path.join(self.dir, name)

    def test_round_trip_preserves_the_vectors(self):
        out = self._out()
        vb.encode_beam(self.path, out, "some text", "test-model")
        back, header = vb.decode_beam(out)
        self.assertEqual(header["tokens"], len(self.path))
        self.assertEqual(header["dims"], len(self.path[0]))
        for original, recovered in zip(self.path, back):
            self.assertGreater(vb.cosine(original, recovered), 0.999)

    def test_round_trip_preserves_the_order(self):
        # The property the whole format exists for.
        out = self._out()
        vb.encode_beam(self.path, out, "t", "m")
        back, _ = vb.decode_beam(out)
        for i, (original, recovered) in enumerate(zip(self.path, back)):
            best = max(range(len(self.path)),
                       key=lambda j: vb.cosine(self.path[j], recovered))
            self.assertEqual(best, i, f"token {i} came back in position {best}")

    def test_header_declares_the_format_and_that_it_is_ordered(self):
        out = self._out()
        header = vb.encode_beam(self.path, out, "t", "m")
        self.assertEqual(header["magic"], vb.MAGIC)
        self.assertTrue(header["ordered"])
        _, read_back = vb.decode_beam(out)
        self.assertEqual(read_back["magic"], vb.MAGIC)

    def test_source_text_is_recorded_as_a_digest_not_as_text(self):
        out = self._out()
        header = vb.encode_beam(self.path, out, "a private sentence", "m")
        self.assertEqual(len(header["source_sha256"]), 64)
        blob = open(out, "rb").read()
        self.assertNotIn(b"a private sentence", blob)

    def test_a_png_without_the_header_is_refused_not_guessed(self):
        out = self._out("plain.png")
        vb._png(out, 2, 2, [bytes(6), bytes(6)])
        with self.assertRaises(ValueError):
            vb.decode_beam(out)

    def test_a_non_png_is_refused(self):
        out = self._out("not.png")
        open(out, "wb").write(b"this is not a png")
        with self.assertRaises(ValueError):
            vb.decode_beam(out)

    def test_a_single_token_path_survives(self):
        out = self._out()
        vb.encode_beam([[0.3, 0.7, 0.1]], out, "t", "m")
        back, header = vb.decode_beam(out)
        self.assertEqual(header["tokens"], 1)
        self.assertEqual(len(back), 1)

    def test_dims_not_divisible_by_three_do_not_lose_the_tail(self):
        # 4 dims needs 2 pixels and leaves 2 padding bytes; the decoder
        # must trim by the declared dims rather than by the row width.
        out = self._out()
        vb.encode_beam(self.path, out, "t", "m")
        back, _ = vb.decode_beam(out)
        self.assertTrue(all(len(row) == 4 for row in back))


class TraceTests(unittest.TestCase):
    """Reading a trajectory against a concept dictionary, token by token.

    The capability the pooled vector cannot provide at all: not what a
    sentence is about, but where in the sentence each meaning appeared.
    """

    def _stone(self):
        # Two orthogonal concepts, so which token leans where is unambiguous.
        return {
            "magic": "SABLEROSETTA1",
            "core_count": 2,
            "project_count": 1,
            "anchors_core": ["east", "north"],
            "anchors_project": ["up"],
            "anchor_vectors": [[1.0, 0.0, 0.0],
                               [0.0, 1.0, 0.0],
                               [0.0, 0.0, 1.0]],
        }

    def test_one_row_per_token(self):
        path = [[1.0, 0.1, 0.0], [0.1, 1.0, 0.0], [0.5, 0.5, 0.0]]
        rows = vb.trace(path, self._stone())
        self.assertEqual(len(rows), len(path))

    def test_each_row_carries_index_colour_and_concepts(self):
        path = [[1.0, 0.1, 0.0], [0.1, 1.0, 0.0], [0.5, 0.5, 0.0]]
        for i, (index, rgb, hits) in enumerate(vb.trace(path, self._stone())):
            self.assertEqual(index, i)
            self.assertEqual(len(rgb), 3)
            self.assertTrue(hits)

    def test_the_concept_is_located_at_the_token_that_carries_it(self):
        # Token 0 points east, token 1 points north. A trace that cannot
        # tell them apart is not doing the one thing it exists for.
        path = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        rows = vb.trace(path, self._stone(), top=1)
        self.assertEqual(rows[0][2][0][1], "east")
        self.assertEqual(rows[1][2][0][1], "north")

    def test_project_anchors_are_excluded_unless_requested(self):
        path = [[0.0, 0.0, 1.0]]
        named = [a for _, _, hits in vb.trace(path, self._stone(), top=3)
                 for _, a in hits]
        self.assertNotIn("up", named)
        named = [a for _, _, hits in
                 vb.trace(path, self._stone(), top=3, use_project=True)
                 for _, a in hits]
        self.assertIn("up", named)


class CosineTests(unittest.TestCase):
    def test_identical_vectors(self):
        self.assertAlmostEqual(vb.cosine([1.0, 2.0], [1.0, 2.0]), 1.0)

    def test_a_zero_vector_does_not_divide_by_zero(self):
        self.assertIsInstance(vb.cosine([0.0, 0.0], [1.0, 1.0]), float)


if __name__ == "__main__":
    unittest.main()
