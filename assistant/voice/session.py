"""Small state hand-off between the command registry and main chat loop."""

_START_REQUESTED = False
_DAISY_REQUESTED = False


class SilentReply(str):
    """A command result that should be shown but not spoken in audio mode."""


def silent_reply(text):
    return SilentReply(text)


def is_silent_reply(reply):
    return isinstance(reply, SilentReply)


def request_start():
    global _START_REQUESTED
    _START_REQUESTED = True


def consume_start_request():
    global _START_REQUESTED
    requested = _START_REQUESTED
    _START_REQUESTED = False
    return requested


def clear_start_request():
    global _START_REQUESTED
    _START_REQUESTED = False


def request_daisy_bell():
    global _DAISY_REQUESTED
    _DAISY_REQUESTED = True


def consume_daisy_bell_request():
    global _DAISY_REQUESTED
    requested = _DAISY_REQUESTED
    _DAISY_REQUESTED = False
    return requested


def clear_daisy_bell_request():
    global _DAISY_REQUESTED
    _DAISY_REQUESTED = False
