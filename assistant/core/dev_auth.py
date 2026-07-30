"""Local owner authentication for developer-mode commands."""

import base64
import hashlib
import json
import math
import os
import re
import secrets
import time

from core.config import ASSISTANT_ROOT


PASSCODE_FILE = os.path.join(ASSISTANT_ROOT, ".dev_passcode")
# A Super Dev key is intentionally distinct from the ordinary developer
# credential.  The secret is never committed or displayed; this file
# stores only a salted verifier on the local machine.
SUPER_PASSCODE_FILE = os.path.join(ASSISTANT_ROOT, ".super_dev_passcode")
PBKDF2_ITERATIONS = 350_000
SALT_BYTES = 16
MIN_PASSCODE_LENGTH = 8
MAX_PASSCODE_LENGTH = 32
FAILURES_BEFORE_LOCKOUT = 3
LOCKOUT_SECONDS = 30
HIDDEN_NUMERIC_CREDENTIAL = "[numeric credential hidden]"
_NUMERIC_CREDENTIAL_RE = re.compile(r"(?<!\d)\d{8,}(?!\d)")

_failed_attempts = 0
_locked_until = 0.0
_super_failed_attempts = 0
_super_locked_until = 0.0


class DevAuthError(RuntimeError):
    """A credential file could not be created or safely interpreted."""


def is_configured():
    return os.path.isfile(PASSCODE_FILE)


def is_super_configured():
    return os.path.isfile(SUPER_PASSCODE_FILE)


def is_credential_like_input(text):
    """Return True for a whole input that resembles a numeric credential."""
    return bool(
        isinstance(text, str)
        and _NUMERIC_CREDENTIAL_RE.fullmatch(text.strip())
    )


def is_numeric_input_in_progress(text):
    """Mask a digits-only draft immediately, before it reaches full length."""
    return bool(isinstance(text, str) and text and text.isascii() and text.isdigit())


def redact_credential_like_text(text):
    """Remove long numeric sequences before display, prompting, or persistence."""
    if not isinstance(text, str):
        return text

    return _NUMERIC_CREDENTIAL_RE.sub(HIDDEN_NUMERIC_CREDENTIAL, text)


# A passcode drawing on letters as well as digits may be one character
# shorter, because the rule being preserved is the size of the search space,
# not the character count. Eight digits is 10^8. Seven characters from any
# alphabet that includes a letter is at least 36^7, roughly 780 times larger.
# So this is a relaxation of the format and a tightening of the floor -- the
# shortest thing now accepted is harder to guess than the shortest thing
# accepted before.
MIN_ALPHANUMERIC_LENGTH = 7


def _passcode_problem(passcode):
    if not isinstance(passcode, str):
        return "The passcode was not text."
    if not passcode.isascii() or not passcode.isalnum():
        return "Use letters and digits only, with no spaces or symbols."

    minimum = (
        MIN_PASSCODE_LENGTH if passcode.isdigit() else MIN_ALPHANUMERIC_LENGTH
    )
    if not minimum <= len(passcode) <= MAX_PASSCODE_LENGTH:
        return (
            f"Use {MIN_PASSCODE_LENGTH} to {MAX_PASSCODE_LENGTH} digits, or "
            f"{MIN_ALPHANUMERIC_LENGTH} to {MAX_PASSCODE_LENGTH} characters "
            "if you include a letter."
        )
    return None


def _derive(passcode, salt, iterations):
    return hashlib.pbkdf2_hmac(
        "sha256",
        passcode.encode("utf-8"),
        salt,
        iterations,
    )


def _enroll_at(path, passcode, confirmation):
    """
    Create the local credential once.

    The passcode itself is never written. O_EXCL prevents a setup race or a
    later caller from silently replacing an established owner credential.
    """
    problem = _passcode_problem(passcode)

    if problem:
        raise DevAuthError(problem)
    if not secrets.compare_digest(passcode, confirmation):
        raise DevAuthError("The two entries did not match.")
    if os.path.isfile(path):
        raise DevAuthError("A passcode is already configured.")

    salt = secrets.token_bytes(SALT_BYTES)
    digest = _derive(passcode, salt, PBKDF2_ITERATIONS)
    payload = {
        "version": 1,
        "algorithm": "pbkdf2_sha256",
        "iterations": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "digest": base64.b64encode(digest).decode("ascii"),
    }

    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(payload, destination)
            destination.flush()
            os.fsync(destination.fileno())
    except FileExistsError as error:
        raise DevAuthError(
            "A passcode is already configured."
        ) from error
    except OSError as error:
        raise DevAuthError(
            "The credential could not be saved."
        ) from error


def enroll(passcode, confirmation):
    """Create the ordinary developer credential once."""
    return _enroll_at(PASSCODE_FILE, passcode, confirmation)


def enroll_super(passcode, confirmation):
    """Create the separate Super Dev credential once."""
    return _enroll_at(SUPER_PASSCODE_FILE, passcode, confirmation)


def _load_credential(path=None, label="Developer"):
    # Resolve the default at call time: tests and recovery tools can point the
    # local credential boundary at an isolated path without reimporting this
    # module.
    path = PASSCODE_FILE if path is None else path
    try:
        with open(path, "r", encoding="utf-8") as source:
            payload = json.load(source)

        if not isinstance(payload, dict):
            raise ValueError("invalid credential object")

        if (
            payload.get("version") != 1
            or payload.get("algorithm") != "pbkdf2_sha256"
        ):
            raise ValueError("unsupported credential format")

        iterations = int(payload["iterations"])

        if not 100_000 <= iterations <= 2_000_000:
            raise ValueError("unsafe iteration count")

        salt = base64.b64decode(payload["salt"], validate=True)
        digest = base64.b64decode(payload["digest"], validate=True)

        if len(salt) < 16 or len(digest) != 32:
            raise ValueError("invalid credential size")

        return salt, digest, iterations
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise DevAuthError(
            f"The {label.lower()} credential is unreadable. {label} mode "
            "remains locked; repair or remove its local credential file."
        ) from error


def verify(passcode):
    if not isinstance(passcode, str):
        return False

    salt, expected, iterations = _load_credential()
    actual = _derive(passcode, salt, iterations)
    return secrets.compare_digest(actual, expected)


def verify_super(passcode):
    if not isinstance(passcode, str):
        return False

    salt, expected, iterations = _load_credential(
        SUPER_PASSCODE_FILE, "Super Dev"
    )
    actual = _derive(passcode, salt, iterations)
    return secrets.compare_digest(actual, expected)


def retry_after():
    return max(0, math.ceil(_locked_until - time.monotonic()))


def _record_failure():
    global _failed_attempts, _locked_until

    _failed_attempts += 1

    if _failed_attempts < FAILURES_BEFORE_LOCKOUT:
        return 0

    _failed_attempts = 0
    _locked_until = time.monotonic() + LOCKOUT_SECONDS
    return LOCKOUT_SECONDS


def _record_success():
    global _failed_attempts, _locked_until
    _failed_attempts = 0
    _locked_until = 0.0


def reset_attempt_state_for_tests():
    """Reset only in-memory throttling; never alter the credential file."""
    _record_success()
    _record_super_success()


def _super_retry_after():
    return max(0, math.ceil(_super_locked_until - time.monotonic()))


def _record_super_failure():
    global _super_failed_attempts, _super_locked_until

    _super_failed_attempts += 1
    if _super_failed_attempts < FAILURES_BEFORE_LOCKOUT:
        return 0

    _super_failed_attempts = 0
    _super_locked_until = time.monotonic() + LOCKOUT_SECONDS
    return LOCKOUT_SECONDS


def _record_super_success():
    global _super_failed_attempts, _super_locked_until
    _super_failed_attempts = 0
    _super_locked_until = 0.0


def unlock_interactive(read_secret):
    """
    Enroll on first use or verify an established owner passcode.

    `read_secret(label)` is injected by the UI so this module never needs to
    echo, log, retain, or otherwise handle terminal presentation.
    """
    remaining = retry_after()

    if remaining:
        return (
            False,
            f"Developer mode is temporarily locked. Try again in "
            f"{remaining} seconds.",
        )

    if not is_configured():
        first = read_secret("CREATE OWNER PASSCODE >")

        if first is None:
            return False, "Passcode setup cancelled. Developer mode remains off."

        problem = _passcode_problem(first)

        if problem:
            return False, f"Passcode not created: {problem}"

        second = read_secret("CONFIRM OWNER PASSCODE >")

        if second is None:
            return False, "Passcode setup cancelled. Developer mode remains off."

        try:
            enroll(first, second)
        except DevAuthError as error:
            return False, f"Passcode not created: {error}"

        _record_success()
        return (
            True,
            "Owner passcode created.\n\nDeveloper mode: ON\n\n"
            "The two-entry setup is complete. Do not type the passcode again; "
            "the next 'YOU >' line is ordinary chat.\n\n"
            "Type 'dev help' for the command list.",
        )

    candidate = read_secret("OWNER PASSCODE >")

    if candidate is None:
        return False, "Developer unlock cancelled."

    try:
        accepted = verify(candidate)
    except DevAuthError as error:
        return False, str(error)

    if accepted:
        _record_success()
        return (
            True,
            "Developer mode: ON\n\nPasscode accepted. Do not type it again; "
            "the next 'YOU >' line is ordinary chat.\n\n"
            "Type 'dev help' for the command list.",
        )

    locked_for = _record_failure()

    if locked_for:
        return (
            False,
            "Incorrect passcode. Developer mode is locked for "
            f"{locked_for} seconds.",
        )

    attempts_left = FAILURES_BEFORE_LOCKOUT - _failed_attempts
    return (
        False,
        f"Incorrect passcode. {attempts_left} attempt"
        f"{'s' if attempts_left != 1 else ''} before a temporary lock.",
    )


def unlock_super_interactive(read_secret):
    """Enroll or verify the local key for the hazard-only mode."""
    remaining = _super_retry_after()
    if remaining:
        return False, f"Super Dev is temporarily locked. Try again in {remaining} seconds."

    if not is_super_configured():
        first = read_secret("CREATE SUPER DEV KEY >")
        if first is None:
            return False, "Super Dev setup cancelled."
        problem = _passcode_problem(first)
        if problem:
            return False, f"Super Dev key not created: {problem}"

        second = read_secret("CONFIRM SUPER DEV KEY >")
        if second is None:
            return False, "Super Dev setup cancelled."
        try:
            enroll_super(first, second)
        except DevAuthError as error:
            return False, f"Super Dev key not created: {error}"

        _record_super_success()
        return True, "Super Dev key created. The key is stored only as a local verifier."

    candidate = read_secret("SUPER DEV KEY >")
    if candidate is None:
        return False, "Super Dev unlock cancelled."

    try:
        accepted = verify_super(candidate)
    except DevAuthError as error:
        return False, str(error)

    if accepted:
        _record_super_success()
        return True, "Super Dev key accepted."

    locked_for = _record_super_failure()
    if locked_for:
        return False, f"Incorrect Super Dev key. Locked for {locked_for} seconds."

    attempts_left = FAILURES_BEFORE_LOCKOUT - _super_failed_attempts
    return (
        False,
        f"Incorrect Super Dev key. {attempts_left} attempt"
        f"{'s' if attempts_left != 1 else ''} before a temporary lock.",
    )
