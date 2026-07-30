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

One activation runs an unattended session bounded by SUPER_DEV_SESSION_MAX_SECONDS
rather than by a patch count, so a night's run is limited by exposure instead
of by how much work it manages to get through.  The session is a loop over the
single-patch transaction, not a batch: the planner is re-run after every
accepted patch because the tree it planned against has changed, and each patch
passes the full gate set on its own before the next is attempted.

Three properties make the loop safe to leave running unattended.

At most one patch is ever in flight -- the transaction marker is written
before the write and cleared once the regression gate passes -- so crash
recovery still has exactly one patch to undo, and every patch already retained
had earned its place.

A candidate refused on judgment -- allowlist, capability, line cap,
regression gate -- is never retried, because retrying cannot change that
answer.  A candidate lost to a drafting error gets one more attempt, because
the worker fumbling its own diff says nothing about whether the change was
good.  Either way each candidate consumes a bounded budget, so a planner that
keeps proposing the same thing still cannot spend the window on it.

And progress is verified against a write counter rather than a returned flag.
_try_patch() increments _patches_written only after a real write clears the
regression gate; if it ever reports success without that, the session halts.
With no patch cap, a success that is really a no-op would otherwise loop for
the entire window.  autonomous_engine.run_observed_serial() guards its batch
the same way.
"""

import json
import os
import time
from datetime import datetime
from urllib.parse import urlparse

import requests

from core import file_utils
from core.config import (
    MODEL_ROLE,
    MODEL_ROLE_SUPER_DEV,
    SUPER_DEV_SESSION_MAX_SECONDS,
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

# Incremented only where a patch has actually been written and has cleared
# the regression gate. The session loop compares it across a call rather than
# trusting the returned flag, so a future refactor that reports success
# without doing the work stops the run instead of spinning through the whole
# window. Borrowed from autonomous_engine.run_observed_serial(), where the
# same cross-check guards the observed batch.
_patches_written = 0

# Why a candidate failed, which decides whether it is worth another go.
#
# JUDGMENT means the change itself was refused -- off the allowlist, over the
# line cap, across the capability boundary, or rejected by the regression
# gate. Retrying cannot change that answer, so the candidate is finished.
#
# DRAFTING means the worker fumbled its own output: it declined, it
# paraphrased the find text instead of copying it, or it emitted something
# that would not parse. The proposed change may be perfectly good.
#
# Treating these as the same thing is what let a six-hour window exhaust
# itself in 49 seconds on the first real run: three candidates, every one
# lost to a drafting error, every one blacklisted as though the gates had
# judged it. The bottleneck was never the clock.
JUDGMENT = "judgment"
DRAFTING = "drafting"

# One retry, so a fumbled diff gets a second chance and the loop still cannot
# spend the window on a single candidate. Termination stays guaranteed by
# arithmetic rather than by hoping the worker does better next time.
MAX_DRAFT_ATTEMPTS = 2


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
        return False, f"planner selected an invalid target ({error})", JUDGMENT

    ui.set_status(f"7B worker drafting patch for {target}")
    edit, error = edit_generator.generate_edit(
        target,
        original,
        suggestion["change"],
        server_url=SUPER_DEV_WORKER_URL,
        headers=SUPER_DEV_WORKER_HEADERS,
    )
    if error:
        return False, f"7B worker declined {target}: {error}", DRAFTING

    updated, apply_error = patch_engine.apply_edit(
        original, edit["find"], edit["replace"]
    )
    if apply_error:
        return False, f"7B patch would not apply to {target}: {apply_error}", DRAFTING

    syntax_problem = edit_guard.check_syntax(updated, os.path.basename(target))
    if syntax_problem:
        return False, f"7B patch failed syntax validation: {syntax_problem}", DRAFTING

    added, removed = patch_engine.diff_stats(original, updated)
    if added + removed > MAX_CHANGED_LINES:
        return False, f"7B patch is too large ({added + removed} lines; limit {MAX_CHANGED_LINES})", JUDGMENT

    safety_problem = edit_guard.autonomous_change_problem(target, original, updated)
    if safety_problem:
        return False, f"7B patch crossed the autonomous boundary: {safety_problem}", JUDGMENT

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
        return False, f"could not stage the transactional patch: {error}.{suffix}", JUDGMENT

    ui.set_status("Running fixed regression gate")
    healthy, diagnostic = self_heal_state.validate_restart()
    if not healthy:
        restore_error = _restore(record)
        suffix = f" Rollback failed: {restore_error}" if restore_error else " The backup was restored."
        return (False,
                f"fixed regression gate rejected the patch.{suffix}\n"
                f"{str(diagnostic)[-1200:]}",
                JUDGMENT)

    _clear_state()
    global _patches_written
    _patches_written += 1
    summary = edit.get("explanation", "small guarded patch")
    _log(
        f"APPLIED {target}: 14B planned; 7B drafted; +{added} -{removed}; "
        f"backup={backup}; summary={summary}"
    )
    return True, f"{target}: {summary} (+{added} -{removed})", None


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


def _describe_window(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours}h{minutes:02d}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def run_session(limit=None, max_seconds=None):
    """Plan, draft, test, and retain patches until the session window closes.

    The session is bounded by time, not by a patch count: `limit` stays
    available for a watched run or a test, but defaults to no cap. It stops
    when the window closes, when the planner errors or offers nothing untried,
    when no untried candidate survives the gates, or when a patch claims
    success without having written anything.

    Returns (applied_any, report).
    """
    if MODEL_ROLE != MODEL_ROLE_SUPER_DEV:
        return False, "Super Dev requires the dedicated super-dev launcher."

    if os.path.exists(STATE_FILE):
        return False, "A prior Super Dev transaction is pending recovery; restart first."

    ready, detail = worker_status()
    if not ready:
        return False, f"SUPER DEV BLOCKED\n{'=' * 58}\n\n{detail}. No files changed."

    if max_seconds is None:
        max_seconds = SUPER_DEV_SESSION_MAX_SECONDS
    try:
        max_seconds = max(1, int(max_seconds))
    except (TypeError, ValueError):
        max_seconds = SUPER_DEV_SESSION_MAX_SECONDS

    if limit is not None:
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = None

    window = _describe_window(max_seconds)
    started = time.monotonic()
    deadline = started + max_seconds
    applied = []
    attempted = {}
    stop_reason = f"the {window} session window closed"
    _log(
        f"SESSION START: window {window}"
        + (f"; patch limit {limit}" if limit is not None else "; no patch limit")
    )

    while True:
        if limit is not None and len(applied) >= limit:
            stop_reason = f"the patch limit of {limit} was reached"
            break
        if time.monotonic() >= deadline:
            break

        left = _describe_window(max(0, deadline - time.monotonic()))
        ui.set_status(
            f"14B planner reviewing candidates "
            f"({len(applied)} retained, {left} left)"
        )
        suggestions, error = suggestion_engine.generate(autonomous=True)
        if error:
            stop_reason = f"the 14B planner stopped: {error}"
            break

        fresh = [item for item in (suggestions or [])
                 if attempted.get(_candidate_key(item), 0) < MAX_DRAFT_ATTEMPTS]
        if not fresh:
            stop_reason = (
                "the 14B planner offered nothing this session had not "
                "already exhausted"
            )
            break

        retained_this_round = False
        halted = None
        for suggestion in fresh:
            key = _candidate_key(suggestion)
            written_before = _patches_written
            accepted, result, kind = _try_patch(suggestion)

            # Trust the counter, not the flag. _try_patch() increments it only
            # after a real write clears the regression gate, so a success
            # reported without one means the loop can no longer tell progress
            # from a no-op -- and with no patch cap that is a whole window
            # spent spinning. Stop instead.
            if accepted and _patches_written <= written_before:
                halted = "a patch reported success without writing anything"
                _log(f"SESSION HALTED: {halted}")
                break

            if accepted:
                attempted[key] = MAX_DRAFT_ATTEMPTS
                applied.append(result)
                retained_this_round = True
                break

            # A judged refusal is final; a fumbled draft has earned one more
            # go. Both consume budget, so neither can be tried without end.
            if kind == DRAFTING:
                attempted[key] = attempted.get(key, 0) + 1
                remaining = MAX_DRAFT_ATTEMPTS - attempted[key]
                _log(f"SKIPPED ({kind}, {remaining} retr"
                     f"{'y' if remaining == 1 else 'ies'} left): {result}")
            else:
                attempted[key] = MAX_DRAFT_ATTEMPTS
                _log(f"SKIPPED ({kind or 'refused'}, final): {result}")

        if halted:
            stop_reason = halted
            break

        if not retained_this_round:
            # Only give up once nothing is left to retry. Stopping on the
            # first barren round would make the retry budget unreachable --
            # a candidate would be granted a second attempt it could never
            # take, which is the bug this whole branch exists to fix.
            retryable = [
                item for item in fresh
                if attempted.get(_candidate_key(item), 0) < MAX_DRAFT_ATTEMPTS
            ]
            if not retryable:
                stop_reason = (
                    "no remaining 14B-planned candidate passed the "
                    "deterministic patch gates"
                )
                break

    elapsed = _describe_window(time.monotonic() - started)
    _log(
        f"SESSION END: {len(applied)} applied in {elapsed}; "
        f"stopped because {stop_reason}"
    )

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
        + f"{noun} in {elapsed}. Each passed the fixed regression gate on "
        + f"its own before the next was attempted.\n\n{body}\n\n"
        + f"The session stopped because {stop_reason}.\n\n"
        + f"Audit: {LOG_FILE}\nBackups retained by the edit guard."
    )
