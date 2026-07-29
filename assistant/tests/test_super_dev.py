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


if __name__ == "__main__":
    unittest.main()
