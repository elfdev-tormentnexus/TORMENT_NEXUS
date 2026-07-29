"""Tests for the per-subsystem source capsule set.

The complete release is cut along size boundaries, so part04 is the middle
of a model file and can say nothing about itself. This set is cut along
meaning instead, and the properties worth guarding are the two that fail
quietly: a map that drops a file still produces a set that looks complete,
and a capsule that carries private runtime state looks exactly like one
that does not.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TOOLS = os.path.join(_ROOT, "tools")

# Loaded by path for the same reason test_machinesoul.py does it: a plain
# import reads as an undeclared third-party package to the dependency
# scanner in test_regressions.py.
sys.path.insert(0, _TOOLS)
_spec = importlib.util.spec_from_file_location(
    "_source_capsules_under_test", os.path.join(_TOOLS, "source_capsules.py"))
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

_ms_spec = importlib.util.spec_from_file_location(
    "_machinesoul_for_source", os.path.join(_TOOLS, "machinesoul.py"))
ms = importlib.util.module_from_spec(_ms_spec)
_ms_spec.loader.exec_module(ms)


class CoverageTests(unittest.TestCase):
    """A set that looks complete and is not is the failure worth preventing."""

    def test_every_source_file_lands_in_exactly_one_capsule(self):
        groups = sc.plan()
        seen = {}
        for name, _root, paths in groups:
            for path in paths:
                self.assertNotIn(path, seen,
                                 f"{path} in both {seen.get(path)} and {name}")
                seen[path] = name
        self.assertGreater(len(seen), 100)

    def test_a_stale_subsystem_map_is_refused_rather_than_shipped(self):
        """Drop a subsystem and the build must refuse, not quietly omit it."""
        original = sc.SUBSYSTEMS
        try:
            sc.SUBSYSTEMS = tuple(entry for entry in original
                                  if entry[0] != "assistant-core")
            with self.assertRaises(sc.SourceCapsuleError) as caught:
                sc.plan()
            self.assertIn("in no capsule", str(caught.exception))
        finally:
            sc.SUBSYSTEMS = original

    def test_the_plan_reaches_the_subsystems_it_names(self):
        names = {name for name, _root, _paths in sc.plan()}
        for expected in ("assistant-core", "assistant-editing", "tools",
                         "docs", "assistant-root"):
            self.assertIn(expected, names)


class PrivateStateTests(unittest.TestCase):
    """Private runtime state lives beside the source and must never travel.

    The release packager excludes it twice over. This tool is not the
    packager, so it carries its own refusal rather than relying on someone
    remembering that it should.
    """

    def test_private_runtime_files_are_never_source(self):
        for name in ("memories.json", "conversation_history.txt",
                     "activity_log.jsonl", "session_rhythm.json",
                     "chosen_name.json", "embeddings.json"):
            self.assertFalse(sc._is_source(name), name)

    def test_no_planned_capsule_contains_private_state(self):
        for _name, _root, paths in sc.plan():
            for path in paths:
                self.assertNotIn(os.path.basename(path), sc.NEVER_CAPSULE,
                                 f"{path} would have been capsuled")

    def test_ordinary_source_is_still_source(self):
        for name in ("main.py", "ARCHITECTURE.md", "core_memory.txt",
                     "project_map.json"):
            self.assertTrue(sc._is_source(name), name)


class RoundTripTests(unittest.TestCase):
    """Reversible or refused, the same promise the container itself makes."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def test_a_subsystem_capsule_restores_its_files_byte_for_byte(self):
        name, _root, paths = next(group for group in sc.plan()
                                  if group[0] == "assistant-web")
        payload = ms.tar_paths(paths, sc.ROOT)
        capsule = os.path.join(self.folder, "s.png")
        ms.build(payload, capsule, frames=2, description=sc.describe(name, paths))

        recovered, _meta = ms.extract(capsule)
        self.assertEqual(recovered, payload)

        import io
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(recovered)) as archive:
            members = sorted(m.name for m in archive.getmembers())
            self.assertEqual(members, sorted(paths))
            for path in paths:
                extracted = archive.extractfile(path).read()
                with open(os.path.join(sc.ROOT, path), "rb") as handle:
                    self.assertEqual(extracted, handle.read(), path)

    def test_the_tar_is_deterministic_so_rebuilds_compare(self):
        _name, _root, paths = next(group for group in sc.plan()
                                   if group[0] == "assistant-web")
        self.assertEqual(ms.tar_paths(paths, sc.ROOT),
                         ms.tar_paths(paths, sc.ROOT))


class DescriptionTests(unittest.TestCase):
    def test_a_subsystem_describes_itself_in_its_modules_own_words(self):
        name, _root, paths = next(group for group in sc.plan()
                                  if group[0] == "assistant-core")
        text = sc.describe(name, paths)
        self.assertIn("assistant-core", text)
        self.assertIn("machinespirit.py", text)
        # The summary is the module's own docstring, not one invented here.
        self.assertIn("per-token trajectories", text)

    def test_a_module_without_a_docstring_contributes_nothing(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        bare = os.path.join(folder, "bare.py")
        with open(bare, "w", encoding="utf-8") as handle:
            handle.write("x = 1\n")
        self.assertIsNone(sc._docstring_summary(
            os.path.relpath(bare, sc.ROOT)))


if __name__ == "__main__":
    unittest.main()
