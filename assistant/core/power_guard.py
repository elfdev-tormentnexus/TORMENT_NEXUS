"""Keep an active Sable session from being interrupted by Windows idle power.

Windows display sleep can remove an HDMI/DisplayPort audio endpoint.  That
invalidates both local playback and the visualizer's loopback capture even
though Sable itself is still running.  The execution-state request is scoped
to the thread that owns it and Windows removes it automatically if that thread
ends unexpectedly.
"""

import os


ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_CONTINUOUS = 0x80000000


def prevent_idle_sleep(kernel32=None):
    """Keep the display and computer awake until ``allow_idle_sleep``."""
    if os.name != "nt":
        return False

    try:
        if kernel32 is None:
            import ctypes

            kernel32 = ctypes.windll.kernel32

        result = kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        return bool(result)
    except Exception:
        # Power management is a convenience, never a reason Sable should fail
        # to launch on a restricted or unusual Windows host.
        return False


def allow_idle_sleep(kernel32=None):
    """Release this thread's persistent Windows execution-state request."""
    if os.name != "nt":
        return False

    try:
        if kernel32 is None:
            import ctypes

            kernel32 = ctypes.windll.kernel32

        result = kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        return bool(result)
    except Exception:
        return False
