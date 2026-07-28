# Monitor-mode Wi-Fi sensing on the Pi

## Where this picks up

The desktop experiment is over and it failed for a statable reason
(`CODEX_HANDOFF.md`, "Open" section): rate adaptation only reports on the
channel when the channel is marginal. A high-SNR 5GHz link never got
dragged far enough by a human body to force a modulation change, so the
collector measured the adapter's own rate-selection churn. Moving read
*quieter* than sitting still. Zero of twenty-eight scan paths disturbed
during vigorous movement. Do not retry that approach; do not tune the
thresholds into agreement.

What survived is the scaffolding: the bridge (`core/wifi_experimental.py`,
shipped in v0.2.0-beta.1), the status-file contract (aggregate record,
`expiry_ms` required, any extra field rejects the record), the calibration
gate, and `--verify`'s distinction between "flat link, needs traffic" and
"varying but uncorrelated, information is not there".

## The different quantity

Per-packet RSSI in monitor mode is not the same idea tuned better; it is a
different measurement. The TP-Link adapter, freed from protecting a link,
reports every frame it hears from ~29 access points at packet rate, raw
and unsmoothed. A body crossing any of those paths shadows some of them.
Twenty-nine noisy witnesses instead of one adapter describing itself.

## Plan

1. **Adapter check first.** Confirm the TP-Link chipset supports monitor
   mode under mainline Linux (`iw list` → "monitor" in supported
   interface modes). If it does not, stop; buying hardware for this is a
   separate decision.
2. **Collector on the Pi**, external to the assistant, same contract:
   `tools/wifi_sense_collector.py` grows a `--monitor` backend using
   `iw dev <if> interface add mon0 type monitor` + a raw socket with
   radiotap parsing (stdlib struct; no scapy dependency unless it earns
   its place). Per-source-MAC RSSI series in memory only — MACs never
   reach the status file, exactly as BSSIDs never did.
3. **Calibrate still vs moving** the way the failed experiment did, but
   score per-path RSSI variance across sources, not one link's rate. The
   statistic that matters is the same one that killed the last approach:
   does the moving distribution actually separate from the still one, and
   in the right direction, across repeated runs.
4. **Confidence stays capped at 0.6** and `approach` stays unused. Scalars
   have no bearing; the bridge accepting a label is not a reason to
   produce one.
5. **Write the result down either way.** A second honest negative here is
   still a contribution — consumer-adapter RF sensing claims are mostly
   demos; carefully logged failure conditions are rarer than successes.

## Why it must wait for the Pi

Monitor mode wants Linux (`iwlwifi`-class driver control); the desktop's
AX211 is the operator's only internet and is off limits (documented: the
Windows firmware does not expose CSI, a custom driver would need kernel
signing, and the payoff is zero). The Pi plus the spare adapter risks
nothing.
