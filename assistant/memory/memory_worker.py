"""
Runs memory extraction off the chat loop.

ask_memory_ai() is a second, separate inference against the same
server. Running it inline meant the input prompt stayed blocked for
its whole duration after the visible reply had already finished --
invisible before streaming, glaring once the reply arrives fast.

Design notes:

- ONE worker, fed by a queue. Fire off three messages quickly and the
  extractions run one after another instead of three inferences
  fighting each other and the main generation for the same model.

- The worker holds off while the assistant is generating. Memory
  extraction is never urgent; the user waiting on tokens always is.
"""

import queue
import threading
import time

from core.config import DEBUG


_q = queue.Queue()
_thread = None
_stop = threading.Event()
_active = threading.Event()

_process_fn = None
_is_busy_fn = None

# Let a newly submitted foreground message claim the model first.
# This also keeps rapid back-and-forth chat from being interrupted by
# an invisible extraction request.
IDLE_GRACE_SECONDS = 5.0


def _worker():
    while not _stop.is_set():
        try:
            item = _q.get(timeout=0.4)
        except queue.Empty:
            continue

        try:
            grace_end = time.time() + IDLE_GRACE_SECONDS

            while time.time() < grace_end and not _stop.is_set():
                if _is_busy_fn is not None and _is_busy_fn():
                    grace_end = time.time() + IDLE_GRACE_SECONDS
                time.sleep(0.1)

            # Yield to the foreground generation before spending the
            # model on something nobody is waiting for.
            if _is_busy_fn is not None:
                waited = 0.0

                while _is_busy_fn() and not _stop.is_set() and waited < 120.0:
                    time.sleep(0.1)
                    waited += 0.1

            if not _stop.is_set() and _process_fn is not None:
                _active.set()
                try:
                    _process_fn(*item)
                finally:
                    _active.clear()

        except Exception as e:
            # A failed extraction must never take the chat down.
            if DEBUG:
                print(f"[memory worker] extraction failed: {e}")

        finally:
            _q.task_done()


def start(process_fn, is_busy_fn=None):
    """
    process_fn(user_input, assistant_reply) -- the extraction to run.
    is_busy_fn() -> bool                    -- True while generating.
    """
    global _thread, _process_fn, _is_busy_fn

    if _thread is not None:
        return

    _process_fn = process_fn
    _is_busy_fn = is_busy_fn

    _stop.clear()
    _thread = threading.Thread(target=_worker, daemon=True)
    _thread.start()


def submit(user_input, assistant_reply):
    """Hand an exchange to the worker and return immediately."""
    if _thread is None:
        return

    _q.put((user_input, assistant_reply))


def pending():
    return _q.qsize()


def active():
    """Whether the shared director is inside memory extraction right now."""
    return _active.is_set()


def stop(drain_seconds=2.0):
    """
    Give queued extractions a moment to land, then shut down. Anything
    still queued is dropped -- a missed memory is not worth hanging
    the exit on.
    """
    global _thread, _process_fn, _is_busy_fn

    deadline = time.time() + drain_seconds

    while not _q.empty() and time.time() < deadline:
        time.sleep(0.05)

    _stop.set()

    if _thread is not None:
        _thread.join(timeout=1.0)

    while True:
        try:
            _q.get_nowait()
        except queue.Empty:
            break
        else:
            _q.task_done()

    # Do not pretend a blocked callback has stopped. Keeping the live
    # thread reference prevents start() from launching a second worker
    # against the same model and queue.
    if _thread is None or not _thread.is_alive():
        _thread = None
        _process_fn = None
        _is_busy_fn = None
        _active.clear()
