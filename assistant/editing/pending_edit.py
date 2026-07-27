"""
Holds the edit that has been previewed and is awaiting confirmation.

Previously this stored only a plan file path, which meant "confirm"
had nothing concrete to apply. It now carries the fully-resolved
change: the target, the new file content, and the diff the user was
actually shown -- so what gets written is exactly what was approved,
not a regeneration that might come out differently.
"""

_pending = None


def set_pending(target, new_content, diff, explanation="", plan_path=None, original=None):
    global _pending

    _pending = {
        "target": target,
        "new_content": new_content,
        "diff": diff,
        "explanation": explanation,
        "plan_path": plan_path,
        "original": original,
    }


def get_pending():
    return _pending


def clear():
    global _pending
    _pending = None
