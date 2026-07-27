"""Finite, restart-safe state for an earned observed self-heal bonus.

This module is part of the trusted edit orchestration, not an autonomous edit
target. It records only a short-lived, explicit developer-authorized credit:
three clean observed edits may earn one extra guarded edit after a restart and
fixed validation. It never stores credentials, chat, or model output.
"""

import json
import os
import subprocess
import sys
import time

from core import file_utils
from core import health_check
from editing import edit_guard


STATE_FILE = os.path.join(edit_guard.PROJECT_ROOT, "logs", "self_heal_state.json")
PHASE_VALIDATE_BATCH = "validate_batch"
PHASE_VALIDATE_BONUS = "validate_bonus"
VALIDATION_TIMEOUT_SECONDS = 120
REWARD_WINDOW_SECONDS = 10 * 60


def _write(state):
    file_utils.save_json(STATE_FILE, state)


def load():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as source:
            state = json.load(source)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, TypeError):
        # A damaged reward marker must never grant autonomous work.
        clear()
        return None

    if not isinstance(state, dict) or state.get("phase") not in (
        PHASE_VALIDATE_BATCH,
        PHASE_VALIDATE_BONUS,
    ):
        clear()
        return None

    if not isinstance(state.get("expires_at"), (int, float)) or \
            time.time() >= state["expires_at"]:
        clear()
        return None

    records = state.get("records")
    if not isinstance(records, list) or not records:
        clear()
        return None

    return state


def begin_batch_reward(records):
    """Record the one possible bonus earned by a complete serial batch."""
    _write({
        "phase": PHASE_VALIDATE_BATCH,
        "records": records,
        "expires_at": time.time() + REWARD_WINDOW_SECONDS,
    })


def begin_bonus_validation(record):
    """Replace the batch marker with the single earned edit to validate."""
    _write({
        "phase": PHASE_VALIDATE_BONUS,
        "records": [record],
        "expires_at": time.time() + REWARD_WINDOW_SECONDS,
    })


def clear():
    try:
        os.remove(STATE_FILE)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def rollback_records(records):
    """Restore all recorded backups in reverse edit order. Returns errors."""
    errors = []

    for record in reversed(records):
        backup = record.get("backup") if isinstance(record, dict) else None
        if not backup:
            errors.append("missing backup record")
            continue

        try:
            edit_guard.restore(os.path.basename(backup))
        except Exception as error:
            errors.append(str(error))

    return errors


def validate_restart():
    """Run the fixed, trusted restart validation used for an earned credit."""
    report = health_check.report()
    if "Overall: healthy" not in report:
        return False, "Health check did not report healthy.\n\n" + report

    try:
        result = subprocess.run(
            [sys.executable,
             os.path.join(edit_guard.PROJECT_ROOT, "run_regressions.py")],
            cwd=edit_guard.PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=VALIDATION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, "Regression validation exceeded two minutes."
    except Exception as error:
        return False, f"Could not run regression validation: {error}"

    if result.returncode:
        output = (result.stdout + "\n" + result.stderr).strip()
        tail = "\n".join(output.splitlines()[-16:])
        return False, "Regression validation failed.\n\n" + tail

    return True, "Health check and regression validation passed."
