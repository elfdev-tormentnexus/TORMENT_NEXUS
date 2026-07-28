"""
Grounded awareness of what the machine has been doing between conversations.

This is the spatial counterpart to time_awareness, and it carries the same
restriction. That module knows time passed because a timestamp says so, not
because it waited. This one knows an application was in the foreground
because a sample recorded it, not because it was watching. Everything here
is an observation with a time on it, and the wording downstream has to stay
on the right side of that line: "Blender was in front for three hours" is
true, "I watched you work" is not.

Samples are taken on a background thread. Windows exposes everything needed
through user32 and kernel32, so nothing here adds a dependency, and on any
other platform the sampler degrades to whatever it can read rather than
failing.

When the operator opts in, observations persist across restarts, which is
what lets it notice that an application was in front yesterday too. What is
written is a change log, not a stream of samples: a line is added when the
foreground application or title changes, when the operator leaves or returns,
and otherwise at a slow heartbeat.

Window titles routinely contain file names, URLs and message previews. The
log is local-only, gitignored, excluded from release packaging and bug
reports (see DENY_PATTERNS in tools/package_release.py), aged out on every
load and write, and erasable with one command.
"""

import json
import os
import platform
import threading
import time
from collections import Counter, deque
from datetime import datetime, timedelta


# How often the sampler looks, and how much history it keeps. Twenty seconds
# is frequent enough to catch a short task and cheap enough to ignore.
SAMPLE_SECONDS = 20.0
HISTORY_HOURS = 24.0

# Beyond this the user is treated as away from the keyboard rather than
# merely quiet. Chosen to sit above a long read and below a coffee break.
IDLE_AWAY_SECONDS = 300.0

# How long the log may go without a line when nothing is changing. Keeps a
# long unattended stretch represented without recording it minute by minute.
HEARTBEAT_SECONDS = 900.0

# Default retention when the caller does not supply one. core.config carries
# the configurable value; this keeps the module importable on its own.
RETENTION_DAYS = 14.0

_IS_WINDOWS = platform.system() == "Windows"


def _encode(snapshot):
    """One log line. Short keys: this file is appended to for a fortnight."""
    entry = {"t": round(snapshot.taken_at.timestamp(), 1)}

    if snapshot.app:
        entry["a"] = snapshot.app
    if snapshot.title:
        entry["w"] = snapshot.title
    if snapshot.idle_seconds:
        entry["i"] = round(float(snapshot.idle_seconds), 1)
    for key, value in (
        ("c", snapshot.cpu_percent),
        ("m", snapshot.memory_percent),
        ("b", snapshot.battery_percent),
    ):
        if value is not None:
            entry[key] = round(float(value), 1)
    if snapshot.on_battery is not None:
        entry["p"] = bool(snapshot.on_battery)

    return json.dumps(entry, ensure_ascii=False, separators=(",", ":"))


class Snapshot:
    """One observation of machine state, with the time it was taken."""

    __slots__ = (
        "taken_at",
        "app",
        "title",
        "idle_seconds",
        "cpu_percent",
        "memory_percent",
        "battery_percent",
        "on_battery",
    )

    def __init__(
        self,
        taken_at,
        app=None,
        title=None,
        idle_seconds=0.0,
        cpu_percent=None,
        memory_percent=None,
        battery_percent=None,
        on_battery=None,
    ):
        self.taken_at = taken_at
        self.app = app
        self.title = title
        self.idle_seconds = idle_seconds
        self.cpu_percent = cpu_percent
        self.memory_percent = memory_percent
        self.battery_percent = battery_percent
        self.on_battery = on_battery

    @property
    def away(self):
        return self.idle_seconds >= IDLE_AWAY_SECONDS


# ------------------------------------------------------------------
# Platform probes. Each returns None rather than raising, so one
# unavailable reading never costs the others.
# ------------------------------------------------------------------

def _windows_foreground():
    """Foreground executable name and window title."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    handle = user32.GetForegroundWindow()

    if not handle:
        return None, None

    length = user32.GetWindowTextLengthW(handle)
    title = None

    if length > 0:
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, buffer, length + 1)
        title = buffer.value or None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    app = None

    if pid.value:
        # PROCESS_QUERY_LIMITED_INFORMATION: enough for the image name and
        # permitted for processes this one may not otherwise open.
        process = kernel32.OpenProcess(0x1000, False, pid.value)

        if process:
            try:
                size = wintypes.DWORD(260)
                buffer = ctypes.create_unicode_buffer(size.value)

                if kernel32.QueryFullProcessImageNameW(
                    process, 0, buffer, ctypes.byref(size)
                ):
                    app = os.path.basename(buffer.value) or None
            finally:
                kernel32.CloseHandle(process)

    return app, title


def _windows_idle_seconds():
    """Seconds since the last keyboard or mouse input."""
    import ctypes
    from ctypes import wintypes

    class LastInput(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("dwTime", wintypes.DWORD),
        ]

    info = LastInput()
    info.cbSize = ctypes.sizeof(LastInput)

    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None

    ticks = ctypes.windll.kernel32.GetTickCount64()
    return max(0.0, (ticks - info.dwTime) / 1000.0)


def _windows_memory_percent():
    import ctypes
    from ctypes import wintypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)

    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None

    return float(status.dwMemoryLoad)


def _windows_battery():
    import ctypes
    from ctypes import wintypes

    class PowerStatus(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", wintypes.BYTE),
            ("BatteryFlag", wintypes.BYTE),
            ("BatteryLifePercent", wintypes.BYTE),
            ("SystemStatusFlag", wintypes.BYTE),
            ("BatteryLifeTime", wintypes.DWORD),
            ("BatteryFullLifeTime", wintypes.DWORD),
        ]

    status = PowerStatus()

    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return None, None

    percent = int(status.BatteryLifePercent)
    on_battery = int(status.ACLineStatus) == 0

    # 255 is the documented "unknown" value, and no battery reports 255%.
    return (percent if percent <= 100 else None), on_battery


class _CpuSampler:
    """CPU load between consecutive calls, from kernel tick counters."""

    def __init__(self):
        self._previous = None

    def percent(self):
        if not _IS_WINDOWS:
            return None

        import ctypes
        from ctypes import wintypes

        idle = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()

        if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            return None

        def total(value):
            return (value.dwHighDateTime << 32) | value.dwLowDateTime

        current = (total(idle), total(kernel) + total(user))
        previous, self._previous = self._previous, current

        if previous is None:
            return None

        idle_delta = current[0] - previous[0]
        busy_delta = current[1] - previous[1]

        if busy_delta <= 0:
            return None

        return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / busy_delta)))


def _safe(probe, default=None):
    try:
        return probe()
    except Exception:
        return default


class SystemAwareness:
    """Samples machine state on a background thread and summarises it."""

    def __init__(self, sample_seconds=SAMPLE_SECONDS,
                 history_hours=HISTORY_HOURS,
                 store_path=None, retention_days=None,
                 enabled=True, preference_path=None):
        self._lock = threading.RLock()
        self._samples = deque()
        self._sample_seconds = max(1.0, float(sample_seconds))
        self._history = timedelta(hours=max(0.1, float(history_hours)))
        self._thread = None
        self._stop = threading.Event()
        self._cpu = _CpuSampler()
        self._enabled = bool(enabled)
        self._store_path = store_path
        self._preference_path = preference_path
        self._retention = timedelta(
            days=max(0.0, float(
                RETENTION_DAYS if retention_days is None else retention_days
            ))
        )
        self._last_written = None
        self._last_write_at = None
        self._load_preference()

    # -- persistence ----------------------------------------------

    def _load_preference(self):
        path = self._preference_path
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            if isinstance(value, dict) and isinstance(value.get("enabled"), bool):
                self._enabled = value["enabled"]
        except (OSError, ValueError, TypeError):
            # Missing or malformed consent never opts a fresh install in.
            pass

    def _save_preference(self):
        path = self._preference_path
        if not path:
            return
        try:
            folder = os.path.dirname(path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            temporary = path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump({"enabled": self.enabled}, handle)
            os.replace(temporary, path)
        except OSError:
            pass

    def load(self):
        """Read back what was observed before this run, dropping stale lines."""
        if not self.enabled:
            return 0

        path = self._store_path

        if not path or not os.path.isfile(path):
            return 0

        cutoff = datetime.now().astimezone() - self._retention
        recovered = []

        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        taken = datetime.fromtimestamp(
                            float(entry["t"])
                        ).astimezone()
                    except (ValueError, TypeError, KeyError):
                        # One corrupt line must not cost the whole history.
                        continue

                    if taken < cutoff:
                        continue

                    recovered.append(Snapshot(
                        taken_at=taken,
                        app=entry.get("a"),
                        title=entry.get("w"),
                        idle_seconds=float(entry.get("i", 0.0)),
                        cpu_percent=entry.get("c"),
                        memory_percent=entry.get("m"),
                        battery_percent=entry.get("b"),
                        on_battery=entry.get("p"),
                    ))
        except OSError:
            return 0

        with self._lock:
            self._samples.extend(recovered)

        # Rewriting drops the aged-out lines from disk too, so the file is
        # pruned by using the program rather than growing until asked.
        self._rewrite(recovered)
        return len(recovered)

    def _rewrite(self, snapshots):
        path = self._store_path

        if not path:
            return

        try:
            folder = os.path.dirname(path)

            if folder:
                os.makedirs(folder, exist_ok=True)

            temporary = path + ".tmp"

            with open(temporary, "w", encoding="utf-8") as handle:
                for snapshot in snapshots:
                    handle.write(_encode(snapshot) + "\n")

            os.replace(temporary, path)
        except OSError:
            pass

    def _append(self, snapshot):
        """
        Record a line only when something changed.

        Writing every sample would mean four thousand near-identical lines a
        day. A change log says the same thing in a fraction of the space and
        can be read by a human deciding whether to keep it.
        """
        path = self._store_path

        if not path:
            return

        previous = self._last_written
        changed = (
            previous is None
            or previous.app != snapshot.app
            or previous.title != snapshot.title
            or previous.away != snapshot.away
        )
        stale = (
            self._last_write_at is None
            or (snapshot.taken_at - self._last_write_at).total_seconds()
            >= HEARTBEAT_SECONDS
        )

        if not (changed or stale):
            return

        try:
            folder = os.path.dirname(path)

            if folder:
                os.makedirs(folder, exist_ok=True)

            with open(path, "a", encoding="utf-8") as handle:
                handle.write(_encode(snapshot) + "\n")

            self._last_written = snapshot
            self._last_write_at = snapshot.taken_at
        except OSError:
            pass

    # -- lifecycle ------------------------------------------------

    def start(self):
        with self._lock:
            if self._thread is not None:
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="system-awareness",
                daemon=True,
            )
            self._thread.start()

    def stop(self):
        self._stop.set()
        with self._lock:
            thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def set_enabled(self, enabled):
        """
        Pause or resume sampling without tearing the thread down.

        Turning it off is also the privacy deletion operation promised by the
        command: retained window titles must not reappear after a restart.
        """
        enabled = bool(enabled)
        with self._lock:
            was_enabled = self._enabled
            self._enabled = enabled

        if not enabled:
            self.forget()
        elif not was_enabled:
            # Explicit opt-in may restore an earlier opted-in log. A fresh
            # package has no such file.
            self.load()

        self._save_preference()
        return enabled

    @property
    def enabled(self):
        with self._lock:
            return self._enabled

    def forget(self):
        """Discard everything observed so far, on disk as well as in memory."""
        with self._lock:
            count = len(self._samples)
            self._samples.clear()
            self._last_written = None
            self._last_write_at = None

        if self._store_path:
            try:
                os.remove(self._store_path)
            except OSError:
                pass

        return count

    @property
    def retention_days(self):
        return self._retention.total_seconds() / (24 * 60 * 60)

    # -- sampling -------------------------------------------------

    def sample(self):
        """Take one observation. Safe to call on any platform."""
        app = title = None
        idle = 0.0
        battery = on_battery = None
        memory = None

        if _IS_WINDOWS:
            app, title = _safe(_windows_foreground, (None, None))
            idle = _safe(_windows_idle_seconds, 0.0) or 0.0
            memory = _safe(_windows_memory_percent)
            battery, on_battery = _safe(_windows_battery, (None, None))

        return Snapshot(
            taken_at=datetime.now().astimezone(),
            app=app,
            title=title,
            idle_seconds=idle,
            cpu_percent=_safe(self._cpu.percent),
            memory_percent=memory,
            battery_percent=battery,
            on_battery=on_battery,
        )

    def _run(self):
        while not self._stop.is_set():
            if self.enabled:
                try:
                    self._record(self.sample())
                except Exception:
                    # Ambient awareness must never take the assistant down.
                    pass
            self._stop.wait(self._sample_seconds)

    def _record(self, snapshot):
        with self._lock:
            self._samples.append(snapshot)
            # With a store, memory mirrors the retained window, or a load
            # would be pruned away the moment the next sample arrived.
            # Without one, history_hours is the only bound there is.
            window = (
                max(self._history, self._retention)
                if self._store_path
                else self._history
            )
            cutoff = snapshot.taken_at - window

            while self._samples and self._samples[0].taken_at < cutoff:
                self._samples.popleft()

        self._append(snapshot)

    def snapshots(self, since=None):
        with self._lock:
            if since is None:
                return list(self._samples)
            return [s for s in self._samples if s.taken_at >= since]

    @property
    def latest(self):
        with self._lock:
            return self._samples[-1] if self._samples else None

    # -- summary --------------------------------------------------

    def foreground_runs(self, since=None):
        """Contiguous stretches of one application being in front."""
        runs = []

        for snapshot in self.snapshots(since):
            if snapshot.away or not snapshot.app:
                continue
            if runs and runs[-1][0] == snapshot.app:
                runs[-1][2] = snapshot.taken_at
                runs[-1][3] += 1
            else:
                runs.append([snapshot.app, snapshot.taken_at,
                             snapshot.taken_at, 1])

        return [
            (app, start, end, count * self._sample_seconds)
            for app, start, end, count in runs
        ]

    def describe(self, since=None, include_titles=True, limit=3):
        """
        A plain statement of what was observed, in observational language.

        Deliberately reports samples, not experience. The caller may put this
        in front of the model; it must not licence a claim to have watched.
        """
        samples = self.snapshots(since)

        if not samples:
            return ""

        span = (samples[-1].taken_at - samples[0].taken_at).total_seconds()
        pieces = []

        totals = Counter()
        for snapshot in samples:
            if snapshot.app and not snapshot.away:
                totals[snapshot.app] += self._sample_seconds

        if totals:
            ranked = totals.most_common(max(1, limit))
            described = ", ".join(
                "%s for %s" % (app, _duration(seconds))
                for app, seconds in ranked
            )
            pieces.append("In front during that period: " + described + ".")

        latest = samples[-1]

        if latest.away:
            pieces.append(
                "No keyboard or mouse input for %s."
                % _duration(latest.idle_seconds)
            )
        elif latest.app:
            current = latest.app
            if include_titles and latest.title:
                current += ' -- "%s"' % _clip(latest.title, 70)
            pieces.append("Most recent sample: " + current + ".")

        away_samples = sum(1 for s in samples if s.away)

        if span > 0 and away_samples:
            share = away_samples / len(samples)
            if share > 0.25:
                pieces.append(
                    "Away from the keyboard for roughly %d%% of it."
                    % round(share * 100)
                )

        if latest.on_battery and latest.battery_percent is not None:
            pieces.append(
                "On battery, %d%%." % latest.battery_percent
            )

        if latest.cpu_percent is not None and latest.cpu_percent >= 70:
            pieces.append(
                "The machine is working hard (%d%% CPU)."
                % round(latest.cpu_percent)
            )

        return " ".join(pieces)


def _clip(text, limit):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _duration(seconds):
    """Coarse, honest durations. Sampling cannot justify finer than this."""
    try:
        total = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "no time"

    if total < 60:
        return "under a minute"

    minutes = total // 60

    if minutes < 60:
        return "%d minute%s" % (minutes, "" if minutes == 1 else "s")

    hours, minutes = divmod(minutes, 60)

    if not minutes:
        return "%d hour%s" % (hours, "" if hours == 1 else "s")

    return "%dh%02dm" % (hours, minutes)
