"""
Offline playback of audio files kept in the local music library.

This exists because the Spotify controls next door need an account, a
network round trip, and a live internet connection, none of which the Pi
is guaranteed to have. Anything dropped into the library folder plays
with no network at all.

Decoding is soundfile/libsndfile, which handles MP3, FLAC, OGG and WAV
without any extra dependency -- the same two libraries the voice stack
already pulls in. Nothing new has to be installed for this to work.

Audio is streamed from disk rather than decoded up front. A 45-minute
MP3 is roughly 470 MB once expanded to float32, which is most of a Pi's
RAM for one track; streaming holds a few blocks instead, and makes
playback start instantly regardless of file length.

Playback runs on its own OutputStream instead of sounddevice's module
level play(), which the voice code owns. Two streams means TORMENT_NEXUS can
answer you without cutting the music off, and `sd.stop()` during speech
does not touch this one.
"""

import contextlib
import os
import queue
import threading


# Formats libsndfile handles locally. Kept explicit rather than accepting
# anything, so a stray .txt in the folder is not offered as a track.
AUDIO_SUFFIXES = (".mp3", ".flac", ".ogg", ".oga", ".wav", ".aiff", ".aif")

BLOCK_FRAMES = 2048

# Decoded blocks held ahead of the speaker. The callback must never wait
# on disk or on the MP3 decoder, so a reader thread stays this far in
# front of it. Eight blocks is roughly 0.37s at 44.1kHz -- enough to ride
# out a slow read on a Pi's SD card without a noticeable stop delay.
QUEUE_BLOCKS = 8


class LocalPlaybackError(Exception):
    """Raised for anything the operator should read as a plain message."""


@contextlib.contextmanager
def _muted_stderr():
    """
    Silence libmpg123's ID3 chatter while a file is opened.

    It writes parser complaints straight to file descriptor 2 from C, so
    a Python-level redirect does not catch them. Left alone they print
    over the terminal UI mid-frame. Only the open is wrapped, so genuine
    errors raised as exceptions still surface normally.
    """
    try:
        saved = os.dup(2)
    except (AttributeError, OSError):
        yield
        return

    try:
        with open(os.devnull, "wb") as devnull:
            os.dup2(devnull.fileno(), 2)
        yield
    finally:
        try:
            os.dup2(saved, 2)
        finally:
            os.close(saved)


def library_dir():
    from core.config import MUSIC_LIBRARY_DIR

    return MUSIC_LIBRARY_DIR


def available_tracks():
    """(display name, full path) for every playable file, name-sorted."""
    folder = library_dir()

    if not os.path.isdir(folder):
        return []

    found = []

    for entry in sorted(os.listdir(folder)):
        path = os.path.join(folder, entry)

        if not os.path.isfile(path):
            continue

        stem, suffix = os.path.splitext(entry)

        if suffix.lower() in AUDIO_SUFFIXES:
            found.append((stem, path))

    return found


def find_track(query):
    """
    Resolve a typed name to one track.

    Matching widens only as far as it has to: exact, then prefix, then
    substring. A single match at any stage wins outright, so "play
    breakcore" is unambiguous even once the folder fills up with names
    that merely contain the word.
    """
    query = (query or "").strip().lower()

    if not query:
        return None, []

    tracks = available_tracks()

    for test in (
        lambda name: name == query,
        lambda name: name.startswith(query),
        lambda name: query in name,
    ):
        matches = [t for t in tracks if test(t[0].lower())]

        if len(matches) == 1:
            return matches[0], []
        if len(matches) > 1:
            return None, [name for name, _ in matches]

    return None, []


class LocalPlayer:
    """One output stream, one track at a time."""

    def __init__(self):
        self._lock = threading.RLock()
        self._stream = None
        self._handle = None
        self._reader = None
        self._blocks = None
        self._stop_reading = None
        self._name = None
        self._paused = False
        self._frames_played = 0
        self._total_frames = 0
        self._samplerate = 0
        self._volume = 1.0
        self._finished = threading.Event()

    # -- state ------------------------------------------------------

    def is_loaded(self):
        # A track that has run to its end leaves the stream object behind
        # until something calls stop(), so the finished flag -- not the
        # stream's existence -- is what says whether audio is still live.
        # Without this, "now playing" keeps reporting a track that ended
        # minutes ago.
        with self._lock:
            return self._stream is not None and not self._finished.is_set()

    def is_playing(self):
        return self.is_loaded() and not self._paused

    def current_track(self):
        with self._lock:
            return self._name

    def position(self):
        """(elapsed seconds, total seconds) for the loaded track."""
        with self._lock:
            if not self._samplerate:
                return 0.0, 0.0

            return (
                self._frames_played / self._samplerate,
                self._total_frames / self._samplerate,
            )

    def volume(self):
        """Current local-playback gain, from silent (0.0) to full (1.0)."""
        with self._lock:
            return self._volume

    def set_volume(self, volume):
        """Change local playback gain immediately and retain it for next track."""
        try:
            value = float(volume)
        except (TypeError, ValueError):
            value = 1.0
        with self._lock:
            self._volume = max(0.0, min(1.0, value))
            return self._volume

    # -- transport --------------------------------------------------

    def play(self, name, path):
        """Load and start a file, replacing whatever was playing."""
        try:
            import sounddevice as sd
            import soundfile as sf
        except ImportError as error:
            raise LocalPlaybackError(
                "Local playback needs the voice extras "
                f"(sounddevice, soundfile): {error}"
            ) from error

        self.stop()

        try:
            with _muted_stderr():
                handle = sf.SoundFile(path)
        except Exception as error:
            raise LocalPlaybackError(f"Could not open {name}: {error}") from error

        with self._lock:
            self._handle = handle
            self._name = name
            self._paused = False
            self._frames_played = 0
            self._total_frames = handle.frames
            self._samplerate = handle.samplerate
            self._blocks = queue.Queue(maxsize=QUEUE_BLOCKS)
            self._stop_reading = threading.Event()
            self._finished.clear()

            channels = handle.channels
            samplerate = handle.samplerate

        self._reader = threading.Thread(
            target=self._read_ahead,
            name="local-music-reader",
            daemon=True,
        )
        self._reader.start()

        try:
            stream = sd.OutputStream(
                samplerate=samplerate,
                channels=channels,
                blocksize=BLOCK_FRAMES,
                callback=self._feed,
                finished_callback=self._finished.set,
            )
            stream.start()
        except Exception as error:
            self.stop()
            raise LocalPlaybackError(
                f"Could not open an audio output for {name}: {error}"
            ) from error

        with self._lock:
            self._stream = stream

        return True

    def pause(self):
        with self._lock:
            if self._stream is None or self._paused:
                return False

            self._paused = True

        return True

    def resume(self):
        with self._lock:
            if self._stream is None or not self._paused:
                return False

            self._paused = False

        return True

    def stop(self):
        """Tear everything down. Safe to call when nothing is playing."""
        with self._lock:
            stream, handle = self._stream, self._handle
            reader, stopper = self._reader, self._stop_reading
            blocks = self._blocks
            self._stream = self._handle = self._reader = None
            self._blocks = self._stop_reading = None
            self._name = None
            self._paused = False
            self._frames_played = self._total_frames = self._samplerate = 0

        if stopper is not None:
            stopper.set()

        # Unblock a reader parked on a full queue so it can see the stop.
        if blocks is not None:
            try:
                blocks.get_nowait()
            except queue.Empty:
                pass

        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=1.0)

        for closer in (stream, handle):
            if closer is None:
                continue
            try:
                closer.close()
            except Exception:
                pass

        return stream is not None

    # -- internals --------------------------------------------------

    def _read_ahead(self):
        """Decode on a worker thread so the audio callback never blocks."""
        with self._lock:
            handle, blocks = self._handle, self._blocks
            stopper = self._stop_reading

        if handle is None or blocks is None:
            return

        try:
            while not stopper.is_set():
                data = handle.read(
                    BLOCK_FRAMES,
                    dtype="float32",
                    always_2d=True,
                )

                if not len(data):
                    break

                while not stopper.is_set():
                    try:
                        blocks.put(data, timeout=0.1)
                        break
                    except queue.Full:
                        continue
        except Exception:
            # A decode failure ends the track rather than taking the
            # assistant down; the callback sees the sentinel and stops.
            pass

        with contextlib.suppress(Exception):
            blocks.put(None, timeout=0.5)

    def _feed(self, outdata, frames, time_info, status):
        import sounddevice as sd

        with self._lock:
            paused = self._paused
            blocks = self._blocks
            volume = self._volume

        if paused or blocks is None:
            outdata[:] = 0
            return

        try:
            data = blocks.get_nowait()
        except queue.Empty:
            # Underrun: emit silence rather than tearing the stream down,
            # so a momentarily slow disk is heard as a gap, not a crash.
            outdata[:] = 0
            return

        if data is None:
            outdata[:] = 0
            raise sd.CallbackStop

        count = min(len(data), frames)
        outdata[:count] = data[:count] * volume

        if count < frames:
            outdata[count:] = 0

        with self._lock:
            self._frames_played += count

        if count < frames:
            raise sd.CallbackStop


_player = None


def get_player():
    global _player

    if _player is None:
        _player = LocalPlayer()

    return _player
