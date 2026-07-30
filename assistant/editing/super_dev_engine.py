"""Hazard-only two-model autonomous patch session.

Super Dev is deliberately not a blanket permission grant.  The 14B model is
the planner/reviewer: it selects a small, grounded improvement from the same
unattended allowlist used by the 7B repair path.  A separately launched 7B
worker can only draft one exact find/replace patch for that selected task.

Trusted Python keeps all authority: it checks the worker is loopback-only,
enforces the allowlist and capability rules, makes a durable backup before a
write, runs the fixed regression gate, and restores the backup on failure.
Neither model receives chat, memories, web pages, credentials, shell access,
or Git authority.

One activation runs an unattended session of up to
SUPER_DEV_SESSION_PATCH_LIMIT patches.  The session is a loop over the
single-patch transaction, not a batch: the planner is re-run after every
accepted patch because the tree it planned against has changed, and each
patch passes the full gate set on its own before the next is attempted.

Two properties make the loop safe to leave running.  At most one patch is
ever in flight -- the transaction marker is written before the write and
cleared once the regression gate passes -- so crash recovery still has
exactly one patch to undo, and every patch already retained had earned its
place.  And a candidate the gates rejected is never retried inside the same
session, which is what guarantees the loop ends instead of grinding on the
same refusal until the limit runs out.
"""

import json
import os
from datetime import datetime
from urllib.parse import urlparse

import requests

from core import file_utils
from core.config import (
    MODEL_ROLE,
    MODEL_ROLE_SUPER_DEV,
    SUPER_DEV_SESSION_PATCH_LIMIT,
    SUPER_DEV_WORKER_HEADERS,
    SUPER_DEV_WORKER_URL,
)
from editing import edit_generator
from editing import edit_guard
from editing import patch_engine
from editing import self_heal_state
from editing import suggestion_engine
from ui import ui


MAX_CHANGED_LINES = 40
LOG_FILE = os.path.join(edit_guard.PROJECT_ROOT, "logs", "super_dev_edits.log")
STATE_FILE = os.path.join(
    edit_guard.PROJECT_ROOT, "logs", "super_dev_session_state.json"
)
STATE_VERSION = 1


def _log(message):
    file_utils.ensure_file(LOG_FILE)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_utils.append_file(LOG_FILE, f"[{stamp}] {message}\n")


def _is_loopback_worker():
    try:
        parsed = urlparse(SUPER_DEV_WORKER_URL)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
            and bool(parsed.port)
        )
    except ValueError:
        return False


def worker_status():
    """Return a safe diagnostic; never attempt a non-loopback worker."""
    if not SUPER_DEV_WORKER_URL:
        return False, "the 7B worker endpoint was not supplied by the launcher"
    if not _is_loopback_worker():
        return False, "the 7B worker endpoint is not a loopback address"
    if not SUPER_DEV_WORKER_HEADERS:
        return False, "the 7B worker has no launcher-issued API credential"

    try:
        response = requests.get(
            SUPER_DEV_WORKER_URL + "/v1/models",
            headers=SUPER_DEV_WORKER_HEADERS,
            timeout=3,
        )
        response.raise_for_status()
        models = response.json().get("data") or []
        model_id = str(models[0].get("id", "")) if models else ""
    except Exception as error:
        return False, f"the 7B worker is unavailable ({error})"

    if model_id != "super-dev-worker":
        return False, f"the worker endpoint has the wrong model profile ({model_id or 'unknown'})"

    return True, "7B worker ready"


def _write_state(record):
    file_utils.save_json(
        STATE_FILE,
        {"version": STATE_VERSION, "phase": "active", "record": record},
    )


def _clear_state():
    try:
        os.remove(STATE_FILE)
    except FileNotFoundError:
        pass


def _restore(record):
    try:
        edit_guard.restore(os.path.basename(record["backup"]))
    except Exception as error:
        return str(error)
    _clear_state()
    return None


def recover_incomplete_session():
    """Fail closed after a crash: restore the one patch before normal use."""
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as source:
            state = json.load(source)
        record = state["record"]
        if state.get("version") != STATE_VERSION or state.get("phase") != "active":
            raise ValueError("unknown transaction format")
        if not isinstance(record.get("backup"), str) or not isinstance(record.get("target"), str):
            raise ValueError("invalid rollback record")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        return (
            "SUPER DEV RECOVERY NEEDS ATTENTION\n" + "=" * 58
            + f"\n\nThe pending transaction marker is invalid: {error}. "
            + f"It was left in place at {STATE_FILE}."
        )

    restore_error = _restore(record)
    if restore_error:
        return (
            "SUPER DEV RECOVERY NEEDS ATTENTION\n" + "=" * 58
            + f"\n\nCould not restore {record['target']}: {restore_error}. "
            + f"The marker was left at {STATE_FILE}."
        )

    _log(f"RECOVERED interrupted session: restored {record['target']}")
    return (
        "SUPER DEV RECOVERED\n" + "=" * 58
        + "\n\nAn interrupted autonomous patch was restored before startup."
    )


def _try_patch(suggestion):
    try:
        target = edit_guard.locate(suggestion["file"])
        original = edit_guard.read(target)
    except (KeyError, edit_guard.GuardError) as error:
        return False, f"planner selected an invalid target ({error})"

    ui.set_status(f"7B worker drafting patch for {target}")
    edit, error = edit_generator.generate_edit(
        target,
        original,
        suggestion["change"],
        server_url=SUPER_DEV_WORKER_URL,
        headers=SUPER_DEV_WORKER_HEADERS,
    )
    if error:
        return False, f"7B worker declined {target}: {error}"

    updated, apply_error = patch_engine.apply_edit(
        original, edit["find"], edit["replace"]
    )
    if apply_error:
        return False, f"7B patch would not apply to {target}: {apply_error}"

    syntax_problem = edit_guard.check_syntax(updated, os.path.basename(target))
    if syntax_problem:
        return False, f"7B patch failed syntax validation: {syntax_problem}"

    added, removed = patch_engine.diff_stats(original, updated)
    if added + removed > MAX_CHANGED_LINES:
        return False, f"7B patch is too large ({added + removed} lines; limit {MAX_CHANGED_LINES})"

    safety_problem = edit_guard.autonomous_change_problem(target, original, updated)
    if safety_problem:
        return False, f"7B patch crossed the autonomous boundary: {safety_problem}"

    ui.set_status(f"Backing up supervised patch for {target}")
    record = None
    try:
        backup = edit_guard.backup(target)
        record = {"target": target, "backup": backup}
        _write_state(record)
        edit_guard.write(target, updated, backup_path=backup)
    except Exception as error:
        restore_error = _restore(record) if record else None
        suffix = f" Rollback failed: {restore_error}" if restore_error else ""
        return False, f"could not stage the transactional patch: {error}.{suffix}"

    ui.set_status("Running fixed regression gate")
    healthy, diagnostic = self_heal_state.validate_restart()
    if not healthy:
        restore_error = _restore(record)
        suffix = f" Rollback failed: {restore_error}" if restore_error else " The backup was restored."
        return False, f"fixed regression gate rejected the patch.{suffix}\n{str(diagnostic)[-1200:]}"

    _clear_state()
    summary = edit.get("explanation", "small guarded patch")
    _log(
        f"APPLIED {target}: 14B planned; 7B drafted; +{added} -{removed}; "
        f"backup={backup}; summary={summary}"
    )
    return True, f"{target}: {summary} (+{added} -{removed})"


def _candidate_key(suggestion):
    """Identify a planned candidate so one refusal is not retried all session.

    Keyed on the pair the planner actually chose rather than on the whole
    record, because the 14B rewords its own explanation between rounds and
    an explanation-sensitive key would let the same rejected change back in
    under a new sentence.
    """
    if not isinstance(suggestion, dict):
        return repr(suggestion)
    return (str(suggestion.get("file", "")), str(suggestion.get("change", "")))


def run_session(limit=None):
    """Plan, draft, test, and retain up to `limit` tightly scoped patches.

    Returns (applied_any, report). The session stops at the limit, at the
    first planning round that offers nothing untried, or at the first round
    where no untried candidate survives the gates.
    """
    if MODEL_ROLE != MODEL_ROLE_SUPER_DEV:
        return False, "Super Dev requires the dedicated super-dev launcher."

    if os.path.exists(STATE_FILE):
        return False, "A prior Super Dev transaction is pending recovery; restart first."

    ready, detail = worker_status()
    if not ready:
        return False, f"SUPER DEV BLOCKED\n{'=' * 58}\n\n{detail}. No files changed."

    if limit is None:
        limit = SUPER_DEV_SESSION_PATCH_LIMIT
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = SUPER_DEV_SESSION_PATCH_LIMIT

    applied = []
    attempted = set()
    stop_reason = f"the session patch limit of {limit} was reached"
    _log(f"SESSION START: patch limit {limit}")

    while len(applied) < limit:
        ui.set_status(
            f"14B planner reviewing candidates ({len(applied) + 1}/{limit})"
        )
        suggestions, error = suggestion_engine.generate(autonomous=True)
        if error:
            stop_reason = f"the 14B planner stopped: {error}"
            break

        fresh = [item for item in (suggestions or [])
                 if _candidate_key(item) not in attempted]
        if not fresh:
            stop_reason = (
                "the 14B planner offered nothing this session had not "
                "already tried"
            )
            break

        retained_this_round = False
        for suggestion in fresh:
            attempted.add(_candidate_key(suggestion))
            accepted, result = _try_patch(suggestion)
            if accepted:
                applied.append(result)
                retained_this_round = True
                break
            _log(f"SKIPPED: {result}")

        if not retained_this_round:
            stop_reason = (
                "no remaining 14B-planned candidate passed the "
                "deterministic patch gates"
            )
            break

    _log(f"SESSION END: {len(applied)} applied; stopped because {stop_reason}")

    if not applied:
        return False, (
            "SUPER DEV SKIPPED\n" + "=" * 58
            + f"\n\nNo patch was retained because {stop_reason}. "
            + f"See {LOG_FILE}. No files changed."
        )

    body = "\n".join(f"  {index}. {entry}"
                     for index, entry in enumerate(applied, 1))
    noun = "patch" if len(applied) == 1 else "patches"
    return True, (
        "SUPER DEV VERIFIED\n" + "=" * 58
        + f"\n\n14B planner + 7B patch worker retained {len(applied)} "
        + f"{noun}. Each passed the fixed regression gate on its own "
        + f"before the next was attempted.\n\n{body}\n\n"
        + f"The session stopped because {stop_reason}.\n\n"
        + f"Audit: {LOG_FILE}\nBackups retained by the edit guard."
    )
