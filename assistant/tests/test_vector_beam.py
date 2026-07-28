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


class CosineTests(unittest.TestCase):
    def test_identical_vectors(self):
        self.assertAlmostEqual(vb.cosine([1.0, 2.0], [1.0, 2.0]), 1.0)

    def test_a_zero_vector_does_not_divide_by_zero(self):
        self.assertIsInstance(vb.cosine([0.0, 0.0], [1.0, 1.0]), float)


if __name__ == "__main__":
    unittest.main()
