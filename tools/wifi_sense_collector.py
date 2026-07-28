"""
A real, safe Wi-Fi disturbance collector for the experimental sensing bridge.

This is deliberately NOT part of TORMENT_NEXUS. It is the separate, external
process that core/wifi_experimental.py was built to accept a record from, and
it stays external so the assistant keeps no radio code, no capture path, and
nothing to disable. It writes one small JSON file and does nothing else.

    python tools/wifi_sense_collector.py --calibrate 60 --out <path>
    python tools/wifi_sense_collector.py --out <path>

What it measures, and why that particular number
------------------------------------------------
The obvious signal is the one that does not work. Windows reports Wi-Fi
"Signal" as a smoothed link-quality percentage, and on this hardware it sat at
85% for twenty-two consecutive seconds, then 84% for eight -- a spread of one
point, standard deviation 0.44. There is no motion information in it. A full
BSSID scan is worse in a different way: Windows caches scan results and only
refreshes them every ten to fifteen seconds, so most sweeps return the
previous sweep's numbers unchanged.

The receive rate does move. Over the same twenty-five seconds it stepped
907 -> 865 -> 907 -> 1021 -> 961 Mbps while the quality figure never budged.
That is rate adaptation: the adapter reselects its modulation and coding in
response to actual signal-to-noise and multipath, and a body moving through
the room changes multipath. It is an indirect measurement, but it is a real
one, and it responds on the timescale a person moves rather than on Windows'
scan-cache timescale.

What this can and cannot tell you
---------------------------------
It detects *disturbance of the radio channel*. That correlates with movement
and is not the same thing as detecting a person. A fan, a door, a neighbour's
network changing channel, or the access point adjusting its own power will all
produce the same reading, and there are thirty-one other BSSIDs audible from
this desk.

It cannot produce direction. Rate is a scalar, so there is no bearing in it,
so this collector never emits "approach" even though the bridge would accept
it. Emitting a direction from a number that contains none would be inventing a
measurement, which is the one thing the whole design exists to prevent.

Confidence is therefore capped below the bridge's "high" band. A reading from
this collector should never read as authoritative, because it is not.
"""

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time


SCHEMA_VERSION = 1
SOURCE_NAME = "wifi-experimental"

SAMPLE_SECONDS = 1.0

# Long enough to contain a few rate transitions, short enough that the state
# still describes now rather than the last minute.
WINDOW_SECONDS = 12

# The bridge expires a record on its own; this only has to outlive the gap
# between writes.
EXPIRY_MS = 6000

# Rate adaptation also responds to how much traffic there is, not only to the
# channel. A link with nothing on it reports a stale figure that looks
# perfectly still, so a run of identical samples is reported as unknown rather
# than as confident stillness.
STALE_SAMPLES = 10

CALIBRATE_SECONDS = 60

# Multiples of the calibrated quiet-room spread. Below the first the channel is
# as settled as it was when empty; above the second something is genuinely
# moving it. Between them is honestly indeterminate.
STILL_FACTOR = 1.5
MOTION_FACTOR = 3.0

# Never "high". This is an indirect proxy through rate adaptation, and the
# bridge's top confidence band would misrepresent it.
MAX_CONFIDENCE = 0.6

BASELINE_FILE = ".wifi_sense_baseline.json"

_RX = re.compile(r"^\s*Receive rate \(Mbps\)\s*:\s*([\d.]+)", re.MULTILINE)
_BSSID = re.compile(r"^\s*BSSID \d+\s*:\s*([0-9a-f:]{17})", re.MULTILINE | re.I)
_SIGNAL = re.compile(r"^\s*Signal\s*:\s*(\d+)%", re.MULTILINE)

# A second radio earns its place by being free to do nothing but listen.
#
# The connected adapter gives one path, sampled fast. An idle second adapter
# gives every access point it can hear -- twenty-nine from this desk -- and a
# body only has to disturb one of them. Windows caches scan results either way,
# but an unassociated radio refreshes in three to nine seconds against the
# connected one's ten to fifteen, because it is not protecting a link.
#
# So the two sources are complementary rather than redundant: one path at 1 Hz,
# and many paths at roughly a third of that. Motion evidence from either counts.
#
# BSSIDs are used in memory to pair each reading with the same access point
# between sweeps. They identify neighbours' hardware and they are never written
# to the status file, logged, or counted anywhere they could leave this process.
SCAN_INTERVAL_SECONDS = 3.0
SCAN_MOTION_FRACTION = 0.25
SCAN_STEP_THRESHOLD = 6


def _sample():
    """One receive-rate reading in Mbps, or None if the link is down.

    netsh is used rather than the native WLAN API on purpose: it needs no
    ctypes struct layouts to be right, and at one sample per second the cost of
    a process launch does not matter. Nothing here reads or retains an SSID,
    BSSID, MAC address, or anything else identifying -- only this one number.
    """
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return None

    found = _RX.search(out)

    return float(found.group(1)) if found else None


def _scan(interface):
    """Per-access-point signal from a listening radio, keyed by BSSID.

    Returns {} on any failure, including the interface not existing, because a
    second radio is an enhancement and its absence must not stop collection.
    """
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid",
             f"interface={interface}"],
            capture_output=True, text=True, timeout=15,
        ).stdout
    except Exception:
        return {}

    # netsh prints each BSSID immediately above its own signal line, so zipping
    # the two ordered lists pairs them correctly.
    bssids = _BSSID.findall(out)
    signals = [int(value) for value in _SIGNAL.findall(out)]

    return dict(zip(bssids, signals))


def _scan_disturbance(previous, current):
    """What fraction of shared access points moved, and by how much.

    Fraction rather than magnitude, because the paths are not comparable: a
    close access point swings ten points on nothing, a distant one barely moves
    when someone walks through it. How MANY paths changed is the robust signal.
    """
    shared = set(previous) & set(current)

    if len(shared) < 4:
        return None

    moved = sum(
        1 for key in shared
        if abs(current[key] - previous[key]) >= SCAN_STEP_THRESHOLD
    )

    return moved / len(shared)


def _spread(samples):
    """How much the channel is moving: mean absolute step between samples."""
    steps = [abs(b - a) for a, b in zip(samples, samples[1:])]

    return statistics.fmean(steps) if steps else 0.0


def calibrate(seconds, out_path):
    """Record what an undisturbed room looks like on this hardware.

    Thresholds cannot be hardcoded. The rate a link settles at, and how much it
    wanders when nothing is happening, depend on the adapter, the access point,
    the band, and how many neighbours are audible. A number that meant
    stillness here would mean nothing anywhere else.
    """
    print(f"Calibrating for {seconds}s. Leave the room still -- no walking "
          f"through, ideally nobody in it.\n")

    samples = []
    started = time.time()

    while time.time() - started < seconds:
        value = _sample()

        if value is not None:
            samples.append(value)
            spread = _spread(samples[-WINDOW_SECONDS:])
            print(f"\r  {len(samples):3d} samples   rate {value:7.1f} Mbps   "
                  f"quiet spread {spread:5.2f}", end="", flush=True)

        time.sleep(SAMPLE_SECONDS)

    print()

    if len(samples) < 10:
        print("\nNot enough samples. Is Wi-Fi connected?")
        return 1

    baseline = _spread(samples)

    if baseline <= 0.0:
        # A perfectly flat calibration means an idle link, not a quiet room.
        # Guessing a threshold from it would make everything look like motion.
        print("\nThe receive rate never changed during calibration, which "
              "means the link was idle rather than the room being quiet.\n"
              "Run something that uses the network continuously -- a large "
              "download, a video stream -- and calibrate again.")
        return 1

    record = {
        "baseline_spread": baseline,
        "median_rate": statistics.median(samples),
        "samples": len(samples),
        "calibrated_at": time.time(),
    }

    path = os.path.join(os.path.dirname(os.path.abspath(out_path)) or ".",
                        BASELINE_FILE)

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)

    print(f"\nQuiet-room spread: {baseline:.2f} Mbps between samples")
    print(f"  still  below {baseline * STILL_FACTOR:.2f}")
    print(f"  motion above {baseline * MOTION_FACTOR:.2f}")
    print(f"\nSaved to {path}")

    return 0


def _load_baseline(out_path):
    path = os.path.join(os.path.dirname(os.path.abspath(out_path)) or ".",
                        BASELINE_FILE)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)["baseline_spread"]
    except Exception:
        return None


def _classify(samples, baseline):
    """A coarse state and a capped confidence, or unknown.

    Returns one of the bridge's states, never "approach": there is no direction
    in a scalar rate, and the bridge accepting the label is not a reason to
    produce one.
    """
    if len(samples) < 4:
        return "unknown", 0.2

    if len(set(samples[-STALE_SAMPLES:])) == 1 and \
            len(samples) >= STALE_SAMPLES:
        # Identical readings mean the link is idle and telling us nothing.
        return "unknown", 0.2

    spread = _spread(samples)

    if spread < baseline * STILL_FACTOR:
        return "still", MAX_CONFIDENCE

    if spread > baseline * MOTION_FACTOR:
        return "motion", MAX_CONFIDENCE

    return "unknown", 0.35


def _write(out_path, state, confidence):
    """Atomically replace the status file, as the bridge contract requires."""
    record = {
        "schema": SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "state": state,
        "confidence": round(confidence, 2),
        "observed_at": time.time(),
        "expiry_ms": EXPIRY_MS,
    }

    folder = os.path.dirname(os.path.abspath(out_path)) or "."
    handle, temp = tempfile.mkstemp(dir=folder, suffix=".tmp")

    try:
        with os.fdopen(handle, "w", encoding="utf-8") as target:
            json.dump(record, target)
            target.flush()
            os.fsync(target.fileno())

        os.replace(temp, out_path)
    except Exception:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise


def collect(out_path, listen_interface=None):
    baseline = _load_baseline(out_path)

    if baseline is None:
        print("No baseline for this room. Run --calibrate first:\n\n"
              f"  python {sys.argv[0]} --calibrate {CALIBRATE_SECONDS} "
              f"--out {out_path}")
        return 1

    print(f"Collecting. Quiet-room spread {baseline:.2f} Mbps.")

    if listen_interface:
        print(f"Second radio '{listen_interface}' listening across every "
              f"access point it can hear.")

    print(f"Writing {out_path}\nCtrl-C to stop.\n")

    samples = []
    previous_scan = {}
    next_scan_at = 0.0
    scan_moved = None
    scan_paths = 0

    try:
        while True:
            now = time.time()

            if listen_interface and now >= next_scan_at:
                current_scan = _scan(listen_interface)
                moved = _scan_disturbance(previous_scan, current_scan)

                if moved is not None:
                    scan_moved = moved
                    scan_paths = len(set(previous_scan) & set(current_scan))

                if current_scan:
                    previous_scan = current_scan

                next_scan_at = now + SCAN_INTERVAL_SECONDS

            value = _sample()

            if value is None:
                _write(out_path, "unknown", 0.2)
            else:
                samples.append(value)
                samples[:] = samples[-WINDOW_SECONDS:]
                state, confidence = _classify(samples, baseline)

                # Either radio may see it. The fast single path catches a
                # disturbance close to this desk; the many slow paths catch one
                # that never crosses the link to the access point at all.
                # Neither is allowed to talk the other out of a detection.
                if scan_moved is not None and scan_moved >= SCAN_MOTION_FRACTION:
                    state, confidence = "motion", MAX_CONFIDENCE

                _write(out_path, state, confidence)

                scan_text = (
                    f"scan {scan_moved:4.0%} of {scan_paths:2d}"
                    if scan_moved is not None else "scan      --"
                )
                print(f"\r  rate {value:7.1f}  spread {_spread(samples):5.2f}"
                      f"  {scan_text}  -> {state:8s} ({confidence:.2f})   ",
                      end="", flush=True)

            time.sleep(SAMPLE_SECONDS)
    except KeyboardInterrupt:
        print("\n\nStopped. The bridge expires the last record on its own; "
              "'wifi sensing forget' clears it now.")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="External Wi-Fi channel-disturbance collector for the "
                    "TORMENT_NEXUS experimental sensing bridge.",
    )
    parser.add_argument("--out", required=True,
                        help="status file the bridge reads "
                             "(TORMENT_NEXUS_WIFI_EXPERIMENT_FILE)")
    parser.add_argument("--calibrate", type=int, metavar="SECONDS",
                        help=f"measure a quiet room first, e.g. "
                             f"--calibrate {CALIBRATE_SECONDS}")
    parser.add_argument("--listen", metavar="INTERFACE",
                        help="a SECOND wireless interface, left unconnected, "
                             "to listen across every access point it can hear "
                             "(e.g. --listen \"Wi-Fi 2\"). Do not name the "
                             "interface carrying your internet connection.")

    args = parser.parse_args()

    if args.calibrate:
        return calibrate(args.calibrate, args.out)

    return collect(args.out, args.listen)


if __name__ == "__main__":
    raise SystemExit(main())
