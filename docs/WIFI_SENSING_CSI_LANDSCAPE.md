# The LiveSense claim, verified — and what actually changed in open CSI

Written 2026-07-28, from primary sources checked that day. This answers the
one question the sensing docs could not: whether the "LiveSense AX211
range–Doppler demonstration" is real, and whether anything in open CSI
extraction moved since early 2026. Read [SENSING_MODULE.md](SENSING_MODULE.md)
first; nothing here changes its ordering.

## Verdict on LiveSense

**Real, demonstrated, and not publicly reproducible.**

- The paper exists: *LiveSense: A Real-Time Wi-Fi Sensing Platform for
  Range–Doppler on COTS Laptop*, arXiv 2603.06545, submitted 2026-03-06,
  demoing at **PerCom 2026**. Claims: synchronised CSI at ≥40 Hz from a
  stock laptop's AX211 (Wi-Fi 6E) or BE201 (Wi-Fi 7), on-device
  self-interference cancellation, live range and radial velocity of two
  people in a busy café, breathing detection to 10 m NLoS.
- **All five authors are Intel** — Intel Labs Santa Clara and Intel
  Deutschland Munich (Sanson, Shah, Pinaroc, Tanriover, Frascolla).
- The extraction mechanism, per their own precursor paper (arXiv
  2508.02799): *"LTF data is collected … using an Intel device driver which
  captures CSI samples for each received packet."* The driver is never
  named. No OS stated, no firmware stated, **no code, no artifact, no
  repository** on either paper.
- The companion gesture paper (WiRD-Gest, arXiv 2603.22131, same group)
  promises to open-source **the dataset and benchmark** — not the
  extraction tool. Future tense as of April 2026.

So the distinction Codex asked for resolves cleanly: this is *demonstrated
capability*, not *publicly usable capability*. The monostatic trick — the
laptop hearing its own transmissions and cancelling self-interference — is
the part nobody outside Intel can currently run.

Corroborating context: Intel's own blog describes an internal Wi-Fi sensing
program that "enabled CSI on all Intel Wi-Fi platforms" and shipped
Wake-on-approach / Walk-away lock on Raptor Lake — a product feature, not a
developer API.

## What genuinely changed in the open landscape

The AX211 guardrail in [WIFI_SENSING_NEXT_STEP.md](WIFI_SENSING_NEXT_STEP.md)
rests on two legs. One aged, one did not:

1. **"Intel's Windows firmware does not expose that path"** — still true,
   and still binding, because the desktop runs Windows and the AX211 is the
   only internet link. The guardrail stands unchanged.
2. **"PicoScenes gets CSI by patching iwlwifi plus firmware"** — no longer
   the whole story. On **Linux**, open tools now target modern Intel cards:

| Tool | Cards | Status | Evidence quality |
|---|---|---|---|
| **FeitCSI** (KuskoSoft, GPL-3.0) | AX200, AX210 confirmed; "newest Intel NIC" plausible | Working public code; all formats a/g/n/ac/ax, 20–160 MHz, 6 GHz band; explicitly runs on ARM Linux, NIC must attach via PCIe | Public repo + docs site |
| **IAX** (IEEE Sensors Journal, doi:10.1109/JSEN.2025.3553130) | **AX200/201/210/211 claimed; AX210 + AX211 firmware actually shipped**; STA/AP/**Monitor**/Injector; 1992 subcarriers at 160 MHz | **Artifact found: `github.com/fflq/iax`, MIT, public** — patched iwlwifi backport + replacement firmware, kernel 5.15.x only. See [WIFI_CSI_REPRODUCTION.md](WIFI_CSI_REPRODUCTION.md) | Public repo, verified by reading the installer |
| **PicoScenes** | AX200/AX210 yes; **AX211 explicitly not detected** (issue #71, March 2026, v2025.1217) | Working but closed-binary, licensed | Public issue tracker |
| Kernel plumbing | — | `iwlwifi: mvm: implement CSI reporting` + `IWL_MVM_VENDOR_CMD_CSI_EVENT` have existed since ~2019; FeitCSI/IAX sit on this | Kernel patchwork |

**Correction to an earlier in-session claim:** Nexmon CSI on the Pi 5 is no
longer dead. Community work (nexmon_csi discussion #395) has it running on
Raspberry Pi OS Trixie (Nov 2025) via `Makefile.rpi` and the
non-16k-pages kernel. Fiddly and unofficial, but demonstrated — "not
supported" was too strong. It remains the Pi's *onboard* radio, though,
and the collector design wants a radio the assistant is not depending on.

## What this means here

- **Nothing displaces the LD2450 radar track.** It is ordered, it measures
  the right quantity for `motion`/`approach`, and no Wi-Fi finding above
  changes the arrival-and-acceptance sequence in SENSING_MODULE.md.
- **The paused monitor-mode plan has a better ceiling than planned.** Its
  Phase 2 measures per-packet RSSI — a scalar. For roughly the same money
  as staying with scalars (~£20–25 Intel **AX210** on an M.2 E-key HAT for
  the Pi 5 — verify HAT availability before buying), FeitCSI yields actual
  **CSI**: per-subcarrier magnitude and phase, the same class of quantity
  LiveSense demos, in the open, bistatic against the home AP's traffic.
  That passes this project's own bar — a different quantity, not the same
  idea tuned better — and touches no guardrail: not the AX211, not the
  Windows disk, nothing the assistant depends on.
- **Monostatic sensing (LiveSense proper) stays out of reach** without
  Intel's driver, and chasing it is not worth further effort. The IAX
  repository has since surfaced and does cover AX211 — see
  [WIFI_CSI_REPRODUCTION.md](WIFI_CSI_REPRODUCTION.md) — and the conclusion
  held exactly as written: the desktop's AX211 stays untouched for the
  only-internet-link reason, which the tool's own installer makes vivid by
  replacing that card's firmware and driver system-wide. Its kernel-5.15
  constraint also rules out the Pi 5, so the earlier AX210-on-Pi sketch is
  dead for IAX specifically; FeitCSI remains the candidate for that shape.

## Sequencing, unchanged

1. LD2450 arrives → acceptance sequence in SENSING_MODULE.md.
2. Radar fails, or `still` needs a complement → the £3 LD2410 class
   (micro-motion presence) before any Wi-Fi work.
3. Wi-Fi sensing resumes only after both → prefer AX210+FeitCSI on the Pi
   over plain monitor-mode RSSI; keep Phase 2's still-versus-moving test as
   the acceptance gate, unchanged.

Do not buy Wi-Fi hardware before step 1 is measured. A £15 radar decision
does not need a hedge purchased in advance.

## Primary sources

- arXiv 2603.06545 (LiveSense, PerCom 2026) · arXiv 2508.02799 (mechanism
  quote) · arXiv 2603.22131 (WiRD-Gest, dataset promise)
- github.com/KuskoSoft/FeitCSI + feitcsi.kuskosoft.com
- IEEE 10944229 (IAX; AX211 claim, artifact behind paywall)
- github.com/wifisensing/PicoScenes-Issue-Tracker issue #71
- github.com/seemoo-lab/nexmon_csi discussion #395, issue #207
- community.intel.com "Wi-Fi Sensing: Adding Sensing Capability" (403 to
  fetchers; content via search index)
