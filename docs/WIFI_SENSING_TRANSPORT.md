# Getting a reading from a Linux collector into TORMENT_NEXUS

Written 2026-07-28. Companion to `WIFI_SENSING_NEXT_STEP.md` (what to capture)
and `LINUX_HOST_PLAN.md` (where Linux lives).

## The short answer

Yes, a dedicated Linux collector transmitting to TORMENT_NEXUS works, and it
is what `core/wifi_experimental.py` was designed for. The bridge reads **one
local file** and does no networking of its own. Anything that ends in an
atomic local write can feed it.

**The record contract does not change.** Same six fields, same four states,
same expiry, same strict rejection of extras. The bridge and its regressions
stay untouched no matter where the collector runs.

## The difficulty moves; it does not disappear

| Collector location | Capture | Delivery |
| --- | --- | --- |
| WSL2, same machine | **Hard** — custom kernel, no `CFG80211`/`MAC80211` in the stock WSL2 kernel | **Trivial** — no network at all |
| Raspberry Pi | **Easy** — Pi OS ships the wireless stack, Realtek driver via DKMS | Needs a real transport |

Pick based on which problem you would rather own.

### WSL2: there is no transport problem

WSL2 mounts the Windows filesystem at `/mnt/c`. A collector running in WSL2
writes straight to the path the bridge already reads:

```
--out /mnt/c/Users/evely/Documents/AI_Project/dump/wifi.json
```

No network, no protocol, no authentication, no new attack surface. The bridge
cannot tell the difference from a Windows-native collector.

**Verify before relying on it:** the collector uses `tempfile.mkstemp` +
`os.replace` for atomicity. Over WSL2's 9p filesystem bridge that *should*
still be atomic, but it is a different filesystem driver and the whole point
of the atomic write is that a half-written record is never read. Test it
explicitly — write in a tight loop from Linux while reading in a tight loop
from Windows and confirm no partial or malformed record is ever seen.

### Pi: the transport worth building

**Pull, not push.** Have a small Windows-side poller fetch from the Pi and do
the local atomic write itself, rather than the Pi POSTing into a listener on
the desktop. Three reasons:

1. No inbound listener on the machine that matters — the desktop makes only
   outbound requests, so nothing new is exposed on the LAN.
2. The atomic write stays in the code path where it is already proven.
3. A dead Pi degrades correctly on its own. The poller writes nothing, the
   last record expires, and the bridge reports no fresh reading — which is the
   behaviour that already exists and is already tested.

Do **not** put an SMB share in the middle. Mounting a share and pointing the
bridge at it makes every conversational turn depend on a network filesystem,
and `os.replace` atomicity over SMB is not something to assume.

## Security, honestly

The bridge already treats the record as untrusted input and validates it
strictly, so a network hop does not weaken the parsing. Two things it *does*
introduce:

- **Spoofing.** Anything on the LAN that can reach the Pi's endpoint could
  serve a fabricated state. The stakes are low — a coarse room label — but a
  preshared token in a header costs nothing and closes it.
- **Leakage.** "Is someone moving in this room" now crosses the network. It
  carries no identity and no MAC by contract, but it is still a fact about the
  operator's home. Keep it on the LAN, not the internet, and do not forward
  the port.

Neither is a reason to avoid the design. Both are reasons to not use plain
HTTP on an open port and call it done.

## What must never change

Carried from `WIFI_SENSING_NEXT_STEP.md`, and none of it is negotiable because
the data arrived over a wire instead of a filesystem:

- No MAC, SSID, or BSSID in the record, ever, at any hop.
- Never emit `approach` — RSSI is a scalar, direction is not in it.
- Confidence stays capped; this is channel disturbance, not people detection.
- The bridge stays inert with no fresh record. A collector that stops must
  produce silence, never a stale reading.
