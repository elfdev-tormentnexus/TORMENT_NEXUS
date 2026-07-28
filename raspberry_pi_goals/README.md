# Raspberry Pi development goals

A holding space for work that **cannot be honestly done or verified on the
Windows desktop**, so it stops leaking into the main tree as speculative
code nobody can test.

The rule for this folder: anything in here is a plan, a measurement
protocol, or a negative result — never a feature quietly wired into the
assistant. Code lands in `assistant/` only once there is hardware to run it
against. This is the same discipline that kept `core/wifi_experimental.py`
honest: the bridge shipped, the collector was written and tested
separately, and when the approach failed the failure was written down
rather than tuned into agreement.

## Target hardware

- Raspberry Pi 5, 8GB
- PiSugar UPS HAT (battery / power management)
- Whisplay HAT (display + audio I/O)
- Spare TP-Link USB Wi-Fi adapter (already owned; monitor-mode capable)

None of it assembled as of 2026-07-28.

## What lives here

| File | What it is |
| --- | --- |
| `01_wifi_monitor_mode.md` | The next rung after the rate-adaptation failure |
| `02_speculative_decoding.md` | Draft-model throughput on Pi-class CPU |
| `03_power_and_thermal.md` | The measurements nobody publishes for this class |
| `04_hardware_integration.md` | PiSugar + Whisplay, and what not to build early |

## Why these are Pi-only

- **Monitor mode** needs Linux and a driver that will surrender the
  adapter. The AX211 in the desktop is the operator's only internet and is
  off limits; Windows cannot expose per-packet RSSI the way `iwlwifi` can.
- **Speculative decoding** is measurable on Windows, but the *question*
  is Pi-class CPU throughput. Desktop numbers with a 4090 in the machine
  answer a different question and would be misleading in a writeup.
- **Power and thermal** are meaningless on a desktop PSU.
- **PiSugar / Whisplay** have no Windows equivalent to stub against, and
  the standing rule is not to write driver code before the hardware
  arrives.

## What is *not* here

Everything runnable on Windows stayed in the main tree or in
`docs/RESEARCH_ROADMAP.md`: entropy-based honesty signals, persona drift
measurement, sycophancy probes, idle-time memory consolidation, and
entropy-guided sampling. Those need only the models already installed.
