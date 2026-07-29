"""Regression tests for the versioned experimental whitening transform."""
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np


sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tools",
))
import vector_whitening as white  # noqa: E402
import whitening_probe as probe  # noqa: E402


class WhiteningFitTests(unittest.TestCase):
    def test_full_rank_unregularised_fit_has_identity_training_covariance(self):
        rng = np.random.default_rng(20260729)
        rows = rng.normal(size=(96, 4)) @ np.array([
            [2.0, 0.4, 0.1, 0.0],
            [0.0, 1.5, 0.3, 0.1],
            [0.0, 0.0, 0.8, 0.2],
            [0.0, 0.0, 0.0, 0.5],
        ])
        transform = white.fit(rows.tolist(), shrinkage=0.0)
        whitened = np.asarray(transform.transform_many(rows.tolist()))
        covariance = np.cov(whitened, rowvar=False)
        self.assertTrue(np.allclose(covariance, np.eye(4), atol=1e-10))

    def test_regularisation_handles_fewer_samples_than_dimensions(self):
        transform = white.fit(
            [[1.0, 0.0, 0.0, 1.0, 2.0],
             [0.0, 1.0, 0.0, 1.0, 2.0],
             [0.0, 0.0, 1.0, 1.0, 2.0]],
            shrinkage=0.10,
        )
        result = transform.transform_many(
            [[0.5, 0.5, 0.5, 1.0, 2.0]], normalise=True)
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertAlmostEqual(float(np.linalg.norm(result[0])), 1.0)

    def test_document_round_trip_preserves_the_transform_and_provenance(self):
        rows = [[1.0, 2.0], [2.0, 4.0], [4.0, 3.0], [5.0, 8.0]]
        original = white.fit(rows, metadata={
            "model": "bge-small:q8", "pooling": "mean",
        })
        restored = white.from_document(original.document())
        self.assertEqual(restored.metadata, original.metadata)
        self.assertEqual(restored.training_digest, original.training_digest)
        self.assertTrue(np.allclose(
            restored.transform_many(rows), original.transform_many(rows)))
        restored.assert_compatible({"model": "bge-small:q8", "pooling": "mean"})
        with self.assertRaises(white.WhiteningError):
            restored.assert_compatible({"model": "other-model", "pooling": "mean"})

    def test_tampering_with_a_document_refuses(self):
        transform = white.fit([[1.0, 0.0], [0.0, 1.0], [2.0, 2.0]])
        document = transform.document()
        document["mean"][0] += 0.1
        with self.assertRaises(white.WhiteningError):
            white.from_document(document)

    def test_invalid_vectors_and_dimensions_refuse(self):
        with self.assertRaises(white.WhiteningError):
            white.fit([[1.0, float("nan")], [0.0, 1.0]])
        transform = white.fit([[1.0, 0.0], [0.0, 1.0]])
        with self.assertRaises(white.WhiteningError):
            transform.transform([1.0, 2.0, 3.0])


class WhiteningProbeTests(unittest.TestCase):
    def test_pairwise_reports_geometry_without_claiming_retrieval(self):
        rows = probe.pairwise([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
        self.assertEqual(rows["count"], 3)
        self.assertGreater(rows["standard_deviation"], 0.0)

    def test_document_digest_changes_with_the_reference_text(self):
        first = probe._document_digest(["one.md"], ["one public chunk"])
        second = probe._document_digest(["one.md"], ["another public chunk"])
        self.assertNotEqual(first, second)

    def test_probe_fits_only_the_declared_reference_and_keeps_a_heldout_test(self):
        with tempfile.TemporaryDirectory() as folder:
            fit_path = os.path.join(folder, "fit.md")
            test_path = os.path.join(folder, "test.md")
            with open(fit_path, "w", encoding="utf-8") as handle:
                handle.write("fit alpha " * 30 + "\n\n" + "fit beta " * 30)
            with open(test_path, "w", encoding="utf-8") as handle:
                handle.write("test alpha " * 30 + "\n\n" + "test beta " * 30)

            vectors = [
                [[1.0, 0.0, 0.0], [0.8, 0.2, 0.0]],
                [[0.0, 1.0, 0.0], [0.0, 0.8, 0.2]],
                [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            ]
            with mock.patch.object(
                probe.embedding_server, "_health_responds", return_value=True,
            ), mock.patch.object(
                probe.embedding_server, "embed", side_effect=vectors,
            ), mock.patch.object(
                probe.embedding_server, "model_identity", return_value="model:1",
            ), mock.patch.object(
                probe.embedding_server, "POOLING_MODE", "mean",
            ), mock.patch.object(
                probe.machinespirit, "anchor_texts",
                return_value=["one", "two", "three"],
            ):
                result, transform = probe.run([fit_path], test_path)

        self.assertEqual(result["fit"]["chunks"], 2)
        self.assertEqual(result["test"]["chunks"], 2)
        self.assertEqual(transform.metadata["model"], "model:1")
        self.assertIn("does not establish", result["interpretation"])
