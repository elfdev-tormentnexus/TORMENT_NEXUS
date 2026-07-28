"""Bounded, transactional repair sessions for the on-demand 14B coder.

This module is deliberately part of ``editing/`` and therefore protected from
every model-driven edit.  It is not a second conversational editor: a session
starts only through the explicit ``full self heal`` developer command, takes
its diagnosis from the fixed health/regression runner, and may make at most
three small repairs.  Every replacement is backed up and durably recorded
*before* it is written.  If a repair does not make the fixed checks green, the
entire session is restored in reverse order.

The model can suggest and generate an exact local patch.  It cannot select a
shell command, loosen the protected-file policy, add sensitive runtime
capability, or keep a partial failed repair.
"""

import json
import os
import time

from core import file_utils
from core.config import MODEL_ROLE, MODEL_ROLE_FULL_MAINTENANCE
from editing import edit_generator
from editing import edit_guard
from editing import patch_engine
from editing import self_heal_state
from editing import suggestion_engine
from ui import ui


STATE_FILE = os.path.join(
    edit_guard.PROJECT_ROOT,
    "logs",
    "maintenance_session_state.json",
)
STATE_VERSION = 1
MAX_SESSION_EDITS = 3
MAX_CHANGED_LINES = 120
MAX_DIAGNOSTIC_DISPLAY_CHARS = 3_000


def _clear_state():
    try:
        os.remove(STATE_FILE)
    except FileNotFoundError:
        return None
    except OSError as error:
        # Keep a marker we cannot remove. A future launch can still attempt
        # recovery rather than pretending the transaction completed.
        return str(error)

    return None


def _read_state():
    """Return ``(state, problem)`` without ever treating a bad marker as safe."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as source:
            state = json.load(source)
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError, TypeError) as error:
        return None, f"could not read the maintenance marker: {error}"

    if not isinstance(state, dict):
        return None, "the maintenance marker is not a valid transaction"

    if state.get("version") != STATE_VERSION or state.get("phase") != "active":
        return None, "the maintenance marker has an unknown format"

    records = state.get("records")
    if not isinstance(records, list) or not records:
        return None, "the maintenance marker has no rollback records"

    if not all(
        isinstance(record, dict)
        and isinstance(record.get("target"), str)
        and isinstance(record.get("backup"), str)
        for record in records
    ):
        return None, "the maintenance marker contains an invalid rollback record"

    return state, None


def _write_state(records):
    """Persist the exact rollback set before any associated file replacement."""
    file_utils.save_json(
        STATE_FILE,
        {
            "version": STATE_VERSION,
            "phase": "active",
            "started_at": time.time(),
            "records": records,
        },
    )


def _rollback(records):
    """Restore a whole transaction, retaining its marker if restoration fails."""
    errors = self_heal_state.rollback_records(records)

    if not errors:
        clear_error = _clear_state()
        if clear_error:
            errors.append(f"could not clear maintenance marker: {clear_error}")

    return errors


def _display_diagnostic(detail):
    detail = str(detail or "").strip()
    return detail[-MAX_DIAGNOSTIC_DISPLAY_CHARS:] or "No diagnostic was returned."


def _rollback_result(records, reason, diagnostic):
    errors = _rollback(records)
    extra = ""

    if errors:
        extra = (
            "\n\nRollback needs attention; the recovery marker was kept:\n"
            + "\n".join(f"  {error}" for error in errors)
        )
    else:
        extra = "\n\nAll edits from this session were restored."

    return {
        "applied": False,
        "message": (
            "FULL SELF-HEAL ROLLED BACK\n" + "=" * 58
            + f"\n\n{reason}\n\n"
            + _display_diagnostic(diagnostic)
            + extra
        ),
    }


def _try_apply(suggestion, records):
    """Try one proposal. Returns ``(status, detail)``.

    ``status`` is ``applied``, ``skip``, or ``rollback``. The latter means a
    backup record has already been persisted and the caller must restore the
    entire session rather than continuing from an uncertain state.
    """
    file_hint = suggestion.get("file", "")
    change = suggestion.get("change", "")

    try:
        target = edit_guard.locate(file_hint)
        original = edit_guard.read(target)
    except edit_guard.GuardError as error:
        return "skip", f"{file_hint}: {error}"

    ui.set_status(f"Generating full-maintenance patch for {target}")
    edit, error = edit_generator.generate_edit(target, original, change)

    if error:
        return "skip", f"{target}: generator declined ({error})"

    new_content, apply_error = patch_engine.apply_edit(
        original,
        edit["find"],
        edit["replace"],
    )

    if apply_error:
        return "skip", f"{target}: {apply_error}"

    syntax_problem = edit_guard.check_syntax(new_content, os.path.basename(target))
    if syntax_problem:
        return "skip", f"{target}: syntax check failed ({syntax_problem})"

    added, removed = patch_engine.diff_stats(original, new_content)
    if added + removed > MAX_CHANGED_LINES:
        return (
            "skip",
            f"{target}: diff is {added + removed} lines; limit is {MAX_CHANGED_LINES}",
        )

    capability_problem = edit_guard.maintenance_change_problem(
        target,
        original,
        new_content,
    )
    if capability_problem:
        return "skip", f"{target}: {capability_problem}"

    # The backup is made first, and then the marker is flushed before writing
    # the new content. A power loss at any point after this marker can only
    # leave the old file or the new file, both recoverable from the backup.
    ui.set_status(f"Preparing transactional backup for {target}")
    try:
        backup_path = edit_guard.backup(target)
    except Exception as error:
        return "skip", f"{target}: could not create backup ({error})"

    record = {
        "target": target,
        "backup": backup_path,
        "summary": f"{target} (+{added} -{removed})",
    }
    records.append(record)

    try:
        _write_state(records)
    except Exception as error:
        records.pop()
        return "skip", f"{target}: could not persist rollback record ({error})"

    ui.set_status(f"Writing transactional repair for {target}")
    try:
        edit_guard.write(target, new_content, backup_path=backup_path)
    except Exception as error:
        return "rollback", f"{target}: write failed after rollback staging ({error})"

    ui.set_status(f"Import-testing transactional repair for {target}")
    import_error = edit_guard.import_check(target)
    if import_error:
        return "rollback", f"{target}: import check failed ({import_error})"

    return "applied", record["summary"]


def recover_incomplete_session():
    """Restore an interrupted full-maintenance transaction at application start."""
    if not os.path.exists(STATE_FILE):
        return None

    state, problem = _read_state()
    if problem:
        return (
            "FULL MAINTENANCE RECOVERY NEEDS ATTENTION\n" + "=" * 58
            + f"\n\n{problem}. The marker was left in place at {STATE_FILE}."
        )

    if not state:
        return None

    errors = _rollback(state["records"])
    if errors:
        return (
            "FULL MAINTENANCE RECOVERY NEEDS ATTENTION\n" + "=" * 58
            + "\n\nAn interrupted repair could not be fully restored:\n"
            + "\n".join(f"  {error}" for error in errors)
            + f"\n\nThe marker was left in place at {STATE_FILE}."
        )

    return (
        "FULL MAINTENANCE RECOVERED\n" + "=" * 58
        + "\n\nAn interrupted repair session was rolled back before startup."
    )


def run_session():
    """Run at most three test-driven repairs, committing only a green result."""
    if MODEL_ROLE != MODEL_ROLE_FULL_MAINTENANCE:
        return {
            "applied": False,
            "message": (
                "FULL SELF-HEAL REFUSED\n" + "=" * 58
                + "\n\nA full self-heal may run only in the dedicated "
                "full-maintenance coder profile."
            ),
        }

    if os.path.exists(STATE_FILE):
        state, problem = _read_state()
        if state:
            return {
                "applied": False,
                "message": (
                    "FULL SELF-HEAL BLOCKED\n" + "=" * 58
                    + "\n\nAn earlier full-maintenance session is still active. "
                    "Restart the application so its transaction is restored first."
                ),
            }

        return {
            "applied": False,
            "message": (
                "FULL SELF-HEAL BLOCKED\n" + "=" * 58
                + f"\n\n{problem or 'Unknown maintenance marker state.'}"
            ),
        }

    ui.set_status("Running fixed full-maintenance diagnostics")
    healthy, diagnostic = self_heal_state.validate_restart()
    if healthy:
        return {
            "applied": False,
            "message": (
                "FULL SELF-HEAL\n" + "=" * 58
                + "\n\nThe fixed health and regression checks already pass. "
                "No repair was needed."
            ),
        }

    records = []
    applied_summaries = []
    skipped = []

    for attempt in range(1, MAX_SESSION_EDITS + 1):
        ui.set_status(
            f"Diagnosing full-maintenance repair {attempt}/{MAX_SESSION_EDITS}"
        )
        suggestions, error = suggestion_engine.generate(
            autonomous=False,
            diagnostic=diagnostic,
        )

        if error:
            return _rollback_result(
                records,
                f"The repair model could not produce a grounded suggestion: {error}",
                diagnostic,
            )

        applied_this_attempt = False
        for suggestion in suggestions:
            status, detail = _try_apply(suggestion, records)

            if status == "skip":
                skipped.append(detail)
                continue

            if status == "rollback":
                return _rollback_result(records, detail, diagnostic)

            applied_summaries.append(detail)
            applied_this_attempt = True
            break

        if not applied_this_attempt:
            reason = "No generated suggestion passed the deterministic repair gates."
            if skipped:
                reason += " Last refusal: " + skipped[-1]
            return _rollback_result(records, reason, diagnostic)

        ui.set_status("Re-running fixed health and regression checks")
        healthy, diagnostic = self_heal_state.validate_restart()
        if healthy:
            clear_error = _clear_state()
            if clear_error:
                return _rollback_result(
                    records,
                    "The repair passed validation but its transaction marker "
                    f"could not be closed ({clear_error}).",
                    diagnostic,
                )

            details = "\n".join(f"  {item}" for item in applied_summaries)
            return {
                "applied": True,
                "message": (
                    "FULL SELF-HEAL VERIFIED\n" + "=" * 58
                    + "\n\nThe fixed health and regression checks pass after "
                    "the following bounded repair(s):\n"
                    + details
                    + "\n\nReloading will activate the verified changes."
                ),
            }

    return _rollback_result(
        records,
        f"The fixed checks still failed after {MAX_SESSION_EDITS} bounded repair attempts.",
        diagnostic,
    )
