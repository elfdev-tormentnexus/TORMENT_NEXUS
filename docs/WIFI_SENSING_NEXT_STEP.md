# Wi-Fi sensing: the monitor-mode plan

Written 2026-07-28, straight after the Windows approach was tested and failed.
Self-contained on purpose — read this and the plan is executable without the
conversation that produced it.

## Status

**Paused, not abandoned.** The active sensing workstream is now the dedicated
24 GHz mmWave hardware experiment recorded in
[Sensing module: active hardware track](SENSING_MODULE.md). That experiment is
pending acquisition and arrival of an HLK-LD2450 radar and CP2102 USB-to-TTL
adapter. Resume this monitor-mode plan only if the radar experiment is measured
and rejected, or if monitor-mode research is explicitly prioritised again.

## What already failed, and why that matters here

`tools/wifi_sense_collector.py` reads Windows userland APIs. It was calibrated
properly and tested with deliberate, vigorous movement:

| phase  | rate spread | scan paths disturbed |
| ------ | ----------- | -------------------- |
| still  | 10.18 Mbps  | 9% of 28             |
| moving | 5.65 Mbps   | 0% of 28             |

Moving was *quieter* than sitting still. That is noise, not a weak signal.

The cause is not fixable by tuning. Rate adaptation only reports on the
channel when the channel is marginal, and a 5 GHz link at 85% signal over a
few metres never is — the adapter has so much margin that a human body never
drags SNR far enough to force a modulation change. Windows' scan values are
separately useless: cached for 3–15s and rounded to whole percent, because
they exist to draw a taskbar icon.

**Monitor mode is a different quantity, not the same one tuned better.**
Instead of asking one adapter how its own link is doing once a second, you
receive every frame crossing the room — hundreds per second, from ~29 access
points plus every client device — each carrying a raw per-packet RSSI in its
radiotap header. Unsmoothed, uncached, unquantised.

## Hard guardrails

1. **Never touch the Intel AX211.** It is the only internet connection on that
   machine, and losing it means losing the ability to look up how to fix it.
   It is also pointless: PicoScenes gets CSI by patching the open-source Linux
   `iwlwifi` driver *plus firmware*, and Intel's Windows firmware does not
   expose that path at all. (2026-07 update: open Linux tools now reach
   AX-series cards — see the repository-only research note
   `docs/WIFI_SENSING_CSI_LANDSCAPE.md`, which is not part of the Windows
   release package. The only-internet-link reason is the binding one and the
   guardrail stands.)
2. **Nothing is installed to the Windows disk.** Live USB only, until the Pi
   takes over. No dual-boot partition, no Secure Boot change, no bootloader.
3. **The TP-Link is the only radio touched.** It carries no traffic; breaking
   it costs nothing.

## Phase 0 — identify the chipset (10 minutes)

USB ID is `2357:0138`. That is TP-Link's vendor ID; the product ID most likely
indicates an Archer T4U-class adapter on a Realtek RTL88x2BU. **Confirm it, do
not assume** — TP-Link reuses model names across completely different silicon,
and the driver choice depends entirely on the answer.

From the live USB in Phase 1:

```
lsusb | grep 2357
dmesg | grep -i -E 'rtl|8812|8814|88x2|mt7'
```

Realtek 8812AU/8814AU/88x2BU are all well-supported out of tree. A MediaTek
part would be *better* — mt76 is in-kernel and needs no external driver.

## Phase 1 — live USB, no install (1 evening)

Use **Kali Linux live** rather than plain Ubuntu, purely because it ships the
Realtek monitor-mode drivers and `aircrack-ng` already built. This is not a
security exercise; it is the distribution that saves the most compilation.

1. Write the ISO to a spare USB stick from Windows (Rufus, or Balena Etcher).
2. Boot it. Choose **live**, never install.
3. Plug in the TP-Link. Run Phase 0's commands.
4. Bring up monitor mode:

```
sudo ip link set wlan1 down
sudo iw dev wlan1 set type monitor
sudo ip link set wlan1 up
sudo iw dev wlan1 set channel 157
```

Match the channel to whatever the home AP uses — the AX211 was on 5 GHz
channel 157. A monitor interface hears one channel at a time; hopping trades
per-channel density for coverage and is the wrong trade here.

5. Confirm frames and RSSI are arriving:

```
sudo tcpdump -i wlan1 -e -c 20
```

Each line should carry a signal figure in dBm. **If it does not, stop.** The
driver is associating rather than truly monitoring, and no amount of
downstream code fixes that.

If the driver is missing, the maintained out-of-tree sources are
`morrownr/88x2bu-20210702` (RTL88x2BU) and `aircrack-ng/rtl8812au` (8812AU).
Both build with DKMS. On a live session that build is lost at reboot, which is
fine for validation and is exactly why Phase 3 exists.

## Phase 2 — does it actually discriminate? (same evening)

Do not build a collector yet. Answer the only question that matters first,
and answer it the same way the Windows attempt was answered so the results are
comparable.

Capture RSSI per source MAC over time:

```
sudo tcpdump -i wlan1 -e -n -l 2>/dev/null | \
  awk '{ for (i=1;i<=NF;i++) if ($i ~ /dBm/) print systime(), $(i-1) }' \
  > /tmp/rssi.log
```

Then, exactly as before: **20 seconds sitting still, 20 seconds moving
deliberately across the line between the router and the desk.** Compute the
mean absolute step between consecutive samples per transmitter, and compare
the two phases.

**Success is the moving phase producing visibly more variance than the still
phase.** If it does not, monitor mode is not the answer either, and the honest
next question is whether a dedicated 24 GHz mmWave presence sensor — a
£10 part that does this properly — is a better use of the effort than
continuing to squeeze Wi-Fi.

Record the numbers either way. A second measured negative is worth as much as
the first.

## Phase 3 — permanent home on the Pi

A live USB cannot be the answer: TORMENT_NEXUS runs on Windows and the desktop
cannot be booted into Linux to sense a room it is not being used in.

The Raspberry Pi is the natural host. It can sit powered on permanently, run
the collector as a service, and hold the TP-Link with nothing else competing
for it. `mt76`- or Realtek-based monitor mode works the same there, with the
driver built once via DKMS and surviving reboots.

Delivery of the status file across machines is then the only open design
question. The bridge (`core/wifi_experimental.py`) reads a **local file path**,
so the options are:

- an SMB share the Pi writes to and Windows mounts — simplest, no code change,
  and the bridge's atomic-replace expectation must be verified over SMB;
- a tiny local writer on Windows that receives a POST and does the atomic
  replace itself — more moving parts, but keeps the atomicity guarantee where
  it is already proven.

Whichever is chosen, the record contract does not change: same six fields,
same four states, same expiry. The bridge and its regressions stay untouched.

## What the collector must still refuse to do

Inherited unchanged from `tools/wifi_sense_collector.py`, and none of it is
negotiable just because the data got better:

- **Never emit `approach`.** Per-packet RSSI is still a scalar per
  transmitter. Direction would require a phased array or a time-of-flight
  measurement, and the bridge accepting the label is not a reason to invent
  one.
- **Never let a MAC address, SSID or BSSID reach the status file.** Monitor
  mode sees every device in range including neighbours' phones. Those
  identifiers may be used in memory to group readings per transmitter and must
  never be written, logged, or retained.
- **Cap confidence.** This detects disturbance of a radio channel. That
  correlates with movement; it is not detection of a person, and a fan or a
  door produces the same reading.
- **Calibrate per room, refuse a degenerate baseline**, and keep `--verify` as
  the acceptance gate. The Windows attempt looked plausible for three
  calibrations before the still-versus-moving test exposed it.
