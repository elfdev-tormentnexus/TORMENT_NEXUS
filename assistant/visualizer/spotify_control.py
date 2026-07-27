"""
Spotify remote control for music mode.

This is a remote, not an audio pipeline. It tells the Spotify client you
already have running what to play; that client produces the sound, the
system loopback in audio_source.py captures it, and the visualiser reacts.
Nothing here touches audio data, and no stream is intercepted or
re-encoded -- which is exactly why it is a clean way to drive the
visualiser rather than pulling audio out of a service that does not want
it pulled.

Requires Spotify Premium: the playback-control endpoints
(/me/player/play and friends) are Premium-only, and the API returns 403
for free accounts. Search and playlist listing work on any account, so
the module reports that distinction rather than failing opaquely.

Credentials come from the environment, never from the assistant's own
files or from chat:

    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
    SPOTIFY_REDIRECT_URI   (default http://127.0.0.1:8888/callback)

Register a free app at https://developer.spotify.com/dashboard to get the
first two, and add the redirect URI there verbatim.
"""

import os
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import quote


def _spotify_executable():
    """
    Locate the Spotify desktop client, or None.

    The Web API can only drive a player that already exists -- it cannot
    start one -- so being able to launch the client is what turns "no
    active device" from a dead end into a short wait.

    TORMENT_NEXUS_SPOTIFY_EXE overrides everything. Otherwise: the standard
    per-user Windows install, then the Start Menu shortcut's target, then
    anything named spotify on PATH (which covers Linux and the Pi, where
    the client may be a snap, flatpak shim, or spotifyd).
    """
    override = os.environ.get("TORMENT_NEXUS_SPOTIFY_EXE", "").strip()

    if override:
        return override if os.path.isfile(override) else None

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        candidate = os.path.join(appdata, "Spotify", "Spotify.exe")

        if os.path.isfile(candidate):
            return candidate

        shortcut = os.path.join(
            appdata,
            "Microsoft", "Windows", "Start Menu", "Programs", "Spotify.lnk",
        )

        if os.path.isfile(shortcut):
            try:
                import win32com.client  # type: ignore

                shell = win32com.client.Dispatch("WScript.Shell")
                target = shell.CreateShortcut(shortcut).TargetPath

                if target and os.path.isfile(target):
                    return target
            except Exception:
                # pywin32 is not a project dependency; the direct path
                # above already covers the normal install.
                pass

    return shutil.which("spotify")


SCOPES = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "playlist-read-private "
    "playlist-read-collaborative"
)

DEFAULT_REDIRECT = "http://127.0.0.1:8888/callback"


class SpotifyError(RuntimeError):
    pass


def _launch_desktop_client():
    """Start the installed Spotify client without inheriting the terminal."""
    executable = _spotify_executable()

    if not executable:
        return False

    try:
        # Detached: the client must outlive whichever command started it,
        # and its console output must not land in the terminal UI.
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.CREATE_NO_WINDOW
                | subprocess.DETACHED_PROCESS
            )
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen([executable], **kwargs)
        return True
    except Exception:
        return False


class SpotifyDesktop:
    """
    Credential-free helper for the locally installed Spotify desktop app.

    This deliberately never reads, copies, or packages Spotify's roaming
    profile. It only starts the user's existing client and asks Windows (or
    the desktop shell) to open a fixed Spotify protocol URI.
    """

    @staticmethod
    def launch():
        if not _spotify_executable():
            raise SpotifyError(
                "No Spotify desktop client was found. Install or open Spotify "
                "normally, or set TORMENT_NEXUS_SPOTIFY_EXE to its executable."
            )

        if not _launch_desktop_client():
            raise SpotifyError("Spotify was found but could not be started.")

        return "Opened the local Spotify desktop app."

    @staticmethod
    def _open_uri(uri):
        """Ask the OS to hand a fixed Spotify URI to the installed client."""
        try:
            if sys.platform == "win32":
                # startfile invokes the registered spotify: protocol. It does
                # not shell-parse the query and cannot run an arbitrary command.
                os.startfile(uri)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(
                    ["open", uri],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            else:
                subprocess.Popen(
                    ["xdg-open", uri],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            return True
        except Exception:
            return False

    @classmethod
    def search(cls, query):
        query = " ".join((query or "").split())

        if not query:
            raise SpotifyError("Give Spotify something to search for.")

        cls.launch()
        uri = "spotify:search:" + quote(query, safe="")

        if not cls._open_uri(uri):
            raise SpotifyError(
                "Spotify started, but Windows could not open its search link."
            )

        return f"Opened Spotify search: {query}"

    @classmethod
    def open_track(cls, track):
        """Open one API-returned track in the existing desktop client."""
        uri = (track or {}).get("uri") if isinstance(track, dict) else track

        if not isinstance(uri, str) or not re.fullmatch(
            r"spotify:track:[A-Za-z0-9]{22}", uri
        ):
            raise SpotifyError("That Spotify track selection is invalid.")

        cls.launch()

        if not cls._open_uri(uri):
            raise SpotifyError(
                "Spotify started, but Windows could not open the selected track."
            )

        name = (track or {}).get("name") if isinstance(track, dict) else None
        return f"Opened selected Spotify track: {name or uri}"


class SpotifyControl:
    def __init__(self):
        self.client = None
        self.error = None

    # -- setup -----------------------------------------------------------

    @staticmethod
    def configured():
        return bool(
            os.environ.get("SPOTIFY_CLIENT_ID")
            and os.environ.get("SPOTIFY_CLIENT_SECRET")
        )

    @staticmethod
    def setup_help():
        return (
            "Spotify's optional remote-control features are not configured. "
            "Music mode still works -- the visualiser reacts to any system "
            "audio -- and 'spotify search' does not need this setup. The "
            "older remote playback commands need these set:\n"
            "  python -m pip install spotipy\n"
            "  SPOTIFY_CLIENT_ID\n"
            "  SPOTIFY_CLIENT_SECRET\n"
            f"  SPOTIFY_REDIRECT_URI   (optional, default {DEFAULT_REDIRECT})\n\n"
            "Register a free app at https://developer.spotify.com/dashboard, "
            "then add the redirect URI there exactly as above.\n"
            "Playback control also needs Spotify Premium; the API refuses it "
            "on free accounts."
        )

    def connect(self):
        """Authorise. Opens a browser once, then caches the token."""
        if self.client is not None:
            return True

        if not self.configured():
            self.error = self.setup_help()
            return False

        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
        except ImportError:
            self.error = (
                "Spotify control needs the spotipy package.\n"
                "Install with: pip install spotipy"
            )
            return False

        try:
            auth = SpotifyOAuth(
                client_id=os.environ["SPOTIFY_CLIENT_ID"],
                client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
                redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT),
                scope=SCOPES,
                cache_path=os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    ".spotify_token",
                ),
                open_browser=True,
            )
            self.client = spotipy.Spotify(auth_manager=auth)
            self.client.current_user()
        except Exception as error:
            self.client = None
            self.error = f"Could not authorise with Spotify: {error}"
            return False

        return True

    # -- helpers ---------------------------------------------------------

    def _list_devices(self):
        try:
            return (self.client.devices() or {}).get("devices", [])
        except Exception as error:
            raise SpotifyError(f"Could not list Spotify devices: {error}")

    def _active_device(self, allow_launch=True):
        """
        The device Spotify will actually play on, launching the desktop
        client first if nothing is available.

        The Web API cannot create a player, only drive one that exists.
        Rather than dead-ending on that, start the client and wait for it
        to register -- a cold start takes a few seconds, so the wait is
        polled rather than fixed.
        """
        devices = self._list_devices()

        if not devices and allow_launch and self._launch_client():
            deadline = time.time() + 25.0

            while time.time() < deadline:
                time.sleep(1.5)
                devices = self._list_devices()

                if devices:
                    break

        if not devices:
            executable = _spotify_executable()
            detail = (
                "Spotify did not register a device in time. It may still be "
                "starting -- try the command again in a moment."
                if executable
                else "No Spotify desktop client found. Open Spotify manually, "
                     "or set TORMENT_NEXUS_SPOTIFY_EXE to its path."
            )
            raise SpotifyError(f"No active Spotify device.\n{detail}")

        for device in devices:
            if device.get("is_active"):
                return device["id"]

        # A freshly launched client is idle rather than active. Handing
        # playback to it explicitly is what wakes it up.
        return devices[0]["id"]

    @staticmethod
    def _launch_client():
        """Start the Spotify desktop client. True if a launch was attempted."""
        return _launch_desktop_client()

    @staticmethod
    def _describe(item):
        if not item:
            return "nothing"

        name = item.get("name", "unknown")
        artists_value = item.get("artists", [])
        if isinstance(artists_value, str):
            artists = artists_value
        else:
            artists = ", ".join(
                a.get("name", "") for a in artists_value if isinstance(a, dict)
            )
        return f"{name} - {artists}" if artists else name

    @staticmethod
    def _track_summary(track):
        """Keep only the tiny, display-safe subset needed for the picker."""
        artists = ", ".join(
            artist.get("name", "")
            for artist in track.get("artists", [])
            if isinstance(artist, dict) and artist.get("name")
        )
        album = track.get("album") or {}

        return {
            "uri": track.get("uri", ""),
            "name": track.get("name", "unknown track"),
            "artists": artists or "unknown artist",
            "album": album.get("name", "") if isinstance(album, dict) else "",
            "duration_ms": track.get("duration_ms", 0),
            "explicit": bool(track.get("explicit")),
        }

    def search_tracks(self, query, limit=5):
        """Return a short, selectable list of official Spotify track results."""
        if not self.connect():
            raise SpotifyError(self.error)

        query = " ".join((query or "").split())
        if not query:
            raise SpotifyError("Give Spotify something to search for.")

        try:
            limit = min(max(int(limit), 1), 5)
            found = self.client.search(q=query, type="track", limit=limit)
            items = ((found or {}).get("tracks") or {}).get("items") or []
        except Exception as error:
            raise SpotifyError(f"Spotify search failed: {error}")

        return [
            self._track_summary(item)
            for item in items
            if isinstance(item, dict) and item.get("uri")
        ]

    def play_track_item(self, track):
        """Ask the active Spotify device to play one previously shown result."""
        if not self.connect():
            raise SpotifyError(self.error)

        uri = (track or {}).get("uri") if isinstance(track, dict) else None
        if not isinstance(uri, str) or not re.fullmatch(
            r"spotify:track:[A-Za-z0-9]{22}", uri
        ):
            raise SpotifyError("That Spotify track selection is invalid.")

        device = self._active_device()

        try:
            self.client.start_playback(device_id=device, uris=[uri])
        except Exception as error:
            raise SpotifyError(self._playback_error(error))

        return f"Playing: {self._describe(track)}"

    # -- commands --------------------------------------------------------

    def play_playlist(self, query):
        """
        Start a playlist by name. Checks the user's own playlists first,
        then falls back to public search, since "my running mix" should
        find the user's copy rather than a stranger's.
        """
        if not self.connect():
            raise SpotifyError(self.error)

        needle = query.strip().lower()
        match = None

        try:
            page = self.client.current_user_playlists(limit=50)

            for item in (page or {}).get("items", []):
                if item and needle in item.get("name", "").lower():
                    match = item
                    break
        except Exception:
            # A missing scope or a private-playlist restriction should not
            # block the public-search path below.
            pass

        if match is None:
            try:
                found = self.client.search(q=query, type="playlist", limit=5)
                items = ((found or {}).get("playlists") or {}).get("items") or []
                items = [i for i in items if i]

                if items:
                    match = items[0]
            except Exception as error:
                raise SpotifyError(f"Spotify search failed: {error}")

        if match is None:
            raise SpotifyError(f"No playlist found matching: {query}")

        device = self._active_device()

        try:
            self.client.start_playback(
                device_id=device,
                context_uri=match["uri"],
            )
        except Exception as error:
            raise SpotifyError(self._playback_error(error))

        owner = (match.get("owner") or {}).get("display_name") or "unknown"
        return f"Playing playlist: {match['name']} (by {owner})"

    def play_track(self, query):
        matches = self.search_tracks(query, limit=1)

        if not matches:
            raise SpotifyError(f"No track found matching: {query}")

        return self.play_track_item(matches[0])

    def _simple(self, method_name, label):
        """Run a no-argument transport command on the active device."""
        if not self.connect():
            raise SpotifyError(self.error)

        device = self._active_device()

        try:
            getattr(self.client, method_name)(device_id=device)
        except Exception as error:
            raise SpotifyError(self._playback_error(error))

        return label

    def pause(self):
        return self._simple("pause_playback", "Paused.")

    def resume(self):
        return self._simple("start_playback", "Resumed.")

    def next_track(self):
        return self._simple("next_track", "Skipped.")

    def previous_track(self):
        return self._simple("previous_track", "Back.")

    def now_playing(self):
        if not self.connect():
            raise SpotifyError(self.error)

        try:
            current = self.client.current_playback()
        except Exception as error:
            raise SpotifyError(f"Could not read playback state: {error}")

        if not current or not current.get("item"):
            return "Nothing is playing."

        state = "Playing" if current.get("is_playing") else "Paused"
        return f"{state}: {self._describe(current['item'])}"

    @staticmethod
    def _playback_error(error):
        text = str(error)

        if "403" in text or "PREMIUM" in text.upper():
            return (
                "Spotify refused playback control. These endpoints are "
                "Premium-only; a free account can search but cannot be "
                "driven remotely."
            )

        if "404" in text:
            return (
                "Spotify has no active device. Open the desktop app and "
                "play something once so it registers, then retry."
            )

        return f"Spotify playback failed: {error}"
