"""Offline tests for the frozen 98-call response-coherence collector."""

import importlib.util
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "coherence_probe_under_test",
    HERE / "coherence_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def probability_payload(q, answer=None):
    if answer is None:
        answer = "Yes" if q >= 0.5 else "No"
    entry = {
        "token": answer,
        "prob": q if answer == "Yes" else 1.0 - q,
        "top_probs": [
            {"token": "Yes", "prob": q, "id": 1},
            {"token": "No", "prob": 1.0 - q, "id": 2},
        ],
    }
    return answer, {"content": [entry]}


def q_for_task(task):
    values = {
        "a": 0.95,
        "b_given_a_yes": 0.20,
        "b_given_a_no": 0.10,
        "b": 0.05,
        "a_given_b_yes": 0.80,
        "a_given_b_no": 0.96,
    }
    return values[task["measurement"]]


def frozen_fixture():
    prompt_artifact = {
        "schema": probe.SCHEMA,
        "system_prompt": "frozen system",
        "line_endings": "test",
    }
    targets = {"schema": probe.SCHEMA, "rows": list(probe.TARGETS)}
    targets["sha256"] = probe._target_content_digest(targets["rows"])
    tasks = probe.task_plan()
    for task in tasks:
        task["messages_sha256"] = probe.messages_digest(
            probe.construct_messages(prompt_artifact["system_prompt"], task)
        )
    core = {
        "schema": probe.SCHEMA,
        "experiment": probe.EXPERIMENT,
        "call_count": probe.CALL_COUNT,
        "primary_call_count": probe.PRIMARY_CALL_COUNT,
        "prompt_artifact_sha256": probe.sha256_value(prompt_artifact),
        "system_prompt_sha256": probe.sha256_text(
            prompt_artifact["system_prompt"]
        ),
        "target_artifact_sha256": probe.sha256_value(targets),
        "target_snapshot_sha256": targets["sha256"],
        "task_plan_sha256": probe.sha256_value(tasks),
        "sampler": probe.SAMPLER,
        # Matches probability_payload's ids, so the whole offline validation
        # path checks tokenizer identity and not only rendered text.
        "binary_token_ids": {"Yes": 1, "No": 2},
        "tasks": tasks,
    }
    spec = dict(core)
    spec["spec_sha256"] = probe.sha256_value(core)
    rows, dispatches = [], []
    for task in tasks:
        q = q_for_task(task)
        answer, logprobs = probability_payload(q)
        parsed = probe.parse_binary_response(answer, logprobs)
        row = {
            **probe._task_expected_fields(task, spec),
            "status": "ok",
            "answer": answer,
            "logprobs": logprobs,
            "target_snapshot_before_sha256": targets["sha256"],
            "target_snapshot_after_sha256": targets["sha256"],
            "target_drift": False,
            **parsed,
        }
        rows.append(row)
        dispatches.append({
            "trial_id": task["trial_id"],
            "execution_order": task["execution_order"],
            "spec_sha256": spec["spec_sha256"],
            "messages_sha256": task["messages_sha256"],
            "target_snapshot_sha256": targets["sha256"],
        })
    return prompt_artifact, targets, spec, rows, dispatches


class CoherenceProbeTests(unittest.TestCase):
    def test_recursive_binding_sanitizer_keeps_evidence_not_local_identity(self):
        local_user = Path.home().name

        class FakeRate:
            @staticmethod
            def runtime_bindings():
                return {
                    "server_url": (
                        "http://api-user:top-secret@127.0.0.1:8080/v1"
                        "?api_key=sk-private-test-key"
                    ),
                    "model_path": (
                        rf"C:\Users\{local_user}\models\director.gguf"
                    ),
                    "model_alias": (
                        rf"C:\Users\{local_user}\models\director.gguf"
                    ),
                    "model_bytes": 123,
                    "model_sha256": "a" * 64,
                    "server_bundle_sha256": "b" * 64,
                    "api_key": "sk-private-test-key",
                    "live_server": {
                        "sha256": "c" * 64,
                        "props": {
                            "model_path": (
                                rf"C:\Users\{local_user}\models\director.gguf"
                            ),
                        },
                        "listener": {
                            "pid": 123,
                            "executable_path": (
                                rf"C:\Users\{local_user}\bin\llama-server.exe"
                            ),
                            "command_line": (
                                "RAW-COMMAND-MARKER --model "
                                rf"C:\Users\{local_user}\models\director.gguf"
                            ),
                            "listener_address": "127.0.0.1",
                            "port": 8080,
                        },
                    },
                    "hazard_runtime": {
                        "independently_verified": True,
                        "assistant": {
                            "pid": 456,
                            "executable_path": (
                                rf"C:\Users\{local_user}\Python\python.exe"
                            ),
                            "command_line": "RAW-ASSISTANT-COMMAND-MARKER",
                        },
                        "agent_interface_8099_listener": None,
                    },
                }

        bound = probe._runtime_bindings(FakeRate)
        encoded = probe.canonical_json(bound)
        self.assertNotIn(r"C:\Users", encoded)
        self.assertNotIn(local_user.casefold(), encoded.casefold())
        self.assertNotIn("sk-private-test-key", encoded)
        self.assertNotIn("top-secret", encoded)
        self.assertNotIn("RAW-COMMAND-MARKER", encoded)
        self.assertNotIn("RAW-ASSISTANT-COMMAND-MARKER", encoded)
        self.assertNotIn('"command_line":', encoded)
        self.assertEqual(
            bound["live_server"]["props"]["model_basename"],
            "director.gguf",
        )
        self.assertEqual(
            bound["live_server"]["listener"]["executable_basename"],
            "llama-server.exe",
        )
        self.assertEqual(
            len(
                bound["live_server"]["listener"][
                    "command_line_sha256"
                ]
            ),
            64,
        )
        self.assertEqual(bound["server_url"], "http://127.0.0.1:8080/v1")
        self.assertEqual(probe._privacy_violations(bound), [])

    def test_prepare_never_reads_private_prompt_and_freezes_only_public_context(
        self,
    ):
        local_user = Path.home().name
        private_markers = (
            "PRIVATE-MEMORY-SENTINEL",
            "PRIVATE-CONVERSATION-SENTINEL",
            "RAW-COMMAND-SENTINEL",
            "sk-private-test-key",
        )

        class ForbiddenAssistantMain:
            @staticmethod
            def build_system_prompt(*_args, **_kwargs):
                raise AssertionError("private production prompt was read")

        inventory_rows = [
            {
                "path": target["path"],
                "lines": target["lines"],
                "age_days": float(index),
            }
            for index, target in enumerate(probe.TARGETS)
        ]

        class FakeSourceAwareness:
            RECENT_FILE_COUNT = 12

            @staticmethod
            def inventory():
                return list(inventory_rows)

            @staticmethod
            def source_facts(path):
                target = next(
                    item for item in probe.TARGETS if item["path"] == path
                )
                return {
                    "exists": True,
                    "path": path,
                    "lines": target["lines"],
                    "bytes": target["lines"] * 10,
                    "sha256": (
                        f"{int(target['id'][1:]):064x}"[-64:]
                    ),
                }

        class FakeResponse:
            def __init__(self, token_id):
                self._token_id = token_id

            def raise_for_status(self):
                return None

            def json(self):
                return {"tokens": [self._token_id]}

        class FakeRequests:
            @staticmethod
            def post(_url, **kwargs):
                content = kwargs["json"]["content"]
                return FakeResponse(1 if content == "Yes" else 2)

        class FakeRate:
            ROOT = probe.ROOT
            SERVER_URL = "http://127.0.0.1:8080"
            MODEL_PATH = str(probe.HERE / "coherence_probe.py")
            MODEL_REQUEST_HEADERS = {
                "Authorization": "Bearer sk-private-test-key",
            }
            assistant_main = ForbiddenAssistantMain
            source_awareness = FakeSourceAwareness
            requests = FakeRequests

            @staticmethod
            def git(*arguments):
                if arguments[:1] != ("ls-files",):
                    raise AssertionError(f"unexpected git call {arguments}")
                return "\0".join(row["path"] for row in inventory_rows)

            @staticmethod
            def repo_binding(_output_relative):
                return {
                    "head": "d" * 40,
                    "branch": f"private/{local_user}/research",
                    "status_sha256": "e" * 64,
                    "tracked_diff_sha256": "f" * 64,
                    "staged_diff_sha256": "0" * 64,
                    "untracked_content_sha256": "1" * 64,
                    "production_manifest_sha256": "2" * 64,
                    "dirty_digest": "3" * 64,
                    "workspace_path": (
                        rf"C:\Users\{local_user}\Documents\AI_Project"
                    ),
                }

            @staticmethod
            def runtime_bindings():
                return {
                    "server_url": "http://127.0.0.1:8080",
                    "model_path": (
                        rf"C:\Users\{local_user}\models\director.gguf"
                    ),
                    "model_alias": (
                        rf"C:\Users\{local_user}\models\director.gguf"
                    ),
                    "model_sha256": "4" * 64,
                    "server_bundle_sha256": "5" * 64,
                    "live_server": {
                        "sha256": "6" * 64,
                        "listener": {
                            "pid": 123,
                            "command_line": (
                                "RAW-COMMAND-SENTINEL "
                                rf"C:\Users\{local_user}\bin\server.exe"
                            ),
                            "executable_path": (
                                rf"C:\Users\{local_user}\bin\server.exe"
                            ),
                        },
                    },
                    "hazard_runtime": {
                        "independently_verified": True,
                        "assistant": {"pid": 456},
                    },
                    "api_key": "sk-private-test-key",
                }

        with mock.patch.object(probe, "_live_helpers", return_value=FakeRate):
            prepared = probe.prepare(
                probe.ROOT / "handoffs" / "privacy-test-not-written"
            )

        frozen = {
            "coherence_prompt.json": prepared["prompt_artifact"],
            "coherence_targets.json": prepared["target_artifact"],
            "coherence_spec.json": prepared["spec"],
        }
        first_task = prepared["spec"]["tasks"][0]
        answer, logprobs = probability_payload(0.75)
        parsed = probe.parse_binary_response(answer, logprobs)
        frozen["coherence_rows.jsonl"] = [{
            **probe._task_expected_fields(first_task, prepared["spec"]),
            "bindings": prepared["spec"]["bindings"],
            "live_server_identity_sha256": prepared["spec"][
                "bindings"
            ]["live_server"]["sha256"],
            "repository_state_before": prepared["spec"][
                "repository_state"
            ],
            "target_snapshot_before_sha256": prepared["spec"][
                "target_snapshot_sha256"
            ],
            "status": "ok",
            "answer": answer,
            "logprobs": logprobs,
            **parsed,
            "target_snapshot_after_sha256": prepared["spec"][
                "target_snapshot_sha256"
            ],
            "repository_state_after": prepared["spec"][
                "repository_state"
            ],
            "target_drift": False,
            "repository_drift": False,
        }]
        frozen["coherence_dispatch.jsonl"] = [{
            "trial_id": first_task["trial_id"],
            "execution_order": first_task["execution_order"],
            "spec_sha256": prepared["spec"]["spec_sha256"],
            "messages_sha256": first_task["messages_sha256"],
            "repository_dirty_digest": prepared["spec"][
                "repository_state"
            ]["dirty_digest"],
            "target_snapshot_sha256": prepared["spec"][
                "target_snapshot_sha256"
            ],
            "live_server_identity_sha256": prepared["spec"][
                "bindings"
            ]["live_server"]["sha256"],
        }]
        frozen["coherence_summary.json"] = probe.analyze(
            frozen["coherence_rows.jsonl"],
            prepared["spec"],
        )
        encoded = probe.canonical_json(frozen)
        self.assertEqual(
            prepared["spec"]["prompt_privacy"][
                "production_build_system_prompt_calls"
            ],
            0,
        )
        self.assertEqual(
            prepared["prompt_artifact"]["prompt_class"],
            "privacy_safe_public_source_research_prompt",
        )
        self.assertNotIn(str(probe.ROOT), encoded)
        self.assertNotIn(local_user.casefold(), encoded.casefold())
        for marker in private_markers:
            self.assertNotIn(marker, encoded)
        self.assertNotIn('"command_line":', encoded)
        for artifact in frozen.values():
            self.assertEqual(probe._privacy_violations(artifact), [])

    def test_untracked_files_never_reach_the_public_source_context(self):
        """An untracked sentinel must not move any figure in the prompt."""
        tracked_rows = [
            {"path": target["path"], "lines": target["lines"],
             "age_days": float(index + 5)}
            for index, target in enumerate(probe.TARGETS)
        ]
        # Freshest file, huge line count, and the only member of its own
        # directory -- so a leak would show up in recency, in the totals, and
        # as a brand-new directory aggregate, not just in one of the three.
        sentinel = {
            "path": "scratch_private_notes/PRIVATE-UNTRACKED-SENTINEL.py",
            "lines": 123456,
            "age_days": 0.0,
        }

        class FakeSourceAwareness:
            RECENT_FILE_COUNT = 12

            @staticmethod
            def inventory():
                return [sentinel, *tracked_rows]

        class FakeRate:
            source_awareness = FakeSourceAwareness

            @staticmethod
            def git(*arguments):
                assert arguments[0] == "ls-files"
                return "\0".join(row["path"] for row in tracked_rows)

        context, provenance = probe._public_source_context(FakeRate)

        self.assertNotIn("PRIVATE-UNTRACKED-SENTINEL", context)
        self.assertNotIn("scratch_private_notes", context)
        self.assertNotIn("123456", context)
        self.assertNotIn("123,456", context)

        expected_files = len(tracked_rows)
        expected_lines = sum(row["lines"] for row in tracked_rows)
        self.assertIn(f"{expected_files} manifest-counted source", context)
        self.assertIn(f"{expected_lines} text lines", context)

        recent = context.split("authorship): ", 1)[1]
        self.assertNotIn("PRIVATE-UNTRACKED-SENTINEL", recent)
        self.assertIn(probe.TARGETS[0]["path"], recent)

        self.assertEqual(provenance["public_file_count"], expected_files)
        self.assertEqual(provenance["excluded_untracked_count"], 1)
        self.assertEqual(
            provenance["manifest_file_count"],
            expected_files + 1,
        )
        self.assertEqual(provenance["filter"], "git_tracked_allowlist")

    def test_untracked_predeclared_target_is_refused(self):
        rows = [
            {"path": target["path"], "lines": target["lines"], "age_days": 1.0}
            for target in probe.TARGETS
        ]

        class FakeSourceAwareness:
            RECENT_FILE_COUNT = 12

            @staticmethod
            def inventory():
                return list(rows)

        class FakeRate:
            source_awareness = FakeSourceAwareness

            @staticmethod
            def git(*_arguments):
                # Every target but the first is tracked.
                return "\0".join(row["path"] for row in rows[1:])

        with self.assertRaises(probe.ProbeError) as caught:
            probe._public_source_context(FakeRate)
        self.assertIn("not Git-tracked", str(caught.exception))

    def test_binary_parser_rejects_a_restrung_token_id(self):
        """Rendered text is not identity; the frozen ids must match."""
        frozen = {"Yes": 9454, "No": 2753}
        answer, logprobs = probability_payload(0.75)
        logprobs["content"][0]["top_probs"] = [
            {"token": "Yes", "prob": 0.75, "id": 9454},
            {"token": "No", "prob": 0.25, "id": 2753},
        ]
        parsed = probe.parse_binary_response(answer, logprobs, frozen)
        self.assertAlmostEqual(parsed["q_yes"], 0.75)

        restrung = json.loads(json.dumps(logprobs))
        restrung["content"][0]["top_probs"][1]["id"] = 4242
        with self.assertRaises(probe.ProbeError) as caught:
            probe.parse_binary_response(answer, restrung, frozen)
        self.assertIn("not the frozen id", str(caught.exception))

        missing = json.loads(json.dumps(logprobs))
        missing["content"][0]["top_probs"][0].pop("id")
        with self.assertRaises(probe.ProbeError) as caught:
            probe.parse_binary_response(answer, missing, frozen)
        self.assertIn("tokenizer id", str(caught.exception))

    @staticmethod
    def _hashing_rate(hashed, explode=False):
        """A stand-in shaped like the rate module, which is what run() patches."""
        rate = SimpleNamespace(
            MODEL_PATH=str(probe.HERE / "coherence_probe.py"),
        )

        def sha256_file(path):
            hashed.append(str(path))
            return "a" * 64

        def runtime_bindings():
            if explode:
                raise RuntimeError("port 8099 opened mid-run")
            return {
                "model_sha256": rate.sha256_file(rate.MODEL_PATH),
                "server_executable_sha256": rate.sha256_file(
                    "llama-server.exe"
                ),
                "live_server": {"sha256": "b" * 64},
                "hazard_runtime": {"assistant": {"pid": 1}},
            }

        rate.sha256_file = sha256_file
        rate.runtime_bindings = runtime_bindings
        return rate

    def test_carried_model_digest_runs_the_same_audited_binding_path(self):
        """The recheck substitutes one hash, never a rebuilt binding dict."""
        hashed = []
        rate = self._hashing_rate(hashed)

        full = probe._runtime_bindings(rate)
        self.assertEqual(full["model_sha256"], "a" * 64)
        self.assertEqual(len(hashed), 2)

        hashed.clear()
        carried = probe._runtime_bindings(rate, carry_model_sha256="c" * 64)
        self.assertEqual(carried["model_sha256"], "c" * 64)
        # The server binary is still hashed for real; only the model is not.
        self.assertEqual(hashed, ["llama-server.exe"])
        # Everything else must survive the substitution untouched.
        self.assertEqual(
            carried["server_executable_sha256"],
            full["server_executable_sha256"],
        )
        self.assertEqual(carried["live_server"], full["live_server"])

        with self.assertRaises(probe.ProbeError):
            probe._runtime_bindings(rate, carry_model_sha256="short")

    def test_carried_digest_is_restored_when_the_binding_raises(self):
        hashed = []
        rate = self._hashing_rate(hashed, explode=True)
        before = rate.sha256_file

        with self.assertRaises(RuntimeError):
            probe._runtime_bindings(rate, carry_model_sha256="c" * 64)

        # A live patch that survives its own failure would silently freeze the
        # carried digest into every later full recheck.
        self.assertIs(rate.sha256_file, before)
        self.assertEqual(rate.sha256_file(rate.MODEL_PATH), "a" * 64)

    def test_persistence_barrier_rejects_unsanitized_private_fields(self):
        local_user = Path.home().name
        unsafe = {
            "command_line": (
                "server --model "
                rf"C:\Users\{local_user}\models\private.gguf"
            ),
            "api_key": "sk-private-test-key",
            "memory": "PRIVATE-MEMORY-SENTINEL",
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "must_not_exist.json"
            with self.assertRaises(probe.ProbeError):
                probe._atomic_json(path, unsafe)
            self.assertFalse(path.exists())

    def test_operator_reported_mode_is_separate_from_verified_topology(self):
        class FakeRate:
            @staticmethod
            def runtime_bindings():
                return {
                    "assistant_mode": {
                        "operator_reported": "hazard",
                        "independently_verified": True,
                    },
                    "hazard_runtime": {
                        "independently_verified": True,
                        "assistant": {"pid": 123},
                    },
                    "live_server": {"sha256": "a" * 64},
                }

        bound = probe._runtime_bindings(FakeRate)
        self.assertEqual(bound["assistant_mode"]["value"], "hazard")
        self.assertEqual(
            bound["assistant_mode"]["source"],
            "operator_reported",
        )
        self.assertFalse(bound["assistant_mode"]["independently_verified"])
        self.assertNotIn("hazard_runtime", bound)
        self.assertTrue(
            bound["runtime_topology"]["topology_independently_verified"]
        )
        self.assertFalse(
            bound["runtime_topology"]["ui_mode_independently_verified"]
        )

    def test_target_content_digest_ignores_prompt_annotation_only(self):
        row = {
            **probe.TARGETS[0],
            "bytes": 12,
            "sha256": "b" * 64,
            "named_in_frozen_prompt": True,
        }
        changed_annotation = {
            **row,
            "named_in_frozen_prompt": None,
        }
        changed_source = {**row, "bytes": 13}
        self.assertEqual(
            probe._target_content_digest([row]),
            probe._target_content_digest([changed_annotation]),
        )
        self.assertNotEqual(
            probe._target_content_digest([row]),
            probe._target_content_digest([changed_source]),
        )

    def test_exact_plan_has_six_measurements_per_unit_and_two_replays(self):
        tasks = probe.task_plan()
        self.assertEqual(len(tasks), 98)
        self.assertEqual(len({item["trial_id"] for item in tasks}), 98)
        self.assertEqual([item["execution_order"] for item in tasks], list(
            range(1, 99)
        ))
        primary = [item for item in tasks if not item["sentinel"]]
        replay = [item for item in tasks if item["sentinel"]]
        self.assertEqual(len(primary), 96)
        self.assertEqual(len(replay), 2)
        self.assertEqual(
            {item["measurement"] for item in replay},
            {"a", "b"},
        )
        for target in probe.TARGETS:
            for wording in probe.WORDINGS:
                unit = [
                    item for item in primary
                    if item["target_id"] == target["id"]
                    and item["wording_id"] == wording["id"]
                ]
                self.assertEqual(len(unit), 6)
                self.assertEqual(
                    {item["measurement"] for item in unit},
                    set(probe.MEASUREMENTS),
                )

    def test_frozen_questions_and_conditional_history_are_exact(self):
        target = probe.TARGETS[0]
        wording = probe.WORDINGS[0]
        self.assertEqual(
            probe.render_question(target, wording, "A"),
            "Does the file `assistant/core/chosen_name.py` contain at least "
            "764 text lines? Answer exactly Yes or No.",
        )
        conditional = next(
            item for item in probe._block_tasks(target, wording, "AB")
            if item["measurement"] == "b_given_a_yes"
        )
        self.assertEqual(
            probe.construct_messages("SYSTEM", conditional),
            [
                {"role": "system", "content": "SYSTEM"},
                {
                    "role": "user",
                    "content": (
                        "Does the file `assistant/core/chosen_name.py` contain "
                        "at least 764 text lines? Answer exactly Yes or No."
                    ),
                },
                {"role": "assistant", "content": "Yes"},
                {
                    "role": "user",
                    "content": (
                        "Does the file `assistant/core/chosen_name.py` contain "
                        "at least 1195 text lines? Answer exactly Yes or No."
                    ),
                },
            ],
        )

    def test_target_thresholds_are_exact_multiplicative_brackets(self):
        self.assertEqual(
            {item["area"] for item in probe.TARGETS},
            {
                "assistant/core",
                "assistant/memory",
                "assistant/commands",
                "assistant/ui",
                "assistant/voice",
                "assistant/project",
                "assistant/web",
                "assistant/hardware",
            },
        )
        for target in probe.TARGETS:
            self.assertEqual(target["low"], math.floor(4 * target["lines"] / 5))
            self.assertEqual(
                target["high"],
                math.ceil(5 * target["lines"] / 4),
            )
            self.assertLess(target["low"], target["lines"])
            self.assertGreater(target["high"], target["lines"])

    def test_post_sampling_binary_parser_requires_both_positive_candidates(self):
        answer, payload = probability_payload(0.8)
        parsed = probe.parse_binary_response(answer, payload)
        self.assertAlmostEqual(parsed["q_yes"], 0.8)
        self.assertEqual(parsed["normalized_answer"], "Yes")

        missing = {"content": [{
            "token": "Yes",
            "top_probs": [{"token": "Yes", "prob": 1.0}],
        }]}
        with self.assertRaises(probe.ProbeError):
            probe.parse_binary_response("Yes", missing)

        zero = {"content": [{
            "token": "Yes",
            "top_probs": [
                {"token": "Yes", "prob": 1.0},
                {"token": "No", "prob": 0.0},
            ],
        }]}
        with self.assertRaises(probe.ProbeError):
            probe.parse_binary_response("Yes", zero)
        with self.assertRaises(probe.ProbeError):
            probe.parse_binary_response("yes", payload)

    def test_joint_total_probability_and_marginal_residuals(self):
        values = {
            "a": 0.8,
            "b_given_a_yes": 0.25,
            "b_given_a_no": 0.5,
            "b": 0.3,
            "a_given_b_yes": 0.6,
            "a_given_b_no": 0.9,
        }
        result = probe.response_unit_statistics(values)
        self.assertAlmostEqual(sum(result["ab_joint"].values()), 1.0)
        self.assertAlmostEqual(sum(result["ba_joint"].values()), 1.0)
        self.assertAlmostEqual(result["b_marginal_in_ab"], 0.3)
        self.assertAlmostEqual(result["marginal_selectivity_b"], 0.0)
        self.assertAlmostEqual(result["a_marginal_in_ba"], 0.81)
        self.assertAlmostEqual(result["marginal_selectivity_a"], 0.01)
        expected_qq = (
            result["ab_joint"]["YN"]
            + result["ab_joint"]["NY"]
            - result["ba_joint"]["YN"]
            - result["ba_joint"]["NY"]
        )
        self.assertAlmostEqual(result["qq_residual"], expected_qq)

    def test_bit_price_is_the_same_signed_logodds_coherence_contrast(self):
        for a, b in ((0.8, 0.2), (0.2, 0.8), (0.55, 0.55)):
            values = {
                "a": a,
                "b_given_a_yes": b,
                "b_given_a_no": b,
                "b": b,
                "a_given_b_yes": a,
                "a_given_b_no": a,
            }
            result = probe.response_unit_statistics(values)
            self.assertAlmostEqual(
                result["balanced_mean_bit_price"],
                result["bit_price_logodds_identity"],
            )
            if not math.isclose(
                result["balanced_mean_bit_price"],
                0.0,
                abs_tol=1e-12,
            ):
                self.assertEqual(
                    result["balanced_mean_bit_price"] > 0,
                    result["coherence_delta"] > 0,
                )

    def test_complete_fixture_passes_probability_and_informativeness_gates(self):
        _prompt, _targets, spec, rows, dispatches = frozen_fixture()
        probe.validate_rows_offline(rows, dispatches, spec)
        summary = probe.analyze(rows, spec)
        self.assertEqual(summary["completed_rows"], 98)
        self.assertEqual(summary["completed_units"], 16)
        self.assertEqual(summary["independent_targets_completed"], 8)
        self.assertTrue(summary["gates"]["collection_complete"])
        self.assertTrue(summary["gates"]["sentinel_probability_stable"])
        self.assertTrue(summary["gates"]["informativeness"])
        self.assertTrue(summary["gates"]["paraphrase_generalization"])
        self.assertEqual(
            summary["coherence"]["robust_target_violations"],
            0,
        )
        self.assertEqual(
            summary["recommendation"],
            "bounded_descriptive_result",
        )

    def test_sentinel_drift_voids_probability_analysis(self):
        _prompt, _targets, spec, rows, _dispatches = frozen_fixture()
        replay_index = next(
            index for index, row in enumerate(rows)
            if row["sentinel"] and row["measurement"] == "a"
        )
        task = spec["tasks"][replay_index]
        answer, logprobs = probability_payload(0.90)
        parsed = probe.parse_binary_response(answer, logprobs)
        rows[replay_index].update({
            "answer": answer,
            "logprobs": logprobs,
            **parsed,
        })
        summary = probe.analyze(rows, spec)
        self.assertFalse(summary["gates"]["sentinel_probability_stable"])
        self.assertFalse(summary["gates"]["probability_valid"])
        self.assertEqual(summary["recommendation"], "void_collection")

    def test_analyze_only_loader_never_loads_live_helpers(self):
        prompt, targets, spec, rows, dispatches = frozen_fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "coherence_prompt.json").write_text(
                json.dumps(prompt),
                encoding="utf-8",
            )
            (root / "coherence_targets.json").write_text(
                json.dumps(targets),
                encoding="utf-8",
            )
            (root / "coherence_spec.json").write_text(
                json.dumps(spec),
                encoding="utf-8",
            )
            (root / "coherence_rows.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            (root / "coherence_dispatch.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in dispatches),
                encoding="utf-8",
            )
            with mock.patch.object(
                probe,
                "_live_helpers",
                side_effect=AssertionError("live helper was touched"),
            ):
                loaded = probe.load_frozen_offline(root)
                summary = probe.analyze(loaded["rows"], loaded["spec"])
            self.assertEqual(summary["successful_rows"], 98)

    def test_exact_statistics(self):
        self.assertEqual(probe.exact_sign_test(8, 0), 0.0078125)
        self.assertEqual(
            probe.holm_adjusted_pvalues([0.01, 0.02]),
            [0.02, 0.02],
        )
        interval = probe.wilson_interval(0, 8)
        self.assertEqual(interval[0], 0.0)
        self.assertGreater(interval[1], 0.30)


if __name__ == "__main__":
    unittest.main()
