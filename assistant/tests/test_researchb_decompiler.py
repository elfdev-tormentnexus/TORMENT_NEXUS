"""Tests for the manifest-driven Research B one-click decompiler."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
machinesoul = importlib.import_module("machinesoul")
release = importlib.import_module("machinesoul_release")
SPEC = importlib.util.spec_from_file_location(
    "researchb_decompiler_under_test",
    ROOT / "tools" / "build_researchb_decompiler.py",
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ResearchBDecompilerTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.manifest_path = self.folder / "MANIFEST_COMBINED.json"
        self.manifest = {
            "format": builder.COMBINED_FORMAT,
            "components": {
                "windows": self._component(
                    "SABLERESEARCHB-WINDOWS",
                    ["setup.bat", "assistant/main.py"],
                    2,
                ),
                "optional_14b": self._component(
                    "SABLERESEARCHB-14B",
                    ["models/companion.gguf"],
                    1,
                ),
            },
        }
        self._write_manifest()
        for name in (
            "machinesoul.py",
            "SABLERESEARCHB-MANIFEST.png",
            "SABLERESEARCHB-REASSEMBLER.png",
            "SABLERESEARCHB-WINDOWS.part01.png",
            "SABLERESEARCHB-WINDOWS.part02.png",
            "SABLERESEARCHB-14B.part01.png",
        ):
            (self.folder / name).write_bytes(name.encode("ascii"))

    @staticmethod
    def _component(prefix, paths, count):
        return {
            "format": builder.COMPONENT_FORMAT,
            "prefix": prefix,
            "capsules": [
                {
                    "name": f"{prefix}.part{number:02d}.png",
                    "decoded_name": f"{prefix}.part{number:02d}.msv",
                }
                for number in range(1, count + 1)
            ],
            "files": [{"path": path} for path in paths],
        }

    def _write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_launcher_is_generated_from_exact_manifest_names(self):
        output = builder.build(self.folder, self.manifest_path)
        raw = output.read_bytes()
        text = raw.decode("ascii")

        self.assertEqual(output.name, "DECOMPILE_SABLE_researchB.bat")
        self.assertIn(b"\r\n", raw)
        self.assertIn("DisableDelayedExpansion", text)
        self.assertIn("SABLERESEARCHB-WINDOWS.part02.png", text)
        self.assertIn("SABLERESEARCHB-WINDOWS.part02.msv", text)
        self.assertIn("--component windows", text)
        self.assertIn("--component optional_14b", text)
        self.assertIn("models\\companion.gguf", text)
        self.assertIn("optional 14B capsule set", text)
        self.assertIn('copy /y "%DECODER%" "%WORK%\\machinesoul.py"', text)

    def test_python_package_init_paths_are_safe_manifest_entries(self):
        self.manifest["components"]["windows"]["files"].append(
            {"path": "assistant/commands/__init__.py"}
        )
        self._write_manifest()

        windows, _optional = builder.inspect_manifest(self.manifest_path)

        self.assertIn(
            "assistant/commands/__init__.py",
            [item["path"] for item in windows["files"]],
        )

    def test_dot_segments_and_separator_injection_remain_refused(self):
        for unsafe in (
            "../setup.bat",
            "assistant/../setup.bat",
            "assistant\\main.py",
            ".hidden",
        ):
            with self.subTest(path=unsafe):
                self.manifest["components"]["windows"]["files"][1]["path"] = unsafe
                self._write_manifest()
                with self.assertRaisesRegex(builder.DecompilerError, "unsafe"):
                    builder.inspect_manifest(self.manifest_path)

    def test_missing_or_gapped_capsules_are_refused(self):
        (self.folder / "SABLERESEARCHB-WINDOWS.part02.png").unlink()
        with self.assertRaisesRegex(builder.DecompilerError, "part02"):
            builder.build(self.folder, self.manifest_path)

        component = self.manifest["components"]["windows"]
        component["capsules"][1]["name"] = "SABLERESEARCHB-WINDOWS.part03.png"
        self._write_manifest()
        with self.assertRaisesRegex(builder.DecompilerError, "not consecutive"):
            builder.inspect_manifest(self.manifest_path)

    def test_optional_component_is_confined_below_models(self):
        self.manifest["components"]["optional_14b"]["files"][0]["path"] = "setup.bat"
        self._write_manifest()
        with self.assertRaisesRegex(builder.DecompilerError, "overlap"):
            builder.inspect_manifest(self.manifest_path)

        self.manifest["components"]["optional_14b"]["files"][0]["path"] = "companion.gguf"
        self._write_manifest()
        with self.assertRaisesRegex(builder.DecompilerError, "below models"):
            builder.inspect_manifest(self.manifest_path)

    def test_output_cannot_escape_or_take_an_unpublished_name(self):
        with self.assertRaisesRegex(builder.DecompilerError, "published name"):
            builder.build(
                self.folder,
                self.manifest_path,
                out_path=self.folder / "installer.bat",
            )


@unittest.skipUnless(os.name == "nt", "executes the generated Windows batch")
class ResearchBDecompilerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.release_dir = self.root / "release!field"
        self.release_dir.mkdir()

    def _cut(self, source, prefix, plan_name, manifest_name, payload_limit=1 << 20):
        plan_path = self.root / plan_name
        review_path = self.root / (plan_name + ".md")
        manifest_path = self.root / manifest_name
        plan = release.make_plan(str(source), prefix, payload_limit=payload_limit)
        digest = release.write_plan(plan, str(plan_path), str(review_path))
        release.cut(
            str(plan_path),
            digest,
            str(self.release_dir),
            str(manifest_path),
        )
        return manifest_path

    def test_actual_capsules_reconstruct_and_install_with_optional_model(self):
        windows = self.root / "windows"
        (windows / "assistant").mkdir(parents=True)
        (windows / "setup.bat").write_bytes(b"@echo off\r\nexit /b 0\r\n")
        (windows / "assistant" / "proof.txt").write_text(
            "exact researchB payload", encoding="utf-8"
        )
        optional = self.root / "optional"
        (optional / "models").mkdir(parents=True)
        (optional / "models" / "companion.gguf").write_bytes(bytes(range(251)))

        windows_manifest = self._cut(
            windows,
            "SABLERESEARCHB-WINDOWS",
            "windows-plan.json",
            "windows-manifest.json",
        )
        optional_manifest = self._cut(
            optional,
            "SABLERESEARCHB-14B",
            "optional-plan.json",
            "optional-manifest.json",
            payload_limit=128,
        )
        combined = self.root / "MANIFEST_COMBINED.json"
        release.combine_manifests(
            str(windows_manifest), str(optional_manifest), str(combined)
        )
        machinesoul.build_stream(
            str(combined),
            str(self.release_dir / "SABLERESEARCHB-MANIFEST.png"),
        )
        machinesoul.build_stream(
            str(TOOLS / "machinesoul_release.py"),
            str(self.release_dir / "SABLERESEARCHB-REASSEMBLER.png"),
        )
        shutil.copy2(TOOLS / "machinesoul.py", self.release_dir / "machinesoul.py")
        launcher = builder.build(self.release_dir, combined)

        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(launcher)],
            cwd=self.release_dir,
            input=b"\r\n\r\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        transcript = result.stdout.decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, transcript)
        installed = self.release_dir / "TORMENT_NEXUS-researchB"
        self.assertEqual(
            (installed / "assistant" / "proof.txt").read_text(encoding="utf-8"),
            "exact researchB payload",
        )
        self.assertEqual(
            (installed / "models" / "companion.gguf").read_bytes(),
            bytes(range(251)),
        )
        self.assertFalse(
            (self.release_dir / ".SABLERESEARCHB-decompile-work").exists()
        )

        # The optional set has multiple parts. One missing part must refuse
        # before reconstructing a target; no optional parts must cleanly take
        # the ordinary-install path promised by the public guide.
        optional_capsules = sorted(
            self.release_dir.glob("SABLERESEARCHB-14B.part*.png")
        )
        self.assertGreater(len(optional_capsules), 1)
        shutil.rmtree(installed)
        optional_capsules[0].unlink()
        partial_result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(launcher)],
            cwd=self.release_dir,
            input=b"\r\n\r\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        partial_transcript = partial_result.stdout.decode(
            "utf-8", errors="replace"
        )
        self.assertEqual(partial_result.returncode, 1, partial_transcript)
        self.assertIn("Only part of the optional 14B", partial_transcript)
        self.assertFalse(installed.exists())

        for capsule in optional_capsules[1:]:
            capsule.unlink()
        ordinary_result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(launcher)],
            cwd=self.release_dir,
            input=b"\r\n\r\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        ordinary_transcript = ordinary_result.stdout.decode(
            "utf-8", errors="replace"
        )
        self.assertEqual(ordinary_result.returncode, 0, ordinary_transcript)
        self.assertTrue(installed.is_dir())
        self.assertFalse((installed / "models" / "companion.gguf").exists())
