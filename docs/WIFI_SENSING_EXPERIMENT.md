# Experimental desktop Wi-Fi sensing

This document describes the boundary for a future, owner-authorised Wi-Fi
room-activity experiment. It is deliberately not a guide for monitoring other
people or spaces. Use it only in your own space, with the people there aware
of what is being tested.

## Current position

TORMENT_NEXUS has an **off-by-default input seam**, but it does not yet have a
collector. The Intel AX211 in this desktop is capable of the kind of
channel-state research needed for motion/range experiments, but the promising
demonstrations are not a safe public Windows capture dependency. Do not change
the Windows Wi-Fi driver, adapter firmware, Secure Boot setting, or network
configuration for this feature.

When a maintained, public AX211 collector is available, it must first be
reviewed as a separate, reversible desktop experiment. The normal TORMENT_NEXUS
installation should remain untouched. That review needs an explicit owner
decision before any alternate operating-system boot, research driver, or
hardware setup is attempted.

## What the app will accept

If a reviewed local collector is later approved, it may atomically replace one
small UTF-8 JSON file. Configure its absolute path through
`TORMENT_NEXUS_WIFI_EXPERIMENT_FILE`, then explicitly run `wifi sensing on`.

```json
{
  "schema": 1,
  "source": "wifi-experimental",
  "state": "motion",
  "confidence": 0.81,
  "observed_at": 1760000000.0,
  "expiry_ms": 5000
}
```

Every one of those six fields is required; extra fields reject the entire
record. `observed_at` is a Unix timestamp. The allowed states are `unknown`,
`still`, `motion`, and `approach`. A record must expire in 0.1–60 seconds.
TORMENT_NEXUS reduces confidence to low, medium, or high and keeps neither the
record nor a sensing history.

The collector must write to a temporary file and atomically replace the status
file. It must not send data over a port or put raw CSI, packet data, MAC
addresses, SSIDs, device names, imagery, audio, location traces, identifiers,
or free-form text in the record.

## First calibration gate

Before Torment receives any live result, test in one known room with a visible
on/off indicator and a short-lived file only:

1. With the experiment off, confirm no file is read and the companion makes no
   room-activity claims.
2. With it on, test only the four allowed coarse labels against a known,
   consensual movement or stillness. Test normal false positives such as a fan,
   pet, doorway movement, and a changing Wi-Fi connection.
3. Treat an unstable result as `unknown`; do not convert it into a claim about
   a person, direction behind a wall, identity, or continued presence.
4. Turn it off and use `wifi sensing forget`; confirm the current reading
   disappears immediately and nothing persists after restarting the app.

The success condition is modest: an honest, optional **room-radio activity**
cue that Torment can phrase as “the enabled experiment reports motion.” It is
not vision, people detection, a security system, a medical sensor, or
through-wall sensing.

## Controls and rollback

`wifi sensing status` shows only whether a fresh aggregate result is available.
`wifi sensing off` disables the bridge and clears the in-memory result.
`wifi sensing forget` discards the current result without touching another
tool's file. Removing the two environment variables and restarting restores
the default inert state.
