"""
Runs one self-improvement cycle without asking for approval first.

This is deliberately isolated from everything conversational: it only
ever looks at the project's own source files, via suggestion_engine
(already grounded to real, non-denylisted files -- see
edit_guard.list_editable_files()), and never sees live chat, memory,
or web search content. That isolation IS the safety property here,
not a nice-to-have -- letting this loop see untrusted external content
would hand a poisoned web page a path to steer a self-edit with nobody
in the loop to catch it. See main.py's maybe_search_context() and
edit_intent.py for where that content lives instead; this module
deliberately never imports either.

Guardrails enforced here, on top of everything edit_guard.py already
enforces on every write regardless of caller (denylist, syntax check,
atomic write, timestamped backup):

- AUTONOMOUS_ALLOWED_FILES: unattended work is limited to non-critical
  presentation, voice, relevance, and read-only analysis modules.
- No new process, network, dynamic-code, or filesystem-write capability.
- MAX_CHANGED_LINES: a diff bigger than this is refused, not applied.
  Small surgical fixes only -- the same philosophy edit_generator.py
  already leans on for a 4B model, just also enforced as a hard cap
  here since nobody is reading the diff before it lands.
- RUN_LIMIT: at most one autonomous edit actually applied per process
  run. Unbounded autonomy on a schedule is how one bad decision
  compounds into several before anyone notices.
- Every attempt -- applied, refused, or failed -- is appended to
  logs/autonomous_edits.log, so what happened is visible after the
  fact even though nobody approved it beforehand.
"""

import os
from datetime import datetime

from editing import edit_guard
from editing import edit_generator
from editing import patch_engine
from editing import suggestion_engine
from core.file_utils import ensure_file, append_file
from ui import ui


MAX_CHANGED_LINES = 40
RUN_LIMIT = 1

LOG_FILE = os.path.join(edit_guard.PROJECT_ROOT, "logs", "autonomous_edits.log")

_applied_this_run = 0


def _log(line):
    ensure_file(LOG_FILE)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_file(LOG_FILE, f"[{stamp}] {line}\n")


def run_cycle():
    """
    One attempt: ask suggestion_engine for ideas and try the first one
    that produces a small enough, valid diff. No approval step -- if
    it passes every check below, it gets written.

    Returns a short human-readable summary if something was applied,
    otherwise None (budget spent, nothing usable, or an error --
    check the log for which).
    """
    if _applied_this_run >= RUN_LIMIT:
        return None

    ui.set_status("Scanning for improvement ideas")
    suggestions, error = suggestion_engine.generate(autonomous=True)

    if error:
        _log(f"SKIPPED: could not generate suggestions ({error})")
        return None

    for suggestion in suggestions:
        ui.set_status(f"Reviewing idea: {suggestion['title']}")
        result = _try_apply(suggestion)

        if result:
            return result

    _log("SKIPPED: no suggestion produced a safe, small enough diff")
    return None


def _try_apply(suggestion):
    global _applied_this_run

    file = suggestion["file"]
    change = suggestion["change"]

    ui.set_status(f"Inspecting {file}")
    try:
        target = edit_guard.locate(file)
        original = edit_guard.read(target)
    except edit_guard.GuardError as e:
        _log(f"REFUSED {file}: {e}")
        return None

    ui.set_status(f"Generating autonomous patch for {target}")
    edit, error = edit_generator.generate_edit(target, original, change)

    if error:
        _log(f"SKIPPED {target}: generator declined ({error})")
        return None

    ui.set_status("Applying autonomous patch in memory")
    new_content, apply_error = patch_engine.apply_edit(
        original, edit["find"], edit["replace"]
    )

    if apply_error:
        _log(f"SKIPPED {target}: {apply_error}")
        return None

    ui.set_status("Checking autonomous patch syntax")
    problem = edit_guard.check_syntax(new_content, os.path.basename(target))

    if problem:
        _log(f"SKIPPED {target}: syntax check failed ({problem})")
        return None

    ui.set_status("Checking autonomous change size")
    added, removed = patch_engine.diff_stats(original, new_content)

    if added + removed > MAX_CHANGED_LINES:
        _log(
            f"SKIPPED {target}: diff too large "
            f"({added + removed} lines, limit {MAX_CHANGED_LINES})"
        )
        return None

    ui.set_status("Checking unattended safety boundary")
    safety_problem = edit_guard.autonomous_change_problem(
        target,
        original,
        new_content,
    )

    if safety_problem:
        _log(f"REFUSED {target}: {safety_problem}")
        return None

    # Same guarded path a human 'confirm edit' writes through --
    # denylist, syntax re-check, backup, atomic replace all happen
    # inside edit_guard.write() regardless of who's calling it.
    ui.set_status(f"Backing up and writing {target}")
    try:
        backup_path = edit_guard.write(target, new_content)
    except edit_guard.GuardError as e:
        _log(f"REFUSED {target}: {e}")
        return None

    ui.set_status(f"Import-testing {target}")
    import_error = edit_guard.import_check(target)

    if import_error:
        ui.set_status(f"Reverting failed autonomous edit to {target}")
        try:
            edit_guard.restore(os.path.basename(backup_path))
            undone = "restored from backup"
        except Exception as e:
            undone = f"ROLLBACK FAILED: {e} -- restore by hand from {backup_path}"

        _log(f"REVERTED {target}: failed import check ({import_error}); {undone}")
        return None

    _applied_this_run += 1
    ui.set_status("Recording autonomous edit result")

    summary = (
        f"APPLIED {target}: {edit['explanation']} "
        f"(+{added} -{removed}, backup: {backup_path})"
    )
    _log(summary)

    return summary
