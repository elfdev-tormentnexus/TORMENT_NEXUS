"""
Orchestrates the self-editing loop.

    modify plan <file> <change>   record the intent
    approve plan                  authorise it
    preview plan                  generate the edit, validate, show a diff
    confirm edit                  write it
    rollback                      undo

The generation happens at PREVIEW, not at confirm. That way what you
approve is the literal diff you were shown, rather than a second
generation that could come out differently.
"""

import os
import re

from core.config import DEBUG as DEBUG_INTENT

from editing import approval_manager
from editing import pending_edit
from editing import patch_engine
from editing import edit_guard
from editing import edit_generator
from editing import edit_intent
from editing import change_planner
from ui import ui


# change_planner writes a human-readable plan; these pull the fields
# back out of it.
_TARGET_RE = re.compile(r"Target file:\s*\n(.+)", re.IGNORECASE)
_REQUEST_RE = re.compile(r"Request:\s*\n(.+)", re.IGNORECASE)


def _parse_plan(text):
    target = _TARGET_RE.search(text)
    request = _REQUEST_RE.search(text)

    return (
        target.group(1).strip() if target else None,
        request.group(1).strip() if request else None,
    )


# Set when a confirmed edit needs the app reloaded to take effect.
_restart_pending = False


def restart_pending():
    return _restart_pending


def clear_restart():
    global _restart_pending
    _restart_pending = False


def mark_restart_pending():
    """
    For callers that write outside this module's own propose/confirm
    flow -- currently just autonomous_engine.py, which writes directly
    with no pending-edit staging step -- but still needs chat_loop's
    existing restart check (same one confirm_edit() drives) to notice.
    """
    global _restart_pending
    _restart_pending = True


def propose(file_hint, change, plan_path=None):
    """
    Shared core of the propose step: resolve the file, generate and
    validate an edit, and stage it as the pending edit. Nothing is
    written here.

    Used by every path that already knows a file and a change
    description -- the conversational path (request_edit), the
    plan path (preview_plan), and accepting a 'suggest' idea -- since
    only how they arrive at (file, change) differs, not what happens
    after.

    plan_path, if given, is recorded as the plan behind this edit (an
    already-approved plan file). If omitted, a new one is written so
    there's still a paper trail.
    """
    ui.set_status(f"Locating {file_hint}")

    try:
        target = edit_guard.locate(file_hint)
    except edit_guard.GuardError as e:
        return f"CANNOT EDIT {file_hint}\n{'=' * 42}\n\n{e}"

    ui.set_status(f"Reading {target}")

    try:
        original = edit_guard.read(target)
    except edit_guard.GuardError as e:
        return f"CANNOT EDIT {target}\n{'=' * 42}\n\n{e}"

    ui.set_status(f"Generating patch for {target}")
    edit, error = edit_generator.generate_edit(target, original, change)

    if error:
        return (
            "COULD NOT PRODUCE AN EDIT\n"
            + "=" * 42 + "\n\n"
            f"File:   {target}\n"
            f"Change: {change}\n\n"
            f"{error}"
        )

    ui.set_status("Applying patch in memory")
    new_content, apply_error = patch_engine.apply_edit(
        original, edit["find"], edit["replace"]
    )

    if apply_error:
        return f"COULD NOT APPLY THE EDIT\n{'=' * 42}\n\n{apply_error}"

    ui.set_status("Checking Python syntax")
    problem = edit_guard.check_syntax(new_content, os.path.basename(target))

    if problem:
        return (
            "EDIT REJECTED\n"
            + "=" * 42 + "\n\n"
            "The result would not parse, so it was discarded.\n\n"
            f"{problem}"
        )

    ui.set_status("Preparing review diff")
    diff = patch_engine.make_diff(original, new_content, target)
    added, removed = patch_engine.diff_stats(original, new_content)

    if plan_path is None:
        # Record it as a plan too, so there is a paper trail.
        plan_path = change_planner.save_plan(
            target, change, ["Generated from a conversational request"]
        )

    ui.set_status("Staging edit for confirmation")
    pending_edit.set_pending(
        target=target,
        new_content=new_content,
        diff=diff,
        explanation=edit["explanation"],
        plan_path=plan_path,
        original=original,
    )

    return (
        "PROPOSED EDIT\n"
        + "=" * 42 + "\n\n"
        f"File:   {target}\n"
        f"Change: {edit['explanation']}\n"
        f"Lines:  +{added} -{removed}\n"
        f"Syntax: valid\n\n"
        + diff + "\n"
        + "=" * 42 + "\n"
        "Nothing written yet. 'confirm edit' to apply and reload, "
        "'cancel edit' to discard."
    )


def request_edit(user_message):
    """
    The conversational path. Returns a response string if this really
    was an edit request, or None to let it fall through to normal
    chat.

    Collapses plan -> approve -> preview into one step, because being
    made to type three commands is exactly what stops it feeling
    alive. The approval gate is still there: nothing is written until
    'confirm edit'.
    """
    ui.set_status("Understanding code request")
    intent, why_not = edit_intent.classify(user_message)

    if not intent:
        if DEBUG_INTENT:
            print(f"[intent] {why_not}")
        return None

    return propose(intent["file"], intent["change"])


def preview_plan():
    ui.set_status("Reading approved change plan")
    approved = approval_manager.get_approved_plan()

    if not approved:
        return (
            "NO APPROVED PLAN\n"
            "================\n"
            "Run 'modify plan <file> <change>' then 'approve plan'."
        )

    if not os.path.exists(approved):
        return f"APPROVED PLAN MISSING\n{approved}"

    with open(approved, "r", encoding="utf-8") as f:
        plan_text = f.read()

    target, request = _parse_plan(plan_text)

    if not target:
        return f"Could not read a target file out of the plan:\n{approved}"

    if not request:
        return f"Could not read a request out of the plan:\n{approved}"

    return propose(target, request, plan_path=approved)


def confirm_edit():
    global _restart_pending

    ui.set_status("Loading pending edit")
    pending = pending_edit.get_pending()

    if not pending:
        return "Nothing to confirm. Ask for a change, or run 'preview plan'."

    target = pending["target"]

    # The diff shown at preview time was computed against `original`.
    # If the file on disk has moved on since then -- a manual edit, or
    # a second preview overwriting this one's pending slot and then
    # being cancelled -- writing new_content now would silently
    # clobber whatever changed it, with no trace of what was lost.
    if pending.get("original") is not None:
        ui.set_status("Checking for newer file changes")
        try:
            current = edit_guard.read(target)
        except edit_guard.GuardError as e:
            return f"WRITE REFUSED\n{'=' * 42}\n\n{e}"

        if current != pending["original"]:
            pending_edit.clear()
            return (
                "EDIT REFUSED\n"
                + "=" * 42 + "\n\n"
                f"{target} has changed on disk since this edit was previewed.\n"
                "Run 'preview plan' again (or re-ask for the change) against "
                "the current file."
            )

    ui.set_status(f"Backing up and writing {target}")
    try:
        backup_path = edit_guard.write(target, pending["new_content"])
    except edit_guard.GuardError as e:
        return f"WRITE REFUSED\n{'=' * 42}\n\n{e}"
    except Exception as e:
        return f"WRITE FAILED\n{'=' * 42}\n\n{e}"

    # Syntax was checked before the write, but a file can parse
    # perfectly and still fail on import. If that is not caught here,
    # the next launch dies and there is no assistant left to fix it.
    ui.set_status(f"Import-testing {target}")
    import_error = edit_guard.import_check(target)

    if import_error:
        ui.set_status(f"Reverting failed edit to {target}")
        try:
            edit_guard.restore(os.path.basename(backup_path))
            undone = "The file has been restored from backup."
        except Exception as e:
            undone = (
                f"AUTOMATIC ROLLBACK ALSO FAILED: {e}\n"
                f"Restore by hand from {backup_path}"
            )

        pending_edit.clear()

        return (
            "EDIT REVERTED\n"
            + "=" * 42 + "\n\n"
            f"{target} parsed, but failed to import:\n\n"
            f"{import_error}\n\n"
            f"{undone}"
        )

    ui.set_status("Finalizing applied edit")
    pending_edit.clear()
    approval_manager.clear_approval()

    _restart_pending = True

    return (
        "EDIT APPLIED\n"
        + "=" * 42 + "\n\n"
        f"File:   {target}\n"
        f"Backup: {backup_path}\n"
        f"Import: clean\n\n"
        "Reloading so the change takes effect."
    )


def cancel_edit():
    if not pending_edit.get_pending():
        return "Nothing pending."

    pending_edit.clear()

    return "Pending edit discarded. Nothing was written."


def rollback(which=None):
    """Restore the most recent backup, or a named one."""
    ui.set_status("Finding the requested backup")
    backups = edit_guard.list_backups()

    if not backups:
        return "No backups exist."

    name = which.strip() if which else backups[0]

    ui.set_status(f"Restoring {name}")
    try:
        restored = edit_guard.restore(name)
    except edit_guard.GuardError as e:
        return f"ROLLBACK FAILED\n{'=' * 42}\n\n{e}"

    return (
        "ROLLED BACK\n"
        + "=" * 42 + "\n\n"
        f"File:    {restored}\n"
        f"From:    {name}\n\n"
        "The version you rolled back from was itself backed up first."
    )


def list_backups():
    backups = edit_guard.list_backups()

    if not backups:
        return "No backups exist."

    return (
        "BACKUPS (newest first)\n"
        + "=" * 42 + "\n"
        + "\n".join(f"  {b}" for b in backups[:40])
    )
