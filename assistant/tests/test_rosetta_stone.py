"""Tests for the rosetta stone anchor translation.

Nothing here touches a network. The measurement that needs two live
embedding servers is `tools/rosetta_stone.py measure`, run by hand and
recorded in docs/VECTOR_PIXEL_RESEARCH.md; these cover the parts that must
never quietly go wrong -- above all, that two stones built on different
anchors refuse to be compared instead of returning a plausible number.
"""
import importlib.util
import math
import os
import unittest

# Loaded by path rather than by name on purpose. `tools/` is not an
# installed package, and a bare `import rosetta_stone` reads to the
# declared-dependency guard as an undeclared third-party import -- which is
# exactly what that guard is for. This says plainly that it is a file in
# this repository.
_ROSETTA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tools",
    "rosetta_stone.py",
)
_spec = importlib.util.spec_from_file_location("_rosetta_stone_under_test",
                                               _ROSETTA)
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


class AnchorDigestTests(unittest.TestCase):
    def test_digest_is_stable_for_the_same_ordered_list(self):
        self.assertEqual(rs.anchor_digest(["a", "b"]), rs.anchor_digest(["a", "b"]))

    def test_order_changes_the_digest(self):
        # Anchor order is part of the coordinate system, not decoration:
        # dimension 3 means "similarity to the third anchor".
        self.assertNotEqual(rs.anchor_digest(["a", "b"]),
                            rs.anchor_digest(["b", "a"]))

    def test_concatenation_cannot_collide_with_a_different_split(self):
        # Without a separator, ["ab","c"] and ["a","bc"] would hash alike.
        self.assertNotEqual(rs.anchor_digest(["ab", "c"]),
                            rs.anchor_digest(["a", "bc"]))

    def test_shipped_core_anchor_list_has_no_duplicates(self):
        self.assertEqual(len(rs.ANCHOR_CORE_V1), len(set(rs.ANCHOR_CORE_V1)))

    def test_shipped_project_anchor_list_has_no_duplicates(self):
        self.assertEqual(len(rs.ANCHOR_PROJECT_V1), len(set(rs.ANCHOR_PROJECT_V1)))

    def test_core_anchor_count_is_enough_to_be_meaningful(self):
        # Too few anchors and distinct meanings collapse onto each other.
        self.assertGreaterEqual(len(rs.ANCHOR_CORE_V1), 100)


class RelativeRepresentationTests(unittest.TestCase):
    def test_cosine_of_a_vector_with_itself_is_one(self):
        self.assertAlmostEqual(rs.cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)

    def test_cosine_ignores_magnitude(self):
        self.assertAlmostEqual(rs.cosine([1.0, 0.0], [7.0, 0.0]), 1.0)

    def test_relative_representation_has_one_axis_per_anchor(self):
        anchors = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
        out = rs.to_relative([[1.0, 0.0], [0.0, 1.0]], anchors)
        self.assertEqual(len(out), 2)
        self.assertTrue(all(len(row) == 3 for row in out))

    def test_relative_dimensionality_is_independent_of_source_space(self):
        # The whole point: a 2-d vector and a 5-d vector both land in the
        # same anchor-count-dimensional space.
        small = rs.to_relative([[1.0, 0.0]], [[1.0, 0.0], [0.0, 1.0]])
        large = rs.to_relative([[1.0, 0.0, 0.0, 0.0, 0.0]],
                               [[1.0, 0.0, 0.0, 0.0, 0.0],
                                [0.0, 1.0, 0.0, 0.0, 0.0]])
        self.assertEqual(len(small[0]), len(large[0]))

    def test_rotating_the_space_leaves_relative_coordinates_unchanged(self):
        # A rotation is exactly the case relative representations are meant
        # to survive: the private axes move, the meanings do not.
        vectors = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]
        anchors = [[1.0, 0.0], [0.0, 1.0]]

        def rotate(v, t):
            return [v[0] * math.cos(t) - v[1] * math.sin(t),
                    v[0] * math.sin(t) + v[1] * math.cos(t)]

        t = 0.9
        before = rs.to_relative(vectors, anchors)
        after = rs.to_relative([rotate(v, t) for v in vectors],
                               [rotate(a, t) for a in anchors])
        for row_a, row_b in zip(before, after):
            for x, y in zip(row_a, row_b):
                self.assertAlmostEqual(x, y, places=9)


class StoneCompatibilityTests(unittest.TestCase):
    def _stone(self, core_digest="aa", project_digest="bb", magic=rs.MAGIC):
        return {
            "magic": magic,
            "model": "test",
            "core_digest": core_digest,
            "project_digest": project_digest,
            "core_count": 2,
            "project_count": 1,
            "anchor_vectors": [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
        }

    def test_matching_core_digests_are_compatible(self):
        self.assertTrue(rs.check_compatible(self._stone(), self._stone()))

    def test_mismatched_core_digests_raise_rather_than_return_a_number(self):
        # The failure this exists to prevent is silent: comparing two
        # unrelated spaces returns a plausible similarity, not an error.
        with self.assertRaises(rs.AnchorMismatch):
            rs.check_compatible(self._stone("aa"), self._stone("zz"))

    def test_a_foreign_file_is_refused(self):
        with self.assertRaises(rs.AnchorMismatch):
            rs.check_compatible(self._stone(), self._stone(magic="SOMETHINGELSE"))

    def test_project_digests_are_only_enforced_when_asked(self):
        a = self._stone(project_digest="bb")
        b = self._stone(project_digest="cc")
        self.assertTrue(rs.check_compatible(a, b))
        with self.assertRaises(rs.AnchorMismatch):
            rs.check_compatible(a, b, require_project=True)

    def test_translate_uses_only_the_core_anchors_by_default(self):
        stone = self._stone()
        out = rs.translate([[1.0, 0.0]], stone)
        self.assertEqual(len(out[0]), stone["core_count"])

    def test_translate_includes_the_project_block_when_requested(self):
        stone = self._stone()
        out = rs.translate([[1.0, 0.0]], stone, use_project=True)
        self.assertEqual(len(out[0]),
                         stone["core_count"] + stone["project_count"])


class ProfileCenteringTests(unittest.TestCase):
    """Centering must change the geometry, not merely rescale the scores.

    The first attempt standardised each vector's similarities across the
    anchors. That is a monotonic transform of one vector's own scores, so
    it cannot reorder anything -- it produced different-looking numbers in
    exactly the same order and looked like it was working.
    """

    def _stone(self, anchor_vectors, texts):
        return {
            "magic": rs.MAGIC,
            "core_count": len(anchor_vectors),
            "project_count": 0,
            "anchors_core": texts,
            "anchors_project": [],
            "anchor_vectors": anchor_vectors,
        }

    def test_centering_can_reorder_the_ranking(self):
        # A strong shared direction is what anisotropy looks like: every
        # anchor points mostly the same way, so raw cosine ranks by that
        # common component instead of by what differs.
        # "popular" carries a large common component and nothing specific,
        # which is what wins under raw cosine in an anisotropic space. The
        # target is really about "third".
        anchors = [
            [10.0, 0.0, 0.0],   # popular
            [1.0, 1.0, 0.0],    # second
            [1.0, 0.0, 1.0],    # third
        ]
        texts = ["popular", "second", "third"]
        stone = self._stone(anchors, texts)
        target = [1.0, 0.2, 0.9]

        raw = [t for _, t in rs.profile(target, stone, top=3, center=False)]
        centred = [t for _, t in rs.profile(target, stone, top=3, center=True)]
        self.assertNotEqual(raw, centred,
                            "centering left the ranking untouched, which is "
                            "the monotonic-rescale bug returning")

    def test_uncentered_profile_is_plain_cosine(self):
        anchors = [[1.0, 0.0], [0.0, 1.0]]
        stone = self._stone(anchors, ["x", "y"])
        rows = rs.profile([1.0, 0.0], stone, top=1, center=False)
        self.assertEqual(rows[0][1], "x")
        self.assertAlmostEqual(rows[0][0], 1.0)

    def test_profile_returns_at_most_top_rows(self):
        anchors = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
        stone = self._stone(anchors, ["x", "y", "z"])
        self.assertEqual(len(rs.profile([1.0, 0.0], stone, top=2)), 2)

    def test_profile_respects_the_core_project_boundary(self):
        stone = {
            "magic": rs.MAGIC,
            "core_count": 2,
            "project_count": 1,
            "anchors_core": ["x", "y"],
            "anchors_project": ["p"],
            "anchor_vectors": [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
        }
        core_only = [t for _, t in rs.profile([1.0, 0.0], stone, top=9)]
        self.assertNotIn("p", core_only)
        with_project = [t for _, t in
                        rs.profile([1.0, 0.0], stone, top=9, use_project=True)]
        self.assertIn("p", with_project)


class SpearmanTests(unittest.TestCase):
    def test_identical_orderings_correlate_perfectly(self):
        self.assertAlmostEqual(rs.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)

    def test_reversed_orderings_anticorrelate(self):
        self.assertAlmostEqual(rs.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_ties_do_not_divide_by_zero(self):
        self.assertIsInstance(rs.spearman([1, 1, 1], [1, 2, 3]), float)


class NeighbourTests(unittest.TestCase):
    def test_a_point_is_never_its_own_neighbour(self):
        vectors = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]]
        for i, row in enumerate(rs.neighbours(vectors, 2)):
            self.assertNotIn(i, row)

    def test_the_nearest_neighbour_is_the_most_similar_vector(self):
        vectors = [[1.0, 0.0], [0.99, 0.01], [0.0, 1.0]]
        self.assertEqual(rs.neighbours(vectors, 1)[0], [1])


if __name__ == "__main__":
    unittest.main()
