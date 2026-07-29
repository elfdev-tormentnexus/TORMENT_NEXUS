"""Tests for the anchor codec.

A least-squares decoder that is subtly wrong still returns vectors of the
right shape with plausible cosines, so the guards here are the cases where
the correct answer is known in advance rather than merely plausible.
"""
import importlib.util
import math
import os
import unittest

_CODEC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tools",
    "machinespirit_codec.py",
)
_spec = importlib.util.spec_from_file_location("_codec_under_test", _CODEC)
codec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codec)


def basis(n):
    """An orthonormal set. The one case where the answer is exact."""
    return [[1.0 if i == j else 0.0 for i in range(n)] for j in range(n)]


class SolverTests(unittest.TestCase):
    def test_it_solves_a_system_with_a_known_answer(self):
        matrix = [[2.0, 1.0], [1.0, 3.0]]
        answer = codec._solve(matrix, [5.0, 10.0])
        self.assertAlmostEqual(answer[0], 1.0, places=6)
        self.assertAlmostEqual(answer[1], 3.0, places=6)

    def test_it_solves_a_system_needing_a_pivot_swap(self):
        """A zero in the first pivot position breaks naive elimination."""
        matrix = [[0.0, 2.0], [1.0, 1.0]]
        answer = codec._solve(matrix, [4.0, 3.0])
        self.assertAlmostEqual(answer[0], 1.0, places=6)
        self.assertAlmostEqual(answer[1], 2.0, places=6)

    def test_a_singular_system_returns_rather_than_dividing_by_zero(self):
        answer = codec._solve([[1.0, 1.0], [2.0, 2.0]], [1.0, 2.0])
        self.assertEqual(len(answer), 2)
        self.assertTrue(all(math.isfinite(v) for v in answer))


class RoundTripTests(unittest.TestCase):
    def test_an_orthonormal_basis_reconstructs_almost_exactly(self):
        """With a full orthonormal basis the codec is lossless in principle."""
        anchors = basis(8)
        vector = codec.unit([0.4, -0.2, 0.9, 0.1, -0.5, 0.3, 0.7, -0.6])
        coords = codec.encode(vector, anchors)
        rebuilt = codec.decode_least_squares(coords, anchors, ridge=1e-9)
        self.assertGreater(codec.cosine(vector, rebuilt), 0.999)

    def test_the_transpose_decoder_also_works_when_anchors_are_orthonormal(self):
        """Its failure is about correlation, not about being wrong outright."""
        anchors = basis(8)
        vector = codec.unit([0.4, -0.2, 0.9, 0.1, -0.5, 0.3, 0.7, -0.6])
        coords = codec.encode(vector, anchors)
        rebuilt = codec.decode_transpose(coords, anchors)
        self.assertGreater(codec.cosine(vector, rebuilt), 0.999)

    def test_correlated_anchors_break_the_transpose_but_not_least_squares(self):
        """The measured 0.66 vs 0.92 gap, reproduced in miniature."""
        anchors = [codec.unit(a) for a in
                   ([1.0, 0.0, 0.0], [0.98, 0.2, 0.0], [0.0, 0.0, 1.0])]
        vector = codec.unit([0.2, 0.1, 0.95])
        coords = codec.encode(vector, anchors)
        loose = codec.cosine(vector, codec.decode_transpose(coords, anchors))
        tight = codec.cosine(
            vector, codec.decode_least_squares(coords, anchors, ridge=1e-9))
        self.assertGreater(tight, loose)
        self.assertGreater(tight, 0.99)

    def test_a_component_outside_the_anchor_span_cannot_be_recovered(self):
        """The hard ceiling, asserted rather than described.

        Two anchors spanning a plane in three dimensions: whatever the
        vector has along the third axis is gone, and no decoder returns it.
        """
        anchors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        vector = codec.unit([0.3, 0.3, 0.9])
        rebuilt = codec.decode_least_squares(
            codec.encode(vector, anchors), anchors, ridge=1e-9)
        self.assertLess(abs(rebuilt[2]), 1e-6,
                        "the orthogonal component must not reappear")
        self.assertLess(codec.cosine(vector, rebuilt), 0.8)


class GramTests(unittest.TestCase):
    def test_the_gram_matrix_is_symmetric(self):
        anchors = [codec.unit([1.0, 0.5, 0.2]), codec.unit([0.1, 1.0, 0.3]),
                   codec.unit([0.4, 0.2, 1.0])]
        grid = codec.gram_matrix(anchors, ridge=0.0)
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(grid[i][j], grid[j][i], places=12)

    def test_the_ridge_lands_on_the_diagonal_only(self):
        anchors = basis(3)
        plain = codec.gram_matrix(anchors, ridge=0.0)
        ridged = codec.gram_matrix(anchors, ridge=0.25)
        for i in range(3):
            for j in range(3):
                expected = plain[i][j] + (0.25 if i == j else 0.0)
                self.assertAlmostEqual(ridged[i][j], expected, places=12)


class RetrievalTests(unittest.TestCase):
    def test_a_perfect_reconstruction_ranks_its_own_item_first(self):
        corpus = [codec.unit([1.0, 0.0]), codec.unit([0.0, 1.0]),
                  codec.unit([0.7, 0.7])]
        self.assertEqual(codec.retrieval_rank(corpus[1], corpus, 1), 1)

    def test_a_wrong_reconstruction_does_not_rank_first(self):
        corpus = [codec.unit([1.0, 0.0]), codec.unit([0.0, 1.0])]
        self.assertEqual(codec.retrieval_rank(corpus[0], corpus, 1), 2)


if __name__ == "__main__":
    unittest.main()
