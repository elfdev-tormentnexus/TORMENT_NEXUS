"""
Animate the desktop shortcut icon with occasional corruption bursts.

Windows has no supported way to animate a shortcut icon: .ico holds static
bitmaps, and Explorer draws one frame and caches it. This drives the icon
anyway. Three decisions make it work rather than thrash:

A distinct file per frame. Explorer's icon cache is keyed on the icon's
path, not its contents -- rewriting a single .ico in place is invisible to
it, which is exactly why the icon refused to update when we first changed
it. Every frame lives at its own path, so there is never a stale entry to
fight.

Pre-built shortcut variants. Changing a shortcut's icon normally means COM
(IShellLink), which needs pywin32 and costs milliseconds per call. Instead
a complete .lnk is built once per frame ahead of time, and animating is
then a plain file copy plus a shell notification -- no dependencies beyond
the standard library, and fast enough for a 90ms frame.

Bursts, not a constant loop. Every frame rewrites the .lnk, and this
Desktop is redirected into OneDrive, so a permanent 12fps loop would mean a
permanent sync queue -- around 43,000 writes an hour. Bursting instead puts
that near 400 writes an hour of a 1.7KB file, a hundredfold less, and it
reads better anyway: something that occasionally misbehaves rather than a
spinning GIF. Widen BURST_MIN_GAP/BURST_MAX_GAP to cut it further.

    python glitch_icon.py --setup     build the shortcut variants (once)
    python glitch_icon.py             run until Ctrl+C
    python glitch_icon.py --once      a single burst, then exit
    python glitch_icon.py --restore   put the resting shortcut back
    python glitch_icon.py --status    show what the shortcut points at

No autostart is registered and nothing is installed. However this process
exits -- including being killed -- the shortcut is left on a real icon,
never a missing file.
"""

import argparse
import atexit
import ctypes
import os
import random
import shutil
import signal
import subprocess
import sys
import time

# This script lives in tools/, so the project root is one level up.
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAME_DIR = os.path.join(PROJECT, "icon_anim")
VARIANT_DIR = os.path.join(FRAME_DIR, "shortcuts")

SOURCE_ICON = os.path.join(PROJECT, "assets", "assistant_icon.ico")

# The resting icon is served from its own path rather than straight from
# assistant_icon.ico, and that is not tidiness -- it is the whole reason
# the icon would not update in the first place. Explorer's cache is keyed
# on path, and the entry for assistant_icon.ico survives even a full cache
# purge and Explorer restart, still drawing the original black square. The
# identical bytes at an unused path draw correctly on the first try.
RESTING_ICON = os.path.join(FRAME_DIR, "rest.ico")

DESKTOP = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
SHORTCUT_NAMES = ("TORMENT_NEXUS.lnk",)

# The label under the icon is the filename, so animating it means renaming
# the file. Every scrambled name is padded to exactly this width: the
# desktop lays icons out on a grid and a name that changes length makes the
# label reflow, which reads as jitter rather than as corruption.
NAME_WIDTH = len("TORMENT_NEXUS")
RESTING_LABEL = "TORMENT_NEXUS"

# Matrix-ish glyphs. Deliberately restricted to characters that are legal
# in a Windows filename -- \ / : * ? " < > | are not -- and that share
# roughly even visual weight, so the label does not appear to pulse
# brighter and darker as it scrambles.
NOISE_GLYPHS = "01アイウエオカキクケコサシスセソナニヌネノ#$%&+=@ABCDEFGHIJKLMNPQRSTUVWXYZ23456789"

# Deliberately fast, against my own measurements.
#
# Sampling the desktop with PrintWindow suggested Explorer only repaints
# the icon about once a second, which would make anything under ~0.8s
# wasted work. But PrintWindow asks the window to re-render rather than
# reading the composited screen, so it may simply be unable to resolve
# frames that were genuinely drawn -- and the operator watching the actual
# desktop reported brief stretches that looked close to fluid at 90ms.
#
# Direct observation beats an instrument with a known blind spot, so the
# fast pacing stands. Tunable without editing code if it ever looks wrong:
#   set TORMENT_NEXUS_GLITCH_FRAME_MS=200
def _env_float(name, default, low, high):
    try:
        return max(low, min(high, float(os.environ.get(name, default))))
    except (TypeError, ValueError):
        return default


FRAME_SECONDS = _env_float("TORMENT_NEXUS_GLITCH_FRAME_MS", 70.0, 10.0, 2000.0) / 1000.0
BURST_MIN_GAP = _env_float("TORMENT_NEXUS_GLITCH_MIN_GAP", 25.0, 2.0, 3600.0)
BURST_MAX_GAP = _env_float("TORMENT_NEXUS_GLITCH_MAX_GAP", 90.0, 3.0, 7200.0)

# Label scrambling is OFF by default, and that is a retreat from a working
# feature rather than an untested guess.
#
# Renaming the shortcut ten times a burst does animate the label, but the
# desktop view does not keep up: Explorer leaves ghost entries for names
# that no longer exist on disk, complete with blank icons, and they linger
# until a manual refresh. One evening of it littered the desktop with a
# dozen dead entries. The files were genuinely gone -- the shell view was
# simply wrong -- but a cosmetic feature that makes the desktop look broken
# is not worth having on by default.
#
# The icon glitch has no such problem, because it never moves a file.
#   set TORMENT_NEXUS_GLITCH_LABEL=1
ANIMATE_LABEL = os.environ.get(
    "TORMENT_NEXUS_GLITCH_LABEL", "0").strip().lower() in {"1", "true", "yes", "on"}

# One animator at a time. Two racing processes each hold a stale path after
# the other renames, and a stale path plus copyfile recreates a shortcut
# that was meant to be gone -- which is how the desktop filled up.
LOCK_FILE = os.path.join(FRAME_DIR, ".animator.lock")

SHCNE_UPDATEITEM = 0x00002000
SHCNF_PATHW = 0x0005
SHCNF_FLUSH = 0x1000


def _is_ours(path):
    """
    True when a .lnk is one of ours, judged by where its icon points.

    Needed because the label animation renames the file: after a crash
    mid-burst the shortcut is sitting on the desktop under a scrambled
    name, and matching on filename would never find it again.
    """
    try:
        import struct

        with open(path, "rb") as handle:
            blob = handle.read()
    except OSError:
        return False

    # The icon path appears in the link's string data; looking for our
    # frame directory avoids parsing the whole .lnk format.
    marker = FRAME_DIR.encode("utf-16-le", errors="ignore")
    return marker in blob or FRAME_DIR.encode("mbcs", errors="ignore") in blob


ORPHAN_QUARANTINE = os.path.join(FRAME_DIR, "recovered")


def _looks_scrambled(stem):
    """
    Only a name this function produced counts as a leftover.

    An earlier version decided ownership purely from the icon path and
    then deleted whatever it matched. That is far too much authority for
    a cosmetic animation to hold over a folder full of the operator's
    shortcuts, and a desktop shortcut went missing under it. Ownership
    now needs BOTH the icon signature and a name of exactly the width
    this animator generates, built only from glyphs it draws from.
    """
    if len(stem) != NAME_WIDTH:
        return False

    allowed = set(NOISE_GLYPHS) | set(RESTING_LABEL)
    return all(character in allowed for character in stem)


def _recover_orphans():
    """
    Move scrambled leftovers aside. Never deletes anything.

    Anything ambiguous is quarantined rather than removed, so a mistake
    costs a file in a folder instead of a file that is gone.
    """
    recovered = []

    if not os.path.isdir(DESKTOP):
        return recovered

    known = set(SHORTCUT_NAMES) | {RESTING_LABEL + ".lnk"}
    target = os.path.join(DESKTOP, RESTING_LABEL + ".lnk")

    for name in os.listdir(DESKTOP):
        if not name.lower().endswith(".lnk") or name in known:
            continue

        path = os.path.join(DESKTOP, name)
        stem = os.path.splitext(name)[0]

        # Both tests must agree before this touches anything.
        if not (_looks_scrambled(stem) and _is_ours(path)):
            continue

        try:
            if not os.path.exists(target):
                os.replace(path, target)
                _notify(target)
            else:
                # The real shortcut is already back, so this is a spare.
                # Set it aside instead of deleting it -- if the ownership
                # test was ever wrong, the file is still retrievable.
                os.makedirs(ORPHAN_QUARANTINE, exist_ok=True)
                shutil.move(path, os.path.join(ORPHAN_QUARANTINE, name))

            _notify(path)
            recovered.append(name)
        except OSError:
            pass

    return recovered


def shortcuts():
    found = [os.path.join(DESKTOP, n) for n in SHORTCUT_NAMES
             if os.path.isfile(os.path.join(DESKTOP, n))]

    # The resting label is a valid name for a renamed shortcut to land on.
    resting = os.path.join(DESKTOP, RESTING_LABEL + ".lnk")
    if os.path.isfile(resting) and resting not in found:
        found.append(resting)

    return found


def frames():
    if not os.path.isdir(FRAME_DIR):
        return []

    # rest.ico lives here too but is the resting state, not a burst frame.
    return sorted(
        os.path.join(FRAME_DIR, n) for n in os.listdir(FRAME_DIR)
        if n.lower().startswith("frame_") and n.lower().endswith(".ico")
    )


def _notify(path):
    """Tell the shell this one item changed, so it redraws now."""
    ctypes.windll.shell32.SHChangeNotify(
        SHCNE_UPDATEITEM, SHCNF_PATHW | SHCNF_FLUSH,
        ctypes.c_wchar_p(path), None)


def variant_path(shortcut, index):
    stem = os.path.splitext(os.path.basename(shortcut))[0]
    return os.path.join(VARIANT_DIR, f"{stem}__{index:02d}.lnk")


def _resting_variant(shortcut):
    stem = os.path.splitext(os.path.basename(shortcut))[0]
    return os.path.join(VARIANT_DIR, f"{stem}__rest.lnk")


def setup():
    """
    Build one .lnk per (shortcut, frame) pair.

    Done through PowerShell's WScript.Shell rather than a COM binding so
    the runtime needs no third-party packages. It runs once; after this
    the animator only ever copies files.
    """
    _recover_orphans()

    targets = shortcuts()
    icons = frames()

    if not targets:
        print(f"No shortcuts found in {DESKTOP}")
        return 1
    if not icons:
        print(f"No .ico frames in {FRAME_DIR}")
        return 1

    # Only take over the shortcut's name when the label animation is
    # actually enabled. It renames the file and every restore lands on
    # RESTING_LABEL, so variants built under a different filename would
    # stop matching after the first burst -- but with the animation off
    # there is no reason to touch a name the operator chose.
    if ANIMATE_LABEL:
        renamed = []
        for index, shortcut in enumerate(list(targets)):
            if os.path.basename(shortcut) != RESTING_LABEL + ".lnk":
                moved = _rename(shortcut, RESTING_LABEL)
                if moved != shortcut:
                    renamed.append(os.path.basename(shortcut))
                    targets[index] = moved

        if renamed:
            print(f"Renamed for the label animation: {', '.join(renamed)}")

        # Renaming can collapse two shortcuts onto one name.
        targets = sorted(set(targets))

    # Clear stale variants. They are keyed on the shortcut's filename, so
    # renaming the shortcut orphans a whole set and leaves the folder
    # holding variants that will never be used again.
    if os.path.isdir(VARIANT_DIR):
        for name in os.listdir(VARIANT_DIR):
            if name.endswith(".lnk"):
                try:
                    os.remove(os.path.join(VARIANT_DIR, name))
                except OSError:
                    pass

    os.makedirs(VARIANT_DIR, exist_ok=True)

    # Publish the resting icon at a path Explorer has never cached.
    if os.path.isfile(SOURCE_ICON):
        shutil.copyfile(SOURCE_ICON, RESTING_ICON)
        print(f"resting icon published to {os.path.basename(RESTING_ICON)}")

    jobs = []
    for shortcut in targets:
        for index, icon in enumerate(icons):
            jobs.append((shortcut, variant_path(shortcut, index), icon))

    # The resting variant is built here too, so restoring is a file copy
    # rather than a rebuild.
    for shortcut in targets:
        jobs.append((shortcut, _resting_variant(shortcut), RESTING_ICON))

    script = ["$sh = New-Object -ComObject WScript.Shell"]
    for source, dest, icon in jobs:
        script.append(f"$s = $sh.CreateShortcut('{source}')")
        script.append(f"$d = $sh.CreateShortcut('{dest}')")
        script.append("$d.TargetPath = $s.TargetPath")
        script.append("$d.Arguments = $s.Arguments")
        script.append("$d.WorkingDirectory = $s.WorkingDirectory")
        script.append("$d.WindowStyle = $s.WindowStyle")
        script.append(f"$d.IconLocation = '{icon},0'")
        script.append("$d.Save()")

    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "; ".join(script)],
        capture_output=True, text=True)

    if result.returncode != 0:
        print("Building shortcut variants failed:")
        print(result.stderr.strip()[:800])
        return 1

    built = sum(1 for _, dest, _ in jobs if os.path.isfile(dest))
    print(f"Built {built}/{len(jobs)} shortcut variants in {VARIANT_DIR}")

    # Put the desktop on the resting variant straight away, so the fresh
    # path takes effect without waiting for a burst to end.
    restore(targets)
    print("Desktop set to the resting icon.")

    return 0 if built == len(jobs) else 1


def scramble_label(settle=0.0):
    """
    One frame of Matrix-style noise, fixed at NAME_WIDTH characters.

    `settle` between 0 and 1 is the fraction of the real name that has
    locked back into place, left to right. Resolving the label rather than
    snapping it back is what makes the effect read as decoding rather than
    as the name simply breaking and being repaired.
    """
    locked = int(round(NAME_WIDTH * max(0.0, min(1.0, settle))))
    out = []

    for i in range(NAME_WIDTH):
        if i < locked:
            out.append(RESTING_LABEL[i])
        else:
            out.append(random.choice(NOISE_GLYPHS))

    return "".join(out)


def _rename(current, label):
    """
    Rename the shortcut so the desktop label changes. Returns the new path.

    The desktop shows a shortcut's filename, so there is no way to animate
    the label without moving the file. Failure returns the original path
    unchanged, so a caller can never end up tracking a name that does not
    exist.
    """
    target = os.path.join(os.path.dirname(current), label + ".lnk")

    if os.path.abspath(target) == os.path.abspath(current):
        return current

    for attempt in range(4):
        try:
            if os.path.exists(target):
                os.remove(target)
            os.replace(current, target)
            _notify(current)
            _notify(target)
            return target
        except OSError:
            time.sleep(0.02 * (attempt + 1))

    return current


def _swap(shortcut, index, attempts=4):
    return _swap_by_identity(shortcut, shortcut, index, attempts)


def _swap_by_identity(shortcut, identity, index, attempts=4):
    """
    Point `shortcut` at frame `index`. False if it could not be written.

    `identity` is the name the variants were built under, which differs
    from `shortcut` once the label animation has renamed the file.

    Retries because OneDrive's filter driver intermittently rejects rapid
    writes to a synced folder with EINVAL -- observed reliably when frames
    are pushed back to back. A dropped frame is invisible in a burst; an
    unhandled OSError would take the whole animator down.
    """
    source = variant_path(identity, index)

    if not os.path.isfile(source):
        return False

    # Refuse to create the shortcut, only ever overwrite one that is
    # already there. copyfile happily creates a missing destination, so a
    # path made stale by a rename would resurrect a shortcut that was
    # supposed to have moved -- one dead icon per frame.
    if not os.path.isfile(shortcut):
        return False

    for attempt in range(attempts):
        try:
            shutil.copyfile(source, shortcut)
            _notify(shortcut)
            return True
        except OSError:
            if attempt == attempts - 1:
                return False
            time.sleep(0.02 * (attempt + 1))

    return False


def restore(targets=None, identity=None):
    """
    Put the resting shortcut and its real name back.

    Returns the restored paths. Safe to call repeatedly, and safe to call
    when a burst renamed things partway through -- `identity` maps a
    current path back to the name its variants were built under.
    """
    identity = identity or {}
    restored = []

    for shortcut in (targets or shortcuts()):
        source = identity.get(shortcut, shortcut)
        resting = _resting_variant(source)

        # Restoring is the one write that must not be dropped -- it is what
        # guarantees the icon is left in a sane state -- so it gets more
        # attempts than a burst frame does.
        for attempt in range(8):
            try:
                if os.path.isfile(resting):
                    shutil.copyfile(resting, shortcut)
                else:
                    shutil.copyfile(variant_path(source, 0), shortcut)
                _notify(shortcut)
                break
            except OSError:
                time.sleep(0.05 * (attempt + 1))
            except Exception:
                break

        # Only rename back if the label animation is what moved it. With
        # the animation off, the operator's chosen filename is left alone.
        final = _rename(shortcut, RESTING_LABEL) if ANIMATE_LABEL else shortcut
        restored.append(final)

    return restored


def _acquire_lock():
    """
    Refuse to start when another animator is already running.

    Returns a file object to hold open, or None. Windows keeps an open
    file locked, so the handle itself is the lock and a killed process
    releases it automatically -- no stale lockfile to clean up.
    """
    os.makedirs(FRAME_DIR, exist_ok=True)

    try:
        handle = open(LOCK_FILE, "w")
    except OSError:
        return None

    try:
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except (ImportError, OSError):
        handle.close()
        return None

    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def burst(targets, count, verbose=False, animate_label=None):
    """
    One corruption burst, ending back at rest.

    The icon and the label are driven together: the name scrambles while
    the icon corrupts, then resolves left to right over the last third of
    the burst so it reads as decoding back to itself rather than snapping.

    `targets` may be renamed as this runs, so the caller's paths go stale.
    The list it returns is the current one.
    """
    # Longer runs at the fast pacing, so a burst reads as motion rather
    # than a single flicker. Frames may repeat within a burst; at this
    # speed a repeat looks like the corruption settling, not a mistake.
    if animate_label is None:
        animate_label = ANIMATE_LABEL

    span = min(random.randint(6, 10), max(2, (count - 1) * 2))
    picks = [random.randrange(1, count) for _ in range(span)]

    current = list(targets)
    identity = {path: path for path in targets}

    for step, index in enumerate(picks):
        # Resolve over the final third; pure noise before that.
        progress = step / max(1, len(picks) - 1)
        settle = 0.0 if progress < 0.66 else (progress - 0.66) / 0.34

        for slot, shortcut in enumerate(current):
            source = identity[shortcut]
            _swap_by_identity(shortcut, source, index)

            if animate_label:
                moved = _rename(shortcut, scramble_label(settle))
                if moved != shortcut:
                    identity[moved] = source
                    current[slot] = moved

        time.sleep(FRAME_SECONDS)

    restored = restore(current, identity)

    if verbose:
        print(f"  burst: {len(picks)} frames"
              + (" with label scramble" if animate_label else ""))

    return restored or current


def status():
    print(f"frames        : {len(frames())} in {FRAME_DIR}")
    variants = (len([n for n in os.listdir(VARIANT_DIR) if n.endswith('.lnk')])
                if os.path.isdir(VARIANT_DIR) else 0)
    print(f"lnk variants  : {variants}")
    print(f"resting icon  : {RESTING_ICON} "
          f"[{'ok' if os.path.isfile(RESTING_ICON) else 'MISSING'}]")

    sh = ("$sh = New-Object -ComObject WScript.Shell; " + "; ".join(
        f"$l = $sh.CreateShortcut('{s}'); "
        f"Write-Output ('{os.path.basename(s)} -> ' + $l.IconLocation)"
        for s in shortcuts()))
    out = subprocess.run(["powershell", "-NoProfile", "-Command", sh],
                         capture_output=True, text=True)
    print(out.stdout.strip() or "(no shortcuts)")


def main():
    parser = argparse.ArgumentParser(
        description="Glitch the desktop shortcut icon.")
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--gap", type=float, default=None,
                        help="fixed seconds between bursts")
    args = parser.parse_args()

    if args.setup:
        return setup()
    if args.status:
        status()
        return 0

    lock = _acquire_lock()

    if lock is None and not args.restore and not args.status:
        print("Another animator is already running. Stop it first "
              "(stop_glitch.bat).")
        return 1

    # A previous run killed mid-burst leaves the shortcut under a scrambled
    # name. Put it back before looking for anything.
    recovered = _recover_orphans()
    if recovered:
        print(f"Recovered {len(recovered)} shortcut(s) "
              f"left scrambled by a previous run.")

    targets = shortcuts()
    count = len(frames())

    if not targets:
        print("No shortcuts found. Nothing to animate.")
        return 1
    if count < 2:
        print(f"Need at least 2 .ico frames in {FRAME_DIR}")
        return 1
    if not os.path.isdir(VARIANT_DIR):
        print("Run once with --setup first.")
        return 1

    if args.restore:
        restore(targets)
        print("Resting shortcut restored.")
        return 0

    # However this dies, the shortcut must be left usable.
    atexit.register(restore, targets)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: sys.exit(0))
        except (ValueError, OSError):
            pass

    if args.once:
        print(f"One burst across {len(targets)} shortcut(s)...")
        burst(targets, count, verbose=True)
        print("Done, resting shortcut restored.")
        return 0

    print(f"Glitching {len(targets)} shortcut(s) from {count} frames.")
    print("Ctrl+C to stop; the resting icon is restored on exit.\n")

    played = 0
    try:
        while True:
            gap = args.gap or random.uniform(BURST_MIN_GAP, BURST_MAX_GAP)
            time.sleep(gap)
            played += 1
            # A burst may rename the shortcut, so it hands back the paths
            # that are now current.
            targets = burst(targets, count) or targets
            print(f"  burst {played} (waited {gap:.0f}s)")
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        restore(targets)
        _recover_orphans()
        print("\nStopped. Resting icon and name restored.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
