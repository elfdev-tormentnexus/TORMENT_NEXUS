"""Offline regression tests for the held-out Rosetta whitening experiment."""
import importlib.util
import os
import unittest


_PROBE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tools", "rosetta_whitening_probe.py",
)
_spec = importlib.util.spec_from_file_location("_rosetta_whitening_probe", _PROBE)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)


class RosettaWhiteningProbeTests(unittest.TestCase):
    def setUp(self):
        self.fit_a = [[1.0, 0.0], [0.8, 0.2], [0.1, 0.9], [0.2, 0.8]]
        self.fit_b = [[1.0, 0.0, 0.0], [0.7, 0.3, 0.0],
                      [0.0, 0.9, 0.1], [0.1, 0.8, 0.1]]
        self.test_a = [[0.9, 0.1], [0.7, 0.3], [0.2, 0.8], [0.1, 0.9]]
        self.test_b = [[0.9, 0.1, 0.0], [0.6, 0.4, 0.0],
                       [0.1, 0.8, 0.1], [0.0, 0.9, 0.1]]
        self.anchors_a = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]
        self.anchors_b = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.6, 0.7, 0.1]]

    def test_compares_controls_and_keeps_one_anchor_coordinate_per_anchor(self):
        rows = probe.evaluate(
            self.fit_a, self.fit_b, self.test_a, self.test_b,
            self.anchors_a, self.anchors_b,
            metadata_a={"model": "a"}, metadata_b={"model": "b"},
            shrinkages=(0.10,), k=1,
        )
        self.assertEqual([row["name"] for row in rows], [
            "raw", "anchor-centred", "zca-0.10", "zca-0.10-anchor-centred",
        ])
        for row in rows:
            self.assertGreaterEqual(row["neighbour_agreement"], 0.0)
            self.assertLessEqual(row["neighbour_agreement"], 1.0)
        self.assertEqual(len(probe._relative(self.test_a, self.anchors_a)[0]), 3)

    def test_whitening_transforms_keep_their_separate_model_provenance(self):
        rows = probe.evaluate(
            self.fit_a, self.fit_b, self.test_a, self.test_b,
            self.anchors_a, self.anchors_b,
            metadata_a={"model": "model-a", "corpus": "same"},
            metadata_b={"model": "model-b", "corpus": "same"},
            shrinkages=(0.02,), k=1,
        )
        whitened = next(row for row in rows if row["name"] == "zca-0.02")
        self.assertNotEqual(whitened["transform_digests"]["a"],
                            whitened["transform_digests"]["b"])

    def test_refuses_a_cross_model_test_pair_with_different_row_counts(self):
        with self.assertRaises(ValueError):
            probe.evaluate(
                self.fit_a, self.fit_b, self.test_a, self.test_b[:-1],
                self.anchors_a, self.anchors_b,
                metadata_a={}, metadata_b={}, shrinkages=(0.10,), k=1,
            )


if __name__ == "__main__":
    unittest.main()
