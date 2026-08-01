"""Small state hand-off between the command registry and main chat loop."""

_START_REQUESTED = False
_SONG_REQUESTED = None


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


def request_song(song_request):
    """Queue one trusted key or validated Song for the audio-session hand-off."""
    global _SONG_REQUESTED

    if song_request is None:
        raise ValueError("song_request must not be blank")

    if isinstance(song_request, str) and not song_request.strip():
        raise ValueError("song_request must not be blank")

    _SONG_REQUESTED = song_request


def consume_song_request():
    global _SONG_REQUESTED
    requested = _SONG_REQUESTED
    _SONG_REQUESTED = None
    return requested


def clear_song_request():
    global _SONG_REQUESTED
    _SONG_REQUESTED = None


def request_daisy_bell():
    request_song("daisy_bell")


def consume_daisy_bell_request():
    global _SONG_REQUESTED

    if _SONG_REQUESTED != "daisy_bell":
        return False

    _SONG_REQUESTED = None
    return True


def clear_daisy_bell_request():
    global _SONG_REQUESTED

    if _SONG_REQUESTED == "daisy_bell":
        _SONG_REQUESTED = None
