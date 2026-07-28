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
    # Still, not empty. A stationary body is constant multipath and becomes
    # part of the baseline, so sitting motionless is a valid null state -- and
    # in a one-room flat it is the only one available. Calibrating "the room as
    # it is when I am sitting here" also makes the detector answer the more
    # useful question afterwards.
    print(f"Calibrating for {seconds}s.\n"
          f"  Sit still -- you do NOT need to leave the room. Breathing is "
          f"fine; walking about is not.\n"
          f"  Keep traffic flowing: a video stream or a download. Rate "
          f"adaptation needs packets\n"
          f"  to adapt to, and an idle link looks perfectly calm no matter "
          f"what the room is doing.\n")

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


def verify(out_path, listen_interface=None, phase=20):
    """Guided still-then-moving test: does this baseline actually discriminate?

    Calibration in a real home is never done in an empty room, and it does not
    need to be. A stationary body is constant multipath and simply becomes part
    of the baseline; what matters is that the room was STILL, not that it was
    empty. In a studio apartment "still" is the only option available anyway.

    That makes an honest check more important, not less. This measures the same
    statistic during a deliberately still phase and a deliberately moving one
    and reports whether the calibrated thresholds actually separate them. A
    detector that cannot tell those two apart is worse than no detector,
    because it will report confidently either way.
    """
    baseline = _load_baseline(out_path)

    if baseline is None:
        print("Calibrate first -- there is nothing to verify against.")
        return 1

    def measure(label, instruction):
        print(f"\n{label}\n  {instruction}")
        input("  Press Enter when ready...")

        samples = []
        fractions = []
        previous_scan = {}
        started = time.time()

        while time.time() - started < phase:
            if listen_interface:
                current = _scan(listen_interface)
                moved = _scan_disturbance(previous_scan, current)

                if moved is not None:
                    fractions.append(moved)

                if current:
                    previous_scan = current

            value = _sample()

            if value is not None:
                samples.append(value)

            left = int(phase - (time.time() - started))
            print(f"\r  {left:2d}s remaining   {len(samples):2d} samples ",
                  end="", flush=True)
            time.sleep(SAMPLE_SECONDS)

        spread = _spread(samples)
        worst = max(fractions) if fractions else None
        print(f"\r  spread {spread:6.2f} Mbps" +
              (f"   scan peak {worst:.0%}" if worst is not None else "") +
              "        ")

        return spread, worst

    print("=" * 62)
    print("DOES THIS BASELINE DISCRIMINATE?")
    print("=" * 62)
    print(f"\nCalibrated quiet spread: {baseline:.2f} Mbps")
    print(f"  still  below {baseline * STILL_FACTOR:.2f}")
    print(f"  motion above {baseline * MOTION_FACTOR:.2f}")
    print("\nKeep the video or download running throughout.")

    still_spread, still_scan = measure(
        "PHASE 1 of 2 - STILL",
        f"Sit as still as you can for {phase}s. Breathing is fine.",
    )
    move_spread, move_scan = measure(
        "PHASE 2 of 2 - MOVING",
        f"Walk about, wave your arms, cross between the PC and the router "
        f"for {phase}s.",
    )

    print("\n" + "=" * 62)
    print(f"still  : rate spread {still_spread:6.2f}" +
          (f"   scan peak {still_scan:.0%}" if still_scan is not None else ""))
    print(f"moving : rate spread {move_spread:6.2f}" +
          (f"   scan peak {move_scan:.0%}" if move_scan is not None else ""))

    rate_separates = move_spread > still_spread * 1.5
    scan_separates = (
        still_scan is not None and move_scan is not None
        and move_scan > still_scan + 0.15
    )

    print()

    if rate_separates:
        print("PASS  the receive rate clearly moves more when you do.")
    else:
        print("WEAK  the receive rate barely changed between the two phases.")

    if still_scan is not None:
        if scan_separates:
            print("PASS  the second radio saw more paths disturbed.")
        else:
            print("WEAK  the second radio saw no clear difference.")

    if not rate_separates and not scan_separates:
        # Two very different failures were being reported as one, and the
        # advice for the first is actively misleading when it is the second.
        #
        # A flat link genuinely is an idle link, and more traffic fixes it. But
        # a link that varies and simply does not correlate with the room is not
        # short of traffic -- it is short of *information*, and no amount of
        # calibrating will put any there. On a strong short-range 5 GHz link
        # the adapter has so much margin that a human body never drags SNR far
        # enough to force a modulation change, so the rate reports on the
        # adapter's own churn instead of on the room. Telling that operator to
        # start a video and try again wastes their evening.
        idle = still_spread < 1.0 and move_spread < 1.0

        if idle:
            print("\nThe rate barely moved in either phase, which means the "
                  "link was idle rather\nthan the room being calm. Rate "
                  "adaptation has nothing to adapt to without\ntraffic. Start "
                  "a video stream or a large download and calibrate again.")
        else:
            backwards = move_spread < still_spread

            print("\nThe link IS varying -- it just is not varying with the "
                  "room" +
                  (", and moving\nproduced less change than sitting still, "
                   "which is the opposite of a weak\nsignal. That is noise."
                   if backwards else "."))
            print("\nThis is the expected outcome on a strong, short-range "
                  "link. The adapter only\nchanges modulation when the "
                  "channel is marginal, and yours is not: a body\nabsorbs some "
                  "signal but never enough to force the decision. Scan values "
                  "are\ncached and rounded to whole percent because they exist "
                  "to draw a taskbar\nicon, not to measure anything.")
            print("\nDo not tune the thresholds to make this agree. The "
                  "information is not in\nthese APIs. The next real step is "
                  "monitor mode on a spare adapter, which\ngives per-packet "
                  "RSSI from every transmitter instead of a smoothed number\n"
                  "once a second -- see the handoff notes.")

        return 1

    suggested = (still_spread + move_spread) / 2

    print(f"\nA threshold near {suggested:.2f} Mbps sits between your two "
          f"phases.")
    print(f"Calibration put the motion line at {baseline * MOTION_FACTOR:.2f}.")

    if baseline * MOTION_FACTOR > move_spread:
        print("\nThat line is ABOVE what your movement actually produced, so "
              "real motion\nwould read as 'unknown'. Recalibrate while sitting "
              "still -- the current\nbaseline was probably captured with "
              "movement in it.")

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
                        help=f"measure a still room first (you need not leave it), e.g. "
                             f"--calibrate {CALIBRATE_SECONDS}")
    parser.add_argument("--listen", metavar="INTERFACE",
                        help="a SECOND wireless interface, left unconnected, "
                             "to listen across every access point it can hear "
                             "(e.g. --listen \"Wi-Fi 2\"). Do not name the "
                             "interface carrying your internet connection.")

    parser.add_argument("--verify", action="store_true",
                        help="guided still-then-moving test: check the "
                             "calibrated thresholds actually separate the two")

    args = parser.parse_args()

    if args.calibrate:
        return calibrate(args.calibrate, args.out)

    if args.verify:
        return verify(args.out, args.listen)

    return collect(args.out, args.listen)


if __name__ == "__main__":
    raise SystemExit(main())
