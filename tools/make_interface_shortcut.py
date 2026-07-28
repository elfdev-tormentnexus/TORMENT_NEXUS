"""
Put an interface-mode shortcut on the Desktop, wearing the inverted icon.

Interface mode opens a listening socket, so telling it apart from a normal
window should not depend on the operator remembering which one they
double-clicked. This builds the shortcut that makes that visible.

Built through PowerShell's WScript.Shell rather than a COM binding, for the
same reason tools/glitch_icon.py does it that way: no third-party package
is needed at runtime.

The shortcut is deliberately left out of glitch_icon.py's animation set.
That animator claims every .lnk whose icon points into icon_anim/, and this
one points at assets/ instead, so the two do not fight over it -- an
interface-mode shortcut that glitched into the normal icon would defeat the
only thing it exists to do.

    python tools/make_interface_shortcut.py            create it
    python tools/make_interface_shortcut.py --remove   take it away
"""

import argparse
import ctypes
import ctypes.wintypes
import os
import subprocess
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(PROJECT, "start_interface_mode.bat")
ICON = os.path.join(PROJECT, "assets", "assistant_icon_interface.ico")
NAME = "TORMENT_NEXUS (interface mode).lnk"

CSIDL_DESKTOPDIRECTORY = 0x0010


def desktop_directory():
    """
    The real Desktop, asked for rather than assumed.

    This one is redirected into OneDrive, and tools/glitch_icon.py hardcodes
    that. Hardcoding is correct until someone installs without OneDrive, or
    with a differently redirected profile, at which point the shortcut is
    written to a folder Explorer never shows and the tool reports success.
    Ask the shell, and fall back only if it refuses to answer.
    """
    try:
        buffer = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(
            None, CSIDL_DESKTOPDIRECTORY, None, 0, buffer
        ) == 0 and buffer.value:
            return buffer.value
    except (AttributeError, OSError):
        pass

    home = os.path.expanduser("~")

    for candidate in (
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "Desktop"),
    ):
        if os.path.isdir(candidate):
            return candidate

    return os.path.join(home, "Desktop")


DESKTOP = desktop_directory()


def _powershell(script):
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )


def create():
    for path, label in ((LAUNCHER, "launcher"), (ICON, "icon")):
        if not os.path.isfile(path):
            print(f"Missing {label}: {path}")
            if path == ICON:
                print("Run: python tools/generate_interface_icon.py")
            return 1

    target = os.path.join(DESKTOP, NAME)
    script = "; ".join([
        "$sh = New-Object -ComObject WScript.Shell",
        f"$s = $sh.CreateShortcut('{target}')",
        f"$s.TargetPath = '{LAUNCHER}'",
        f"$s.WorkingDirectory = '{PROJECT}'",
        f"$s.IconLocation = '{ICON},0'",
        "$s.Description = "
        "'TORMENT_NEXUS with the read-only agent interface listening'",
        "$s.Save()",
    ])

    result = _powershell(script)

    if result.returncode != 0 or not os.path.isfile(target):
        print("Could not create the shortcut:")
        print(result.stderr.strip()[:800])
        return 1

    print(f"Created {target}")
    print(f"  target: {LAUNCHER}")
    print(f"  icon:   {ICON} (inverted)")
    return 0


def remove():
    target = os.path.join(DESKTOP, NAME)

    if not os.path.isfile(target):
        print("No interface-mode shortcut on the Desktop.")
        return 0

    try:
        os.remove(target)
    except OSError as error:
        print(f"Could not remove it: {error}")
        return 1

    print(f"Removed {target}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true",
                        help="delete the shortcut instead of creating it")
    arguments = parser.parse_args()

    return remove() if arguments.remove else create()


if __name__ == "__main__":
    sys.exit(main())
