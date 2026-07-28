# PiSugar and Whisplay integration

**Standing rule (unchanged):** no driver code before the hardware
arrives. This file exists so the intentions are parked somewhere safer
than memory and vaguer than code.

**PiSugar (power):**
- Battery percentage into `core/system_awareness.py` as ambient context —
  the same consent boundary as window titles: the assistant may know, the
  prompt only carries it when relevant.
- Low-battery behaviour routes through the existing idle check-in and
  clean-shutdown path, not a new one.

**Whisplay (display + audio):**
- The terminal UI's panel (entropy strip, retrieval cloud) is the design
  language for the small display: the face of the machine is its own
  telemetry, honestly rendered. Port the renderer's data feeds, not the
  ANSI renderer itself.
- Audio in/out replaces the desktop sound stack; the Moonshine/Silero/
  Piper pipeline is already offline and portable. What needs testing on
  real hardware is latency and the vocoder's CPU budget next to
  generation — numbers `03_power_and_thermal.md` will produce.

**Verification when the time comes:** every step lands behind the same
pattern as everything else — absent hardware detected at startup means
absent feature, no error. `setup\test_assistant.bat` stays green on the
desktop with zero hardware attached.
