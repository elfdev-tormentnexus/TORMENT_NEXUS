"""Regression checks for the hazard-only two-model Super Dev boundary."""

import os
import tempfile
import unittest
from unittest import mock

from commands import command_handlers
from core import config, dev_auth
from editing import edit_engine, super_dev_engine


class SuperDevAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = dev_auth.SUPER_PASSCODE_FILE
        self.old_iterations = dev_auth.PBKDF2_ITERATIONS
        dev_auth.SUPER_PASSCODE_FILE = os.path.join(self.temp.name, ".super_key")
        dev_auth.PBKDF2_ITERATIONS = 100_000
        dev_auth.reset_attempt_state_for_tests()

    def tearDown(self):
        dev_auth.SUPER_PASSCODE_FILE = self.old_path
        dev_auth.PBKDF2_ITERATIONS = self.old_iterations
        dev_auth.reset_attempt_state_for_tests()
        self.temp.cleanup()

    def test_super_key_is_a_separate_salted_local_verifier(self):
        secret = "246813579"
        dev_auth.enroll_super(secret, secret)

        with open(dev_auth.SUPER_PASSCODE_FILE, encoding="utf-8") as source:
            saved = source.read()

        self.assertNotIn(secret, saved)
        self.assertTrue(dev_auth.verify_super(secret))
        self.assertFalse(dev_auth.verify_super("975318642"))


class SuperDevWorkerBoundaryTests(unittest.TestCase):
    def test_worker_must_be_local_and_authenticated(self):
        with mock.patch.object(
            super_dev_engine, "SUPER_DEV_WORKER_URL", "https://example.com:8093"
        ), mock.patch.object(super_dev_engine, "SUPER_DEV_WORKER_HEADERS", {"Authorization": "Bearer x"}):
            ready, message = super_dev_engine.worker_status()

        self.assertFalse(ready)
        self.assertIn("loopback", message)

    def test_super_session_refuses_wrong_model_profile_before_any_network_call(self):
        with mock.patch.object(
            super_dev_engine, "MODEL_ROLE", config.MODEL_ROLE_DIRECTOR
        ), mock.patch.object(super_dev_engine, "worker_status") as worker:
            applied, message = super_dev_engine.run_session()

        self.assertFalse(applied)
        self.assertIn("dedicated super-dev launcher", message)
        worker.assert_not_called()


class SuperDevCommandTests(unittest.TestCase):
    def setUp(self):
        self.old_mode = command_handlers.SUPER_DEV_MODE
        self.old_expires = command_handlers.SUPER_DEV_MODE_EXPIRES_AT
        command_handlers.SUPER_DEV_MODE = False
        command_handlers.SUPER_DEV_MODE_EXPIRES_AT = 0.0

    def tearDown(self):
        command_handlers.SUPER_DEV_MODE = self.old_mode
        command_handlers.SUPER_DEV_MODE_EXPIRES_AT = self.old_expires

    def test_unlock_runs_one_session_and_marks_only_a_verified_patch_for_reload(self):
        with mock.patch.object(command_handlers, "is_experimental_mode", return_value=True), \
             mock.patch.object(command_handlers, "MODEL_ROLE", config.MODEL_ROLE_SUPER_DEV), \
             mock.patch.object(dev_auth, "unlock_super_interactive", return_value=(True, "key accepted")), \
             mock.patch.object(super_dev_engine, "run_session", return_value=(True, "verified")) as session, \
             mock.patch.object(edit_engine, "mark_restart_pending") as restart:
            reply = command_handlers.handle_super_dev_mode("super dev mode")

        session.assert_called_once_with()
        restart.assert_called_once_with()
        self.assertIn("verified", reply)
        self.assertTrue(command_handlers.SUPER_DEV_MODE)

    def test_inline_super_key_is_refused(self):
        reply = command_handlers.handle_super_dev_mode("super dev mode 246813579")
        self.assertIn("masked numeric prompt", reply)


class SuperDevSessionLoopTests(unittest.TestCase):
    """The unattended session must end on its own and gate every patch.

    An unattended loop has two failure modes a reader cannot check by
    inspection: it never stops, or it stops gating. Both are held here.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(super_dev_engine, "MODEL_ROLE",
                              config.MODEL_ROLE_SUPER_DEV),
            mock.patch.object(super_dev_engine, "STATE_FILE",
                              os.path.join(self.temp.name, "absent.json")),
            mock.patch.object(super_dev_engine, "worker_status",
                              return_value=(True, "ready")),
            mock.patch.object(super_dev_engine, "_log"),
            mock.patch.object(super_dev_engine.ui, "set_status"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    @staticmethod
    def _candidate(index):
        return {"file": f"file_{index}.py", "change": f"change {index}"}

    def test_session_retains_more_than_one_patch(self):
        rounds = [([self._candidate(i)], None) for i in range(5)]
        with mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               side_effect=rounds), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=lambda s: (True, s["file"])) as attempt:
            applied, report = super_dev_engine.run_session(limit=3)

        self.assertTrue(applied)
        self.assertEqual(attempt.call_count, 3)
        self.assertIn("retained 3 patches", report)
        self.assertIn("file_0.py", report)
        self.assertIn("file_2.py", report)

    def test_session_stops_at_its_limit_even_when_work_remains(self):
        with mock.patch.object(
                super_dev_engine.suggestion_engine, "generate",
                side_effect=lambda **kw: ([self._candidate(mock_counter())], None)), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=lambda s: (True, s["file"])) as attempt:
            applied, report = super_dev_engine.run_session(limit=2)

        self.assertTrue(applied)
        self.assertEqual(attempt.call_count, 2)
        self.assertIn("limit of 2 was reached", report)

    def test_a_rejected_candidate_is_never_retried_so_the_loop_ends(self):
        # The planner keeps proposing the same two things; the gates keep
        # refusing them. Without the attempted-set this runs until the limit.
        same = [self._candidate(1), self._candidate(2)]
        with mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               return_value=(same, None)), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               return_value=(False, "gate refused")) as attempt:
            applied, report = super_dev_engine.run_session(limit=20)

        self.assertFalse(applied)
        self.assertEqual(attempt.call_count, 2)
        self.assertIn("No files changed", report)

    def test_every_patch_is_gated_individually_not_batched(self):
        # _try_patch is the whole gate set. One call per retained patch means
        # the gates ran per patch; a batched implementation would call it once.
        rounds = [([self._candidate(i)], None) for i in range(3)]
        seen = []

        def gate(suggestion):
            seen.append(suggestion["file"])
            return True, suggestion["file"]

        with mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               side_effect=rounds), \
             mock.patch.object(super_dev_engine, "_try_patch", side_effect=gate):
            super_dev_engine.run_session(limit=3)

        self.assertEqual(seen, ["file_0.py", "file_1.py", "file_2.py"])

    def test_planner_failure_keeps_the_patches_already_verified(self):
        rounds = [([self._candidate(0)], None), ([], "planner unreachable")]
        with mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               side_effect=rounds), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=lambda s: (True, s["file"])):
            applied, report = super_dev_engine.run_session(limit=5)

        self.assertTrue(applied)
        self.assertIn("retained 1 patch", report)
        self.assertIn("planner unreachable", report)

    def test_limit_defaults_to_the_configured_ceiling(self):
        with mock.patch.object(super_dev_engine,
                               "SUPER_DEV_SESSION_PATCH_LIMIT", 2), \
             mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               side_effect=lambda **kw: ([self._candidate(mock_counter())], None)), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=lambda s: (True, s["file"])) as attempt:
            super_dev_engine.run_session()

        self.assertEqual(attempt.call_count, 2)


_counter = {"n": 0}


def mock_counter():
    _counter["n"] += 1
    return _counter["n"]


if __name__ == "__main__":
    unittest.main()
