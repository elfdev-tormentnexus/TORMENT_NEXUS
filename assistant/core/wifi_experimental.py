"""A deliberately narrow bridge for an *external* Wi-Fi sensing experiment.

This is not a radio capture implementation.  Public AX211 CSI research tools
are not presently a safe Windows dependency, so TORMENT_NEXUS must not change
a wireless driver, enter monitor mode, transmit packets, or record raw radio
measurements.  A separately authorised experiment may instead write one small
aggregate JSON record to a local file.  This module reads only that record.

The boundary is intentionally boring:

    {
      "schema": 1,
      "source": "wifi-experimental",
      "state": "motion",
      "confidence": 0.81,
      "observed_at": 1760000000.0,
      "expiry_ms": 5000
    }

Only the four named states below are accepted.  There are no identities,
images, device addresses, packet contents, range traces, or retained samples.
That lets the companion react to a coarse, opt-in room-activity signal without
pretending that a radio experiment is vision or a record of a person.
"""

import json
import os
import threading
import time


SCHEMA_VERSION = 1
SOURCE_NAME = "wifi-experimental"
MAX_STATUS_BYTES = 4096
MAX_EXPIRY_SECONDS = 60.0
MAX_FUTURE_SECONDS = 2.0

# These deliberately describe a changing radio path, not a person.  An
# experiment can be wrong; it must never smuggle an identity or a story into
# the assistant through a free-form sensor label.
VALID_STATES = frozenset({"unknown", "still", "motion", "approach"})
RECORD_FIELDS = frozenset({
    "schema",
    "source",
    "state",
    "confidence",
    "observed_at",
    "expiry_ms",
})
_STATE_LABELS = {
    "unknown": "an indeterminate change",
    "still": "no recent movement",
    "motion": "movement",
    "approach": "approaching movement",
}


class Observation:
    """One validated, short-lived aggregate classification."""

    __slots__ = ("state", "confidence", "observed_at", "expiry_seconds")

    def __init__(self, state, confidence, observed_at, expiry_seconds):
        self.state = state
        self.confidence = confidence
        self.observed_at = observed_at
        self.expiry_seconds = expiry_seconds

    def age(self, now=None):
        return max(0.0, (time.time() if now is None else float(now)) - self.observed_at)

    def fresh(self, now=None):
        return self.age(now) <= self.expiry_seconds


def _number(value):
    """Return a finite float, rejecting bools and non-numeric input."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _parse_record(record, now=None):
    """Strictly validate a record from an untrusted local sidecar."""
    if (
        not isinstance(record, dict)
        or set(record) != RECORD_FIELDS
        or isinstance(record.get("schema"), bool)
        or record.get("schema") != SCHEMA_VERSION
        or record.get("source") != SOURCE_NAME
    ):
        return None

    state = record.get("state")
    if not isinstance(state, str):
        return None
    state = state.strip().lower()
    if state not in VALID_STATES:
        return None

    confidence = _number(record.get("confidence"))
    observed_at = _number(record.get("observed_at"))
    expiry_ms = _number(record.get("expiry_ms"))
    if confidence is None or observed_at is None or expiry_ms is None:
        return None
    if not 0.0 <= confidence <= 1.0 or not 100.0 <= expiry_ms <= MAX_EXPIRY_SECONDS * 1000:
        return None

    current = time.time() if now is None else float(now)
    if observed_at > current + MAX_FUTURE_SECONDS:
        return None

    return Observation(
        state=state,
        confidence=confidence,
        observed_at=observed_at,
        expiry_seconds=expiry_ms / 1000.0,
    )


class WifiExperimental:
    """Read one expiring aggregate status file; retain neither CSI nor history."""

    def __init__(self, status_path, enabled=False):
        configured = str(status_path or "").strip()
        self.status_path = os.path.abspath(configured) if configured else ""
        self._enabled = bool(enabled) and bool(self.status_path)
        self._lock = threading.RLock()
        self._latest = None
        self._last_problem = None
        self._discarded_through = None

    @property
    def enabled(self):
        with self._lock:
            return self._enabled

    @property
    def configured(self):
        return bool(self.status_path)

    def set_enabled(self, enabled):
        """Explicitly opt in/out; disabling also drops the current reading."""
        with self._lock:
            self._enabled = bool(enabled) and self.configured
            if not self._enabled:
                self._latest = None
                self._last_problem = None
                self._discarded_through = None
            return self._enabled

    def forget(self):
        """Drop the in-memory reading without deleting another tool's file."""
        with self._lock:
            existed = self._latest is not None
            if self._latest is not None:
                self._discarded_through = self._latest.observed_at
            self._latest = None
            self._last_problem = None
            return existed

    def _read_record(self):
        if not self.status_path:
            return None, "no local aggregate feed is configured"
        try:
            if os.path.getsize(self.status_path) > MAX_STATUS_BYTES:
                return None, "status file is too large"
            with open(self.status_path, "r", encoding="utf-8") as handle:
                return json.load(handle), None
        except FileNotFoundError:
            return None, "waiting for an experiment record"
        except (OSError, ValueError, json.JSONDecodeError):
            return None, "waiting for a valid aggregate record"

    def refresh(self, now=None):
        """Load one fresh classification, if the owner has enabled the bridge."""
        with self._lock:
            if not self._enabled:
                return None

        record, problem = self._read_record()
        observation = _parse_record(record, now=now) if record is not None else None
        current = time.time() if now is None else float(now)

        with self._lock:
            if not self._enabled:
                return None
            if observation is None:
                self._latest = None
                self._last_problem = problem or "waiting for a valid aggregate record"
                return None
            if (
                self._discarded_through is not None
                and observation.observed_at <= self._discarded_through
            ):
                self._latest = None
                self._last_problem = "current aggregate record was discarded"
                return None
            if not observation.fresh(current):
                self._latest = None
                self._last_problem = "last aggregate record has expired"
                return None
            self._latest = observation
            self._last_problem = None
            return observation

    def latest(self, now=None):
        return self.refresh(now=now)

    def describe(self, now=None):
        """Honest wording suitable for a model context or owner-facing status."""
        observation = self.refresh(now=now)
        if observation is None:
            return ""

        age = observation.age(now)
        age_text = "just now" if age < 1.0 else f"{int(round(age))}s ago"
        confidence = (
            "high" if observation.confidence >= 0.75
            else "medium" if observation.confidence >= 0.45
            else "low"
        )
        label = _STATE_LABELS[observation.state]
        return (
            "A local experimental Wi-Fi measurement classified the radio path "
            f"as {label} ({confidence} confidence, {age_text}). "
            "This is an aggregate signal, not visual observation or identity."
        )

    def status(self, now=None):
        """Short diagnostic output that never prints raw input or file contents."""
        if not self.enabled:
            return (
                "Wi-Fi experiment: OFF. It is not reading a status file or "
                "changing wireless hardware."
            )

        if not self.configured:
            return (
                "Wi-Fi experiment: ON, but no aggregate-feed path is configured. "
                "No wireless hardware has been changed."
            )

        observation = self.refresh(now=now)
        if observation is None:
            with self._lock:
                problem = self._last_problem or "waiting for an experiment record"
            return (
                "Wi-Fi experiment: ON, but no fresh aggregate reading "
                f"({problem}). No raw radio data is retained."
            )

        return "Wi-Fi experiment: ON. " + self.describe(now=now)
