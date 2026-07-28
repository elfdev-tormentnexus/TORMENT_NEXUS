# Reproducing Wi-Fi CSI sensing: the executable path

Written 2026-07-28. The artifact hunt succeeded — this is a build plan against
a real repository, not a survey. Read
[WIFI_SENSING_CSI_LANDSCAPE.md](WIFI_SENSING_CSI_LANDSCAPE.md) for why this and
not LiveSense, and [SENSING_MODULE.md](SENSING_MODULE.md) for why the radar
still goes first.

## The artifact

**`github.com/fflq/iax` — MIT licensed, public, 18 stars, last pushed
2026-03-11.** It was never behind the paywall; only the link was. `fflq` is
Liquan Fang, second author of the IEEE Sensors Journal paper
(doi:10.1109/JSEN.2025.3553130, Zhang · Fang · Xie · Yang · Chen · Chen,
USTC Intelligent Perception Lab).

This is the real thing: a patched `iwlwifi` backport tree, replacement Intel
firmware blobs, a C++ CSI listener, and a MATLAB parser.

| Property | Value |
| --- | --- |
| Cards claimed | AX200 / AX201 / AX210 / AX211, plus legacy Intel 5300 |
| Firmware actually shipped | `ty-a0-gf-a0` (**AX210**, 11 versions) and `so-a0-gf-a0` (**AX211**) |
| Modes | STA, AP, **Monitor**, Injector |
| Bandwidth | 20/40/80/160 MHz, Non-HT/HT/VHT/HE, 6 GHz on AX210/211 |
| Control surface | debugfs: `/sys/kernel/debug/iwlwifi/*/iwlmvm/{csi_enabled,csi_interval,csi_addresses,monitor_tx_rate}` |
| Output | C++ listener → file and/or TCP; MATLAB parser |

Note the mismatch worth knowing before buying: the README claims AX200/201 but
**ships no `cc-a0` firmware**, and states plainly that AX201 firmware "is not
yet included … (No equipment yet)". The shipped blobs cover exactly the two
cards that matter here. **AX210 is the safe purchase.**

## The hard constraint that decides everything

```
if [ -z "$(uname -r | grep '5.15')" ]; then
   echo "* please change kernel $(uname -r) to 5.15.*"
   exit;
fi
```

`iwlwifi/setup.sh` refuses to run on anything but **kernel 5.15.x**. This is
not caution — the driver is a backport tree built against the 5.15 iwlwifi
API. The README recommends **Ubuntu 22.04.0/22.04.1** and warns that 22.04.5's
default 6.8 kernel will not match.

**Therefore: this cannot run on the Raspberry Pi 5.** Pi 5 support did not
exist before kernel 6.1. Kernel 5.15 and Pi 5 are mutually exclusive, and no
amount of effort reconciles them. That kills the "Pi as permanent sensing
host" shape for *this* tool, and it is better to know now than after buying a
HAT.

## What it does to the machine it runs on

`update-firmware.sh` **moves the system's `iwlwifi-{5000,so,ty}*` firmware
aside and installs its own.** `remake-csi-iwlwifi.sh` compiles and
`modules_install`s a replacement `iwlwifi` module. `restore.sh` reverses both.

Read that against the standing guardrail: the desktop's AX211 is the only
internet connection on that machine. **This tool replaces exactly that card's
firmware and driver, system-wide.** Running it there is precisely the
forbidden action, and the fact that CSI is now technically reachable on an
AX211 changes nothing — the guardrail was never about feasibility.

## The rig that would work

A **separate x86 machine**, because of the kernel constraint:

- Any x86-64 box — a spare laptop, a mini PC, a second SSD in the desktop.
- **Ubuntu 22.04.1 LTS**, kernel 5.15.x. Do not update the kernel.
- **Intel AX210** in M.2 2230 E-key (~£15–25), with antennas. AX211 works per
  the shipped `so` firmware, but it is CNVi and generally not a card you can
  simply fit to an arbitrary machine; AX210 is discrete M.2 and portable.
- The home AP as the illuminator. No AP-side change is needed in any mode.

Monitor mode is the one to use — it takes CSI from ambient traffic already
crossing the room, which matches the collector design already documented:

```bash
sudo ./tools/iaxcsi-set-monitor.sh wlp8s0 40 HE160
sudo ./csi/iaxcsi/cpp/iaxcsi wlp8s0mon0 /tmp/iax.csi 127.0.0.1:12345
```

## The gap this project would have to close

**There is no Python parser.** The README lists Python as `TODO` twice —
under CSI Listening and under CSI Parsing. What exists is a C++ listener and a
MATLAB reader. This project is Python, and MATLAB is not an acceptable
dependency for it.

That work is well-specified rather than open-ended, which is the good news:

- The wire format is defined by `csi/iaxcsi/cpp/iaxcsi.h` and
  `csi/iaxcsi/cpp/iwl_fw_api_rs.h`.
- `csi/iaxcsi/matlab/iaxcsi.m` is a complete, working reference decoder.
- The C++ tool can already emit to a TCP socket, so a Python collector can
  consume the stream without touching the driver at all.

So the sidecar shape stays exactly as designed: an external collector, Python,
reading a TCP stream, emitting only the short-lived aggregate JSON the bridge
in `core/wifi_experimental.py` already accepts. **The contract does not
change.** Same six fields, same four states, same expiry, same refusals — no
MAC or BSSID ever reaches the status file, `approach` still requires evidence
a scalar cannot provide, confidence still capped.

## Acceptance gate — unchanged, and still the point

CSI is a better quantity than rounded percentages, and that is a reason to
test it, not a reason to believe it. Phase 2 of
[WIFI_SENSING_NEXT_STEP.md](WIFI_SENSING_NEXT_STEP.md) applies verbatim:
**20 seconds still, 20 seconds moving deliberately**, compare per-subcarrier
variance between the phases. If moving is not visibly noisier than still,
record the second measured negative and stop. The Windows attempt looked
plausible for three calibrations before that test exposed it.

## Where this sits in the queue

Still behind the radar. Nothing here changes
[SENSING_MODULE.md](SENSING_MODULE.md):

1. **LD2450 radar** — ordered, pending arrival, measures the right quantity.
2. **LD2410-class** micro-motion, only if the radar drops `still`.
3. **IAX CSI** — only if both are measured and rejected, and only on a
   separate x86 host running Ubuntu 22.04.1.

**Buy nothing for step 3 yet.** The kernel constraint means it needs a whole
spare machine, not a £20 card, and that is a much larger commitment than the
radar it is queued behind.

## Primary sources

- `github.com/fflq/iax` — README, `iwlwifi/setup.sh`,
  `iwlwifi/update-firmware.sh`, `iwlwifi/remake-csi-iwlwifi.sh`,
  `tools/iaxcsi-activate.sh`, firmware blob listing (read 2026-07-28)
- doi:10.1109/JSEN.2025.3553130 — IEEE Sensors Journal 2025; author list and
  affiliation via OpenAlex
- `ustc-ip-lab.github.io` — Intelligent Perception Lab, USTC
