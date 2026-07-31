"""Tests for direct, review-gated machinesoul release cutting."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in os.sys.path:
    os.sys.path.insert(0, str(_TOOLS))
_SPEC = importlib.util.spec_from_file_location(
    "_machinesoul_release_under_test",
    _TOOLS / "machinesoul_release.py",
)
release = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = release
_SPEC.loader.exec_module(release)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CutPlanTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.source = Path(self.folder, "source")
        self.source.mkdir()

    def test_whole_file_boundaries_are_preferred(self):
        Path(self.source, "a.py").write_text("def a():\n    return 1\n")
        Path(self.source, "b.py").write_text("def b():\n    return 2\n")

        plan = release.make_plan(
            str(self.source),
            "SABLERESEARCHA-TEST",
            payload_limit=30,
        )

        self.assertEqual(len(plan["capsules"]), 2)
        self.assertEqual(plan["capsules"][0]["boundary"]["kind"], "file_end")
        self.assertEqual(plan["capsules"][0]["boundary"]["activity"], 0.0)
        self.assertEqual(
            plan["capsules"][0]["boundary"]["path"],
            "a.py",
        )

    def test_an_in_file_cut_is_aligned_to_a_complete_pixel_vector(self):
        Path(self.source, "model.gguf").write_bytes(bytes(range(251)) * 20)
        plan = release.make_plan(
            str(self.source),
            "SABLERESEARCHA-TEST",
            payload_limit=1024,
        )

        self.assertGreater(len(plan["capsules"]), 1)
        for capsule in plan["capsules"][:-1]:
            boundary = capsule["boundary"]
            if boundary["kind"] == "quiet_vector_window":
                self.assertEqual(boundary["offset"] % 4, 0)

    def test_a_quiet_zero_region_beats_noisy_neighbours(self):
        noisy = bytes(range(256)) * 64
        quiet = b"\x00" * (256 * 64)
        path = Path(self.source, "large.gguf")
        path.write_bytes(noisy + quiet + noisy)

        old_radius = release.QUIET_RADIUS
        old_window = release.QUIET_WINDOW
        old_step = release.QUIET_STEP
        self.addCleanup(setattr, release, "QUIET_RADIUS", old_radius)
        self.addCleanup(setattr, release, "QUIET_WINDOW", old_window)
        self.addCleanup(setattr, release, "QUIET_STEP", old_step)
        release.QUIET_RADIUS = len(noisy + quiet)
        release.QUIET_WINDOW = 4096
        release.QUIET_STEP = 1024

        cut = release.quiet_cut(str(path), 0, path.stat().st_size)
        self.assertEqual(cut["kind"], "quiet_vector_window")
        self.assertGreaterEqual(cut["offset"], len(noisy))
        self.assertLessEqual(cut["offset"], len(noisy + quiet) + 4096)


class CutAndReassembleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.source = Path(self.folder, "source")
        self.source.mkdir()
        Path(self.source, "alpha.py").write_text(
            "RULES = ['preserve']\n\n\ndef alpha():\n    return 1\n",
            encoding="utf-8",
        )
        Path(self.source, "empty.txt").write_bytes(b"")
        Path(self.source, "model.gguf").write_bytes(bytes(range(253)) * 25)
        self.plan_path = Path(self.folder, "plan.json")
        self.review_path = Path(self.folder, "CUT_REVIEW.md")
        self.out = Path(self.folder, "capsules")
        self.manifest = Path(self.folder, "manifest.json")

    def _plan(self):
        plan = release.make_plan(
            str(self.source),
            "SABLERESEARCHA-TEST",
            payload_limit=2048,
        )
        digest = release.write_plan(
            plan,
            str(self.plan_path),
            str(self.review_path),
        )
        return plan, digest

    def _cut(self):
        plan, digest = self._plan()
        manifest = release.cut(
            str(self.plan_path),
            digest,
            str(self.out),
            str(self.manifest),
        )
        return plan, manifest

    def test_cut_requires_the_exact_reviewed_plan_hash(self):
        self._plan()
        with self.assertRaises(release.ReleaseError):
            release.cut(
                str(self.plan_path),
                "0" * 64,
                str(self.out),
                str(self.manifest),
            )
        self.assertFalse(self.out.exists())

    def test_a_file_added_after_planning_is_refused(self):
        # Rehashing only the planned files proves nothing about a file that
        # did not exist when the plan was reviewed. Such a file was never in
        # the Markdown table, never rendered into an APNG frame, and is not
        # covered by the approved plan hash, yet it would have been cut in.
        _plan, digest = self._plan()
        Path(self.source, "smuggled.py").write_text(
            "def smuggled():\n    return 'never reviewed'\n",
            encoding="utf-8",
        )

        with self.assertRaises(release.ReleaseError) as caught:
            release.cut(
                str(self.plan_path),
                digest,
                str(self.out),
                str(self.manifest),
            )

        self.assertIn("gained files after review", str(caught.exception))
        self.assertIn("smuggled.py", str(caught.exception))
        self.assertFalse(self.out.exists())
        self.assertFalse(self.manifest.exists())

    def test_a_planned_file_removed_after_planning_is_still_refused(self):
        _plan, digest = self._plan()
        Path(self.source, "alpha.py").unlink()

        with self.assertRaises(release.ReleaseError) as caught:
            release.cut(
                str(self.plan_path),
                digest,
                str(self.out),
                str(self.manifest),
            )

        self.assertIn("alpha.py", str(caught.exception))
        self.assertFalse(self.out.exists())

    def test_an_untouched_source_still_cuts(self):
        # The reinventory must not make the ordinary path stricter.
        _plan, manifest = self._cut()

        self.assertTrue(self.out.exists())
        self.assertTrue(manifest["capsules"])

    def test_cut_review_renders_as_a_plan_bound_apng(self):
        plan, digest = self._plan()
        image = Path(self.folder, "CUT_REVIEW.png")
        report = release.render_plan_apng(str(self.plan_path), str(image))
        blob = image.read_bytes()

        self.assertEqual(blob[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn(b"acTL", blob)
        self.assertIn(digest.encode("ascii"), blob)
        self.assertEqual(report["frames"], len(plan["capsules"]) + 1)
        self.assertEqual(report["plan_sha256"], digest)

    def test_capsules_decompile_and_reassemble_the_tree_exactly(self):
        plan, manifest = self._cut()
        self.assertNotIn("source_root", manifest)
        self.assertNotIn(str(self.source), self.manifest.read_text("utf-8"))
        segments = Path(self.folder, "segments")
        segments.mkdir()
        for capsule in manifest["capsules"]:
            release.machinesoul.extract_stream(
                str(self.out / capsule["name"]),
                str(segments / capsule["decoded_name"]),
            )

        rebuilt = Path(self.folder, "rebuilt")
        release.reassemble(
            str(self.manifest),
            str(segments),
            str(rebuilt),
        )

        self.assertEqual(
            [record["path"] for record in plan["files"]],
            sorted(
                str(path.relative_to(rebuilt)).replace("\\", "/")
                for path in rebuilt.rglob("*")
                if path.is_file()
            ),
        )
        for record in plan["files"]:
            self.assertEqual(_sha(rebuilt / record["path"]), record["sha256"])

    def _cut_optional(self):
        """Cut a second component shaped like the optional model pack.

        It must be genuinely separate: combine_manifests() decides which
        component is which from argument order, so a test that hands it the
        same manifest twice cannot show that ordering is respected.
        """
        source = Path(self.folder, "source-14b")
        (source / "models").mkdir(parents=True)
        Path(source, "models", "companion.gguf").write_bytes(
            bytes(range(211)) * 30
        )
        plan = release.make_plan(
            str(source),
            "SABLERESEARCHA-TEST-14B",
            payload_limit=2048,
        )
        plan_path = Path(self.folder, "plan-14b.json")
        digest = release.write_plan(
            plan,
            str(plan_path),
            str(Path(self.folder, "CUT_REVIEW_14B.md")),
        )
        manifest_path = Path(self.folder, "manifest-14b.json")
        manifest = release.cut(
            str(plan_path),
            digest,
            str(Path(self.folder, "capsules-14b")),
            str(manifest_path),
        )
        return manifest_path, manifest

    def test_swapped_components_are_refused(self):
        self._cut()
        optional_path, _optional = self._cut_optional()

        with self.assertRaises(release.ReleaseError) as caught:
            release.combine_manifests(
                str(optional_path),
                str(self.manifest),
                str(Path(self.folder, "swapped.json")),
            )

        self.assertIn("must live under models/", str(caught.exception))

    def test_the_same_manifest_supplied_twice_is_refused(self):
        self._cut()

        with self.assertRaises(release.ReleaseError) as caught:
            release.combine_manifests(
                str(self.manifest),
                str(self.manifest),
                str(Path(self.folder, "doubled.json")),
            )

        self.assertIn("supplied twice", str(caught.exception))

    def test_combined_manifest_selects_each_release_component(self):
        _, manifest = self._cut()
        optional_path, _optional = self._cut_optional()
        combined_path = Path(self.folder, "combined.json")
        combined = release.combine_manifests(
            str(self.manifest),
            str(optional_path),
            str(combined_path),
        )
        self.assertEqual(combined["format"], "SABLERESEARCHA_MANIFEST1")
        self.assertEqual(
            set(combined["components"]),
            {"windows", "optional_14b"},
        )

        segments = Path(self.folder, "combined-segments")
        segments.mkdir()
        for capsule in manifest["capsules"]:
            release.machinesoul.extract_stream(
                str(self.out / capsule["name"]),
                str(segments / capsule["decoded_name"]),
            )

        rebuilt = Path(self.folder, "combined-rebuilt")
        release.reassemble(
            str(combined_path),
            str(segments),
            str(rebuilt),
            component="windows",
        )
        for record in manifest["files"]:
            self.assertEqual(_sha(rebuilt / record["path"]), record["sha256"])

        with self.assertRaises(release.ReleaseError):
            release.reassemble(
                str(combined_path),
                str(segments),
                str(Path(self.folder, "missing-component")),
            )

    def test_final_windows_promotion_retries_a_transient_scanner_lock(self):
        source = Path(self.folder, "promotion-source")
        destination = Path(self.folder, "promotion-destination")
        source.mkdir()
        Path(source, "complete.txt").write_text("verified", encoding="utf-8")
        real_replace = release.os.replace
        attempts = []

        def briefly_locked(old, new):
            attempts.append((old, new))
            if len(attempts) < 3:
                raise PermissionError("simulated Windows scanner handle")
            return real_replace(old, new)

        with mock.patch.object(release.os, "replace", side_effect=briefly_locked):
            with mock.patch.object(release.time, "sleep") as sleep:
                release._promote_directory(str(source), str(destination))

        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(
            Path(destination, "complete.txt").read_text("utf-8"),
            "verified",
        )

    def test_a_tampered_decoded_capsule_is_refused(self):
        _, manifest = self._cut()
        segments = Path(self.folder, "segments")
        segments.mkdir()
        for capsule in manifest["capsules"]:
            release.machinesoul.extract_stream(
                str(self.out / capsule["name"]),
                str(segments / capsule["decoded_name"]),
            )
        first = segments / manifest["capsules"][0]["decoded_name"]
        damaged = bytearray(first.read_bytes())
        damaged[0] ^= 1
        first.write_bytes(damaged)

        with self.assertRaises(release.ReleaseError):
            release.reassemble(
                str(self.manifest),
                str(segments),
                str(Path(self.folder, "rebuilt")),
            )

    def test_a_manifest_path_cannot_escape_the_target(self):
        _, manifest = self._cut()
        manifest["files"][0]["path"] = "../escape"
        bad = Path(self.folder, "bad.json")
        bad.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(release.ReleaseError):
            release.reassemble(
                str(bad),
                str(Path(self.folder, "segments")),
                str(Path(self.folder, "rebuilt")),
            )


if __name__ == "__main__":
    unittest.main()
