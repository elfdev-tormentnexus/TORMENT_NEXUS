# Power and thermal envelope

**Question:** what does an always-on 4B assistant actually cost in watts,
heat, and battery, on a Pi 5 with a PiSugar? Nobody publishes this for
conversational (bursty) workloads — only sustained-inference stress tests.

**Measurements, in order:**

1. Idle baseline: model resident, no generation. Wall power + PiSugar
   drain rate + SoC temperature over an hour.
2. Conversation profile: replayed real session (the regression suite's
   prompts at human cadence). Power per reply, thermal ramp, throttling
   onset if any.
3. Background load: the semantic index worker embedding a backlog —
   verify it stays polite (it already yields while generating; confirm
   that holds on 4 cores).
4. Battery reality: full-charge runtime under profile 2. This number
   decides whether the companion is portable in practice or in theory.

**Instrumentation:** `vcgencmd measure_temp`, PiSugar's battery API, and
a cheap USB-C inline power meter (the one purchase this plan needs).

**Feeds back into:** `CONTEXT_SIZE` (drop to 4096 on the Pi — already
documented), `LLAMA_THREADS=4` default (already set for aarch64), and
whether idle check-in shutdown (`IDLE_CHECKIN_*`) needs to become more
aggressive on battery.
