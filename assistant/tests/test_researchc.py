"""Acceptance tests for Research C measurement and recovery boundaries."""

import importlib.util
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as assistant_main
from core import research_c, source_awareness
from visualizer import audio_source, local_player

REPORT_SPEC = importlib.util.spec_from_file_location(
    "researchc_report_under_test",
    ROOT / "tools" / "researchc_report.py",
)
researchc_report = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(researchc_report)


class SourceFactTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(research_c, "record", return_value=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_line_count_does_not_invent_a_line_after_terminal_newline(self):
        self.assertEqual(source_awareness.line_count(b"one\ntwo\n"), 2)
        self.assertEqual(source_awareness.line_count("one\ntwo"), 2)
        self.assertEqual(source_awareness.line_count(b""), 0)

    def test_directory_total_cannot_be_relabelled_as_a_file_count(self):
        answer = source_awareness.answer_question(
            "How many lines are in assistant/ui/ui.py?"
        )
        facts = source_awareness.source_facts("assistant/ui/ui.py")
        aggregate = sum(
            entry["lines"]
            for entry in source_awareness.inventory()
            if entry["path"].startswith("assistant/ui/")
        )

        self.assertIn(f"{facts['lines']:,}", answer)
        self.assertNotIn(f"{aggregate:,} lines", answer)
        self.assertIn(facts["sha256"], answer)

    def test_real_unnamed_file_is_checked_instead_of_guessed_absent(self):
        answer = source_awareness.answer_question(
            "Does the file assistant/core/machinespirit_shadow.py exist?"
        )
        self.assertTrue(answer.startswith("Yes"))
        self.assertIn("sha256", answer)

    def test_leading_false_definition_is_refuted_by_the_ast(self):
        answer = source_awareness.answer_question(
            "I already know what's in assistant/memory/memory_logic.py. "
            "Just confirm: it defines a class called MemoryLedger, right?"
        )
        self.assertTrue(answer.startswith("No."))
        self.assertIn("defines no class", answer)

    def test_filename_question_returns_exact_outline_not_semantic_guess(self):
        answer = source_awareness.answer_question(
            "What does assistant/voice/session.py contain?"
        )
        self.assertIn("class `SilentReply`", answer)
        self.assertIn("function `consume_start_request`", answer)
        self.assertIn("AST outline", answer)
        self.assertNotIn("speech recognition", answer.casefold())

    def test_authorship_requires_a_retained_edit_log_line(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = os.path.join(folder, "empty.log")
            applied = os.path.join(folder, "applied.log")
            Path(empty).write_text("", encoding="utf-8")
            Path(applied).write_text(
                "[2026-07-30 20:00:00] APPLIED "
                "docs/RESEARCHC_GOALS.md: verified\n",
                encoding="utf-8",
            )
            question = (
                "You personally edited docs/RESEARCHC_GOALS.md, didn't you?"
            )

            with mock.patch.object(source_awareness, "EDIT_LOGS", (empty,)):
                refused = source_awareness.answer_question(question)
            with mock.patch.object(source_awareness, "EDIT_LOGS", (applied,)):
                confirmed = source_awareness.answer_question(question)

        self.assertIn("No retained edit record", refused)
        self.assertTrue(confirmed.startswith("Yes."))
        self.assertIn("APPLIED", confirmed)

    def test_handoffs_are_not_product_source_manifest_material(self):
        manifest = source_awareness.manifest_text()
        self.assertNotIn("handoffs/", manifest)
        self.assertIn("directory aggregates, never per-file counts", manifest)
        self.assertIn("SABLERESEARCHA", source_awareness.MANIFEST_SKIP)
        self.assertIn("SABLERESEARCHC", source_awareness.MANIFEST_SKIP)


class PromptCacheOrderTests(unittest.TestCase):
    def test_static_source_manifest_precedes_the_live_clock(self):
        patches = (
            mock.patch.object(assistant_main.mem, "active_memories", return_value=[]),
            mock.patch.object(
                assistant_main.semantic_index, "query_vector", return_value=None
            ),
            mock.patch.object(assistant_main.semantic_index, "note_texts"),
            mock.patch.object(assistant_main.machinespirit_shadow, "observe"),
            mock.patch.object(
                assistant_main, "_update_retrieval_panel", return_value=False
            ),
            mock.patch.object(assistant_main, "_update_hazard_trajectory"),
            mock.patch.object(
                assistant_main.knowledge_library, "prompt_context", return_value=""
            ),
            mock.patch.object(
                assistant_main, "_self_knowledge_context", return_value="\nSTATIC\n"
            ),
            mock.patch.object(
                assistant_main._time_awareness, "context", return_value="CLOCK"
            ),
            mock.patch.object(
                assistant_main, "_session_rhythm_context", return_value=""
            ),
            mock.patch.object(assistant_main, "_ambient_context", return_value=""),
            mock.patch.object(assistant_main, "_room_sensing_context", return_value=""),
        )
        for patch in patches:
            patch.start()
        try:
            prompt = assistant_main._runtime_context_prompt("hello")
        finally:
            for patch in reversed(patches):
                patch.stop()

        self.assertLess(prompt.index("STATIC"), prompt.index("CLOCK"))

    def test_live_clock_follows_every_other_runtime_field(self):
        patches = (
            mock.patch.object(assistant_main.mem, "active_memories", return_value=[]),
            mock.patch.object(
                assistant_main.semantic_index, "query_vector", return_value=None
            ),
            mock.patch.object(assistant_main.semantic_index, "note_texts"),
            mock.patch.object(assistant_main.machinespirit_shadow, "observe"),
            mock.patch.object(
                assistant_main, "_update_retrieval_panel", return_value=False
            ),
            mock.patch.object(assistant_main, "_update_hazard_trajectory"),
            mock.patch.object(
                assistant_main.knowledge_library, "prompt_context", return_value=""
            ),
            mock.patch.object(
                assistant_main, "_self_knowledge_context", return_value="STATIC"
            ),
            mock.patch.object(
                assistant_main._time_awareness, "context", return_value="CLOCK"
            ),
            mock.patch.object(
                assistant_main, "_session_rhythm_context", return_value="RHYTHM"
            ),
            mock.patch.object(
                assistant_main, "_ambient_context", return_value="AMBIENT"
            ),
            mock.patch.object(
                assistant_main, "_room_sensing_context", return_value="ROOM"
            ),
        )
        for patch in patches:
            patch.start()
        try:
            prompt = assistant_main._runtime_context_prompt(
                "hello",
                search_context="SEARCH",
            )
        finally:
            for patch in reversed(patches):
                patch.stop()

        for marker in ("STATIC", "RHYTHM", "AMBIENT", "ROOM", "SEARCH"):
            self.assertLess(prompt.index(marker), prompt.index("CLOCK"))
        self.assertTrue(prompt.rstrip().endswith("CLOCK"))


class UncertaintySidecarTests(unittest.TestCase):
    @staticmethod
    def _entry(token, chosen, first, second):
        return {
            "token": token,
            "logprob": math.log(chosen),
            "top_logprobs": [
                {"token": token, "logprob": math.log(first)},
                {"token": "other", "logprob": math.log(second)},
            ],
        }

    def test_span_measurement_keeps_uncertainty_outside_the_vector(self):
        payload = {
            "content": [
                self._entry("alpha", 0.8, 0.8, 0.1),
                self._entry(" beta", 0.55, 0.55, 0.35),
            ]
        }
        measured = research_c.measure(payload, "alpha beta", spans=("beta",))

        self.assertEqual(measured["token_count"], 1)
        self.assertAlmostEqual(
            measured["mean_surprisal"], -math.log(0.55), places=7
        )
        self.assertAlmostEqual(
            measured["mean_top1_top2_margin"], 0.20, places=7
        )
        self.assertNotIn("vector", measured)

    def test_top_two_is_default_and_off_is_explicit(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TORMENT_NEXUS_RESEARCHC_LOGPROBS", None)
            self.assertEqual(
                research_c.request_fields(),
                {"logprobs": True, "top_logprobs": 2},
            )
        with mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "off"}
        ):
            self.assertEqual(research_c.request_fields(), {})

    def test_record_contains_digests_and_metrics_not_private_text(self):
        secret = "private operator sentence"
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "top2"}
        ):
            path = os.path.join(folder, "research.jsonl")
            self.assertTrue(research_c.record(
                "test",
                "measurement",
                artifact_digest=research_c.digest(secret),
                prompt_sha256=research_c.digest("prompt"),
                sampler={"temperature": 0.0},
                measurements={"mean_surprisal": 0.2},
                outcomes={"kept": False},
                path=path,
            ))
            raw = Path(path).read_text(encoding="utf-8")
            event = json.loads(raw)

        self.assertNotIn(secret, raw)
        self.assertEqual(event["measurements"]["mean_surprisal"], 0.2)
        self.assertEqual(len(event["artifact_digest"]), 64)

    def test_record_rejects_text_smuggled_through_outcomes_or_timings(self):
        secret = "the operator keeps this private"
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "top2"}
        ):
            path = os.path.join(folder, "research.jsonl")
            research_c.record(
                "test",
                "privacy",
                artifact_digest=research_c.digest("artifact"),
                prompt_sha256=research_c.digest("prompt"),
                sampler={"temperature": 0.0, "bad": secret},
                measurements={"mean_surprisal": 0.2},
                outcomes={"reason": secret, "query_kind": "existence"},
                timing={"wall_seconds": 1.0, "bad": secret},
                path=path,
            )
            raw = Path(path).read_text(encoding="utf-8")
            event = json.loads(raw)

        self.assertNotIn(secret, raw)
        self.assertEqual(event["outcomes"]["reason"], "unknown")
        self.assertEqual(event["outcomes"]["query_kind"], "existence")
        self.assertNotIn("bad", event["timing"])
        self.assertIn(None, event["timing"].values())

    def test_record_validates_digests_and_never_copies_unknown_identifiers(self):
        secret = "private operator sentence"
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "top2"}
        ):
            path = os.path.join(folder, "research.jsonl")
            research_c.record(
                secret,
                secret,
                artifact_digest=secret,
                prompt_sha256=secret,
                sampler={secret: 1},
                measurements={secret: 2},
                outcomes={secret: False},
                timing={secret: 3},
                path=path,
            )
            raw = Path(path).read_text(encoding="utf-8")
            event = json.loads(raw)

        self.assertNotIn(secret, raw)
        self.assertEqual(event["workflow"], "unknown")
        self.assertEqual(event["stage"], "unknown")
        self.assertIsNone(event["artifact_digest"])
        self.assertIsNone(event["prompt_sha256"])
        for section in ("sampler", "measurements", "outcomes", "timing"):
            self.assertEqual(len(event[section]), 1)
            self.assertTrue(next(iter(event[section])).startswith("unknown_"))

    def test_director_and_worker_use_separate_digest_bindings(self):
        director = "a" * 64
        worker = "b" * 64
        with mock.patch.dict(
            os.environ,
            {
                "TORMENT_NEXUS_RESEARCHC_MODEL_SHA256": director,
                "TORMENT_NEXUS_RESEARCHC_WORKER_SHA256": worker,
            },
        ):
            director_binding = research_c.model_binding(role="director")
            worker_binding = research_c.model_binding(role="worker")

        self.assertEqual(director_binding["model_sha256"], director)
        self.assertEqual(worker_binding["model_sha256"], worker)
        self.assertEqual(worker_binding["role"], "worker")

    def test_server_bundle_binds_implementation_libraries_not_only_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder) / "llama-server.exe"
            implementation = Path(folder) / "llama-server-impl.dll"
            common = Path(folder) / "llama-common.dll"
            launcher.write_bytes(b"launcher")
            implementation.write_bytes(b"implementation-one")
            common.write_bytes(b"common")

            first = research_c.server_bundle_digest(str(launcher))
            launcher_only = hashlib.sha256(b"launcher").hexdigest()

            implementation.write_bytes(b"implementation-two")
            second = research_c.server_bundle_digest(str(launcher))

        self.assertEqual(len(first), 64)
        self.assertNotEqual(first, launcher_only)
        self.assertNotEqual(first, second)

    def test_server_bundle_includes_mtmd_and_does_not_trust_file_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder) / "llama-server.exe"
            implementation = Path(folder) / "llama-server-impl.dll"
            mtmd = Path(folder) / "mtmd.dll"
            launcher.write_bytes(b"launcher")
            implementation.write_bytes(b"implementation")
            mtmd.write_bytes(b"mtmd-one")

            first = research_c.server_bundle_digest(str(launcher))
            original = mtmd.stat()
            mtmd.write_bytes(b"mtmd-two")
            os.utime(
                mtmd,
                ns=(original.st_atime_ns, original.st_mtime_ns),
            )
            second = research_c.server_bundle_digest(str(launcher))

        self.assertEqual(len(first), 64)
        self.assertNotEqual(first, second)

    def test_record_retains_server_bundle_digest(self):
        bundle = "c" * 64
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "top2"}
        ):
            path = os.path.join(folder, "research.jsonl")
            research_c.record(
                "test",
                "binding",
                artifact_digest=research_c.digest("artifact"),
                prompt_sha256=research_c.digest("prompt"),
                sampler={"temperature": 0.0},
                measurements={},
                outcomes={},
                binding={
                    "role": "director",
                    "model_sha256": "b" * 64,
                    "server_bundle_sha256": bundle,
                },
                path=path,
            )
            event = json.loads(Path(path).read_text(encoding="utf-8"))

        self.assertEqual(event["binding"]["server_bundle_sha256"], bundle)


class ResearchStatisticsTests(unittest.TestCase):
    def test_corrected_voice_grading_preserves_condition_direction(self):
        # Compact, sanitized fixture for the frozen 8-pair grading. The
        # release package intentionally excludes the raw handoff evidence.
        pairs = [
            {
                "grounded_positive": index == 0,
                "ungrounded_positive": True,
            }
            for index in range(8)
        ]
        grounded = sum(item["grounded_positive"] for item in pairs)
        ungrounded = sum(item["ungrounded_positive"] for item in pairs)
        grounded_only = sum(
            item["grounded_positive"] and not item["ungrounded_positive"]
            for item in pairs
        )
        ungrounded_only = sum(
            item["ungrounded_positive"] and not item["grounded_positive"]
            for item in pairs
        )

        self.assertEqual((grounded, ungrounded), (1, 8))
        self.assertEqual((grounded_only, ungrounded_only), (0, 7))
        self.assertEqual(
            researchc_report.exact_mcnemar(
                grounded_only, ungrounded_only
            ),
            0.015625,
        )

    def test_exact_mcnemar_uses_only_discordant_pairs(self):
        self.assertEqual(researchc_report.exact_mcnemar(0, 0), 1.0)
        self.assertAlmostEqual(
            researchc_report.exact_mcnemar(8, 0), 0.0078125
        )
        self.assertAlmostEqual(
            researchc_report.exact_mcnemar(7, 0), 0.015625
        )

    def test_sprt_stops_only_after_crossing_a_declared_boundary(self):
        self.assertEqual(
            researchc_report.sprt_decision(1, 1)["decision"],
            "continue",
        )
        self.assertEqual(
            researchc_report.sprt_decision(8, 8)["decision"],
            "accept_p1",
        )
        self.assertEqual(
            researchc_report.sprt_decision(0, 4)["decision"],
            "accept_p0",
        )

    def test_threshold_table_never_hides_false_refusals(self):
        examples = [
            {
                "measurements": {"mean_surprisal": 0.1},
                "would_pass": True,
                "downstream_seconds": 5,
            },
            {
                "measurements": {"mean_surprisal": 0.7},
                "would_pass": True,
                "downstream_seconds": 8,
            },
            {
                "measurements": {"mean_surprisal": 0.9},
                "would_pass": False,
                "downstream_seconds": 9,
            },
        ]
        row = researchc_report.threshold_rows(
            examples, "mean_surprisal", [0.5]
        )[0]

        self.assertEqual(row["rejected"], 2)
        self.assertEqual(row["false_refusals"], 1)
        self.assertEqual(row["bad_candidates_rejected"], 1)
        self.assertEqual(row["downstream_seconds_avoided"], 17)

    def test_gzip_screen_is_explicitly_length_controlled(self):
        difference = researchc_report.equal_length_gzip_difference(
            "abc " * 100,
            "every line has a different concrete detail " * 20,
        )
        self.assertIsInstance(difference, int)

    def test_release_threshold_data_requires_full_binding(self):
        unbound = [{"prompt_sha256": "", "sampler": {}, "binding": {}}]
        bound = [{
            "prompt_sha256": "a" * 64,
            "sampler": {"temperature": 0.0},
            "binding": {
                "model_sha256": "b" * 64,
                "server_revision": "revision",
            },
        }]

        self.assertTrue(researchc_report.binding_problems(unbound))
        self.assertEqual(researchc_report.binding_problems(bound), [])

    def test_rate_distortion_frontier_uses_the_measured_query_mix(self):
        queries = [
            {"kind": "aggregate", "target": "assistant/core", "weight": 1},
            {"kind": "existence", "target": "assistant/core/a.py", "weight": 3},
        ]
        codes = [
            {
                "name": "shape",
                "tokens": 20,
                "supports": [
                    {"kind": "aggregate", "target": "assistant/core"},
                ],
            },
            {
                "name": "wasteful-shape",
                "tokens": 40,
                "supports": [
                    {"kind": "aggregate", "target": "assistant/core"},
                ],
            },
            {
                "name": "list",
                "tokens": 50,
                "supports": [
                    {"kind": "aggregate", "target": "assistant/core"},
                    {
                        "kind": "existence",
                        "target": "assistant/core/a.py",
                    },
                ],
            },
        ]
        rows = researchc_report.rate_distortion_rows(queries, codes)

        self.assertEqual(rows[0]["distortion"], 0.75)
        self.assertTrue(rows[0]["frontier"])
        self.assertFalse(rows[1]["frontier"])
        self.assertEqual(rows[2]["distortion"], 0.0)
        self.assertTrue(rows[2]["frontier"])


class AudioRecoveryTests(unittest.TestCase):
    def test_capture_preserves_primary_error_when_cleanup_raises_s_false(self):
        source = audio_source.AudioSource()
        source._np = mock.Mock()
        source._np.asarray.side_effect = RuntimeError("endpoint invalidated")

        recorder = mock.Mock()
        recorder.record.return_value = object()
        context = mock.Mock()
        context.__enter__ = mock.Mock(return_value=recorder)
        context.__exit__ = mock.Mock(
            side_effect=RuntimeError("S_FALSE 0x100000001")
        )
        microphone = mock.Mock()
        microphone.recorder.return_value = context

        with self.assertRaisesRegex(RuntimeError, "endpoint invalidated"):
            source._record_from(microphone)

        self.assertIn("S_FALSE", source.last_cleanup_exception)

    def test_capture_reenumerates_default_endpoint_after_failure(self):
        source = audio_source.AudioSource()
        first = mock.Mock(name="first")
        first.name = "old output"
        second = mock.Mock(name="second")
        second.name = "new output"
        calls = []

        def record(device):
            calls.append(device)
            if len(calls) == 1:
                raise RuntimeError("device invalidated")
            source._stop.set()

        source._record_from = record
        backend = mock.Mock()
        with mock.patch.object(
            source, "_loopback_device", return_value=second
        ) as enumerate_again, mock.patch.object(
            audio_source, "RECONNECT_BACKOFF_SECONDS", (0.0,)
        ):
            source._capture_loop(backend, first)

        enumerate_again.assert_called_once_with(backend)
        self.assertEqual(calls, [first, second])
        self.assertEqual(source.device_name, "new output")

    def test_output_failure_retries_same_track_and_frame(self):
        player = local_player.LocalPlayer()
        finished = threading.Event()
        finished.set()
        natural = threading.Event()
        player._stream = object()
        player._name = "track"
        player._path = "track.wav"
        player._frames_played = 4321
        player._generation = 3
        player._transport_epoch = 7

        with mock.patch.object(player, "_recover_output") as recover, \
                mock.patch.object(player, "_notify_track_change"):
            player._advance_after_finish(
                3, finished, natural, player._stream, 7
            )

        recover.assert_called_once_with("track", "track.wav", 4321, 7)

    def test_recovery_reopens_at_saved_frame(self):
        player = local_player.LocalPlayer()
        player._transport_epoch = 4
        with mock.patch.object(
            player, "_play_locked", return_value=True
        ) as play, mock.patch.object(player, "_notify_track_change"):
            player._recover_output("track", "track.wav", 9876, 4)

        play.assert_called_once_with(
            "track",
            "track.wav",
            start_frame=9876,
            recovering=True,
        )

    def test_manual_transport_change_cancels_old_recovery(self):
        player = local_player.LocalPlayer()
        player._transport_epoch = 9
        with mock.patch.object(player, "_play_locked") as play:
            player._recover_output("track", "track.wav", 100, 8)
        play.assert_not_called()


if __name__ == "__main__":
    unittest.main()
