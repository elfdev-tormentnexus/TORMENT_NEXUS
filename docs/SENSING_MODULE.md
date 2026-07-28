# Sensing module: active hardware track

**Status:** Active — pending acquisition and arrival of the selected hardware.

**Decision date:** 2026-07-28

## Selected experiment

The next sensing experiment uses a dedicated 24 GHz FMCW radar rather than
trying to tune the failed Windows Wi-Fi proxy or treating LoRa packet strength
as vision.

Selected parts:

- JMT/Hi-Link `HLK-LD2450` movement-tracking radar;
- IZOKEE `CP2102` USB-to-TTL adapter with jumper wires; and
- only if the radar does not include one, a single preassembled JST-ZH
  1.5 mm four-pin lead. Do not buy a bulk connector or crimping assortment
  before inspecting the delivered module.

The LD2450 is a moving-target sensor. It reports target position, distance,
angle, and speed over UART at up to a 10 Hz update rate. The selected listing
specifies 5 V module power and a serial connection at 256000 baud, one stop
bit, and no parity. Its UART logic is 3.3 V.

Before applying power, verify the delivered board's printed pin order. Connect
module TX to adapter RX and module RX to adapter TX only after that inspection.
Do not infer the connector orientation from wire colours.

## What this means for TORMENT_NEXUS

This is privacy-preserving spatial awareness, not sight. A validated collector
may honestly derive short-lived observations such as:

- movement or no reliable observation;
- approach or retreat from a sustained distance trend; and
- a coarse left, centre, or right zone during movement.

The sensor does not provide identity, appearance, facial expression, object
recognition, or imagery. The LD2450 may also lose a person who remains
motionless, so it must not claim continued occupancy without evidence.

The existing experimental bridge accepts only `unknown`, `still`, `motion`,
and `approach`, plus coarse confidence and expiry. The first radar sidecar
should map verified live measurements into that narrow contract and should
not retain raw frames or a tracking history. Preserving target count, range,
or zones in the application would be a separate trust-boundary decision and
is not authorised by this hardware selection.

Do not implement the collector before the real module is connected and its
output has been measured. Vendor descriptions are not acceptance evidence.

## Arrival and acceptance sequence

1. Connect the CP2102 by itself and record the Windows COM port.
2. Inspect the radar connector, cable, pin labels, and adapter voltage labels.
3. Power the radar at 5 V with 3.3 V UART signalling.
4. Confirm stable frames at 256000 baud without running the vendor tool and
   the collector against the port simultaneously.
5. Record short, disposable trials for an empty field, lateral crossing,
   approach, retreat, and a person becoming motionless.
6. Test likely false positives, including a fan, moving curtain, pet, doorway
   movement, and motion behind the sensor.
7. Only after the measurements discriminate those cases, implement the
   expiring aggregate sidecar and its regression tests.

Success means a repeatable, consent-based room-motion cue that expires when
the radar stops providing evidence. Failure is also a valid result and must
be documented without tuning thresholds merely to force a pass.

## Other sensing tracks

- **Windows Wi-Fi userland:** measured failure. Movement produced less
  variation than the still trial, so the available values were noise rather
  than a weak sensing signal.
- **Wi-Fi monitor mode:** paused. It remains a separately scoped research plan,
  but is no longer the active next step while dedicated radar hardware is
  pending.
- **T-Deck LoRa/SX1262:** exploratory only. Packet RSSI/SNR from a controlled
  second node could form a radio-path tripwire, but the stock single-antenna
  device does not provide CSI, phase, ranging, or camera-like spatial data.

