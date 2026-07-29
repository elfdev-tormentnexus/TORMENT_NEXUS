"""
Put a mode shortcut on the Desktop, wearing the icon that says which mode.

Both non-ordinary launchers start something an operator should be able to
recognise before double-clicking. INTERLINKED opens a listening socket.
HAZARD starts a second embedding server and an unproven representation.
Neither should look like the ordinary launcher, and neither should depend
on remembering which window is which.

Built through PowerShell's WScript.Shell rather than a COM binding, for the
same reason tools/glitch_icon.py does it that way: no third-party package
is needed at runtime.

The shortcut is deliberately left out of glitch_icon.py's animation set.
That animator claims every .lnk whose icon points into icon_anim/, and this
one points at assets/ instead, so the two do not fight over it -- an
interface-mode shortcut that glitched into the normal icon would defeat the
only thing it exists to do.

    python tools/make_interface_shortcut.py                 INTERLINKED
    python tools/make_interface_shortcut.py --hazard        HAZARD
    python tools/make_interface_shortcut.py --both          both
    python tools/make_interface_shortcut.py --remove --both take them away
"""

import argparse
import ctypes
import ctypes.wintypes
import os
import subprocess
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODES = {
    "interlinked": {
        "launcher": os.path.join(PROJECT, "start_interface_mode.bat"),
        "icon": os.path.join(PROJECT, "assets", "assistant_icon_interface.ico"),
        "name": "TORMENT_NEXUS_INTERLINKED.lnk",
        "description": ("TORMENT_NEXUS_INTERLINKED - read-only agent "
                        "interface listening"),
        "rebuild": "python tools/generate_interface_icon.py",
    },
    "hazard": {
        "launcher": os.path.join(PROJECT, "start_assistant_hazard.bat"),
        "icon": os.path.join(PROJECT, "assets", "hazard_icon.ico"),
        "name": "TORMENT_NEXUS_HAZARD.lnk",
        "description": ("TORMENT_NEXUS_HAZARD - experimental, two embedding "
                        "servers, slower on purpose"),
        "rebuild": "python tools/build_hazard_icon.py",
    },
}

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


def create(mode):
    spec = MODES[mode]

    for path, label in ((spec["launcher"], "launcher"), (spec["icon"], "icon")):
        if not os.path.isfile(path):
            print(f"Missing {label}: {path}")
            if path == spec["icon"]:
                print(f"Run: {spec['rebuild']}")
            return 1

    target = os.path.join(DESKTOP, spec["name"])
    script = "; ".join([
        "$sh = New-Object -ComObject WScript.Shell",
        f"$s = $sh.CreateShortcut('{target}')",
        f"$s.TargetPath = '{spec['launcher']}'",
        f"$s.WorkingDirectory = '{PROJECT}'",
        f"$s.IconLocation = '{spec['icon']},0'",
        f"$s.Description = '{spec['description']}'",
        "$s.Save()",
    ])

    result = _powershell(script)

    if result.returncode != 0 or not os.path.isfile(target):
        print("Could not create the shortcut:")
        print(result.stderr.strip()[:800])
        return 1

    print(f"Created {target}")
    print(f"  target: {spec['launcher']}")
    print(f"  icon:   {spec['icon']}")
    return 0


def remove(mode):
    target = os.path.join(DESKTOP, MODES[mode]["name"])

    if not os.path.isfile(target):
        print(f"No {mode} shortcut on the Desktop.")
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
    parser.add_argument("--hazard", action="store_true",
                        help="TORMENT_NEXUS_HAZARD instead of INTERLINKED")
    parser.add_argument("--both", action="store_true",
                        help="both mode shortcuts")
    arguments = parser.parse_args()

    if arguments.both:
        modes = ["interlinked", "hazard"]
    elif arguments.hazard:
        modes = ["hazard"]
    else:
        modes = ["interlinked"]

    action = remove if arguments.remove else create
    return max(action(mode) for mode in modes)


if __name__ == "__main__":
    sys.exit(main())
