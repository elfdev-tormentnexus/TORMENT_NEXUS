import os
import json
import shutil
import threading
from datetime import datetime
from memory import memory_logic


from core import dev_auth
from core.config import CORE_MEMORY_FILE, MEMORY_FILE, HISTORY_FILE, DEBUG, SHOW_MEMORY_EVENTS
from core.file_utils import load_text, load_json, save_json, append_file, save_text
from ui import ui


# Only the last 1000 characters of conversation_history are ever used
# (main.py slices it for the prompt), but the string itself used to
# grow without bound for the life of the process -- and the on-disk
# file forever, since append_history() only ever appended. Fine on a
# dev machine restarted daily; not fine on something meant to run for
# weeks unattended on 8GB of RAM. Cap well above what's actually read
# so nothing currently relying on a longer slice breaks.
MAX_HISTORY_CHARS = 20_000

# memories.json has no natural ceiling either -- every save is an
# O(n) scan for duplicates/conflicts, and a memory that's been
# superseded still costs space and scan time forever. Cap the count
# and prune superseded entries first, since those exist only as an
# audit trail once a newer fact has replaced them.
MAX_MEMORIES = 500


# ============================================================
# MEMORY DATABASE (loaded once at import time)
# ============================================================

core_memory = load_text(CORE_MEMORY_FILE)
conversation_history = load_text(HISTORY_FILE)
redacted_history = dev_auth.redact_credential_like_text(conversation_history)

if redacted_history != conversation_history:
    # Do not preserve a backup containing the leaked credential. The live
    # history is only chat context, and keeping a secret-bearing recovery copy
    # would defeat the redaction.
    save_text(HISTORY_FILE, redacted_history)
    conversation_history = redacted_history


def _load_memory_list():
    """
    Keep one malformed entry from making every later memory operation fail.

    Invalid data is preserved beside the live file before the cleaned list is
    saved, so resilience never comes at the cost of silently discarding the
    only copy.
    """
    loaded = load_json(MEMORY_FILE)
    cleaned = []

    if isinstance(loaded, list):
        cleaned = [
            item
            for item in loaded
            if (
                isinstance(item, dict)
                and isinstance(item.get("memory"), str)
                and item["memory"].strip()
            )
        ]

    if isinstance(loaded, list) and len(cleaned) == len(loaded):
        return cleaned

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    recovery = MEMORY_FILE + f".{stamp}.invalid-shape"

    try:
        shutil.copy2(MEMORY_FILE, recovery)
    except OSError:
        recovery = None

    save_json(MEMORY_FILE, cleaned)
    detail = f" Preserved at {recovery}." if recovery else ""
    print(
        "[memory] WARNING: malformed memory data was removed from the live "
        f"store.{detail}"
    )
    return cleaned


memories = _load_memory_list()

# save_memory() runs on the background extraction thread
# (memory_worker.py) while forget_memory()/show_memories() run on the
# main thread from chat commands. Both read-modify-write `memories` in
# multiple steps (find conflicts, mutate by index, append, persist),
# so without a lock the two can interleave: a `forget` landing between
# a conflict lookup and its index-based mutation can silently corrupt
# or drop an update. One lock around every multi-step access closes
# that window.
_lock = threading.Lock()

if DEBUG:
    print("\nDEBUG MEMORY FILE:")
    print(os.path.abspath(MEMORY_FILE))

    print("\nDEBUG LOADED MEMORIES:")
    print(json.dumps(memories, indent=4))


# ============================================================
# MEMORY STORAGE
# ============================================================

def similar_memory(new_fact):
    new_words = set(new_fact.lower().split())

    for item in memories:
        old_words = set(item["memory"].lower().split())
        overlap = len(new_words & old_words)
        similarity = overlap / max(len(new_words), 1)

        if similarity > 0.55:
            return True

    return False


# ============================================================
# MEMORY CLEANER
# ============================================================

def clean_memory(memory):
    if not memory:
        return None

    memory = memory.strip()

    # Remove common AI phrases
    remove_phrases = [
        "the user is",
        "the user wants",
        "the user asked",
        "i need to remember",
        "i should remember",
        "the assistant thinks",
        "the assistant should",
    ]

    lower = memory.lower()

    for phrase in remove_phrases:
        if lower.startswith(phrase):
            memory = memory[len(phrase):].strip()
            break

    # Fix punctuation
    if not memory.endswith("."):
        memory += "."

    # Length check
    if len(memory) < 15:
        return None

    if len(memory) > 250:
        return None

    return memory


def _prune_memories():
    """
    Keep the store under MAX_MEMORIES. Caller must already hold _lock.

    Superseded entries are dropped first -- they're kept only as a
    short audit trail, not because the model still needs them. If
    trimming those isn't enough, fall back to dropping the oldest
    active entries, since those are also the ones most likely to be
    stale.
    """
    global memories

    if len(memories) <= MAX_MEMORIES:
        return

    active_items = [m for m in memories if not m.get("superseded")]
    superseded_items = [m for m in memories if m.get("superseded")]

    room_for_superseded = max(MAX_MEMORIES - len(active_items), 0)
    kept_superseded = superseded_items[-room_for_superseded:] if room_for_superseded else []

    memories = (active_items[-MAX_MEMORIES:] + kept_superseded)[-MAX_MEMORIES:]


def save_memory(memory, category, confidence):
    global memories

    memory = clean_memory(memory)

    if not memory:
        if DEBUG:
            ui.print_framed("[Memory rejected by cleaner]", color=ui.RED)
        return

    memory = memory.strip()

    if not memory:
        return

    old = None

    with _lock:
        # Already know this?
        if memory_logic.find_duplicate(memory, memories) is not None:
            if DEBUG:
                ui.print_framed("[Duplicate memory ignored]", color=ui.YELLOW)
            return

        # Same fact with a changed value? Retire the old one rather
        # than keeping both and telling the model two contradictory
        # things.
        conflicts = memory_logic.find_conflicts(memory, memories)

        for i in conflicts:
            memories[i]["superseded"] = True
            memories[i]["superseded_at"] = str(datetime.now())

        if conflicts:
            old = memories[conflicts[0]]["memory"]

        entry = {
            "memory": memory,
            "category": category,
            "confidence": confidence,
            "created": str(datetime.now()),
        }

        memories.append(entry)
        _prune_memories()
        save_json(MEMORY_FILE, memories)

    if SHOW_MEMORY_EVENTS:
        if old is not None:
            ui.print_framed(f"[Memory Updated] {old}", color=ui.YELLOW)
            ui.print_framed(f"             now: {memory}", color=ui.GREEN)
        else:
            ui.print_framed(f"[Memory Saved] {memory}", color=ui.GREEN)


def show_memories():
    with _lock:
        active = memory_logic.active(memories)

    if not active:
        ui.print_framed("No memories stored.", color=ui.YELLOW)
        return

    ui.print_framed("========== MEMORIES ==========", color=ui.VIOLET)

    for item in active:
        ui.print_framed(f"[{item.get('category', 'unknown')}]", color=ui.MAGENTA)
        ui.print_framed(item.get("memory", ""))
        ui.print_framed(f"Confidence: {item.get('confidence', 0)}")


def active_memories():
    """Thread-safe snapshot of facts that are still considered true."""
    with _lock:
        return list(memory_logic.active(memories))


def forget_memory(search):
    global memories

    with _lock:
        before = len(memories)

        memories = [
            item
            for item in memories
            if search.lower() not in item["memory"].lower()
        ]

        save_json(MEMORY_FILE, memories)
        removed = before - len(memories)

    return removed


# ============================================================
# CONVERSATION HISTORY
# ============================================================

def append_history(block):
    """Persist a chat block to disk and keep the in-memory copy in sync."""
    global conversation_history

    block = dev_auth.redact_credential_like_text(block)
    conversation_history += block

    if len(conversation_history) > MAX_HISTORY_CHARS:
        # Rewrite rather than append once over the cap, so the file
        # actually shrinks back down instead of growing forever.
        conversation_history = conversation_history[-MAX_HISTORY_CHARS:]
        save_text(HISTORY_FILE, conversation_history)
    else:
        append_file(HISTORY_FILE, block)
